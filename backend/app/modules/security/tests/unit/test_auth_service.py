from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.errors import AuthenticationError
from app.core.passwords import hash_password
from app.modules.security.errors import (
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    RefreshUserNotFoundError,
)
from app.modules.security.schemas import LoginRequest
from app.modules.security.services.auth import AuthService
from app.modules.security.services.token import TokenService


@pytest.fixture
def users() -> MagicMock:
    return MagicMock()


@pytest.fixture
def token_service() -> TokenService:
    return TokenService("test-secret")


@pytest.fixture
def service(users: MagicMock, token_service: TokenService) -> AuthService:
    return AuthService(users, token_service)


def _user(*, is_active: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        id=42, is_active=is_active, password_hash=hash_password("StrongPass123")
    )


def _login(password: str = "StrongPass123") -> LoginRequest:
    return LoginRequest(email="user@example.com", password=password)


def test_login_returns_token_pair_for_valid_credentials(
    service: AuthService, users: MagicMock, token_service: TokenService
) -> None:
    users.find_by_email.return_value = _user()

    tokens = service.login(_login())

    access = token_service.decode_token(tokens.access)
    refresh = token_service.decode_token(tokens.refresh)
    assert access is not None
    assert (access["sub"], access["type"]) == ("42", "access")
    assert refresh is not None
    assert (refresh["sub"], refresh["type"]) == ("42", "refresh")


def test_login_rejects_unknown_user_and_still_verifies_a_password(
    service: AuthService, users: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    users.find_by_email.return_value = None
    burned: list[str] = []
    monkeypatch.setattr(
        "app.modules.security.services.auth.burn_password_verification",
        burned.append,
    )

    with pytest.raises(InvalidCredentialsError) as exc_info:
        service.login(_login())

    assert burned == ["StrongPass123"]
    assert exc_info.value.status_code == 401
    assert exc_info.value.code == "INVALID_CREDENTIALS"


def test_login_rejects_wrong_password(service: AuthService, users: MagicMock) -> None:
    users.find_by_email.return_value = _user()

    with pytest.raises(InvalidCredentialsError):
        service.login(_login("WrongPass123"))


def test_login_rejects_inactive_user_with_the_same_error(
    service: AuthService, users: MagicMock
) -> None:
    users.find_by_email.return_value = _user(is_active=False)

    with pytest.raises(InvalidCredentialsError) as exc_info:
        service.login(_login())

    assert exc_info.value.message == "Invalid credentials"


def test_login_verifies_the_password_even_for_an_inactive_user(
    service: AuthService, users: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An inactive account must cost as much as a wrong password (no timing oracle)."""
    users.find_by_email.return_value = _user(is_active=False)
    verified: list[str] = []

    def spy(plain: str, hashed: str | None) -> bool:
        verified.append(plain)
        return True

    monkeypatch.setattr("app.modules.security.services.auth.verify_password", spy)

    with pytest.raises(InvalidCredentialsError):
        service.login(_login())

    assert verified == ["StrongPass123"]


def test_refresh_returns_new_token_pair(
    service: AuthService, users: MagicMock, token_service: TokenService
) -> None:
    users.find_by_id.return_value = _user()
    refresh = token_service.create_refresh_token({"sub": "42"})

    tokens = service.refresh(refresh)

    payload = token_service.decode_token(tokens.access)
    assert payload is not None
    assert payload["sub"] == "42"
    users.find_by_id.assert_called_once_with(42)


def test_refresh_rejects_access_token(
    service: AuthService, token_service: TokenService
) -> None:
    access = token_service.create_access_token({"sub": "42"})

    with pytest.raises(InvalidRefreshTokenError) as exc_info:
        service.refresh(access)

    assert exc_info.value.code == "INVALID_REFRESH_TOKEN"


@pytest.mark.parametrize("token", ["garbage", ""])
def test_refresh_rejects_undecodable_token(service: AuthService, token: str) -> None:
    with pytest.raises(InvalidRefreshTokenError):
        service.refresh(token)


@pytest.mark.parametrize("sub", ["not-a-number", "", " 1", "+1", "-1", chr(0x661)])
def test_refresh_rejects_non_numeric_subject_instead_of_crashing(
    service: AuthService, token_service: TokenService, sub: str
) -> None:
    refresh = token_service.create_refresh_token({"sub": sub})

    with pytest.raises(InvalidRefreshTokenError):
        service.refresh(refresh)


def test_refresh_rejects_token_without_subject(
    service: AuthService, token_service: TokenService
) -> None:
    refresh = token_service.create_refresh_token({})

    with pytest.raises(InvalidRefreshTokenError):
        service.refresh(refresh)


@pytest.mark.parametrize("user", [None, _user(is_active=False)])
def test_refresh_rejects_missing_or_inactive_user(
    service: AuthService,
    users: MagicMock,
    token_service: TokenService,
    user: SimpleNamespace | None,
) -> None:
    users.find_by_id.return_value = user
    refresh = token_service.create_refresh_token({"sub": "42"})

    with pytest.raises(RefreshUserNotFoundError) as exc_info:
        service.refresh(refresh)

    assert isinstance(exc_info.value, AuthenticationError)
    assert exc_info.value.code == "REFRESH_USER_NOT_FOUND"
