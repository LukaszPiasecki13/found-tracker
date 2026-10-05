"""The time-weighted return end to end: real HTTP, real database, a faked price
history (ADR-0004, ADR-0016). Days are built lazily on the first read, reused by
the next one and rebuilt from the earliest changed operation on."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.conftest import IntegrationData
from app.modules.assets import wiring as assets_wiring
from app.modules.assets.models import Asset, AssetClass, Currency
from app.modules.assets.tests.fakes import FakeMarketDataProvider
from app.modules.portfolios.models import PortfolioDaily

D = Decimal
FIRST = date(2025, 1, 2)


@pytest.fixture
def fake_provider(monkeypatch: pytest.MonkeyPatch) -> FakeMarketDataProvider:
    provider = FakeMarketDataProvider()
    monkeypatch.setattr(assets_wiring, "build_market_data_provider", lambda: provider)
    return provider


def _when(day: int) -> str:
    return datetime(2025, 1, day, 12, tzinfo=UTC).isoformat()


def _currency(session: Session) -> Currency:
    currency = session.scalar(select(Currency).where(Currency.code == "PLN"))
    if currency is None:
        currency = Currency(code="PLN", exchange_rate=D("0.25"))
        session.add(currency)
        session.flush()
    return currency


def _asset(
    session: Session, data: IntegrationData, currency: Currency, price: str
) -> Asset:
    asset_class = session.scalar(select(AssetClass).order_by(AssetClass.id))
    assert asset_class is not None, "the integration database needs an asset class"
    asset = Asset(
        ticker=data.value("twr")[:20].upper(),
        name="Asset twr",
        asset_class_id=asset_class.id,
        currency_id=currency.id,
        current_price=D(price),
        exchange="",
        sector="",
    )
    session.add(asset)
    session.flush()
    return asset


def _history() -> dict[date, D]:
    """100 until 10 January 2025, 110 from the 11th on, every day to today."""
    closes: dict[date, Decimal] = {}
    day = FIRST
    while day <= date.today():
        closes[day] = D("100") if day <= date(2025, 1, 10) else D("110")
        day += timedelta(days=1)
    return closes


def _post(
    client: TestClient, headers: dict[str, str], path: str, payload: dict[str, Any]
) -> Any:
    response = client.post(path, headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _detail(
    client: TestClient, headers: dict[str, str], portfolio_id: int
) -> dict[str, Any]:
    response = client.get(f"/portfolios/{portfolio_id}", headers=headers)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_the_return_is_time_weighted_cached_and_rebuilt_after_a_back_dated_change(
    integration_client: TestClient,
    integration_session: Session,
    integration_data: IntegrationData,
    auth_headers: dict[str, str],
    fake_provider: FakeMarketDataProvider,
) -> None:
    pln = _currency(integration_session)
    asset = _asset(integration_session, integration_data, pln, "110")
    fake_provider.history[asset.ticker] = _history()
    portfolio_id = _post(
        integration_client,
        auth_headers,
        "/portfolios/",
        {"name": integration_data.value("twr"), "base_currency_id": pln.id},
    )["id"]
    operations = "/portfolios/operations"
    _post(
        integration_client,
        auth_headers,
        operations,
        {
            "portfolio_id": portfolio_id,
            "operation_type": "deposit",
            "amount": 1000,
            "operation_date": _when(2),
        },
    )
    _post(
        integration_client,
        auth_headers,
        operations,
        {
            "portfolio_id": portfolio_id,
            "operation_type": "buy",
            "asset_id": asset.id,
            "quantity": 10,
            "price": 100,
            "operation_date": _when(3),
        },
    )

    first = _detail(integration_client, auth_headers, portfolio_id)

    # 1000 became 1100 when the close moved from 100 to 110: +10%.
    assert first["total_value"] == 1100
    assert first["total_return_pct"] == pytest.approx(10)
    assert first["return_method"] == "daily_pp_v1"
    stored = integration_session.scalar(
        select(func.count()).where(PortfolioDaily.portfolio_id == portfolio_id)
    )
    assert stored and stored > 300
    history_calls = fake_provider.calls.count(("history", asset.ticker))

    again = _detail(integration_client, auth_headers, portfolio_id)

    assert again["total_return_pct"] == first["total_return_pct"]
    # Nothing new to fetch: the days are stored.
    assert fake_provider.calls.count(("history", asset.ticker)) == history_calls

    # A deposit back-dated to the 5th: 500 idle in cash while the shares gained.
    _post(
        integration_client,
        auth_headers,
        operations,
        {
            "portfolio_id": portfolio_id,
            "operation_type": "deposit",
            "amount": 500,
            "operation_date": _when(5),
        },
    )

    changed = _detail(integration_client, auth_headers, portfolio_id)

    # The 500 sits in cash from the 5th: 1600 on the 11th against 1500 the day
    # before is +6.67% (the new money earned nothing, the shares +10% on 1000).
    assert changed["total_value"] == 1600
    assert changed["total_return_pct"] == pytest.approx(6.6667, abs=1e-3)
