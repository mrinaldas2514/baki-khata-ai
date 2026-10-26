"""Database engine and session setup."""

from collections.abc import Generator
from typing import Any

from fastapi import Request
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session

from app.models import Base


def build_engine(database_url: str, *, echo: bool = False, **kwargs: Any) -> Engine:
    """Create an engine. SQLite-specific tweaks are only applied for SQLite URLs."""
    is_sqlite = database_url.startswith("sqlite")
    connect_args = {"check_same_thread": False} if is_sqlite else {}
    engine = create_engine(database_url, echo=echo, connect_args=connect_args, **kwargs)

    if is_sqlite:
        # SQLite ignores foreign keys unless asked to enforce them on every connection.
        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, _record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def create_tables(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def get_db(request: Request) -> Generator[Session]:
    """FastAPI dependency: one session per request, always closed afterwards."""
    db: Session = request.app.state.session_factory()
    try:
        yield db
    finally:
        db.close()
