from fastapi.testclient import TestClient

from app.conftest import IntegrationData


def test_assets_and_reference_data_round_trip(
    integration_client: TestClient,
    integration_data: IntegrationData,
    auth_headers: dict[str, str],
    seeded_currency,
) -> None:
    asset_class_name = integration_data.value("class")[:20]
    ticker = integration_data.value("ticker")[:20].upper()
    asset_name = integration_data.value("asset")[:100]

    asset_class = integration_client.post(
        "/assets/asset-classes",
        headers=auth_headers,
        json={"name": asset_class_name},
    )
    assert asset_class.status_code == 201
    asset_class_id = asset_class.json()["id"]

    currencies = integration_client.get("/assets/currencies", headers=auth_headers)
    assert currencies.status_code == 200
    assert any(item["id"] == seeded_currency.id for item in currencies.json())

    asset = integration_client.post(
        "/assets/",
        headers=auth_headers,
        json={
            "ticker": ticker,
            "name": asset_name,
            "asset_class_id": asset_class_id,
            "currency_id": seeded_currency.id,
            "current_price": 123.45,
            "exchange": "TEST",
            "sector": "Integration",
        },
    )
    assert asset.status_code == 201
    asset_id = asset.json()["id"]
    assert asset.json()["ticker"] == ticker

    searched = integration_client.get(
        "/assets/", params={"search": asset_name}, headers=auth_headers
    )
    assert searched.status_code == 200
    assert any(item["id"] == asset_id for item in searched.json())

    updated = integration_client.patch(
        f"/assets/{asset_id}",
        headers=auth_headers,
        json={"name": "Updated Integration Asset"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated Integration Asset"

    detail = integration_client.get(f"/assets/{asset_id}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["asset_class"]["id"] == asset_class_id
    assert detail.json()["currency"]["id"] == seeded_currency.id

    # The initial price is history now: the asset cannot be deleted, only archived.
    refused = integration_client.delete(f"/assets/{asset_id}", headers=auth_headers)
    assert refused.status_code == 409
    assert refused.json()["code"] == "ASSET_HAS_HISTORY"

    archived = integration_client.post(
        f"/assets/{asset_id}/archive", headers=auth_headers
    )
    assert archived.status_code == 200
    assert archived.json()["archived_at"] is not None
    hidden = integration_client.get(
        "/assets/", params={"search": ticker}, headers=auth_headers
    )
    assert all(item["id"] != asset_id for item in hidden.json())
    shown = integration_client.get(
        "/assets/",
        params={"search": ticker, "include_archived": True},
        headers=auth_headers,
    )
    assert any(item["id"] == asset_id for item in shown.json())

    unarchived = integration_client.post(
        f"/assets/{asset_id}/unarchive", headers=auth_headers
    )
    assert unarchived.json()["archived_at"] is None


def test_an_asset_without_history_is_deleted_for_good(
    integration_client: TestClient,
    integration_data: IntegrationData,
    auth_headers: dict[str, str],
    seeded_currency,
) -> None:
    asset_class = integration_client.post(
        "/assets/asset-classes",
        headers=auth_headers,
        json={"name": integration_data.value("class")[:20]},
    )
    asset = integration_client.post(
        "/assets/",
        headers=auth_headers,
        json={
            "ticker": integration_data.value("ticker")[:20].upper(),
            "name": "No history",
            "asset_class_id": asset_class.json()["id"],
            "currency_id": seeded_currency.id,
        },
    )
    assert asset.status_code == 201
    asset_id = asset.json()["id"]
    assert asset.json()["stale"] is True
    assert asset.json()["price_date"] is None

    deleted = integration_client.delete(f"/assets/{asset_id}", headers=auth_headers)

    assert deleted.status_code == 204
    assert (
        integration_client.get(f"/assets/{asset_id}", headers=auth_headers).status_code
        == 404
    )


def test_asset_endpoints_require_authentication(
    integration_client: TestClient,
) -> None:
    response = integration_client.get("/assets/")

    assert response.status_code == 401
