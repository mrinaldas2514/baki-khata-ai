"""Alembic migrations: they build exactly the schema in app/models, and the app insists on them."""

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.database import (
    DatabaseNotMigratedError,
    _alembic_config,
    build_engine,
    schema_revision,
    upgrade_database,
)
from app.main import create_app
from app.models import Base


@pytest.fixture
def file_engine(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path / 'baki_khata.db'}")
    yield engine
    engine.dispose()


def test_upgrade_head_matches_the_models(file_engine):
    upgrade_database(file_engine)
    with file_engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert diff == []
    current, head = schema_revision(file_engine)
    assert current == head


def test_initial_migration_is_the_old_create_all_schema(file_engine):
    config = _alembic_config()
    with file_engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0001")
    tables = set(inspect(file_engine).get_table_names())
    assert tables == {"alembic_version", "shops", "customers", "transactions"}


def test_downgrade_to_nothing_and_back(file_engine):
    upgrade_database(file_engine)
    config = _alembic_config()
    with file_engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
    assert set(inspect(file_engine).get_table_names()) == {"alembic_version"}
    upgrade_database(file_engine)
    assert "users" in inspect(file_engine).get_table_names()


def test_app_refuses_to_start_on_an_unmigrated_database(file_engine):
    app = create_app(file_engine, check_migrations=True)
    with pytest.raises(DatabaseNotMigratedError, match="alembic upgrade head"):
        with TestClient(app):
            pass


def test_app_starts_on_a_migrated_database_without_create_all(file_engine):
    upgrade_database(file_engine)
    with TestClient(create_app(file_engine, check_migrations=True)) as client:
        assert client.get("/health").status_code == 200


def test_app_startup_does_not_create_tables(file_engine):
    with TestClient(create_app(file_engine, check_migrations=False)):
        pass
    assert inspect(file_engine).get_table_names() == []
