"""Authentication schemas."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.modules.security.constants import MAX_PASSWORD_BYTES


class LoginRequest(BaseModel):
    """Login request - identified by e-mail.

    An over-long password is rejected here (in bytes, not characters) so it
    never reaches bcrypt, which cannot hash more than `MAX_PASSWORD_BYTES`.
    """

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1)

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value: str) -> str:
        if len(value.encode()) > MAX_PASSWORD_BYTES:
            raise ValueError(f"Password exceeds {MAX_PASSWORD_BYTES} bytes")
        return value


class TokenRefreshRequest(BaseModel):
    """Token refresh request."""

    model_config = ConfigDict(extra="forbid")

    refresh: str = Field(min_length=1)


class TokenResponse(BaseModel):
    """Access/refresh token pair."""

    access: str
    refresh: str
