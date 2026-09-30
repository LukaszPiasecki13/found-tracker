"""Unit tests for `SQLRepository`. Tests use a mocked session."""

from unittest.mock import MagicMock

import pytest

from app.infrastructure.sql.repository import SQLRepository


def test_transaction_commits_on_success() -> None:
    session = MagicMock()

    with SQLRepository(session).transaction():
        pass

    session.commit.assert_called_once()
    session.rollback.assert_not_called()


def test_transaction_rolls_back_and_reraises_on_error() -> None:
    session = MagicMock()

    with pytest.raises(ValueError, match="boom"), SQLRepository(session).transaction():
        raise ValueError("boom")

    session.rollback.assert_called_once()
    session.commit.assert_not_called()


def test_transaction_does_not_swallow_base_exceptions_into_a_commit() -> None:
    session = MagicMock()

    with pytest.raises(KeyboardInterrupt), SQLRepository(session).transaction():
        raise KeyboardInterrupt

    session.commit.assert_not_called()


def test_savepoint_enters_and_exits_the_nested_transaction() -> None:
    session = MagicMock()

    with SQLRepository(session).savepoint():
        pass

    nested = session.begin_nested.return_value
    nested.__enter__.assert_called_once()
    nested.__exit__.assert_called_once()


def test_an_exception_still_exits_the_nested_transaction() -> None:
    session = MagicMock()

    with pytest.raises(ValueError), SQLRepository(session).savepoint():
        raise ValueError("boom")

    session.begin_nested.return_value.__exit__.assert_called_once()


def test_flush_and_refresh_delegate_to_the_session() -> None:
    session = MagicMock()
    repo = SQLRepository(session)
    entity = object()

    repo.flush()
    repo.refresh(entity)

    session.flush.assert_called_once()
    session.refresh.assert_called_once_with(entity)
