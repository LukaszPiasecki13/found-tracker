"""Shared pytest fixtures.

Safety: integration tests write to the database, so they must never run against a
shared or production one. The target is `TEST_DATABASE_URL`; without it,
`DATABASE_URL` is accepted when it points at a local host, or when it is a shared
database and `TEST_SCHEMA` names a schema of its own: the tests then run with
`search_path` pinned to that schema (no fallback to `public`), which is refused if
it is `public` or `PRODUCTION_SCHEMA`. Otherwise the integration tests are skipped.
Each integration test runs inside a transaction that is rolled back, so nothing is
left behind. Prepare a test schema once:
`alembic -x db_schema=<TEST_SCHEMA> upgrade head`, then
`DATABASE_SCHEMA=<TEST_SCHEMA> python -m seed.seed` (reference data the tests need).
"""

import os
import re
import secrets
import string
from collections.abc import Generator
from dataclasses import dataclass, field
from uuid import uuid4

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

load_dotenv()

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "postgres"}


# Placeholder for runs without a safe database: `Settings` needs a URL to import,
# and engines connect lazily, so unit tests never touch it.
_UNIT_ONLY_DATABASE_URL = "postgresql+psycopg2://unit:unit@localhost:5432/unit_only"


def _test_schema() -> str | None:
    """The schema the integration tests are confined to, when `TEST_SCHEMA` is set
    and is not the production one (`PRODUCTION_SCHEMA`, default `public`)."""
    schema = (os.environ.get("TEST_SCHEMA") or "").strip()
    if not schema:
        return None
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", schema):
        raise RuntimeError(f"TEST_SCHEMA is not a valid schema name: {schema!r}")
    production = (os.environ.get("PRODUCTION_SCHEMA") or "public").strip()
    if schema.lower() in {"public", production.lower()}:
        raise RuntimeError(
            f"TEST_SCHEMA={schema!r} is the production schema; tests need their own"
        )
    return schema


def _resolve_test_database() -> tuple[str, str | None, bool]:
    """Pick the test database and schema and say whether they are safe for
    integration tests.

    Without a disposable database (no `TEST_DATABASE_URL`, and `DATABASE_URL`
    missing or not local, with no `TEST_SCHEMA` to confine the tests to) the run is
    unit-only: a placeholder URL is used and integration tests are skipped, so
    `pytest -m "not integration"` needs no database at all.
    """
    schema = _test_schema()
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit, schema, True
    url = os.environ.get("DATABASE_URL")
    if url and make_url(url).host in _LOCAL_HOSTS:
        return url, schema, True
    if url and schema:
        return url, schema, True
    return _UNIT_ONLY_DATABASE_URL, None, False


# Settings read the environment at import time, so this must precede `app.*`.
_DATABASE_URL, _TEST_SCHEMA, _DATABASE_IS_SAFE = _resolve_test_database()
os.environ["DATABASE_URL"] = _DATABASE_URL
if _TEST_SCHEMA:
    os.environ["DATABASE_SCHEMA"] = _TEST_SCHEMA
os.environ.setdefault("ENVIRONMENT", "test")

import app.infrastructure.sql.models_registry
from app.core.config import get_settings
from app.core.dependencies import get_db
from app.core.rate_limit import limiter
from app.main import app
from app.modules.assets.models import Asset, Currency


@dataclass
class IntegrationData:
    prefix: str = field(default_factory=lambda: f"it_{uuid4().hex[:10]}")

    def value(self, suffix: str) -> str:
        return f"{self.prefix}_{suffix}"


@dataclass
class CurrencyCodes:
    """Unused 3-letter currency codes for integration tests.

    Rows created under a code are rolled back with the test transaction.
    """

    session: Session
    issued: list[str] = field(default_factory=list)

    def new(self) -> str:
        while True:
            code = "".join(secrets.choice(string.ascii_uppercase) for _ in range(3))
            if code in self.issued:
                continue
            taken = self.session.execute(
                select(Currency.id).where(Currency.code == code)
            ).first()
            if taken is None:
                self.issued.append(code)
                return code


@pytest.fixture
def integration_session() -> Generator[Session]:
    """Session whose commits only release a savepoint; the outer transaction is
    rolled back at the end, so tests leave the database untouched."""
    engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    connection = engine.connect()
    outer = connection.begin()
    if engine.dialect.name == "postgresql":
        # The server defaults this connection to read-only; the tests need writes,
        # which stay confined to the test schema and are rolled back below.
        connection.exec_driver_sql("SET TRANSACTION READ WRITE")
        # Only the test schema, no fallback to `public`; local to the outer
        # transaction, so it also holds through a transaction-mode pooler.
        schema_sql = engine.dialect.identifier_preparer.quote(
            get_settings().database_schema
        )
        connection.exec_driver_sql(f"SET LOCAL search_path TO {schema_sql}")
    session = Session(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()
        engine.dispose()


@pytest.fixture
def integration_data() -> IntegrationData:
    return IntegrationData()


@pytest.fixture
def currency_codes(integration_session: Session) -> CurrencyCodes:
    return CurrencyCodes(integration_session)


@pytest.fixture
def integration_client(
    integration_session: Session,
) -> Generator[TestClient]:
    app.dependency_overrides[get_db] = lambda: integration_session
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def auth_headers(
    integration_client: TestClient,
    integration_data: IntegrationData,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, str]:
    email = f"{integration_data.value('user')}@example.com"
    # Assets, asset classes and currencies are admin-only. The user is created
    # per test and rolled back with it, so making it an admin is safe and keeps
    # the suite independent of the developer's ADMIN_EMAILS.
    monkeypatch.setattr(
        get_settings(), "admin_emails", [email, *get_settings().admin_emails]
    )
    registration = integration_client.post(
        "/auth/register",
        json={"email": email, "password": "StrongPass123"},
    )
    assert registration.status_code == 201, registration.text

    login = integration_client.post(
        "/auth/login",
        json={"email": email, "password": "StrongPass123"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access']}"}


@pytest.fixture
def seeded_currency(integration_session: Session) -> Currency:
    currency = integration_session.query(Currency).order_by(Currency.id).first()
    if currency is None:
        pytest.fail("Integration database needs at least one currency")
    return currency


@pytest.fixture
def seeded_asset(integration_session: Session) -> Asset:
    asset = integration_session.query(Asset).order_by(Asset.id).first()
    if asset is None:
        pytest.fail("Integration database needs at least one asset")
    return asset


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark tests by directory so `-m "not integration"` skips database tests;
    without a safe database, integration tests are skipped."""
    no_database = pytest.mark.skip(
        reason=(
            "No disposable database: set TEST_DATABASE_URL, a local DATABASE_URL "
            "or TEST_SCHEMA"
        )
    )
    for item in items:
        parts = item.path.parts
        if "integration" in parts:
            item.add_marker(pytest.mark.integration)
            if not _DATABASE_IS_SAFE:
                item.add_marker(no_database)
        elif "unit" in parts:
            item.add_marker(pytest.mark.unit)


@pytest.fixture(autouse=True)
def reset_rate_limiter() -> Generator[None]:
    """Counters are process-wide: without a reset, tests hitting a limited
    endpoint would draw down the same budget."""
    limiter.reset()
    yield
    limiter.reset()
