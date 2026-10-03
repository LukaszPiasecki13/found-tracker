from app.core.passwords import (
    burn_password_verification,
    verify_password,
)
from app.modules.core_data.models.user import User
from app.modules.core_data.services.users import UserService
from app.modules.security.constants import TOKEN_TYPE_REFRESH
from app.modules.security.errors import (
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    RefreshUserNotFoundError,
)
from app.modules.security.schemas.auth import LoginRequest, TokenResponse
from app.modules.security.services.token import TokenService, parse_user_id


class AuthService:
    """Login and token refresh. Accounts live in `core_data` (`UserService`)."""

    def __init__(self, users: UserService, token_service: TokenService) -> None:
        self._users = users
        self._token_service = token_service

    def _issue_tokens(self, user: User) -> TokenResponse:
        sub = {"sub": str(user.id)}
        return TokenResponse(
            access=self._token_service.create_access_token(sub),
            refresh=self._token_service.create_refresh_token(sub),
        )

    def login(self, data: LoginRequest) -> TokenResponse:
        """Exchange e-mail + password for a token pair.

        Unknown user, inactive account and wrong password fail through the
        same error, and an unknown user still pays for a password check, so
        neither the response nor its timing reveals whether the account exists.
        """
        user = self._users.find_by_email(data.email)
        if user is None:
            burn_password_verification(data.password)
            raise InvalidCredentialsError
        # Verify before looking at `is_active`, so an inactive account costs the
        # same as a wrong password.
        password_ok = verify_password(data.password, user.password_hash)
        if not (password_ok and user.is_active):
            raise InvalidCredentialsError
        return self._issue_tokens(user)

    def refresh(self, refresh_token: str) -> TokenResponse:
        """Exchange a valid refresh token for a new token pair (stateless)."""
        payload = self._token_service.decode_token(refresh_token)
        if not payload or payload.get("type") != TOKEN_TYPE_REFRESH:
            raise InvalidRefreshTokenError
        user_id = parse_user_id(payload)
        if user_id is None:
            raise InvalidRefreshTokenError

        user = self._users.find_by_id(user_id)
        if user is None or not user.is_active:
            raise RefreshUserNotFoundError
        return self._issue_tokens(user)
