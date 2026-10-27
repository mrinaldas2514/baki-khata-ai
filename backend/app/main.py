"""FastAPI application. Run with: uvicorn app.main:app --reload"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.database import build_engine, create_tables
from app.llm import LLMClient, LLMNotConfiguredError, LLMProviderError
from app.routers import customers, dashboard, parse, shops, transactions
from app.services.exceptions import ConflictError, NotFoundError
from app.services.parsing import LLMOutputError, NotATransactionError

logger = logging.getLogger(__name__)


def create_app(engine: Engine | None = None, llm_client: LLMClient | None = None) -> FastAPI:
    settings = get_settings()
    if engine is None:
        engine = build_engine(settings.database_url, echo=settings.sql_echo)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Fine for now; switch to Alembic migrations once the schema starts changing.
        create_tables(engine)
        yield

    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.state.session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    # None means "build the configured provider on first use" (see app.llm.get_llm_client).
    app.state.llm_client = llm_client

    # Lets the frontend (a different origin in development) call the API from the browser.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(shops.router)
    app.include_router(customers.router)
    app.include_router(transactions.router)
    app.include_router(dashboard.router)
    app.include_router(parse.router)

    @app.get("/health", tags=["health"])
    def health():
        return {"status": "ok"}

    _register_error_handlers(app)
    return app


def _register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def _not_found(_request: Request, exc: NotFoundError):
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})

    @app.exception_handler(ConflictError)
    async def _conflict(_request: Request, exc: ConflictError):
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})

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
