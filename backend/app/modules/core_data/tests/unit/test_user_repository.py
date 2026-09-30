from unittest.mock import MagicMock

import pytest

from app.core.errors import NotFoundError
from app.modules.core_data.models.user import User
from app.modules.core_data.repositories.users import UserRepository


def test_get_by_id_raises_not_found_with_code() -> None:
    session = MagicMock()
    session.execute.return_value.scalar_one_or_none.return_value = None

    with pytest.raises(NotFoundError) as exc_info:
        UserRepository(session).get_by_id(1)

    assert exc_info.value.code == "USER_NOT_FOUND"


def test_find_by_id_returns_none_when_missing() -> None:
    session = MagicMock()
    session.execute.return_value.scalar_one_or_none.return_value = None

    assert UserRepository(session).find_by_id(1) is None


def test_create_adds_and_flushes_without_committing() -> None:
    session = MagicMock()

    user = UserRepository(session).create("user@example.com", "hash")

    assert isinstance(user, User)
    assert user.email == "user@example.com"
    session.add.assert_called_once_with(user)
    session.flush.assert_called_once()
    session.commit.assert_not_called()
