"""Treasury bonds against the real database schema.

This is exactly the layer that mocked unit tests cannot cover: the
`assets_bond_terms` table migration once never reached the dev database, so
`POST /assets/{id}/bond-terms` returned a 500 (`UndefinedTable`) in
production while every mocked unit test stayed green. These tests exercise
the real schema so that regression cannot hide again.

The bond data provider is replaced in `wiring.py` (the one place that picks
it), so no test reaches the network - same convention as
`test_reference_data_flow.py` for Yahoo Finance.
"""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.conftest import IntegrationData
from app.modules.assets import wiring as assets_wiring
from app.modules.assets.models.bond_terms import BondTerms as BondTermsModel
from app.modules.assets.tests.fakes import FakeBondDataProvider, make_bond_terms


@pytest.fixture
def fake_bond_provider(monkeypatch: pytest.MonkeyPatch) -> FakeBondDataProvider:
    provider = FakeBondDataProvider()
    monkeypatch.setattr(assets_wiring, "build_bond_data_provider", lambda: provider)
    return provider


def _create_bond_asset(
    integration_client: TestClient,
    auth_headers: dict[str, str],
    integration_data: IntegrationData,
    seeded_currency,
) -> int:
    asset_class = integration_client.post(
        "/assets/asset-classes",
        headers=auth_headers,
        json={"name": integration_data.value("class")[:20]},
    )
    assert asset_class.status_code == 201

    asset = integration_client.post(
        "/assets/",
        headers=auth_headers,
        json={
            "ticker": integration_data.value("bond")[:20].upper(),
            "name": "Integration bond",
            "asset_class_id": asset_class.json()["id"],
            "currency_id": seeded_currency.id,
            "asset_type": "bond",
        },
    )
    assert asset.status_code == 201
    return asset.json()["id"]


BOND_TERMS_PAYLOAD = {
    "bond_symbol": "EDO",
    "series_code": "EDO1036",
    "nominal_value": "100.00",
    "issue_date": "2026-10-01",
    "maturity_date": "2036-10-01",
    "capitalization": "annual",
    "first_period_rate": "5.35",
    "reference_type": "cpi",
    "margin": "2.00",
    "redemption_fee": "3.00",
}


def test_register_bond_terms_persists_against_the_real_schema(
    integration_client: TestClient,
    integration_session,
    integration_data: IntegrationData,
    auth_headers: dict[str, str],
    seeded_currency,
) -> None:
    asset_id = _create_bond_asset(
        integration_client, auth_headers, integration_data, seeded_currency
    )

    response = integration_client.post(
        f"/assets/{asset_id}/bond-terms",
        headers=auth_headers,
        json=BOND_TERMS_PAYLOAD,
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["asset_id"] == asset_id
    assert body["source"] == "manual"
    assert body["bond_symbol"] == "EDO"
    assert Decimal(str(body["first_period_rate"])) == Decimal("5.35")

    # The exact gap that shipped broken: read the row back from the real
    # table, not just trust the response the same request echoed.
    stored = (
        integration_session.query(BondTermsModel).filter_by(asset_id=asset_id).one()
    )
    assert stored.series_code == "EDO1036"
    assert stored.nominal_value == Decimal("100.00")
    assert stored.redemption_fee == Decimal("3.00")
    assert stored.source == "manual"


def test_registering_terms_twice_updates_the_same_row(
    integration_client: TestClient,
    integration_session,
    integration_data: IntegrationData,
    auth_headers: dict[str, str],
    seeded_currency,
) -> None:
    asset_id = _create_bond_asset(
        integration_client, auth_headers, integration_data, seeded_currency
    )
    integration_client.post(
        f"/assets/{asset_id}/bond-terms", headers=auth_headers, json=BOND_TERMS_PAYLOAD
    )

    updated = integration_client.post(
        f"/assets/{asset_id}/bond-terms",
        headers=auth_headers,
        json={**BOND_TERMS_PAYLOAD, "redemption_fee": "4.00"},
    )

    assert updated.status_code == 201
    rows = integration_session.query(BondTermsModel).filter_by(asset_id=asset_id).all()
    assert len(rows) == 1
    assert rows[0].redemption_fee == Decimal("4.00")


def test_register_bond_terms_rejects_invalid_dates(
    integration_client: TestClient,
    integration_data: IntegrationData,
    auth_headers: dict[str, str],
    seeded_currency,
) -> None:
    asset_id = _create_bond_asset(
        integration_client, auth_headers, integration_data, seeded_currency
    )

    response = integration_client.post(
        f"/assets/{asset_id}/bond-terms",
        headers=auth_headers,
        json={**BOND_TERMS_PAYLOAD, "maturity_date": "2020-01-01"},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_BOND_TERMS"


def test_register_bond_terms_rejects_a_non_bond_asset(
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
    stock = integration_client.post(
        "/assets/",
        headers=auth_headers,
        json={
            "ticker": integration_data.value("stk")[:20].upper(),
            "name": "Not a bond",
            "asset_class_id": asset_class.json()["id"],
            "currency_id": seeded_currency.id,
            "asset_type": "stock",
        },
    )
    asset_id = stock.json()["id"]

    response = integration_client.post(
        f"/assets/{asset_id}/bond-terms",
        headers=auth_headers,
        json=BOND_TERMS_PAYLOAD,
    )

    assert response.status_code == 400
    assert response.json()["code"] == "ASSET_NOT_A_BOND"


def test_register_bond_terms_404s_for_a_missing_asset(
    integration_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = integration_client.post(
        "/assets/999999999/bond-terms",
        headers=auth_headers,
        json=BOND_TERMS_PAYLOAD,
    )

    assert response.status_code == 404
    assert response.json()["code"] == "ASSET_NOT_FOUND"


def test_search_bond_series_returns_prefill_data_from_the_provider(
    integration_client: TestClient,
    auth_headers: dict[str, str],
    fake_bond_provider: FakeBondDataProvider,
) -> None:
    fake_bond_provider.series["EDO1036"] = make_bond_terms("EDO1036")

    response = integration_client.get(
        "/assets/bond-series/EDO1036", headers=auth_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["bond_symbol"] == "EDO"
    assert body["series_code"] == "EDO1036"
    assert Decimal(str(body["redemption_fee"])) == Decimal("3.00")
    assert fake_bond_provider.calls == [("series", "EDO1036")]


def test_search_bond_series_404s_for_an_unknown_series(
    integration_client: TestClient,
    auth_headers: dict[str, str],
    fake_bond_provider: FakeBondDataProvider,
) -> None:
    response = integration_client.get(
        "/assets/bond-series/ZZZ9999", headers=auth_headers
    )

    assert response.status_code == 404
    assert response.json()["code"] == "BOND_TERMS_NOT_FOUND"


def test_search_bond_series_502s_when_the_provider_is_down(
    integration_client: TestClient,
    auth_headers: dict[str, str],
    fake_bond_provider: FakeBondDataProvider,
) -> None:
    fake_bond_provider.failing.add("EDO1036")

    response = integration_client.get(
        "/assets/bond-series/EDO1036", headers=auth_headers
    )

    assert response.status_code == 502
    assert response.json()["code"] == "BOND_DATA_UNAVAILABLE"


def test_search_bond_series_requires_authentication(
    integration_client: TestClient,
) -> None:
    response = integration_client.get("/assets/bond-series/EDO1036")

    assert response.status_code == 401


def test_bond_pricing_service_writes_a_synthetic_price_against_the_real_schema(
    integration_client: TestClient,
    integration_session,
    integration_data: IntegrationData,
    auth_headers: dict[str, str],
    seeded_currency,
) -> None:
    """The service layer, called the same way `entrypoints.refresh_bond_prices`
    does, must actually commit a row to `assets_price` - not just claim to."""
    asset_id = _create_bond_asset(
        integration_client, auth_headers, integration_data, seeded_currency
    )
    integration_client.post(
        f"/assets/{asset_id}/bond-terms", headers=auth_headers, json=BOND_TERMS_PAYLOAD
    )

    from app.modules.assets.models.assets import Asset

    bond_asset = integration_session.get(Asset, asset_id)
    assert bond_asset.current_price == Decimal("0")

    bond_pricing = assets_wiring.build_bond_pricing_service(integration_session)
    ok = bond_pricing.refresh_bond_prices([bond_asset], date(2027, 10, 1))

    assert ok == 1
    integration_session.refresh(bond_asset)
    assert bond_asset.current_price > Decimal("0")

    from app.modules.assets.models.prices import AssetPrice

    stored_price = (
        integration_session.query(AssetPrice)
        .filter_by(asset_id=asset_id, source="bonds")
        .one()
    )
    assert stored_price.is_synthetic is True
    assert stored_price.close == bond_asset.current_price


def test_full_purchase_flow_books_a_buy_operation(
    integration_client: TestClient,
    integration_data: IntegrationData,
    auth_headers: dict[str, str],
    seeded_currency,
) -> None:
    """The exact sequence the frontend's `useCreateBondAndBuy` sends: create
    the asset, register its terms, then book the purchase."""
    asset_id = _create_bond_asset(
        integration_client, auth_headers, integration_data, seeded_currency
    )
    terms = integration_client.post(
        f"/assets/{asset_id}/bond-terms", headers=auth_headers, json=BOND_TERMS_PAYLOAD
    )
    assert terms.status_code == 201

    portfolio = integration_client.post(
        "/portfolios/",
        headers=auth_headers,
        json={
            "name": integration_data.value("pocket"),
            "base_currency_id": seeded_currency.id,
        },
    )
    assert portfolio.status_code == 201
    portfolio_id = portfolio.json()["id"]

    deposit = integration_client.post(
        "/portfolios/operations",
        headers=auth_headers,
        json={
            "portfolio_id": portfolio_id,
            "operation_type": "deposit",
            "amount": "10000.00",
            "fee": "0",
            "fx_rate": "1",
            "operation_date": "2026-10-09T00:00:00",
        },
    )
    assert deposit.status_code == 201

    buy = integration_client.post(
        "/portfolios/operations",
        headers=auth_headers,
        json={
            "portfolio_id": portfolio_id,
            "asset_id": asset_id,
            "operation_type": "buy",
            "quantity": "10",
            "price": "100.00",
            "amount": "1001.00",
            "fee": "1.00",
            "fx_rate": "1",
            "operation_date": "2026-10-09T00:00:00",
            "notes": "integration test",
        },
    )

    assert buy.status_code == 201, buy.text
    body = buy.json()
    assert body["asset_id"] == asset_id
    assert Decimal(str(body["quantity"])) == Decimal("10")
