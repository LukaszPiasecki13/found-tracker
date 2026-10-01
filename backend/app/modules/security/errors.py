"""Domain errors of the `security` module.

Each subclasses a generic `app.core.errors` type, so the global handler and
any `except` on the base class keep working; the subclass names the reason
and owns its message (ADR-0007).
"""

from app.core.errors import AuthenticationError

# RFC 6750 §3: a 401 from a bearer-protected resource must carry a challenge.
_BEARER_CHALLENGE = {"WWW-Authenticate": "Bearer"}


# --- Login and refresh (401, no challenge: the client is not holding a token) ---


class InvalidCredentialsError(AuthenticationError):
    """Unknown user, inactive account or wrong password.

    Deliberately one error for all three, so a login response never reveals
    whether the account exists.
    """

    def __init__(self) -> None:
        super().__init__("Invalid credentials", code="INVALID_CREDENTIALS")


class InvalidRefreshTokenError(AuthenticationError):
    """Refresh token is malformed, expired or of the wrong type."""

    def __init__(self) -> None:
        super().__init__("Invalid refresh token", code="INVALID_REFRESH_TOKEN")


class RefreshUserNotFoundError(AuthenticationError):
    """The refresh token's owner no longer exists or was deactivated."""

    def __init__(self) -> None:
        super().__init__("User not found", code="REFRESH_USER_NOT_FOUND")


# --- Bearer-protected endpoints (401 with a `WWW-Authenticate` challenge) ---


class BearerAuthenticationError(AuthenticationError):
    """Base for 401s on endpoints that expect an access token."""

    def __init__(self, message: str, code: str) -> None:
        super().__init__(message, code=code, headers=_BEARER_CHALLENGE)


class MissingCredentialsError(BearerAuthenticationError):
    """No `Authorization: Bearer ...` header on the request."""

    def __init__(self) -> None:
        super().__init__(
            "Missing or invalid authorization header", "MISSING_CREDENTIALS"
        )


class InvalidAccessTokenError(BearerAuthenticationError):
    """Access token is undecodable, of the wrong type or has a bad `sub`."""

    def __init__(self) -> None:
        super().__init__("Invalid token", "INVALID_ACCESS_TOKEN")


class InactiveUserError(BearerAuthenticationError):
    """The access token's owner no longer exists or was deactivated."""

    def __init__(self) -> None:
        super().__init__("User not found or inactive", "INACTIVE_USER")
