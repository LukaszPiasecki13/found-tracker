from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.modules.auth.schemas import LoginRequest, UserCreate
from app.modules.auth.service import AuthService


@pytest.fixture
def repo() -> MagicMock:
    return MagicMock()


@pytest.fixture
def service(repo: MagicMock) -> AuthService:
    return AuthService(repo)


def test_register_creates_hidden_username_and_hashes_password(
    service: AuthService,
    repo: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo.get_by_email.return_value = None
    repo.create.side_effect = lambda user: user
    monkeypatch.setattr(
        "app.modules.auth.service.hash_password",
        lambda password: f"hashed:{password}",
    )

    data = UserCreate(
        email="User@Example.com",
        password="StrongPass123",
        first_name="Jan",
        last_name="Kowalski",
    )

    user = service.register(data)

    assert user.email == "user@example.com"
    assert user.username.startswith("user_")
    assert user.password_hash == "hashed:StrongPass123"
    assert user.first_name == "Jan"
    assert user.last_name == "Kowalski"
    repo.create.assert_called_once()


def test_register_rejects_duplicate_email(
    service: AuthService,
    repo: MagicMock,
) -> None:
    repo.get_by_email.return_value = SimpleNamespace(id=1)

    with pytest.raises(HTTPException) as exc_info:
        service.register(
            UserCreate(
                email="user@example.com",
                password="StrongPass123",
                first_name="Jan",
                last_name="Kowalski",
            )
        )

    assert exc_info.value.status_code == 400


def test_login_returns_token_pair(
    service: AuthService,
    repo: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = SimpleNamespace(id=42, is_active=True, password_hash="stored-hash")
    repo.get_by_email.return_value = user
    monkeypatch.setattr(
        "app.modules.auth.service.verify_password",
        lambda plain, hashed: plain == "StrongPass123" and hashed == "stored-hash",
    )
    monkeypatch.setattr(
        "app.modules.auth.service.create_access_token",
        lambda data: f"access:{data['sub']}",
    )
    monkeypatch.setattr(
        "app.modules.auth.service.create_refresh_token",
        lambda data: f"refresh:{data['sub']}",
    )

    token = service.login(
        LoginRequest(email="user@example.com", password="StrongPass123")
    )

    assert token.access == "access:42"
    assert token.refresh == "refresh:42"


def test_login_rejects_invalid_credentials(
    service: AuthService,
    repo: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo.get_by_email.return_value = None
    monkeypatch.setattr(
        "app.modules.auth.service.verify_password",
        lambda plain, hashed: True,
    )

    with pytest.raises(HTTPException) as exc_info:
        service.login(LoginRequest(email="user@example.com", password="bad"))

    assert exc_info.value.status_code == 401


def test_refresh_returns_new_tokens(
    service: AuthService,
    repo: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo.get_by_id.return_value = SimpleNamespace(id=42, is_active=True)
    monkeypatch.setattr(
        "app.modules.auth.service.decode_token",
        lambda token: {"sub": "42", "type": "refresh"},
    )
    monkeypatch.setattr(
        "app.modules.auth.service.create_access_token",
        lambda data: f"access:{data['sub']}",
    )
    monkeypatch.setattr(
        "app.modules.auth.service.create_refresh_token",
        lambda data: f"refresh:{data['sub']}",
    )

    token = service.refresh("refresh-token")

    assert token.access == "access:42"
    assert token.refresh == "refresh:42"
