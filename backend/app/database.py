"""Database engine and session setup. The schema itself is managed by Alembic (migrations/)."""

from collections.abc import Generator
from pathlib import Path
from typing import Any

from fastapi import Request
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session

from app.models import Base

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


def build_engine(database_url: str, *, echo: bool = False, **kwargs: Any) -> Engine:
    """Create an engine. SQLite-specific tweaks are only applied for SQLite URLs."""
    is_sqlite = database_url.startswith("sqlite")
    if is_sqlite:
        connect_args = {"check_same_thread": False}
    else:
        # Don't hang forever on an unreachable server; replace connections the server dropped.
        connect_args = {"connect_timeout": 10}
        kwargs.setdefault("pool_pre_ping", True)
    engine = create_engine(
        database_url,
        echo=echo,
        connect_args=connect_args,
        # Keep the values (names, phone numbers, amounts) out of error messages and logs,
        # unless SQL_ECHO is on for debugging.
        hide_parameters=not echo,
        **kwargs,
    )

    if is_sqlite:
        # SQLite ignores foreign keys unless asked to enforce them on every connection.
        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, _record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def create_tables(engine: Engine) -> None:
    """Only for tests (a fresh in-memory database). Real databases use `alembic upgrade head`."""
    Base.metadata.create_all(engine)


def _alembic_config():
    from alembic.config import Config

    return Config(str(ALEMBIC_INI))


def upgrade_database(engine: Engine) -> None:
    """Same as `alembic upgrade head`, on this engine."""
    from alembic import command

    config = _alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


def schema_revision(engine: Engine) -> tuple[str | None, str]:
    """(the database's migration revision or None, the newest revision in migrations/)."""
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    head = ScriptDirectory.from_config(_alembic_config()).get_current_head()
    with engine.connect() as connection:
        current = MigrationContext.configure(connection).get_current_revision()
    return current, head


class DatabaseNotMigratedError(RuntimeError):
    pass


def check_schema(engine: Engine) -> None:
    """Stop at startup with a clear message when the database needs `alembic upgrade head`."""
    current, head = schema_revision(engine)
    if current != head:
        state = "has no tables yet" if current is None else f"is at migration {current}"
        raise DatabaseNotMigratedError(
            f"The database {state}; this code needs migration {head}. "
            "Run `alembic upgrade head` in backend/ (see README), then start the server again."
        )


def get_db(request: Request) -> Generator[Session]:
    """FastAPI dependency: one session per request, always closed afterwards."""
    db: Session = request.app.state.session_factory()
    try:
        yield db
    finally:
        db.close()
