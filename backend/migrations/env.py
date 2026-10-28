"""Alembic environment: migrates the database in DATABASE_URL (backend/.env) to app.models."""

from logging.config import fileConfig

from alembic import context

from app.config import get_settings
from app.database import build_engine
from app.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _url() -> str:
    # `alembic -x url=...` wins over DATABASE_URL.
    return context.get_x_argument(as_dictionary=True).get("url") or get_settings().database_url


def _configure(**kwargs) -> None:
    # SQLite can't ALTER most things; batch mode rebuilds the table instead.
    context.configure(target_metadata=target_metadata, render_as_batch=True, **kwargs)


if context.is_offline_mode():
    # `alembic upgrade head --sql`: print the SQL instead of running it.
    _configure(url=_url(), literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()
elif (connection := config.attributes.get("connection")) is not None:
    # Called from code (tests, app.migrations) with an open connection.
    _configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()
else:
    with build_engine(_url()).connect() as connection:
        _configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
