"""FastAPI application. Run with: uvicorn app.main:app --reload"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.database import build_engine, create_tables
from app.routers import customers, dashboard, shops, transactions
from app.services.exceptions import ConflictError, NotFoundError


def create_app(engine: Engine | None = None) -> FastAPI:
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

    app.include_router(shops.router)
    app.include_router(customers.router)
    app.include_router(transactions.router)
    app.include_router(dashboard.router)

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
