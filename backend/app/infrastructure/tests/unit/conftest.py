"""
Unit test fixtures - mocked objects for fast, dependency-free testing.
"""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_engine():
    """Mock SQLAlchemy engine."""
    engine = MagicMock()
    engine.dispose = MagicMock()
    return engine


@pytest.fixture
def mock_session():
    """Mock SQLAlchemy session."""
    session = MagicMock()
    session.close = MagicMock()
    return session


@pytest.fixture
def sqlite_url():
    return "sqlite:///test.db"


@pytest.fixture
def postgres_url():
    return "postgresql+psycopg2://user:pass@localhost:5432/testdb"
