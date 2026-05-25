from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.assets.dependencies import get_market_data_service
from app.modules.core_data.dependencies import get_current_user
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
