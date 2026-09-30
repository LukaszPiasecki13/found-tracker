"""Integration test fixtures for SQL infrastructure tests."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
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


@pytest.fixture
def postgres_session() -> Session:
    """Provide a real PostgreSQL session and roll back all test changes."""
    engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()
