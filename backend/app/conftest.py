from collections.abc import Generator
from dataclasses import dataclass, field
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session

import app.infrastructure.sql.models_registry
from app.core.config import get_settings
from app.core.dependencies import get_db
from app.main import app
from app.modules.assets.models.assets import Asset, AssetClass
from app.modules.assets.models.currencies import Currency
from app.modules.core_data.models import User
from app.modules.portfolios.models import Portfolio


@dataclass
class IntegrationData:
    prefix: str = field(default_factory=lambda: f"it_{uuid4().hex[:10]}")

    def value(self, suffix: str) -> str:
        return f"{self.prefix}_{suffix}"


@pytest.fixture
def integration_session() -> Generator[Session]:
    engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    session = Session(engine, expire_on_commit=False)
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.fixture
def integration_data(
    integration_session: Session,
) -> Generator[IntegrationData]:
    data = IntegrationData()
    yield data

    portfolios = (
        integration_session.query(Portfolio)
        .filter(Portfolio.name.like(f"{data.prefix}%"))
        .all()
    )
    users = (
        integration_session.query(User).filter(User.email.like(f"{data.prefix}%")).all()
    )
    assets = (
        integration_session.query(Asset)
        .filter(func.lower(Asset.ticker).like(f"{data.prefix.lower()}%"))
        .all()
    )
    asset_classes = (
        integration_session.query(AssetClass)
        .filter(AssetClass.name.like(f"{data.prefix}%"))
        .all()
    )

    for portfolio in portfolios:
        integration_session.delete(portfolio)
    for asset in assets:
        integration_session.delete(asset)
    for asset_class in asset_classes:
        integration_session.delete(asset_class)
    for user in users:
        integration_session.delete(user)
    integration_session.commit()


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
) -> dict[str, str]:
    email = f"{integration_data.value('user')}@example.com"
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
