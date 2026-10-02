"""Settings loading and production hardening."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings

_STRONG_KEY = "k" * 32


@pytest.fixture(autouse=True)
def _clean_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """`conftest` loads the developer's `.env` into the process environment;
    without this, a local CORS_ORIGINS/ADMIN_EMAILS leaks into these tests."""
    for name in ("CORS_ORIGINS", "ADMIN_EMAILS", "TRUST_PROXY_HEADERS"):
        monkeypatch.delenv(name, raising=False)


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "sqlite+pysqlite:///:memory:",
        "secret_key": "test-key",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[call-arg, arg-type]


def test_settings_ignore_variables_from_other_application_versions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=sqlite+pysqlite:///:memory:\n"
        "SECRET_KEY=test-key\n"
        "REMOVED_SETTING=whatever\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)

    settings = Settings(_env_file=env_file)  # type: ignore[call-arg]

    assert settings.database_url == "sqlite+pysqlite:///:memory:"
    assert settings.secret_key == "test-key"


def test_cors_origins_accepts_comma_separated_string() -> None:
    settings = _settings(cors_origins="http://a.test, http://b.test")

    assert settings.cors_origins == ["http://a.test", "http://b.test"]


def test_development_allows_weak_secret_and_no_cors_origins() -> None:
    settings = _settings()

    assert not settings.is_production
    assert settings.docs_enabled


def test_log_level_is_normalized_and_validated() -> None:
    assert _settings(log_level=" debug ").log_level == "DEBUG"
    with pytest.raises(ValidationError):
        _settings(log_level="loud")


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_production_requires_a_strong_secret(environment: str) -> None:
    with pytest.raises(ValidationError, match="secret_key"):
        _settings(environment=environment, cors_origins=["https://app.test"])


def test_production_requires_explicit_non_wildcard_cors_origins() -> None:
    with pytest.raises(ValidationError, match="cors_origins must be set"):
        _settings(environment="production", secret_key=_STRONG_KEY)
    with pytest.raises(ValidationError, match="wildcard"):
        _settings(environment="production", secret_key=_STRONG_KEY, cors_origins=["*"])


def test_production_with_safe_values_disables_docs() -> None:
    settings = _settings(
        environment="production",
        secret_key=_STRONG_KEY,
        cors_origins=["https://app.test"],
    )

    assert settings.is_production
    assert not settings.docs_enabled


def test_list_settings_accept_comma_separated_and_json_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test, http://b.test")
    monkeypatch.setenv("ADMIN_EMAILS", '["root@a.test"]')
    settings = _settings()
    assert settings.cors_origins == ["http://a.test", "http://b.test"]
    assert settings.admin_emails == ["root@a.test"]
