from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.modules.core_data.schemas import UserCreate
from app.modules.core_data.service import UserService


@pytest.fixture
def repo() -> MagicMock:
    return MagicMock()


@pytest.fixture
def service(repo: MagicMock) -> UserService:
    return UserService(repo)


def test_register_normalizes_email_and_hashes_password(
    service: UserService,
    repo: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo.get_by_email.return_value = None
    repo.create.side_effect = lambda user: user
    monkeypatch.setattr(
        "app.modules.core_data.service.hash_password",
        lambda password: f"hashed:{password}",
    )

    data = UserCreate(
        email="User@Example.com",
        password="StrongPass123",
    )

    user = service.register(data)

    assert user.email == "user@example.com"
    assert user.password_hash == "hashed:StrongPass123"
    repo.create.assert_called_once()


def test_register_rejects_duplicate_email(
    service: UserService,
    repo: MagicMock,
) -> None:
    repo.get_by_email.return_value = SimpleNamespace(id=1)

    with pytest.raises(HTTPException) as exc_info:
        service.register(
            UserCreate(
                email="user@example.com",
                password="StrongPass123",
            )
        )

    assert exc_info.value.status_code == 400
