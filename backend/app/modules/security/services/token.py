from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt

from app.modules.security.constants import TOKEN_TYPE_ACCESS, TOKEN_TYPE_REFRESH


class TokenService:
    """Encapsulates token creation/decoding and accepts configuration via
    constructor so the service can be injected and tested without importing
    application settings at module import time.
    """

    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 30,
        refresh_token_expire_days: int = 1,
        issuer: str = "found-tracker",
        audience: str = "found-tracker-client",
    ) -> None:
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._access_expire_minutes = access_token_expire_minutes
        self._refresh_expire_days = refresh_token_expire_days
        self._issuer = issuer
        self._audience = audience

    def _encode(
        self, data: dict[str, Any], token_type: str, lifetime: timedelta
    ) -> str:
        to_encode = data.copy()
        to_encode.update(
            {
                "exp": datetime.now(UTC) + lifetime,
                "type": token_type,
                "iss": self._issuer,
                "aud": self._audience,
            }
        )
        return jwt.encode(  # type: ignore[no-any-return]
            to_encode, self._secret_key, algorithm=self._algorithm
        )

    def create_access_token(
        self, data: dict[str, Any], expires_delta: timedelta | None = None
    ) -> str:
        return self._encode(
            data,
            TOKEN_TYPE_ACCESS,
            expires_delta or timedelta(minutes=self._access_expire_minutes),
        )

    def create_refresh_token(self, data: dict[str, Any]) -> str:
        return self._encode(
            data, TOKEN_TYPE_REFRESH, timedelta(days=self._refresh_expire_days)
        )

    def decode_token(self, token: str) -> dict[str, Any] | None:
        try:
            return jwt.decode(  # type: ignore[no-any-return]
                token,
                self._secret_key,
                algorithms=[self._algorithm],
                issuer=self._issuer,
                audience=self._audience,
                options={"require_exp": True, "require_iss": True, "require_aud": True},
            )
        except JWTError:
            return None


def parse_user_id(payload: dict[str, Any]) -> int | None:
    """The user id in a token's `sub`, or None if it is not a plain ASCII integer.

    Stricter than `int()`, which also accepts " 1", "+1" and non-ASCII digits.
    """
    sub = payload.get("sub")
    if not isinstance(sub, str) or not (sub.isascii() and sub.isdigit()):
        return None
    return int(sub)
