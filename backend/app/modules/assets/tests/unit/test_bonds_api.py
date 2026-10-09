"""`GET /assets/bond-series/{series_code}` (provider prefill) and
`POST /assets/{asset_id}/bond-terms` (registration, always `source="manual"`)."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import register_error_handlers
from app.core.market_data import BondTerms as BondTermsPort
from app.modules.assets.api import router
from app.modules.assets.dependencies import (
    get_asset_service,
    get_bond_data_provider,
    get_bond_data_service,
)
from app.modules.security.dependencies import get_current_user

USER = SimpleNamespace(id=1, email="user@example.com", is_active=True)

EDO_PORT_TERMS = BondTermsPort(
    bond_symbol="EDO",
    series_code="EDO1036",
    nominal_value=Decimal("100.00"),
    issue_date=date(2026, 10, 1),
    maturity_date=date(2036, 10, 1),
    capitalization="annual",
    first_period_rate=Decimal("5.35"),
    reference_type="cpi",
    margin=Decimal("2.00"),
    redemption_fee=Decimal("3.00"),
)

EDO_REQUEST_PAYLOAD = {
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


def _bond_asset(asset_type: str = "bond") -> SimpleNamespace:
    return SimpleNamespace(id=1, asset_type=asset_type)


def build_client(
    *,
    assets: MagicMock | None = None,
    bond_data: MagicMock | None = None,
    bond_provider: MagicMock | None = None,
) -> TestClient:
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: USER
    app.dependency_overrides[get_asset_service] = lambda: assets or MagicMock()
    app.dependency_overrides[get_bond_data_service] = lambda: bond_data or MagicMock()
    app.dependency_overrides[get_bond_data_provider] = lambda: (
        bond_provider or MagicMock()
    )
    return TestClient(app, raise_server_exceptions=False)


# --- GET /assets/bond-series/{series_code} ---


def test_search_bond_series_returns_prefill_data() -> None:
    provider = MagicMock()
    provider.fetch_series.return_value = EDO_PORT_TERMS

    response = build_client(bond_provider=provider).get("/assets/bond-series/EDO1036")

    assert response.status_code == 200
    body = response.json()
    assert body["bond_symbol"] == "EDO"
    assert body["series_code"] == "EDO1036"
    assert body["first_period_rate"] == 5.35
    assert body["margin"] == 2.0
    provider.fetch_series.assert_called_once_with("EDO1036")


def test_search_bond_series_404_when_unknown() -> None:
    provider = MagicMock()
    provider.fetch_series.return_value = None

    response = build_client(bond_provider=provider).get("/assets/bond-series/ZZZ9999")

    assert response.status_code == 404
    assert response.json()["code"] == "BOND_TERMS_NOT_FOUND"


# --- POST /assets/{asset_id}/bond-terms ---


def test_register_bond_terms_uses_manual_source_regardless_of_payload() -> None:
    assets = MagicMock()
    assets.get_by_id.return_value = _bond_asset()
    bond_data = MagicMock()
    bond_data.register_series.return_value = SimpleNamespace(
        asset_id=1,
        bond_symbol="EDO",
        series_code="EDO1036",
        nominal_value=Decimal("100.00"),
        issue_date=date(2026, 10, 1),
        maturity_date=date(2036, 10, 1),
        capitalization="annual",
        first_period_rate=Decimal("5.35"),
        reference_type="cpi",
        margin=Decimal("2.00"),
        redemption_fee=Decimal("3.00"),
        source="manual",
    )

    response = build_client(assets=assets, bond_data=bond_data).post(
        "/assets/1/bond-terms", json=EDO_REQUEST_PAYLOAD
    )

    assert response.status_code == 201
    assert response.json()["source"] == "manual"
    _, kwargs = bond_data.register_series.call_args
    assert kwargs["asset_id"] == 1
    assert kwargs["source"] == "manual"


def test_register_bond_terms_rejects_a_non_bond_asset() -> None:
    assets = MagicMock()
    assets.get_by_id.return_value = _bond_asset(asset_type="stock")
    bond_data = MagicMock()

    response = build_client(assets=assets, bond_data=bond_data).post(
        "/assets/1/bond-terms", json=EDO_REQUEST_PAYLOAD
    )

    assert response.status_code == 400
    assert response.json()["code"] == "ASSET_NOT_A_BOND"
    bond_data.register_series.assert_not_called()


@pytest.mark.parametrize(
    "field,bad_value",
    [("bond_symbol", "NOPE"), ("capitalization", "weekly"), ("reference_type", "wat")],
)
def test_register_bond_terms_rejects_unknown_enum_values(
    field: str, bad_value: str
) -> None:
    assets = MagicMock()
    assets.get_by_id.return_value = _bond_asset()
    payload = EDO_REQUEST_PAYLOAD | {field: bad_value}

    response = build_client(assets=assets).post("/assets/1/bond-terms", json=payload)

    assert response.status_code == 422


def test_register_bond_terms_rejects_extra_fields() -> None:
    assets = MagicMock()
    assets.get_by_id.return_value = _bond_asset()
    payload = EDO_REQUEST_PAYLOAD | {"unexpected_field": "x"}

    response = build_client(assets=assets).post("/assets/1/bond-terms", json=payload)

    assert response.status_code == 422
