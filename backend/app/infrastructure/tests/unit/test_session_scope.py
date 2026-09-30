"""Unit tests for `session_scope` / the request session (ADR-0002)."""

import logging
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.infrastructure.sql.factory import SQLConnectionFactory


def _session() -> MagicMock:
    session = MagicMock(spec=Session)
    session.new, session.dirty, session.deleted = set(), set(), set()
    return session


def _scope(session: MagicMock):  # type: ignore[no-untyped-def]
    return SQLConnectionFactory().create_session_scope(lambda: session)


def test_scope_closes_and_never_commits_on_success() -> None:
    session = _session()

    with _scope(session)() as yielded:
        assert yielded is session

    session.close.assert_called_once()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


@pytest.mark.parametrize("error", [ValueError("boom"), SystemExit(1)])
def test_scope_rolls_back_and_closes_on_any_exception(error: BaseException) -> None:
    session = _session()

    with pytest.raises(type(error)), _scope(session)():
        raise error

    session.rollback.assert_called_once()
    session.close.assert_called_once()
    session.commit.assert_not_called()


def test_scope_keeps_the_original_error_when_rollback_fails() -> None:
    session = _session()
    session.rollback.side_effect = RuntimeError("rollback failed")

    with pytest.raises(ValueError, match="original"), _scope(session)():
        raise ValueError("original")

    session.close.assert_called_once()


def test_scope_warns_about_uncommitted_changes(
    caplog: pytest.LogCaptureFixture,
) -> None:
    session = _session()
    session.new = {object()}

    with caplog.at_level(logging.WARNING), _scope(session)():
        pass

    assert "missing transaction()" in caplog.text
    session.commit.assert_not_called()


def test_request_dependency_uses_the_same_mechanism() -> None:
    session = _session()
    dependency = SQLConnectionFactory().get_session_dependency(lambda: session)

    generator = dependency()
    assert next(generator) is session
    with pytest.raises(ValueError, match="boom"):
        generator.throw(ValueError("boom"))

    session.rollback.assert_called_once()
    session.close.assert_called_once()
