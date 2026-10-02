"""Routers with mocked services (`dependency_overrides`): routing, auth, the
error contract, `extra="forbid"`, numbers in JSON and the frontend's payloads."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from app.core.errors import register_error_handlers
from app.modules.portfolios.api import (
    metrics_router,
    operations_router,
    portfolios_router,
    positions_router,
    router,
)
from app.modules.portfolios.dependencies import (
    get_metrics_service,
    get_operation_service,
    get_portfolio_service,
    get_position_service,
)
from app.modules.portfolios.exceptions import (
    OperationRejectedError,
    PortfolioAlreadyExistsError,
    PortfolioNotFoundError,
)
from app.modules.portfolios.schemas.metrics import PortfolioVectorsResponse
from app.modules.portfolios.schemas.portfolios import PortfolioSummaryResponse
from app.modules.portfolios.schemas.positions import PositionResponse
from app.modules.security.dependencies import get_current_user

USER = SimpleNamespace(id=7, email="user@example.com", is_active=True)
NOW = datetime(2026, 1, 2, tzinfo=UTC)
D = Decimal


class Services(SimpleNamespace):
    portfolios: MagicMock
    positions: MagicMock
    operations: MagicMock
    metrics: MagicMock


@pytest.fixture
def services() -> Services:
    return Services(
        portfolios=MagicMock(),
        positions=MagicMock(),
        operations=MagicMock(),
        metrics=MagicMock(),
    )


def build_client(
    services: Services,
    *,
    routers: tuple[APIRouter, ...] = (router,),
    authenticated: bool = True,
) -> TestClient:
    app = FastAPI()
    register_error_handlers(app)
    for included in routers:
        app.include_router(included)
    app.dependency_overrides[get_portfolio_service] = lambda: services.portfolios
    app.dependency_overrides[get_position_service] = lambda: services.positions
    app.dependency_overrides[get_operation_service] = lambda: services.operations
    app.dependency_overrides[get_metrics_service] = lambda: services.metrics
    if authenticated:
        app.dependency_overrides[get_current_user] = lambda: USER
    return TestClient(app, raise_server_exceptions=False)


def _currency() -> SimpleNamespace:
    return SimpleNamespace(
        id=1, code="PLN", exchange_rate=D("1.000000000"), base_currency_id=None
    )


def _portfolio() -> SimpleNamespace:
    return SimpleNamespace(
        id=3,
        owner_id=7,
        name="Main",
        base_currency=_currency(),
        cash_balance=D("799.000"),
        total_deposited=D("1000.000"),
        is_active=True,
        created_at=NOW,
    )


def _operation(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "id": 11,
        "portfolio_id": 3,
        "asset_id": None,
        "asset": None,
        "operation_type": "deposit",
        "quantity": D("0E-9"),
        "price": D("0E-9"),
        "amount": D("1000.00"),
        "fee": D("0.00"),
        "fx_rate": D("1.000000000"),
        "notes": None,
        "operation_date": NOW,
        "created_at": NOW,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


# --- Routing and auth ---


@pytest.mark.parametrize(
    "routers",
    [
        (router,),
        # Worst case: the `{portfolio_id}` router registered first.
        (portfolios_router, positions_router, operations_router, metrics_router),
    ],
)
def test_static_paths_are_never_captured_by_portfolio_id(
    services: Services, routers: tuple[APIRouter, ...]
) -> None:
    services.positions.list_valued.return_value = []
    services.operations.list_operations.return_value = []
    services.metrics.portfolio_vectors.return_value = PortfolioVectorsResponse({})
    client = build_client(services, routers=routers)

    assert client.get("/portfolios/positions?portfolio_name=Main").json() == []
    assert client.get("/portfolios/operations").json() == []
    assert client.get("/portfolios/portfolio-vectors").json() == {}
    services.portfolios.get_detail.assert_not_called()


def test_non_numeric_ids_are_not_routed(services: Services) -> None:
    client = build_client(services)

    assert client.get("/portfolios/abc").status_code == 404
    assert client.delete("/portfolios/operations/abc").status_code == 404
    services.portfolios.get_detail.assert_not_called()
    services.operations.delete.assert_not_called()


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/portfolios/"),
        ("POST", "/portfolios/"),
        ("GET", "/portfolios/1"),
        ("PATCH", "/portfolios/1"),
        ("DELETE", "/portfolios/1"),
        ("GET", "/portfolios/positions?portfolio_name=x"),
        ("GET", "/portfolios/operations"),
        ("POST", "/portfolios/operations"),
        ("PUT", "/portfolios/operations/1"),
        ("DELETE", "/portfolios/operations/1"),
        ("GET", "/portfolios/portfolio-vectors"),
    ],
)
def test_every_endpoint_requires_authentication(
    services: Services, method: str, path: str
) -> None:
    response = build_client(services, authenticated=False).request(method, path)

    assert response.status_code == 401
    assert response.json()["code"] == "MISSING_CREDENTIALS"


# --- Portfolios ---


def test_list_returns_valued_summaries_as_numbers(services: Services) -> None:
    services.portfolios.list_summaries.return_value = [
        PortfolioSummaryResponse(
            **dict(vars(_portfolio())),
            positions_value=D("1234.5"),
            total_value=D("2033.5"),
            total_profit_loss=D("1033.5"),
            total_return_pct=D("103.35"),
            total_fees=D("1.5"),
        )
    ]

    response = build_client(services).get("/portfolios/", params={"name": "Main"})

    assert response.status_code == 200
    services.portfolios.list_summaries.assert_called_once_with(7, name="Main")
    [body] = response.json()
    assert body == {
        "id": 3,
        "owner_id": 7,
        "name": "Main",
        "base_currency": {
            "id": 1,
            "code": "PLN",
            "exchange_rate": 1.0,
            "base_currency_id": None,
        },
        "cash_balance": 799.0,
        "total_deposited": 1000.0,
        "is_active": True,
        "created_at": "2026-01-02T00:00:00Z",
        "positions_value": 1234.5,
        "total_value": 2033.5,
        "total_profit_loss": 1033.5,
        "total_return_pct": 103.35,
        "total_fees": 1.5,
        "rate_missing": False,
    }


def test_summary_without_a_rate_has_null_totals_and_the_flag(
    services: Services,
) -> None:
    services.portfolios.list_summaries.return_value = [
        PortfolioSummaryResponse(
            **dict(vars(_portfolio())),
            positions_value=None,
            total_value=None,
            total_profit_loss=None,
            total_return_pct=None,
            total_fees=D("1.5"),
            rate_missing=True,
        )
    ]

    response = build_client(services).get("/portfolios/")

    [body] = response.json()
    assert body["rate_missing"] is True
    assert body["positions_value"] is None
    assert body["total_value"] is None
    assert body["total_profit_loss"] is None
    assert body["total_return_pct"] is None
    assert body["total_fees"] == 1.5
    assert body["cash_balance"] == 799.0


def test_position_without_a_rate_has_null_values_but_keeps_its_cost(
    services: Services,
) -> None:
    services.positions.list_valued.return_value = [
        PositionResponse.model_validate(
            {
                "id": 5,
                "portfolio_id": 3,
                "asset_id": 9,
                "asset": {
                    "id": 9,
                    "ticker": "BARC",
                    "name": "Barclays",
                    "asset_class": {"id": 1, "name": "Stock"},
                    "currency": {
                        "id": 4,
                        "code": "GBP",
                        "exchange_rate": D("1"),
                        "base_currency_id": None,
                    },
                    "current_price": D("2.5"),
                    "exchange": "LSE",
                    "sector": "",
                    "updated_at": NOW,
                },
                "quantity": D("10"),
                "average_buy_price": D("2"),
                "average_fx_rate": D("5"),
                "total_fees": D("0"),
                "total_dividends": D("0"),
                "opened_at": NOW,
                "updated_at": NOW,
                "cost_basis": D("20"),
                "cost_basis_in_portfolio_currency": D("100"),
                "market_value": None,
                "unrealized_pnl": None,
                "return_pct": None,
                "portfolio_weight_pct": None,
                "rate_missing": True,
            }
        )
    ]

    response = build_client(services).get(
        "/portfolios/positions", params={"portfolio_name": "Main"}
    )

    [body] = response.json()
    assert body["rate_missing"] is True
    assert body["market_value"] is None
    assert body["unrealized_pnl"] is None
    assert body["return_pct"] is None
    assert body["portfolio_weight_pct"] is None
    assert body["cost_basis"] == 20.0
    assert body["cost_basis_in_portfolio_currency"] == 100.0


def test_create_returns_201_with_the_entity(services: Services) -> None:
    services.portfolios.create.return_value = _portfolio()

    response = build_client(services).post(
        "/portfolios/", json={"name": "Main", "base_currency_id": 1}
    )

    assert response.status_code == 201
    assert response.json()["cash_balance"] == 799.0
    data = services.portfolios.create.call_args.args[0]
    assert (data.name, data.base_currency_id) == ("Main", 1)
    assert services.portfolios.create.call_args.kwargs == {"owner_id": 7}


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "Main", "base_currency_id": 1, "owner_id": 8},
        {"name": "", "base_currency_id": 1},
        {"name": "x" * 101, "base_currency_id": 1},
        {"name": "Main"},
    ],
)
def test_create_rejects_bad_shapes_with_422(
    services: Services, payload: dict[str, object]
) -> None:
    response = build_client(services).post("/portfolios/", json=payload)

    assert response.status_code == 422
    services.portfolios.create.assert_not_called()


def test_service_errors_keep_the_contract_with_code(services: Services) -> None:
    services.portfolios.create.side_effect = PortfolioAlreadyExistsError
    services.portfolios.get_detail.side_effect = PortfolioNotFoundError
    client = build_client(services)

    conflict = client.post("/portfolios/", json={"name": "Main", "base_currency_id": 1})
    missing = client.get("/portfolios/5")

    assert conflict.status_code == 409
    assert conflict.json() == {
        "detail": "Portfolio with this name already exists",
        "code": "PORTFOLIO_ALREADY_EXISTS",
    }
    assert missing.status_code == 404
    assert missing.json()["code"] == "PORTFOLIO_NOT_FOUND"
    services.portfolios.get_detail.assert_called_once_with(5, owner_id=7)


def test_put_and_patch_update_the_same_way(services: Services) -> None:
    services.portfolios.update.return_value = _portfolio()
    client = build_client(services)

    for method in ("PUT", "PATCH"):
        response = client.request(method, "/portfolios/3", json={"name": None})
        assert response.status_code == 200

    assert services.portfolios.update.call_count == 2
    assert client.patch("/portfolios/3", json={"is_active": False}).status_code == 422


def test_delete_returns_204(services: Services) -> None:
    response = build_client(services).delete("/portfolios/3")

    assert response.status_code == 204
    services.portfolios.delete.assert_called_once_with(3, owner_id=7)


# --- Positions ---


def test_positions_require_a_portfolio_name(services: Services) -> None:
    client = build_client(services)

    assert client.get("/portfolios/positions").status_code == 422
    client.get("/portfolios/positions", params={"portfolio_name": "Main"})
    services.positions.list_valued.assert_called_once_with(7, "Main")
    services.positions.refresh_valued.assert_not_called()


def test_refreshing_positions_is_a_post(services: Services) -> None:
    client = build_client(services)
    services.positions.refresh_valued.return_value = []

    response = client.post(
        "/portfolios/positions/refresh", params={"portfolio_name": "Main"}
    )

    assert response.status_code == 200
    services.positions.refresh_valued.assert_called_once_with(7, "Main")


# --- Operations ---


def test_operations_list_filters_by_portfolio_name(services: Services) -> None:
    services.operations.list_operations.return_value = [_operation()]

    response = build_client(services).get(
        "/portfolios/operations", params={"portfolio_name": "Main"}
    )

    assert response.status_code == 200
    services.operations.list_operations.assert_called_once_with(7, "Main")
    assert response.json() == [
        {
            "id": 11,
            "portfolio_id": 3,
            "asset_id": None,
            "asset": None,
            "operation_type": "deposit",
            "quantity": 0.0,
            "price": 0.0,
            "amount": 1000.0,
            "fee": 0.0,
            "fx_rate": 1.0,
            "notes": None,
            "operation_date": "2026-01-02T00:00:00Z",
            "created_at": "2026-01-02T00:00:00Z",
        }
    ]


@pytest.mark.parametrize(
    "payload",
    [
        # BuyAssetDialog
        {
            "portfolio_id": 3,
            "asset_id": 5,
            "operation_type": "buy",
            "quantity": 2,
            "price": 100.5,
            "amount": 202,
            "fee": 1,
            "fx_rate": 1,
            "operation_date": "2026-01-02",
            "notes": "",
        },
        # CashOperationDialog
        {
            "portfolio_id": 3,
            "operation_type": "withdrawal",
            "amount": 50,
            "fee": 0,
            "operation_date": "2026-01-02",
            "notes": "",
        },
        # A buy of a ticker to create
        {
            "portfolio_id": 3,
            "operation_type": "buy",
            "ticker": "CDR.WA",
            "asset_class": "Stock",
            "quantity": 1,
            "price": 1,
            "amount": 1,
            "operation_date": "2026-01-02T10:00:00Z",
        },
    ],
)
def test_frontend_operation_payloads_validate(
    services: Services, payload: dict[str, object]
) -> None:
    services.operations.record.return_value = _operation()

    response = build_client(services).post("/portfolios/operations", json=payload)

    assert response.status_code == 201, response.text
    data = services.operations.record.call_args.args[0]
    assert data.operation_type == payload["operation_type"]
    assert services.operations.record.call_args.kwargs == {"owner_id": 7}


def test_operation_amounts_arrive_as_decimals(services: Services) -> None:
    services.operations.record.return_value = _operation()

    build_client(services).post(
        "/portfolios/operations",
        json={
            "portfolio_id": 3,
            "operation_type": "deposit",
            "amount": 0.1,
            "fee": 0.2,
            "operation_date": "2026-01-02",
        },
    )

    data = services.operations.record.call_args.args[0]
    assert (data.amount, data.fee) == (D("0.1"), D("0.2"))


@pytest.mark.parametrize(
    "change",
    [
        {"operation_type": "transfer"},
        {"unexpected": 1},
        {"quantity": "abc"},
        {"price": 1e9},  # beyond Numeric(18, 9)
        {"ticker": "   "},
        {"asset_class": "x" * 21},
        {"operation_date": None},
    ],
)
def test_operation_shape_errors_are_422(
    services: Services, change: dict[str, object]
) -> None:
    payload = {
        "portfolio_id": 3,
        "operation_type": "deposit",
        "amount": 1,
        "operation_date": "2026-01-02",
    }
    payload.update(change)

    response = build_client(services).post("/portfolios/operations", json=payload)

    assert response.status_code == 422
    services.operations.record.assert_not_called()


def test_negative_numbers_reach_the_ledger_not_the_schema(services: Services) -> None:
    """Sign rules live in the domain: the schema lets them through, the service
    answers 400 with the ledger's code."""
    services.operations.record.side_effect = OperationRejectedError(
        "quantity must be > 0", "INVALID_OPERATION"
    )

    response = build_client(services).post(
        "/portfolios/operations",
        json={
            "portfolio_id": 3,
            "asset_id": 5,
            "operation_type": "buy",
            "quantity": -1,
            "price": 1,
            "amount": 0,
            "operation_date": "2026-01-02",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "quantity must be > 0",
        "code": "INVALID_OPERATION",
    }


def test_update_and_delete_operation(services: Services) -> None:
    services.operations.update.return_value = _operation(notes="edited")
    client = build_client(services)

    updated = client.patch("/portfolios/operations/11", json={"notes": "edited"})
    replaced = client.put("/portfolios/operations/11", json={"amount": 5})
    deleted = client.delete("/portfolios/operations/11")

    assert updated.status_code == 200
    assert updated.json()["notes"] == "edited"
    assert replaced.status_code == 200
    assert deleted.status_code == 204
    services.operations.delete.assert_called_once_with(11, owner_id=7)
    assert (
        client.patch("/portfolios/operations/11", json={"asset_id": 2}).status_code
        == 422
    )


# --- Vectors ---


def test_vectors_pass_the_frontends_camel_case_parameters(services: Services) -> None:
    services.metrics.portfolio_vectors.return_value = PortfolioVectorsResponse(
        {
            "date": [datetime(2025, 1, 1), datetime(2025, 1, 2)],
            "pocket_value_vector": [10.0, 11.5],
            "assets": {"AAA": [1.0, 2.0]},
        }
    )

    response = build_client(services).get(
        "/portfolios/portfolio-vectors",
        params={
            "portfolioName": "Main",
            "startDate": "2025-01-01",
            "endDate": "2025-01-02",
            "interval": "1d",
            "vectors": '["pocket_value_vector","assets"]',
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "date": ["2025-01-01T00:00:00", "2025-01-02T00:00:00"],
        "pocket_value_vector": [10.0, 11.5],
        "assets": {"AAA": [1.0, 2.0]},
    }
    owner_id, query = services.metrics.portfolio_vectors.call_args.args
    assert owner_id == 7
    assert (query.portfolio_name, query.start_date, query.end_date) == (
        "Main",
        "2025-01-01",
        "2025-01-02",
    )
    assert query.vectors == '["pocket_value_vector","assets"]'
