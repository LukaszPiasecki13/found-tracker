import json
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

Environment = Literal["development", "test", "staging", "production"]


class Settings(BaseSettings):
    # Application
    app_name: str = "Found Tracker"
    environment: Environment = "development"
    log_level: str = "INFO"
    log_json: bool = False

    # Database - required, must be set in .env
    database_url: str
    # Database schema name (default: public)
    database_schema: str = "public"

    # JWT
    secret_key: str
    access_token_expire_minutes: int = Field(default=30, gt=0)
    refresh_token_expire_days: int = Field(default=1, gt=0)
    algorithm: str = "HS256"
    jwt_issuer: str = "found-tracker"
    jwt_audience: str = "found-tracker-client"

    # HTTP
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # Accounts (e-mails, comma-separated or a JSON list) allowed to change the
    # data every user shares: assets, asset classes and currencies.
    admin_emails: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # Open sign-up. Switch off once the accounts you need exist: with it on, anyone
    # can create an account and call the endpoints that reach external providers.
    registration_enabled: bool = True

    # Rate limiter: trust `X-Forwarded-For` from a reverse proxy. `None` means
    # "not set explicitly": on in production, off elsewhere; an explicit value wins.
    trust_proxy_headers: bool | None = None

    # A deployment may retain variables used by an older/newer application
    # version. They must not prevent the backend from starting after a rollback.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def is_production(self) -> bool:
        return self.environment in ("staging", "production")

    @property
    def docs_enabled(self) -> bool:
        return not self.is_production

    @property
    def effective_trust_proxy_headers(self) -> bool:
        if self.trust_proxy_headers is not None:
            return self.trust_proxy_headers
        return self.is_production

    @field_validator("cors_origins", "admin_emails", mode="before")
    @classmethod
    def split_list_setting(cls, value: object) -> object:
        """Accept a comma-separated string or a JSON list (CORS_ORIGINS, ...)."""
        if not isinstance(value, str):
            return value
        text = value.strip()
        if text.startswith("["):
            return json.loads(text)
        return [item.strip() for item in text.split(",") if item.strip()]

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        level = value.strip().upper()
        allowed = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}
        if level not in allowed:
            raise ValueError(f"log_level must be one of {sorted(allowed)}")
        return level

    @model_validator(mode="after")
    def enforce_production_hardening(self) -> Settings:
        """Fail fast instead of booting a deployment with unsafe defaults."""
        if not self.is_production:
            return self
        if len(self.secret_key) < 32:
            raise ValueError("secret_key must be at least 32 characters outside dev")
        # An empty list is rejected too: main.py falls back to a wildcard when
        # no origin is configured, so "unset" is as unsafe as an explicit "*".
        if not self.cors_origins:
            raise ValueError("cors_origins must be set outside dev")
        if "*" in self.cors_origins:
            raise ValueError("cors_origins must not be a wildcard outside dev")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
