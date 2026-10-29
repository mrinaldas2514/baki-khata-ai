"""FastAPI application. Run with: uvicorn app.main:app --reload"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.auth import NotAuthenticatedError
from app.config import get_settings
from app.database import build_engine, check_schema
from app.groq_models import start_model_check
from app.http_security import BodySizeLimit, SecurityHeaders
from app.llm import LLMClient, LLMNotConfiguredError, LLMProviderError
from app.logging_privacy import install_access_log_filter
from app.rate_limit import RateLimitedError, build_rate_limiter
from app.routers import (
    auth,
    customers,
    dashboard,
    export,
    parse,
    shops,
    transactions,
    transcribe,
)
from app.routers.transcribe import AIDisabledError
from app.security import resolve_jwt_secret
from app.services.auth import WrongPasswordError
from app.services.exceptions import ConflictError, NotFoundError
from app.services.parsing import LLMOutputError, NotATransactionError
from app.services.transcription import AudioRejectedError
from app.stt import SpeechToTextClient, STTNotConfiguredError, STTProviderError

logger = logging.getLogger(__name__)


class ProductionConfigError(RuntimeError):
    """ENVIRONMENT=production with settings that aren't safe (no JWT_SECRET, SQLite...)."""


def create_app(
    engine: Engine | None = None,
    llm_client: LLMClient | None = None,
    stt_client: SpeechToTextClient | None = None,
    *,
    check_migrations: bool | None = None,
) -> FastAPI:
    """The API. Tests pass their own engine (tables made with create_all) and fake AI clients.

    `check_migrations` (default: only for the database from DATABASE_URL) stops startup with a
    clear message when the database needs `alembic upgrade head`.

    With ENVIRONMENT=production it refuses to start until the settings are safe (see
    Settings.production_problems), and the interactive API docs are off.
    """
    settings = get_settings()
    if problems := settings.production_problems():
        raise ProductionConfigError(
            "ENVIRONMENT=production, but the settings aren't safe yet:\n"
            + "\n".join(f"  - {problem}" for problem in problems)
        )
    if check_migrations is None:
        check_migrations = engine is None
    if engine is None:
        engine = build_engine(settings.database_url, echo=settings.sql_echo)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if check_migrations:
            check_schema(engine)
        if settings.seed_demo_on_start:
            _seed_demo(engine)
        if llm_client is None or stt_client is None:
            # Logs a clear error if Groq has retired (or never had) a configured model.
            start_model_check(settings)
        yield

    docs = (
        {}
        if not settings.is_production
        else {"docs_url": None, "redoc_url": None, "openapi_url": None}
    )
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan, **docs)
    app.state.session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    # None means "build the configured provider on first use" (see app.llm.get_llm_client).
    app.state.llm_client = llm_client
    app.state.stt_client = stt_client
    app.state.jwt_secret = resolve_jwt_secret(settings)
    app.state.jwt_expire_minutes = settings.jwt_expire_minutes
    app.state.rate_limiter = build_rate_limiter(settings)
    install_access_log_filter()

    # Added first = innermost: both run inside CORS, so their answers (a 413) carry its headers.
    audio_limit = settings.stt_max_audio_bytes + 64 * 1024
    app.add_middleware(
        BodySizeLimit,
        limit_for=lambda path: audio_limit if path == "/transcribe" else settings.max_request_bytes,
    )
    app.add_middleware(SecurityHeaders, hsts=settings.is_production)
    # Lets the frontend (another origin) call the API from the browser: only the origins in
    # CORS_ORIGINS, only the methods and headers the app uses.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
        # Readable by the app: the CSV's file name, and how long to wait after a 429.
        expose_headers=["Content-Disposition", "Retry-After"],
        max_age=600,
    )

    app.include_router(auth.router)
    app.include_router(shops.router)
    app.include_router(customers.router)
    app.include_router(transactions.router)
    app.include_router(dashboard.router)
    app.include_router(parse.router)
    app.include_router(transcribe.router)
    app.include_router(export.router)

    @app.get("/health", tags=["health"])
    def health():
        """For the hosting provider's health check: is the API up, and can it reach the database?"""
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            # The error can hold the database's address; log its kind only.
            logger.error("Health check: the database is unreachable (%s)", type(exc).__name__)
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "error", "database": "unreachable"},
            )
        return {"status": "ok", "database": "ok"}

    _register_error_handlers(app)
    return app


def _seed_demo(engine: Engine) -> None:
    """SEED_DEMO_ON_START: the demo shop and login, only if they don't exist yet."""
    from app import seed

    with Session(engine, expire_on_commit=False) as db:
        existed = seed.demo_user(db) is not None
        shop = seed.seed(db)
    # A warning: anyone can log in to it, and INFO isn't shown by default.
    if existed:
        logger.warning(
            "SEED_DEMO_ON_START: the demo shop %d already exists, left as it is", shop.id
        )
    else:
        logger.warning("SEED_DEMO_ON_START: created the demo shop %d", shop.id)


def _register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def _not_found(_request: Request, exc: NotFoundError):
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})

    @app.exception_handler(ConflictError)
    async def _conflict(_request: Request, exc: ConflictError):
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})

    @app.exception_handler(NotAuthenticatedError)
    async def _not_authenticated(_request: Request, exc: NotAuthenticatedError):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": str(exc)},
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(WrongPasswordError)
    async def _wrong_password(_request: Request, exc: WrongPasswordError):
        # 403, not 401: the login itself is fine, so the app must not log out.
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"detail": str(exc)})

    @app.exception_handler(AIDisabledError)
    async def _ai_disabled(_request: Request, exc: AIDisabledError):
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"detail": str(exc)})

    @app.exception_handler(RateLimitedError)
    async def _rate_limited(_request: Request, exc: RateLimitedError):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "detail": f"Onek bar chesta hoyeche. {exc.retry_after} second por abar chesta korun.",
                "retry_after": exc.retry_after,
            },
            headers={"Retry-After": str(exc.retry_after)},
        )

    @app.exception_handler(NotATransactionError)
    async def _not_a_transaction(_request: Request, exc: NotATransactionError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": str(exc)}
        )

    @app.exception_handler(LLMOutputError)
    async def _llm_output(_request: Request, exc: LLMOutputError):
        return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content={"detail": str(exc)})

    @app.exception_handler(LLMNotConfiguredError)
    async def _llm_not_configured(_request: Request, exc: LLMNotConfiguredError):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"detail": str(exc)}
        )

    @app.exception_handler(LLMProviderError)
    async def _llm_provider(_request: Request, exc: LLMProviderError):
        # The provider's message can mention keys or quotas; log it, don't show it.
        logger.error("LLM provider error: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "detail": "The AI service is not reachable right now. "
                "Please try again or enter the transaction manually."
            },
        )

    @app.exception_handler(AudioRejectedError)
    async def _audio_rejected(_request: Request, exc: AudioRejectedError):
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})

    @app.exception_handler(STTNotConfiguredError)
    async def _stt_not_configured(_request: Request, exc: STTNotConfiguredError):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"detail": str(exc)}
        )

    @app.exception_handler(STTProviderError)
    async def _stt_provider(_request: Request, exc: STTProviderError):
        # 502, not 503: the server is set up, the speech service failed this time.
        logger.error("Speech-to-text provider error: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": "The speech-to-text service failed. Please try again or type it."},
        )

    @app.exception_handler(Exception)
    async def _unexpected(_request: Request, exc: Exception):
        # Never send a traceback or the error's text (it can hold data) to the client.
        logger.exception("Unexpected error: %s", type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Something went wrong on the server. Please try again."},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_request: Request, exc: RequestValidationError):
        """Flatten Pydantic errors into [{field, message}] that a mobile app can show directly."""
        errors = []
        for err in exc.errors():
            loc = [str(part) for part in err["loc"]]
            if loc and loc[0] in ("body", "query", "path"):
                loc = loc[1:]
            errors.append(
                {
                    "field": ".".join(loc) or None,
                    "message": err["msg"].removeprefix("Value error, "),
                }
            )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": "Invalid request data", "errors": errors},
        )


app = create_app()
