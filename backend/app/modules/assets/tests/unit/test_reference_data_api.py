"""Asset classes and currencies over HTTP (services mocked)."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import register_error_handlers
from app.modules.assets.api import router
from app.modules.assets.dependencies import (
    get_asset_class_service,
    get_currency_service,
)
from app.modules.assets.exceptions import (
    AssetClassAlreadyExistsError,
    AssetClassInUseError,
    CurrencyInUseError,
    CurrencyNotFoundError,
)
from app.modules.security.dependencies import get_current_user


@pytest.fixture
def asset_classes() -> MagicMock:
    return MagicMock()


@pytest.fixture
def currencies() -> MagicMock:
    return MagicMock()


@pytest.fixture
def client(asset_classes: MagicMock, currencies: MagicMock) -> TestClient:
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_asset_class_service] = lambda: asset_classes
    app.dependency_overrides[get_currency_service] = lambda: currencies
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
    return TestClient(app, raise_server_exceptions=False)


def _currency(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "id": 1,
        "code": "EUR",
        "exchange_rate": Decimal("4.250000000"),
        "base_currency_id": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


# --- Asset classes ---


def test_create_asset_class(client: TestClient, asset_classes: MagicMock) -> None:
    asset_classes.create.return_value = SimpleNamespace(id=5, name="Bond")

    response = client.post("/assets/asset-classes", json={"name": "Bond"})

    assert response.status_code == 201
    assert response.json() == {"id": 5, "name": "Bond"}


@pytest.mark.parametrize("method", ["put", "patch"])
def test_update_asset_class_by_put_or_patch(
    client: TestClient, asset_classes: MagicMock, method: str
) -> None:
    asset_classes.update.return_value = SimpleNamespace(id=5, name="Bonds")

    response = client.request(method, "/assets/asset-classes/5", json={"name": "Bonds"})

    assert response.status_code == 200
    asset_id, data = asset_classes.update.call_args.args
    assert (asset_id, data.name) == (5, "Bonds")


def test_duplicate_asset_class_is_409_with_code(
    client: TestClient, asset_classes: MagicMock
) -> None:
    asset_classes.create.side_effect = AssetClassAlreadyExistsError

    response = client.post("/assets/asset-classes", json={"name": "ETF"})

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Asset class with this name already exists",
        "code": "ASSET_CLASS_ALREADY_EXISTS",
    }


def test_delete_asset_class_in_use_is_409(
    client: TestClient, asset_classes: MagicMock
) -> None:
    asset_classes.delete.side_effect = AssetClassInUseError

    response = client.delete("/assets/asset-classes/5")

    assert response.status_code == 409
    assert response.json()["code"] == "ASSET_CLASS_IN_USE"


def test_asset_class_request_rejects_unknown_fields(client: TestClient) -> None:
    response = client.post("/assets/asset-classes", json={"name": "ETF", "id": 1})

    assert response.status_code == 422


# --- Currencies (mounted under /assets/currencies) ---


def test_list_currencies_returns_rates_as_numbers(
    client: TestClient, currencies: MagicMock
) -> None:
    currencies.list_currencies.return_value = [_currency()]

    response = client.get("/assets/currencies")

    assert response.status_code == 200
    assert response.json() == [
        {"id": 1, "code": "EUR", "exchange_rate": 4.25, "base_currency_id": None}
    ]


def test_create_currency_passes_raw_code_to_the_service(
    client: TestClient, currencies: MagicMock
) -> None:
    currencies.create.return_value = _currency()

    response = client.post(
        "/assets/currencies", json={"code": "eur", "exchange_rate": 4.25}
    )

    assert response.status_code == 201
    (data,) = currencies.create.call_args.args
    assert (data.code, data.exchange_rate) == ("eur", Decimal("4.25"))


def test_get_missing_currency_is_404_with_code(
    client: TestClient, currencies: MagicMock
) -> None:
    currencies.get_by_id.side_effect = CurrencyNotFoundError

    response = client.get("/assets/currencies/77")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Currency not found",
        "code": "CURRENCY_NOT_FOUND",
    }


def test_delete_currency_in_use_is_409(
    client: TestClient, currencies: MagicMock
) -> None:
    currencies.delete.side_effect = CurrencyInUseError

    response = client.delete("/assets/currencies/1")

    assert response.status_code == 409
    assert response.json()["code"] == "CURRENCY_IN_USE"


@pytest.mark.parametrize(
    "payload",
    [{"code": "EURO"}, {"code": "EUR", "exchange_rate": -1}, {"code": "EUR", "x": 1}],
)
def test_create_currency_validates_shape(
    client: TestClient, payload: dict[str, object]
) -> None:
    assert client.post("/assets/currencies", json=payload).status_code == 422
