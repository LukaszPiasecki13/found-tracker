"""Valuation of foreign positions end to end: real HTTP, real database, faked
market data (E0.1).

Rates are the "USD per one unit" values `assets` stores. They are set on the
seeded currencies inside the test transaction, which is rolled back afterwards.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.conftest import IntegrationData
from app.modules.assets import wiring as assets_wiring
from app.modules.assets.models import Asset, AssetClass, Currency
from app.modules.assets.tests.fakes import FakeMarketDataProvider, make_quote

D = Decimal


@pytest.fixture
def fake_provider(monkeypatch: pytest.MonkeyPatch) -> FakeMarketDataProvider:
    provider = FakeMarketDataProvider()
    monkeypatch.setattr(assets_wiring, "build_market_data_provider", lambda: provider)
    return provider


def _when(day: int) -> str:
    return datetime(2025, 1, day, 12, tzinfo=UTC).isoformat()


def _currency(session: Session, code: str, rate: str) -> Currency:
    currency = session.scalar(select(Currency).where(Currency.code == code))
    if currency is None:
        currency = Currency(code=code, exchange_rate=D(rate))
        session.add(currency)
    currency.exchange_rate = D(rate)
    session.flush()
    return currency


def _asset(
    session: Session,
    data: IntegrationData,
    suffix: str,
    currency: Currency,
    price: str,
) -> Asset:
    asset_class = session.scalar(select(AssetClass).order_by(AssetClass.id))
    assert asset_class is not None, "the integration database needs an asset class"
    asset = Asset(
        ticker=data.value(suffix)[:20].upper(),
        name=f"Asset {suffix}",
        asset_class_id=asset_class.id,
        currency_id=currency.id,
        current_price=D(price),
        exchange="",
        sector="",
    )
    session.add(asset)
    session.flush()
    return asset


class Api:
    def __init__(self, client: TestClient, headers: dict[str, str]) -> None:
        self.client = client
        self.headers = headers

    def create_portfolio(self, name: str, currency: Currency) -> int:
        response = self.client.post(
            "/portfolios/",
            headers=self.headers,
            json={"name": name, "base_currency_id": currency.id},
        )
        assert response.status_code == 201, response.text
        return int(response.json()["id"])

    def operation(self, portfolio_id: int, **payload: Any) -> None:
        response = self.client.post(
            "/portfolios/operations",
            headers=self.headers,
            json={"portfolio_id": portfolio_id, **payload},
        )
        assert response.status_code == 201, response.text

    def deposit(self, portfolio_id: int, amount: int) -> None:
        self.operation(
            portfolio_id,
            operation_type="deposit",
            amount=amount,
            operation_date=_when(2),
        )

    def buy(
        self,
        portfolio_id: int,
        asset: Asset,
        quantity: int,
        price: int,
        fx_rate: int,
    ) -> None:
        self.operation(
            portfolio_id,
            operation_type="buy",
            asset_id=asset.id,
            quantity=quantity,
            price=price,
            fx_rate=fx_rate,
            operation_date=_when(3),
        )

    def detail(self, portfolio_id: int) -> dict[str, Any]:
        response = self.client.get(f"/portfolios/{portfolio_id}", headers=self.headers)
        assert response.status_code == 200, response.text
        body: dict[str, Any] = response.json()
        return body

    def summaries(self, name: str) -> list[dict[str, Any]]:
        response = self.client.get(
            "/portfolios/", headers=self.headers, params={"name": name}
        )
        assert response.status_code == 200, response.text
        body: list[dict[str, Any]] = response.json()
        return body

    def positions(self, name: str) -> list[dict[str, Any]]:
        response = self.client.get(
            "/portfolios/positions",
            headers=self.headers,
            params={"portfolio_name": name},
        )
        assert response.status_code == 200, response.text
        body: list[dict[str, Any]] = response.json()
        return body


def test_foreign_positions_are_valued_at_cross_rates(
    integration_client: TestClient,
    integration_session: Session,
    integration_data: IntegrationData,
    auth_headers: dict[str, str],
    fake_provider: FakeMarketDataProvider,
) -> None:
    usd = _currency(integration_session, "USD", "1")
    eur = _currency(integration_session, "EUR", "1.08")
    pln = _currency(integration_session, "PLN", "0.25")
    eur_asset = _asset(integration_session, integration_data, "eur", eur, "100")
    usd_asset = _asset(integration_session, integration_data, "usd", usd, "100")
    pln_asset = _asset(integration_session, integration_data, "pln", pln, "60")
    api = Api(integration_client, auth_headers)
    name = integration_data.value("z1")
    portfolio_id = api.create_portfolio(name, pln)
    api.deposit(portfolio_id, 10000)
    api.buy(portfolio_id, eur_asset, quantity=10, price=90, fx_rate=4)  # 3 600 PLN
    api.buy(portfolio_id, usd_asset, quantity=10, price=80, fx_rate=4)  # 3 200 PLN
    api.buy(portfolio_id, pln_asset, quantity=5, price=50, fx_rate=1)  # 250 PLN

    detail = api.detail(portfolio_id)

    # EUR: 10 * 100 * 1.08 / 0.25 = 4 320; USD: 10 * 100 / 0.25 = 4 000; PLN: 300.
    by_asset = {p["asset_id"]: p for p in detail["positions"]}
    assert by_asset[eur_asset.id]["market_value"] == 4320
    assert by_asset[usd_asset.id]["market_value"] == 4000
    assert by_asset[pln_asset.id]["market_value"] == 300
    assert by_asset[eur_asset.id]["unrealized_pnl"] == 720
    assert by_asset[eur_asset.id]["return_pct"] == 20
    assert by_asset[usd_asset.id]["unrealized_pnl"] == 800
    assert by_asset[usd_asset.id]["return_pct"] == 25
    assert detail["rate_missing"] is False
    assert detail["cash_balance"] == 2950  # 10 000 - 3 600 - 3 200 - 250
    assert detail["positions_value"] == 8620
    assert detail["total_value"] == 11570
    assert detail["total_profit_loss"] == 1570
    assert detail["total_return_pct"] == 15.7
    assert by_asset[eur_asset.id]["portfolio_weight_pct"] == round(
        4320 / 11570 * 100, 4
    )
    [summary] = api.summaries(name)
    assert summary["total_value"] == 11570
    assert summary["rate_missing"] is False

    # The positions endpoint refreshes through the provider first; the refreshed
    # rates and prices are the same, so the valuation does not move.
    fake_provider.rates[("EUR", "USD")] = D("1.08")
    fake_provider.rates[("PLN", "USD")] = D("0.25")
    for asset, price in ((eur_asset, "100"), (usd_asset, "100"), (pln_asset, "60")):
        fake_provider.quotes[asset.ticker] = make_quote(
            asset.ticker, current_price=D(price)
        )
    valued = {p["asset_id"]: p for p in api.positions(name)}
    assert valued[eur_asset.id]["market_value"] == 4320
    assert valued[usd_asset.id]["market_value"] == 4000
    assert valued[pln_asset.id]["market_value"] == 300
    assert valued[eur_asset.id]["rate_missing"] is False


def test_a_usd_portfolio_keeps_valuing_foreign_positions_as_before(
    integration_client: TestClient,
    integration_session: Session,
    integration_data: IntegrationData,
    auth_headers: dict[str, str],
) -> None:
    usd = _currency(integration_session, "USD", "1")
    eur = _currency(integration_session, "EUR", "1.08")
    eur_asset = _asset(integration_session, integration_data, "eur", eur, "100")
    api = Api(integration_client, auth_headers)
    portfolio_id = api.create_portfolio(integration_data.value("usd"), usd)
    api.deposit(portfolio_id, 2000)
    api.buy(portfolio_id, eur_asset, quantity=10, price=90, fx_rate=1)

    detail = api.detail(portfolio_id)

    [position] = detail["positions"]
    assert position["market_value"] == 1080  # 10 * 100 * 1.08, as the old formula
    assert detail["positions_value"] == 1080
    assert detail["rate_missing"] is False


def test_a_currency_without_a_rate_leaves_the_portfolio_unvalued_not_wrong(
    integration_client: TestClient,
    integration_session: Session,
    integration_data: IntegrationData,
    auth_headers: dict[str, str],
) -> None:
    pln = _currency(integration_session, "PLN", "0.25")
    gbp = _currency(integration_session, "GBP", "1")  # the column default: no quote
    pln_asset = _asset(integration_session, integration_data, "pln", pln, "60")
    gbp_asset = _asset(integration_session, integration_data, "gbp", gbp, "2.5")
    api = Api(integration_client, auth_headers)
    name = integration_data.value("missing")
    portfolio_id = api.create_portfolio(name, pln)
    api.deposit(portfolio_id, 1000)
    api.buy(portfolio_id, pln_asset, quantity=5, price=50, fx_rate=1)
    api.buy(portfolio_id, gbp_asset, quantity=10, price=2, fx_rate=5)

    detail = api.detail(portfolio_id)

    assert detail["rate_missing"] is True
    assert detail["positions_value"] is None
    assert detail["total_value"] is None
    assert detail["total_profit_loss"] is None
    assert detail["total_return_pct"] is None
    assert detail["cash_balance"] == 650  # 1 000 - 250 - 100
    by_asset = {p["asset_id"]: p for p in detail["positions"]}
    unpriced = by_asset[gbp_asset.id]
    assert unpriced["rate_missing"] is True
    assert unpriced["market_value"] is None
    assert unpriced["cost_basis"] == 20
    assert unpriced["cost_basis_in_portfolio_currency"] == 100
    assert by_asset[pln_asset.id]["market_value"] == 300
    assert by_asset[pln_asset.id]["portfolio_weight_pct"] is None
    [summary] = api.summaries(name)
    assert summary["rate_missing"] is True
    assert summary["total_value"] is None
