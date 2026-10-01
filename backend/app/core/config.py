from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

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
    cors_origins: list[str] = Field(default_factory=list)

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

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: object) -> object:
        """Accept CORS_ORIGINS as a comma-separated string or a JSON list."""
        if isinstance(value, str) and not value.strip().startswith("["):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

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
