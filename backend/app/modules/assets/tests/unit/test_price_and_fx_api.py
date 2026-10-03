"""HTTP contract of the price-history, exchange-rate, archive and refresh
endpoints, with the services mocked."""

from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import register_error_handlers
from app.modules.assets import entrypoints
from app.modules.assets.api import router
from app.modules.assets.dependencies import (
    get_asset_service,
    get_fx_rate_service,
    get_market_data_service,
    get_price_service,
)
from app.modules.assets.exceptions import (
    AssetArchivedError,
    AssetNotFoundError,
    InvalidDateRangeError,
    PriceNotFoundError,
    RateMissingError,
)
from app.modules.assets.schemas.assets import AssetResponse
from app.modules.assets.services.fx_rates import FxQuote
from app.modules.assets.services.market_data import AssetDataStatus, DataStatus
from app.modules.assets.services.prices import PriceSeries, PriceSeriesItem
from app.modules.security.dependencies import get_current_admin, get_current_user

USER = SimpleNamespace(id=1, email="user@example.com", is_active=True)


class Services(SimpleNamespace):
    assets: MagicMock
    prices: MagicMock
    fx: MagicMock
    market_data: MagicMock


@pytest.fixture
def services() -> Services:
    return Services(
        assets=MagicMock(),
        prices=MagicMock(),
        fx=MagicMock(),
        market_data=MagicMock(),
    )


@pytest.fixture
def client(services: Services) -> TestClient:
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_asset_service] = lambda: services.assets
    app.dependency_overrides[get_price_service] = lambda: services.prices
    app.dependency_overrides[get_fx_rate_service] = lambda: services.fx
    app.dependency_overrides[get_market_data_service] = lambda: services.market_data
    app.dependency_overrides[get_current_user] = lambda: USER
    app.dependency_overrides[get_current_admin] = lambda: USER
    return TestClient(app, raise_server_exceptions=False)


def _asset_response() -> AssetResponse:
    return AssetResponse(
        id=1,
        ticker="AAPL",
        name="Apple",
        asset_class_id=3,
        currency_id=2,
        current_price=Decimal("10"),
        exchange="NMS",
        sector="",
    )


# --- price series ---


def test_price_series_maps_the_aliased_query_parameters(
    client: TestClient, services: Services
) -> None:
    services.prices.series.return_value = PriceSeries(
        asset_id=1,
        currency_id=2,
        items=[
            PriceSeriesItem(
                day=date(2026, 9, 2),
                price_date=date(2026, 9, 1),
                close=Decimal("10.5"),
                source="manual",
                is_synthetic=False,
                stale=False,
            )
        ],
    )

    response = client.get(
        "/assets/1/prices",
        params={
            "from": "2026-09-01",
            "to": "2026-09-03",
            "source": "manual",
            "fill": "forward",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "asset_id": 1,
        "currency_id": 2,
        "items": [
            {
                "day": "2026-09-02",
                "price_date": "2026-09-01",
                "close": 10.5,
                "source": "manual",
                "is_synthetic": False,
                "stale": False,
            }
        ],
    }
    services.prices.series.assert_called_once_with(
        1,
        from_date=date(2026, 9, 1),
        to_date=date(2026, 9, 3),
        source="manual",
        fill="forward",
    )


def test_price_series_defaults_to_no_fill(
    client: TestClient, services: Services
) -> None:
    services.prices.series.return_value = PriceSeries(1, 2, [])

    assert client.get("/assets/1/prices").status_code == 200

    services.prices.series.assert_called_once_with(
        1, from_date=None, to_date=None, source=None, fill="none"
    )


def test_price_series_rejects_an_unknown_fill_mode(
    client: TestClient, services: Services
) -> None:
    response = client.get("/assets/1/prices", params={"fill": "backward"})

    assert response.status_code == 422
    services.prices.series.assert_not_called()


def test_price_series_range_error_carries_its_code(
    client: TestClient, services: Services
) -> None:
    services.prices.series.side_effect = InvalidDateRangeError

    response = client.get("/assets/1/prices")

    assert (response.status_code, response.json()["code"]) == (
        400,
        "INVALID_DATE_RANGE",
    )


def test_price_series_of_an_unknown_asset_is_404(
    client: TestClient, services: Services
) -> None:
    services.prices.series.side_effect = AssetNotFoundError

    assert client.get("/assets/9/prices").status_code == 404


# --- manual prices ---


def test_put_manual_price_passes_the_day_and_a_json_number(
    client: TestClient, services: Services
) -> None:
    services.prices.set_manual_price.return_value = SimpleNamespace(
        asset_id=1,
        price_date=date(2026, 10, 1),
        close=Decimal("42.5"),
        currency_id=2,
        source="manual",
        is_synthetic=False,
    )

    response = client.put("/assets/1/prices/2026-10-01", json={"close": 42.5})

    assert response.status_code == 200
    assert response.json()["close"] == 42.5
    assert response.json()["source"] == "manual"
    services.prices.set_manual_price.assert_called_once_with(
        1, date(2026, 10, 1), Decimal("42.5"), None
    )


@pytest.mark.parametrize(
    "body",
    [{"close": 0}, {"close": -1}, {"close": 1e10}, {}, {"close": 1, "owner": 1}],
)
def test_put_manual_price_validates_the_body(
    client: TestClient, services: Services, body: dict[str, object]
) -> None:
    response = client.put("/assets/1/prices/2026-10-01", json=body)

    assert response.status_code == 422
    services.prices.set_manual_price.assert_not_called()


def test_put_manual_price_rejects_a_malformed_day(client: TestClient) -> None:
    assert (
        client.put("/assets/1/prices/yesterday", json={"close": 1}).status_code == 422
    )


def test_put_manual_price_on_an_archived_asset_is_409(
    client: TestClient, services: Services
) -> None:
    services.prices.set_manual_price.side_effect = AssetArchivedError

    response = client.put("/assets/1/prices/2026-10-01", json={"close": 1})

    assert (response.status_code, response.json()["code"]) == (409, "ASSET_ARCHIVED")


def test_delete_manual_price_is_204_without_a_body(
    client: TestClient, services: Services
) -> None:
    response = client.delete("/assets/1/prices/2026-10-01")

    assert (response.status_code, response.content) == (204, b"")
    services.prices.delete_manual_price.assert_called_once_with(1, date(2026, 10, 1))


def test_delete_manual_price_without_one_is_404_with_code(
    client: TestClient, services: Services
) -> None:
    services.prices.delete_manual_price.side_effect = PriceNotFoundError

    response = client.delete("/assets/1/prices/2026-10-01")

    assert (response.status_code, response.json()["code"]) == (404, "PRICE_NOT_FOUND")


# --- exchange rates ---


def test_rate_lookup_returns_the_quote_and_maps_date(
    client: TestClient, services: Services
) -> None:
    services.fx.get_rate.return_value = FxQuote(
        from_currency="PLN",
        to_currency="USD",
        rate=Decimal("0.26"),
        rate_date=date(2026, 10, 1),
        source="nbp",
        is_synthetic=False,
        stale=False,
        via="direct",
    )

    response = client.get(
        "/assets/currencies/rate",
        params={"from_currency": "pln", "to_currency": "usd", "date": "2026-10-01"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "from_currency": "PLN",
        "to_currency": "USD",
        "rate": 0.26,
        "rate_date": "2026-10-01",
        "source": "nbp",
        "is_synthetic": False,
        "stale": False,
        "via": "direct",
    }
    services.fx.get_rate.assert_called_once_with("pln", "usd", date(2026, 10, 1))


def test_rate_lookup_without_a_date_asks_for_today(
    client: TestClient, services: Services
) -> None:
    services.fx.get_rate.side_effect = RateMissingError

    response = client.get(
        "/assets/currencies/rate", params={"from_currency": "PLN", "to_currency": "EUR"}
    )

    assert (response.status_code, response.json()["code"]) == (404, "RATE_MISSING")
    services.fx.get_rate.assert_called_once_with("PLN", "EUR", None)


@pytest.mark.parametrize(
    "params",
    [
        {"from_currency": "PLN"},
        {"from_currency": "PL", "to_currency": "USD"},
        {"from_currency": "PLN", "to_currency": "USD1"},
    ],
)
def test_rate_lookup_validates_the_codes(
    client: TestClient, services: Services, params: dict[str, str]
) -> None:
    assert client.get("/assets/currencies/rate", params=params).status_code == 422
    services.fx.get_rate.assert_not_called()


def test_rate_route_is_not_captured_by_the_currency_id_route(
    client: TestClient, services: Services
) -> None:
    services.fx.get_rate.side_effect = RateMissingError

    client.get(
        "/assets/currencies/rate", params={"from_currency": "PLN", "to_currency": "EUR"}
    )

    services.fx.get_rate.assert_called_once()


def test_fx_history_lists_items(client: TestClient, services: Services) -> None:
    services.fx.history.return_value = [
        SimpleNamespace(
            rate_date=date(2026, 10, 1),
            rate=Decimal("0.26"),
            source="nbp",
            is_synthetic=False,
        )
    ]

    response = client.get(
        "/assets/fx-rates",
        params={
            "from_currency": "PLN",
            "to_currency": "USD",
            "from": "2026-09-01",
            "to": "2026-10-01",
            "source": "nbp",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "rate_date": "2026-10-01",
                "rate": 0.26,
                "source": "nbp",
                "is_synthetic": False,
            }
        ]
    }
    services.fx.history.assert_called_once_with(
        "PLN",
        "USD",
        from_date=date(2026, 9, 1),
        to_date=date(2026, 10, 1),
        source="nbp",
    )


def test_put_manual_fx_rate_returns_the_row(
    client: TestClient, services: Services
) -> None:
    services.fx.set_manual_rate.return_value = SimpleNamespace(
        from_currency_id=2,
        to_currency_id=1,
        rate_date=date(2026, 10, 1),
        rate=Decimal("0.26"),
        source="manual",
        is_synthetic=False,
    )

    response = client.put(
        "/assets/fx-rates",
        json={
            "from_currency_id": 2,
            "to_currency_id": 1,
            "rate_date": "2026-10-01",
            "rate": 0.26,
        },
    )

    assert response.status_code == 200
    assert response.json()["source"] == "manual"
    services.fx.set_manual_rate.assert_called_once_with(
        2, 1, date(2026, 10, 1), Decimal("0.26")
    )


@pytest.mark.parametrize(
    "body",
    [
        {
            "from_currency_id": 2,
            "to_currency_id": 2,
            "rate_date": "2026-10-01",
            "rate": 1,
        },
        {
            "from_currency_id": 2,
            "to_currency_id": 1,
            "rate_date": "2026-10-01",
            "rate": 0,
        },
        {"from_currency_id": 2, "to_currency_id": 1, "rate": 1},
        {
            "from_currency_id": 2,
            "to_currency_id": 1,
            "rate_date": "2026-10-01",
            "rate": 1,
            "source": "x",
        },
    ],
)
def test_put_manual_fx_rate_validates_the_body(
    client: TestClient, services: Services, body: dict[str, object]
) -> None:
    assert client.put("/assets/fx-rates", json=body).status_code == 422
    services.fx.set_manual_rate.assert_not_called()


# --- archive ---


def test_archive_and_unarchive_return_the_asset(
    client: TestClient, services: Services
) -> None:
    services.assets.to_response.side_effect = lambda asset: _asset_response()
    services.assets.archive.return_value = SimpleNamespace(id=1)
    services.assets.unarchive.return_value = SimpleNamespace(id=1)

    assert client.post("/assets/1/archive").status_code == 200
    assert client.post("/assets/1/unarchive").status_code == 200

    services.assets.archive.assert_called_once_with(1)
    services.assets.unarchive.assert_called_once_with(1)


# --- list filters ---


def test_list_passes_the_filters(client: TestClient, services: Services) -> None:
    services.assets.list_responses.return_value = []

    response = client.get(
        "/assets/",
        params={
            "search": "pl",
            "asset_type": "etf",
            "asset_class_id": 4,
            "country": "pl",
            "include_archived": "true",
        },
    )

    assert response.status_code == 200
    services.assets.list_responses.assert_called_once_with(
        "pl",
        asset_type="etf",
        asset_class_id=4,
        country="PL",
        include_archived=True,
    )


@pytest.mark.parametrize(
    "params",
    [{"asset_type": "stonk"}, {"country": "POL"}, {"asset_class_id": 0}],
)
def test_list_rejects_bad_filters(
    client: TestClient, services: Services, params: dict[str, object]
) -> None:
    assert client.get("/assets/", params=params).status_code == 422
    services.assets.list_responses.assert_not_called()


# --- data status ---


def test_data_status_maps_the_service_result(
    client: TestClient, services: Services
) -> None:
    fetched = datetime(2026, 10, 2, 8, 0, tzinfo=UTC)
    services.market_data.data_status.return_value = DataStatus(
        fx_last_success_at=fetched,
        assets=[
            AssetDataStatus(
                asset_id=1,
                ticker="AAPL",
                price_date=date(2026, 10, 1),
                source="yahoo",
                stale=False,
                last_success_at=fetched,
            ),
            AssetDataStatus(
                asset_id=2,
                ticker="NONE",
                price_date=None,
                source=None,
                stale=True,
                last_success_at=None,
            ),
        ],
    )

    response = client.get("/assets/data-status", params={"only_problems": "false"})

    assert response.status_code == 200
    body = response.json()
    assert body["fx"] == {"last_success_at": "2026-10-02T08:00:00Z"}
    assert [a["ticker"] for a in body["assets"]] == ["AAPL", "NONE"]
    assert body["assets"][1] == {
        "asset_id": 2,
        "ticker": "NONE",
        "price_date": None,
        "stale": True,
        "source": None,
        "last_success_at": None,
    }
    services.market_data.data_status.assert_called_once_with(only_problems=False)


# --- manual refresh ---


def test_refresh_answers_202_and_runs_the_entrypoint_in_the_background(
    client: TestClient, services: Services, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[int]] = []
    monkeypatch.setattr(entrypoints, "refresh_prices", lambda ids: calls.append(ids))
    services.assets.accept_for_refresh.return_value = [1, 3]

    response = client.post("/assets/refresh-prices", json={"asset_ids": [1, 3, 1]})

    assert response.status_code == 202
    assert response.json() == {"accepted": [1, 3]}
    services.assets.accept_for_refresh.assert_called_once_with([1, 3, 1])
    assert calls == [[1, 3]]


def test_refresh_of_an_unknown_asset_is_404_and_queues_nothing(
    client: TestClient, services: Services, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[int]] = []
    monkeypatch.setattr(entrypoints, "refresh_prices", lambda ids: calls.append(ids))
    services.assets.accept_for_refresh.side_effect = AssetNotFoundError

    response = client.post("/assets/refresh-prices", json={"asset_ids": [9]})

    assert response.status_code == 404
    assert calls == []


@pytest.mark.parametrize(
    "body",
    [
        {"asset_ids": []},
        {"asset_ids": list(range(1, 52))},
        {},
        {"asset_ids": [1], "x": 1},
    ],
)
def test_refresh_validates_the_body(
    client: TestClient, services: Services, body: dict[str, object]
) -> None:
    assert client.post("/assets/refresh-prices", json=body).status_code == 422
    services.assets.accept_for_refresh.assert_not_called()


@pytest.mark.parametrize(
    "body",
    [{"close": "0.0000000001"}, {"close": "1.0000000001"}],
)
def test_manual_price_needs_a_value_the_column_can_hold(
    client: TestClient, services: Services, body: dict[str, object]
) -> None:
    response = client.put("/assets/1/prices/2026-10-01", json=body)

    assert response.status_code == 422
    services.prices.set_manual_price.assert_not_called()


def test_manual_rate_needs_a_value_the_column_can_hold(
    client: TestClient, services: Services
) -> None:
    response = client.put(
        "/assets/fx-rates",
        json={
            "from_currency_id": 2,
            "to_currency_id": 1,
            "rate_date": "2026-10-01",
            "rate": "0.0000000001",
        },
    )

    assert response.status_code == 422
