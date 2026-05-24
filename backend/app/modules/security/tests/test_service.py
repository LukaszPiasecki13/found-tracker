from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.modules.security.schemas import LoginRequest
from app.modules.security.services.auth import AuthService


@pytest.fixture
def repo() -> MagicMock:
    return MagicMock()


@pytest.fixture
def service(repo: MagicMock) -> AuthService:
    token_service = MagicMock()
    return AuthService(repo, token_service)


def test_register_creates_hidden_username_and_hashes_password(
    service: AuthService,
    repo: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = SimpleNamespace(id=42, is_active=True, password_hash="stored-hash")
    repo.get_by_email.return_value = user
    monkeypatch.setattr(
        "app.modules.security.services.auth.verify_password",
        lambda plain, hashed: plain == "StrongPass123" and hashed == "stored-hash",
    )
    service.token_service.create_access_token.return_value = "access:42"
    service.token_service.create_refresh_token.return_value = "refresh:42"

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
        "app.modules.security.services.auth.verify_password",
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
    service.token_service.decode_token.return_value = {"sub": "42", "type": "refresh"}
    service.token_service.create_access_token.return_value = "access:42"
    service.token_service.create_refresh_token.return_value = "refresh:42"

    token = service.refresh("refresh-token")

    assert token.access == "access:42"
    assert token.refresh == "refresh:42"
