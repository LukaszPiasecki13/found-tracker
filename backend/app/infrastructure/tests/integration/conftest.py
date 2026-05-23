"""Integration test fixtures for SQL infrastructure tests."""

import pytest

from app.infrastructure.sql.factory import SQLConnectionFactory

SQLITE_URL = "sqlite+pysqlite:///:memory:"


@pytest.fixture
def sql_factory() -> SQLConnectionFactory:
    return SQLConnectionFactory()


@pytest.fixture
def sql_engine(sql_factory: SQLConnectionFactory):
    engine = sql_factory.get_or_create_engine(SQLITE_URL)
    yield engine
    sql_factory.dispose_all()
