"""Mocked repositories sharing one mocked session, so `transaction()` from any of
them commits or rolls back that session - like the real wiring (ADR-0001)."""

from functools import partial
from unittest.mock import MagicMock

import pytest

from app.infrastructure.sql.repository import SQLRepository


def _transactional_repo(session: MagicMock) -> MagicMock:
    repo = MagicMock()
    repo.commit = session.commit
    repo.rollback = session.rollback
    repo.transaction = partial(SQLRepository.transaction, repo)
    return repo


@pytest.fixture
def session() -> MagicMock:
    return MagicMock()


@pytest.fixture
def portfolio_repo(session: MagicMock) -> MagicMock:
    return _transactional_repo(session)


@pytest.fixture
def position_repo(session: MagicMock) -> MagicMock:
    return _transactional_repo(session)


@pytest.fixture
def operation_repo(session: MagicMock) -> MagicMock:
    return _transactional_repo(session)
