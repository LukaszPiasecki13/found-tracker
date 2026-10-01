"""Asset classes, currencies and create-from-provider against the real database.

The market-data provider is replaced in `wiring.py` (the one place that picks
it), so no test reaches the network.
"""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.conftest import CurrencyCodes, IntegrationData
from app.modules.assets import wiring as assets_wiring
from app.modules.assets.models import Currency
from app.modules.assets.tests.fakes import FakeMarketDataProvider, make_quote


@pytest.fixture
def fake_provider(monkeypatch: pytest.MonkeyPatch) -> FakeMarketDataProvider:
    provider = FakeMarketDataProvider()
    monkeypatch.setattr(assets_wiring, "build_market_data_provider", lambda: provider)
    return provider


def test_asset_class_crud_reports_conflicts_with_codes(
    integration_client: TestClient,
    integration_data: IntegrationData,
    auth_headers: dict[str, str],
) -> None:
    first = integration_data.value("c1")[:20]
    second = integration_data.value("c2")[:20]
    created = integration_client.post(
        "/assets/asset-classes", headers=auth_headers, json={"name": first}
    )
    assert created.status_code == 201
    other = integration_client.post(
        "/assets/asset-classes", headers=auth_headers, json={"name": second}
    )
    assert other.status_code == 201

    duplicate = integration_client.post(
        "/assets/asset-classes", headers=auth_headers, json={"name": first}
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "ASSET_CLASS_ALREADY_EXISTS"

    renamed_onto_existing = integration_client.patch(
        f"/assets/asset-classes/{other.json()['id']}",
        headers=auth_headers,
        json={"name": first},
    )
    assert renamed_onto_existing.status_code == 409
    assert renamed_onto_existing.json()["code"] == "ASSET_CLASS_ALREADY_EXISTS"

    missing = integration_client.delete(
        "/assets/asset-classes/999999999", headers=auth_headers
    )
    assert missing.status_code == 404
    assert missing.json()["code"] == "ASSET_CLASS_NOT_FOUND"


def test_asset_class_in_use_cannot_be_deleted(
    integration_client: TestClient,
    integration_data: IntegrationData,
    auth_headers: dict[str, str],
    seeded_currency: Currency,
) -> None:
    asset_class = integration_client.post(
        "/assets/asset-classes",
        headers=auth_headers,
        json={"name": integration_data.value("used")[:20]},
    ).json()
    asset = integration_client.post(
        "/assets/",
        headers=auth_headers,
        json={
            "ticker": integration_data.value("t")[:20],
            "name": "In use",
            "asset_class_id": asset_class["id"],
            "currency_id": seeded_currency.id,
        },
    )
    assert asset.status_code == 201

    response = integration_client.delete(
        f"/assets/asset-classes/{asset_class['id']}", headers=auth_headers
    )

    assert response.status_code == 409
    assert response.json()["code"] == "ASSET_CLASS_IN_USE"


def test_asset_rejects_duplicate_ticker_and_unknown_references(
    integration_client: TestClient,
    integration_data: IntegrationData,
    auth_headers: dict[str, str],
    seeded_currency: Currency,
) -> None:
    asset_class = integration_client.post(
        "/assets/asset-classes",
        headers=auth_headers,
        json={"name": integration_data.value("dup")[:20]},
    ).json()
    payload = {
        "ticker": integration_data.value("t")[:20],
        "name": "Duplicate",
        "asset_class_id": asset_class["id"],
        "currency_id": seeded_currency.id,
    }
    assert (
        integration_client.post(
            "/assets/", headers=auth_headers, json=payload
        ).status_code
        == 201
    )

    # Lower-case variant normalizes to the same ticker.
    duplicate = integration_client.post(
        "/assets/",
        headers=auth_headers,
        json={**payload, "ticker": payload["ticker"].lower()},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "ASSET_ALREADY_EXISTS"

    unknown_class = integration_client.post(
        "/assets/",
        headers=auth_headers,
        json={
            **payload,
            "ticker": integration_data.value("u")[:20],
            "asset_class_id": 999999999,
        },
    )
    assert unknown_class.status_code == 400
    assert unknown_class.json()["code"] == "ASSET_CLASS_NOT_FOUND"


def test_currency_crud_normalizes_code_and_reports_conflicts(
    integration_client: TestClient,
    auth_headers: dict[str, str],
    currency_codes: CurrencyCodes,
) -> None:
    code = currency_codes.new()

    created = integration_client.post(
        "/assets/currencies",
        headers=auth_headers,
        json={"code": code.lower(), "exchange_rate": 4.25},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["code"] == code
    # Decimal on the server, a JSON number on the wire (ADR-0010).
    assert body["exchange_rate"] == 4.25

    duplicate = integration_client.post(
        "/assets/currencies", headers=auth_headers, json={"code": code}
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "CURRENCY_ALREADY_EXISTS"

    deleted = integration_client.delete(
        f"/assets/currencies/{body['id']}", headers=auth_headers
    )
    assert deleted.status_code == 204
    missing = integration_client.get(
        f"/assets/currencies/{body['id']}", headers=auth_headers
    )
    assert missing.status_code == 404
    assert missing.json()["code"] == "CURRENCY_NOT_FOUND"


def test_create_from_provider_derives_class_and_currency(
    integration_client: TestClient,
    integration_data: IntegrationData,
    auth_headers: dict[str, str],
    currency_codes: CurrencyCodes,
    fake_provider: FakeMarketDataProvider,
) -> None:
    ticker = integration_data.value("y")[:20].upper()
    code = currency_codes.new()
    fake_provider.quotes[ticker] = make_quote(
        ticker,
        name="Provider Asset",
        quote_type="ETF",
        currency=code,
        current_price=Decimal("12.5"),
    )

    created = integration_client.post(
        "/assets/create-from-yahoo",
        headers=auth_headers,
        json={"ticker": ticker.lower()},
    )

    assert created.status_code == 201, created.text
    body = created.json()
    assert body["ticker"] == ticker
    assert body["name"] == "Provider Asset"
    assert body["asset_class"]["name"] == "ETF"
    assert body["currency"]["code"] == code
    assert body["current_price"] == 12.5

    again = integration_client.post(
        "/assets/create-from-yahoo", headers=auth_headers, json={"ticker": ticker}
    )
    assert again.status_code == 409
    assert again.json()["code"] == "ASSET_ALREADY_EXISTS"


def test_create_from_provider_unknown_ticker_is_404_and_writes_nothing(
    integration_client: TestClient,
    integration_data: IntegrationData,
    auth_headers: dict[str, str],
    fake_provider: FakeMarketDataProvider,
) -> None:
    ticker = integration_data.value("n")[:20].upper()

    response = integration_client.post(
        "/assets/create-from-yahoo", headers=auth_headers, json={"ticker": ticker}
    )

    assert response.status_code == 404
    assert response.json()["code"] == "ASSET_NOT_FOUND_ON_PROVIDER"
    listed = integration_client.get(
        "/assets/", params={"search": ticker}, headers=auth_headers
    )
    assert listed.json() == []
