from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database - required, must be set in .env
    database_url: str

    # JWT
    secret_key: str
    access_token_expire_minutes: int = 120
    algorithm: str = "HS256"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[misc]
