"""Portfolios end to end: real HTTP, real database, faked market data.

The market-data provider is replaced in `assets/wiring.py` (the one place that
picks it), so no test reaches the network.
"""

from datetime import UTC, date, datetime
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


def _when(day: int, hour: int = 12) -> str:
    return datetime(2025, 1, day, hour, tzinfo=UTC).isoformat()


class Api:
    """Thin helper over the client for one user."""

    def __init__(self, client: TestClient, headers: dict[str, str]) -> None:
        self.client = client
        self.headers = headers

    def post(self, path: str, payload: dict[str, Any]) -> Any:
        return self.client.post(path, headers=self.headers, json=payload)

    def get(self, path: str, **params: Any) -> Any:
        return self.client.get(path, headers=self.headers, params=params)

    def post_query(self, path: str, **params: Any) -> Any:
        return self.client.post(path, headers=self.headers, params=params)

    def patch(self, path: str, payload: dict[str, Any]) -> Any:
        return self.client.patch(path, headers=self.headers, json=payload)

    def delete(self, path: str) -> Any:
        return self.client.delete(path, headers=self.headers)

    def operation(self, portfolio_id: int, **payload: Any) -> Any:
        return self.post(
            "/portfolios/operations", {"portfolio_id": portfolio_id, **payload}
        )

    def detail(self, portfolio_id: int) -> dict[str, Any]:
        response = self.get(f"/portfolios/{portfolio_id}")
        assert response.status_code == 200, response.text
        return response.json()


def _other_user_headers(client: TestClient, data: IntegrationData) -> dict[str, str]:
    email = f"{data.value('other')}@example.com"
    password = "StrongPass123"
    registered = client.post(
        "/auth/register", json={"email": email, "password": password}
    )
    assert registered.status_code == 201, registered.text
    login = client.post("/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {login.json()['access']}"}


def test_full_portfolio_flow(
    integration_client: TestClient,
    integration_session: Session,
    integration_data: IntegrationData,
    auth_headers: dict[str, str],
    seeded_currency: Currency,
    fake_provider: FakeMarketDataProvider,
) -> None:
    api = Api(integration_client, auth_headers)
    name = integration_data.value("flow")
    ticker = integration_data.value("t")[:20].upper()
    rejected_ticker = integration_data.value("x")[:20].upper()
    asset_class = integration_data.value("cls")[:20]
    rejected_class = integration_data.value("nocls")[:20]

    created = api.post(
        "/portfolios/", {"name": name, "base_currency_id": seeded_currency.id}
    )
    assert created.status_code == 201, created.text
    portfolio_id = created.json()["id"]
    duplicate = api.post(
        "/portfolios/", {"name": name, "base_currency_id": seeded_currency.id}
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "PORTFOLIO_ALREADY_EXISTS"

    assert (
        api.operation(
            portfolio_id,
            operation_type="deposit",
            amount=1000,
            operation_date=_when(2, 9),
        ).status_code
        == 201
    )

    # Buy of an unknown ticker: the asset is created with the operation.
    buy = api.operation(
        portfolio_id,
        operation_type="buy",
        ticker=ticker.lower(),
        asset_class=asset_class,
        quantity=2,
        price=100,
        fee=1,
        amount=201,
        operation_date=_when(2),
    )
    assert buy.status_code == 201, buy.text
    assert buy.json()["asset"]["ticker"] == ticker
    assert buy.json()["asset"]["asset_class"]["name"] == asset_class
    assert buy.json()["asset"]["currency"]["id"] == seeded_currency.id
    asset_id = buy.json()["asset_id"]

    # Not enough cash: 400 with the ledger's code, and nothing stays behind -
    # neither the cash change nor the asset and class created for it.
    rejected = api.operation(
        portfolio_id,
        operation_type="buy",
        ticker=rejected_ticker,
        asset_class=rejected_class,
        quantity=100,
        price=100,
        operation_date=_when(2),
    )
    assert rejected.status_code == 400
    assert rejected.json()["code"] == "INSUFFICIENT_CASH"
    integration_session.expire_all()
    assert (
        integration_session.scalar(select(Asset).where(Asset.ticker == rejected_ticker))
        is None
    )
    assert (
        integration_session.scalar(
            select(AssetClass).where(AssetClass.name == rejected_class)
        )
        is None
    )
    assert D(str(api.detail(portfolio_id)["cash_balance"])) == D("799")

    sell = api.operation(
        portfolio_id,
        operation_type="sell",
        asset_id=asset_id,
        quantity=1,
        price=150,
        fee=1,
        amount=149,
        operation_date=_when(3),
    )
    assert sell.status_code == 201, sell.text
    dividend = api.operation(
        portfolio_id,
        operation_type="dividend",
        asset_id=asset_id,
        amount=10,
        operation_date=_when(6, 10),
    )
    assert dividend.status_code == 201, dividend.text
    assert (
        api.operation(
            portfolio_id,
            operation_type="withdrawal",
            amount=100,
            operation_date=_when(7),
        ).status_code
        == 201
    )
    no_asset_for_cash = api.operation(
        portfolio_id,
        operation_type="deposit",
        asset_id=asset_id,
        amount=1,
        operation_date=_when(7),
    )
    assert no_asset_for_cash.status_code == 400
    assert no_asset_for_cash.json()["code"] == "OPERATION_FORBIDS_ASSET"

    detail = api.detail(portfolio_id)
    assert D(str(detail["cash_balance"])) == D("858")  # 1000-201+149+10-100
    assert D(str(detail["total_deposited"])) == D("900")
    [position] = detail["positions"]
    assert (position["asset_id"], position["quantity"]) == (asset_id, 1)
    assert position["average_buy_price"] == 100.5
    assert position["total_fees"] == 2
    assert position["total_dividends"] == 10
    assert position["market_value"] == 0  # created at price 0, not refreshed yet
    assert detail["total_fees"] == 2

    [summary] = api.get("/portfolios/", name=name).json()
    assert summary["total_value"] == 858
    assert summary["total_profit_loss"] == -42

    # GET values at the stored prices (no side effects); only POST /refresh
    # pulls prices from the (fake) provider.
    fake_provider.quotes[ticker] = make_quote(ticker, current_price=D("120"))
    stored = api.get("/portfolios/positions", portfolio_name=name)
    assert stored.status_code == 200, stored.text
    assert stored.json()[0]["asset"]["current_price"] == 0
    positions = api.post_query("/portfolios/positions/refresh", portfolio_name=name)
    assert positions.status_code == 200, positions.text
    [valued] = positions.json()
    assert valued["asset"]["current_price"] == 120
    assert valued["market_value"] == 120
    assert valued["unrealized_pnl"] == 19.5
    assert valued["portfolio_weight_pct"] == round(120 / 978 * 100, 4)

    history = api.get("/portfolios/operations", portfolio_name=name).json()
    assert [op["operation_type"] for op in history] == [
        "withdrawal",
        "dividend",
        "sell",
        "buy",
        "deposit",
    ]

    # Editing an operation rebuilds the portfolio from its history.
    position_id = position["id"]
    edited = api.patch(f"/portfolios/operations/{buy.json()['id']}", {"price": 90})
    assert edited.status_code == 200, edited.text
    detail = api.detail(portfolio_id)
    assert D(str(detail["cash_balance"])) == D("878")
    [position] = detail["positions"]
    assert position["average_buy_price"] == 90.5
    assert position["id"] == position_id  # the row survives the rebuild

    # An edit that breaks the history is rejected; nothing changes.
    broken = api.patch(f"/portfolios/operations/{buy.json()['id']}", {"quantity": 1000})
    assert broken.status_code == 400
    assert broken.json()["code"] == "INSUFFICIENT_CASH"
    assert D(str(api.detail(portfolio_id)["cash_balance"])) == D("878")

    # Deleting the dividend takes its cash and total back.
    assert (
        api.delete(f"/portfolios/operations/{dividend.json()['id']}").status_code == 204
    )
    detail = api.detail(portfolio_id)
    assert D(str(detail["cash_balance"])) == D("868")
    assert detail["positions"][0]["total_dividends"] == 0

    # Deleting the deposit would leave the buy without cash: rejected.
    deposit_id = history[-1]["id"]
    refused = api.delete(f"/portfolios/operations/{deposit_id}")
    assert refused.status_code == 400
    assert refused.json()["code"] == "INSUFFICIENT_CASH"

    # Vectors over the same history, with fixed closes.
    fake_provider.history[ticker] = {
        date(2025, 1, 2): D("100"),
        date(2025, 1, 3): D("110"),
        date(2025, 1, 6): D("115"),
    }
    vectors = api.get(
        "/portfolios/portfolio-vectors",
        portfolioName=name,
        startDate="2025-01-01",
        endDate="2025-01-07",
    )
    assert vectors.status_code == 200, vectors.text
    body = vectors.json()
    assert body["date"][0] == "2025-01-01T00:00:00"
    assert len(body["date"]) == 7
    assert body["net_deposits_vector"] == [0, 1000, 1000, 1000, 1000, 1000, 900]
    # quantity 2 then 1 (sell on the 3rd) x closes 100,100,110,110,110,115,120
    assert body["assets"] == {ticker: [0, 200, 110, 110, 110, 115, 120]}
    assert body["pocket_value_vector"] == body["portfolio_value_vector"]

    assert api.delete(f"/portfolios/{portfolio_id}").status_code == 204
    assert api.get(f"/portfolios/{portfolio_id}").status_code == 404


def test_another_users_portfolio_and_operations_are_not_found(
    integration_client: TestClient,
    integration_data: IntegrationData,
    auth_headers: dict[str, str],
    seeded_currency: Currency,
) -> None:
    owner = Api(integration_client, auth_headers)
    created = owner.post(
        "/portfolios/",
        {
            "name": integration_data.value("mine"),
            "base_currency_id": seeded_currency.id,
        },
    )
    portfolio_id = created.json()["id"]
    deposit = owner.operation(
        portfolio_id, operation_type="deposit", amount=10, operation_date=_when(2)
    )
    operation_id = deposit.json()["id"]
    stranger = Api(
        integration_client, _other_user_headers(integration_client, integration_data)
    )

    responses = {
        "get": stranger.get(f"/portfolios/{portfolio_id}"),
        "patch": stranger.patch(f"/portfolios/{portfolio_id}", {"name": "x"}),
        "delete": stranger.delete(f"/portfolios/{portfolio_id}"),
        "operation": stranger.operation(
            portfolio_id, operation_type="deposit", amount=1, operation_date=_when(2)
        ),
    }
    for action, response in responses.items():
        assert response.status_code == 404, action
        assert response.json()["code"] == "PORTFOLIO_NOT_FOUND", action

    for response in (
        stranger.patch(f"/portfolios/operations/{operation_id}", {"notes": "x"}),
        stranger.delete(f"/portfolios/operations/{operation_id}"),
    ):
        assert response.status_code == 404
        assert response.json()["code"] == "OPERATION_NOT_FOUND"
    assert stranger.get("/portfolios/").json() == []
    assert stranger.get("/portfolios/operations").json() == []
    assert (
        stranger.get(
            "/portfolios/positions", portfolio_name=integration_data.value("mine")
        ).status_code
        == 404
    )
    assert D(str(owner.detail(portfolio_id)["cash_balance"])) == D("10")


def test_portfolio_endpoints_require_authentication(
    integration_client: TestClient,
) -> None:
    response = integration_client.get("/portfolios/")

    assert response.status_code == 401


def test_portfolio_vectors_calculate_cash_history_from_real_operations(
    integration_client: TestClient,
    integration_data: IntegrationData,
    auth_headers: dict[str, str],
    seeded_currency: Currency,
) -> None:
    api = Api(integration_client, auth_headers)
    portfolio = api.post(
        "/portfolios/",
        {
            "name": integration_data.value("analytics"),
            "base_currency_id": seeded_currency.id,
        },
    )
    assert portfolio.status_code == 201, portfolio.text
    operation = api.operation(
        portfolio.json()["id"],
        operation_type="deposit",
        amount=250,
        operation_date="2025-01-01T00:00:00Z",
    )
    assert operation.status_code == 201, operation.text

    response = api.get(
        "/portfolios/portfolio-vectors",
        portfolioName=integration_data.value("analytics"),
        startDate="2025-01-01",
        endDate="2025-01-02",
        vectors='["net_deposits_vector","free_cash_vector"]',
    )

    assert response.status_code == 200
    assert response.json() == {
        "date": ["2025-01-01T00:00:00", "2025-01-02T00:00:00"],
        "net_deposits_vector": [250.0, 250.0],
        "free_cash_vector": [250.0, 250.0],
    }
    bad_dates = api.get(
        "/portfolios/portfolio-vectors",
        portfolioName=integration_data.value("analytics"),
        startDate="2025-01-02",
        endDate="2025-01-01",
    )
    assert bad_dates.status_code == 400
    assert bad_dates.json()["code"] == "INVALID_DATE_RANGE"


def test_portfolio_and_operation_updates_ignore_null_and_reject_unknown_currency(
    integration_client: TestClient,
    integration_data: IntegrationData,
    auth_headers: dict[str, str],
    seeded_currency: Currency,
) -> None:
    api = Api(integration_client, auth_headers)
    created = api.post(
        "/portfolios/",
        {
            "name": integration_data.value("nulls"),
            "base_currency_id": seeded_currency.id,
        },
    )
    assert created.status_code == 201, created.text
    portfolio = created.json()

    patched = api.patch(
        f"/portfolios/{portfolio['id']}", {"name": None, "base_currency_id": None}
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["name"] == portfolio["name"]

    unknown = api.patch(
        f"/portfolios/{portfolio['id']}", {"base_currency_id": 999_999_999}
    )
    assert unknown.status_code == 400
    assert unknown.json()["code"] == "CURRENCY_NOT_FOUND"

    deposit = api.operation(
        portfolio["id"],
        operation_type="deposit",
        amount=100,
        fee=0,
        operation_date=datetime.now(UTC).isoformat(),
    )
    assert deposit.status_code == 201, deposit.text

    updated = api.patch(
        f"/portfolios/operations/{deposit.json()['id']}",
        {"operation_date": None, "amount": None},
    )
    assert updated.status_code == 200, updated.text
    assert D(str(updated.json()["amount"])) == D("100")
