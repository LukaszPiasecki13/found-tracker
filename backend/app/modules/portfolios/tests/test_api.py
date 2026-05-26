from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.assets.dependencies import get_market_data_service
from app.modules.core_data.dependencies import get_current_user
from app.modules.portfolios import api as portfolios_api
from app.modules.portfolios.analytics.portfolio_metrics import PortfolioMetrics
from app.modules.portfolios.api import router
from app.modules.portfolios.dependencies import get_portfolio_repo, get_position_repo


def build_client(
    portfolio_repo: MagicMock,
    position_repo: MagicMock,
    market_data_service: MagicMock,
    current_user: object | None = None,
) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_portfolio_repo] = lambda: portfolio_repo
    app.dependency_overrides[get_position_repo] = lambda: position_repo
    app.dependency_overrides[get_market_data_service] = lambda: market_data_service
    if current_user is not None:
        app.dependency_overrides[get_current_user] = lambda: current_user
    return TestClient(app)


def test_positions_route_matches_static_path_before_portfolio_id() -> None:
    portfolio = SimpleNamespace(
        id=1,
        owner_id=7,
        name="US Stocks",
        cash_balance=0,
        total_deposited=0,
        positions=[],
        base_currency=None,
        base_currency_id=None,
    )
    portfolio_repo = MagicMock()
    portfolio_repo.get_by_owner_and_name.return_value = portfolio
    position_repo = MagicMock()
    position_repo.list_by_portfolio.return_value = []
    market_data_service = MagicMock()
    current_user = SimpleNamespace(id=7)

    client = build_client(
        portfolio_repo=portfolio_repo,
        position_repo=position_repo,
        market_data_service=market_data_service,
        current_user=current_user,
    )

    response = client.get(
        "/portfolios/positions", params={"portfolio_name": "US Stocks"}
    )

    assert response.status_code == 200
    assert response.json() == []


def test_portfolio_vectors_returns_pocket_value_vector_even_when_profit_fails() -> None:
    class FakeMetrics:
        def __init__(self, operations, interval, start_time, end_time):
            self.time_diff = 3

        def get_date_vector(self):
            return np.array([1, 2, 3])

        def get_assets_vectors(self):
            return {}

        def get_asset_classes_vectors(self):
            return {}

        def get_net_deposits_vector(self):
            return np.array([0.0, 0.0, 0.0])

        def get_transaction_cost_vector(self):
            return np.array([0.0, 0.0, 0.0])

        def get_profit_vector(self):
            raise RuntimeError("boom")

        def get_free_cash_vector(self):
            return np.array([0.0, 0.0, 0.0])

        def get_portfolio_value_vector(self):
            return np.array([10.0, 11.0, 12.0])

    portfolio = SimpleNamespace(id=1, owner_id=7, name="Crypto Portfolio")
    op_repo = MagicMock()
    op_repo.list_by_owner.return_value = [SimpleNamespace(operation_type="buy")]
    current_user = SimpleNamespace(id=7)

    original_metrics = portfolios_api.PortfolioMetrics
    portfolios_api.PortfolioMetrics = FakeMetrics
    try:
        client = build_client(
            portfolio_repo=MagicMock(),
            position_repo=MagicMock(),
            market_data_service=MagicMock(),
            current_user=current_user,
        )
        client.app.dependency_overrides[get_portfolio_repo] = lambda: MagicMock()
        client.app.dependency_overrides[get_position_repo] = lambda: MagicMock()
        client.app.dependency_overrides[get_market_data_service] = lambda: MagicMock()
        client.app.dependency_overrides[portfolios_api.get_operation_repo] = lambda: (
            op_repo
        )
        client.app.dependency_overrides[portfolios_api.get_current_user] = lambda: (
            current_user
        )

        response = client.get(
            "/portfolios/portfolio-vectors",
            params={
                "portfolioName": "Crypto Portfolio",
                "startDate": "2025-05-25",
                "endDate": "2026-05-25",
                "interval": "1d",
                "vectors": '["pocket_value_vector","profit_vector"]',
            },
        )
    finally:
        portfolios_api.PortfolioMetrics = original_metrics

    assert response.status_code == 200
    body = response.json()
    assert body["pocket_value_vector"] == [10.0, 11.0, 12.0]
    assert body["profit_vector"] == [0.0, 0.0, 0.0]


def test_portfolio_metrics_handles_timezone_aware_operations() -> None:
    operation = SimpleNamespace(
        operation_type="buy",
        operation_date=datetime(2025, 5, 25, 12, 0, tzinfo=UTC),
        quantity=2,
        price=10,
        fee=0,
        asset=SimpleNamespace(
            ticker="CDR",
            asset_class=SimpleNamespace(name="Stock"),
        ),
    )

    metrics = PortfolioMetrics(
        operations=[operation],
        interval="1d",
        start_time=datetime(2025, 5, 25, 0, 0),
        end_time=datetime(2025, 5, 26, 0, 0),
    )
    metrics._asset_historical_values = lambda ticker: np.array([10.0, 10.5])

    profit = metrics.get_profit_vector()

    assert profit.tolist() == [0.0, 1.0]
