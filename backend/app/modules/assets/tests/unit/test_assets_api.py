from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from app.core.errors import register_error_handlers
from app.core.market_data import MarketDataUnavailableError
from app.modules.assets.api import (
    asset_classes_router,
    assets_router,
    currencies_router,
    router,
)
from app.modules.assets.dependencies import (
    get_asset_class_service,
    get_asset_service,
    get_currency_service,
)
from app.modules.assets.exceptions import (
    AssetAlreadyExistsError,
    AssetNotFoundError,
)
from app.modules.assets.schemas.assets import (
    AssetFromProviderRequest,
    AssetSearchResponse,
    AssetUpdateRequest,
    ProviderQuoteResponse,
)
from app.modules.security.dependencies import get_current_user

USER = SimpleNamespace(id=1, email="user@example.com", is_active=True)


def _currency() -> SimpleNamespace:
    return SimpleNamespace(
        id=2, code="USD", exchange_rate=Decimal("1.000000000"), base_currency_id=None
    )


def _asset(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "id": 1,
        "ticker": "AAPL",
        "name": "Apple",
        "asset_class_id": 3,
        "asset_class": SimpleNamespace(id=3, name="Stock"),
        "currency_id": 2,
        "currency": _currency(),
        "current_price": Decimal("123.450000000"),
        "exchange": "NMS",
        "sector": "Technology",
        "updated_at": datetime(2026, 1, 2, tzinfo=UTC),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class Services(SimpleNamespace):
    assets: MagicMock
    asset_classes: MagicMock
    currencies: MagicMock


@pytest.fixture
def services() -> Services:
    return Services(
        assets=MagicMock(), asset_classes=MagicMock(), currencies=MagicMock()
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
    app.dependency_overrides[get_asset_service] = lambda: services.assets
    app.dependency_overrides[get_asset_class_service] = lambda: services.asset_classes
    app.dependency_overrides[get_currency_service] = lambda: services.currencies
    if authenticated:
        app.dependency_overrides[get_current_user] = lambda: USER
    return TestClient(app, raise_server_exceptions=False)


# --- Routing ---


@pytest.mark.parametrize(
    "routers",
    [
        (router,),
        # Worst case: the `{asset_id}` router registered before the static ones.
        (assets_router, asset_classes_router, currencies_router),
    ],
)
def test_static_paths_are_never_captured_by_asset_id(
    services: Services, routers: tuple[APIRouter, ...]
) -> None:
    services.asset_classes.list_asset_classes.return_value = [
        SimpleNamespace(id=1, name="ETF")
    ]
    services.currencies.list_currencies.return_value = [_currency()]
    services.assets.search_local_and_provider.return_value = AssetSearchResponse(
        local=[], yahoo=[]
    )
    client = build_client(services, routers=routers)

    assert client.get("/assets/asset-classes").json() == [{"id": 1, "name": "ETF"}]
    assert client.get("/assets/currencies").status_code == 200
    assert client.get("/assets/search-yahoo", params={"q": "aa"}).status_code == 200
    services.assets.get_by_id.assert_not_called()


def test_non_numeric_asset_id_is_not_routed(services: Services) -> None:
    response = build_client(services).get("/assets/not-a-number")

    assert response.status_code == 404
    services.assets.get_by_id.assert_not_called()


def test_every_endpoint_requires_authentication(services: Services) -> None:
    client = build_client(services, authenticated=False)

    for path in ("/assets/", "/assets/asset-classes", "/assets/currencies"):
        response = client.get(path)
        assert response.status_code == 401
        assert response.json()["code"] == "MISSING_CREDENTIALS"


# --- Contract: numbers, shapes, errors ---


def test_asset_detail_serializes_decimals_as_json_numbers(services: Services) -> None:
    services.assets.get_by_id.return_value = _asset()

    response = build_client(services).get("/assets/1")

    assert response.status_code == 200
    body = response.json()
    assert body["current_price"] == 123.45
    assert isinstance(body["current_price"], float)
    assert body["currency"] == {
        "id": 2,
        "code": "USD",
        "exchange_rate": 1.0,
        "base_currency_id": None,
    }
    assert body["asset_class"] == {"id": 3, "name": "Stock"}
    services.assets.get_by_id.assert_called_once_with(1)


def test_list_assets_passes_search_query(services: Services) -> None:
    services.assets.list_assets.return_value = [_asset()]

    response = build_client(services).get("/assets/", params={"search": "app"})

    assert response.status_code == 200
    assert response.json()[0]["asset_class_id"] == 3
    services.assets.list_assets.assert_called_once_with("app")


def test_not_found_is_returned_with_code(services: Services) -> None:
    services.assets.get_by_id.side_effect = AssetNotFoundError

    response = build_client(services).get("/assets/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Asset not found", "code": "ASSET_NOT_FOUND"}


def test_create_asset_rejects_unknown_fields(services: Services) -> None:
    response = build_client(services).post(
        "/assets/",
        json={
            "ticker": "AAPL",
            "name": "Apple",
            "asset_class_id": 1,
            "currency_id": 1,
            "owner_id": 7,
        },
    )

    assert response.status_code == 422
    services.assets.create.assert_not_called()


def test_create_asset_accepts_json_numbers_as_decimal(services: Services) -> None:
    services.assets.create.return_value = _asset()

    response = build_client(services).post(
        "/assets/",
        json={
            "ticker": "AAPL",
            "name": "Apple",
            "asset_class_id": 3,
            "currency_id": 2,
            "current_price": 123.45,
        },
    )

    assert response.status_code == 201
    (data,) = services.assets.create.call_args.args
    assert data.current_price == Decimal("123.45")


def test_patch_passes_only_given_fields(services: Services) -> None:
    services.assets.update.return_value = _asset(name="Apple Inc.")

    response = build_client(services).patch("/assets/1", json={"name": "Apple Inc."})

    assert response.status_code == 200
    asset_id, data = services.assets.update.call_args.args
    assert asset_id == 1
    assert isinstance(data, AssetUpdateRequest)
    assert data.model_dump(exclude_unset=True) == {"name": "Apple Inc."}


def test_patch_rejects_explicit_null_for_not_null_column(services: Services) -> None:
    response = build_client(services).patch("/assets/1", json={"ticker": None})

    assert response.status_code == 422
    services.assets.update.assert_not_called()


def test_delete_returns_204_without_body(services: Services) -> None:
    response = build_client(services).delete("/assets/1")

    assert response.status_code == 204
    assert response.content == b""
    services.assets.delete.assert_called_once_with(1)


# --- Provider search and import ---


def test_search_yahoo_keeps_the_historical_response_shape(services: Services) -> None:
    services.assets.search_local_and_provider.return_value = AssetSearchResponse(
        local=[_asset()],
        yahoo=[
            ProviderQuoteResponse(
                symbol="MSFT",
                name="Microsoft",
                exchange="NMS",
                type="EQUITY",
                currency="USD",
                sector="Technology",
            )
        ],
    )

    response = build_client(services).get("/assets/search-yahoo", params={"q": "ms"})

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"local", "yahoo"}
    assert body["local"][0]["ticker"] == "AAPL"
    assert body["local"][0]["current_price"] == 123.45
    assert body["yahoo"] == [
        {
            "symbol": "MSFT",
            "name": "Microsoft",
            "exchange": "NMS",
            "type": "EQUITY",
            "currency": "USD",
            "sector": "Technology",
        }
    ]
    services.assets.search_local_and_provider.assert_called_once_with("ms")


def test_search_yahoo_requires_two_characters(services: Services) -> None:
    response = build_client(services).get("/assets/search-yahoo", params={"q": "a"})

    assert response.status_code == 422
    services.assets.search_local_and_provider.assert_not_called()


def test_create_from_yahoo_returns_detail(services: Services) -> None:
    services.assets.create_from_provider.return_value = _asset()

    response = build_client(services).post(
        "/assets/create-from-yahoo", json={"ticker": "aapl"}
    )

    assert response.status_code == 201
    assert response.json()["currency"]["code"] == "USD"
    (data,) = services.assets.create_from_provider.call_args.args
    assert data == AssetFromProviderRequest(ticker="aapl")


def test_create_from_yahoo_duplicate_is_409_with_code(services: Services) -> None:
    services.assets.create_from_provider.side_effect = AssetAlreadyExistsError

    response = build_client(services).post(
        "/assets/create-from-yahoo", json={"ticker": "AAPL"}
    )

    assert response.status_code == 409
    assert response.json()["code"] == "ASSET_ALREADY_EXISTS"


def test_create_from_yahoo_provider_outage_is_502_with_code(
    services: Services,
) -> None:
    services.assets.create_from_provider.side_effect = MarketDataUnavailableError

    response = build_client(services).post(
        "/assets/create-from-yahoo", json={"ticker": "AAPL"}
    )

    assert response.status_code == 502
    assert response.json()["code"] == "MARKET_DATA_UNAVAILABLE"


def test_create_from_yahoo_rejects_unknown_fields(services: Services) -> None:
    response = build_client(services).post(
        "/assets/create-from-yahoo", json={"ticker": "AAPL", "price": 1}
    )

    assert response.status_code == 422
