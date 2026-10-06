"""`GET /portfolios/currency-split` over real HTTP and the test database."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.conftest import IntegrationData
from app.modules.assets.models import Currency


def test_cash_of_one_portfolio_is_split_in_its_base_currency(
    integration_client: TestClient,
    integration_data: IntegrationData,
    auth_headers: dict[str, str],
    seeded_currency: Currency,
) -> None:
    name = integration_data.value("split")
    created = integration_client.post(
        "/portfolios/",
        headers=auth_headers,
        json={"name": name, "base_currency_id": seeded_currency.id},
    )
    assert created.status_code == 201, created.text
    deposit = integration_client.post(
        "/portfolios/operations",
        headers=auth_headers,
        json={
            "portfolio_id": created.json()["id"],
            "operation_type": "deposit",
            "amount": 500,
            "operation_date": datetime(2025, 1, 2, 9, tzinfo=UTC).isoformat(),
        },
    )
    assert deposit.status_code == 201, deposit.text

    response = integration_client.get(
        "/portfolios/currency-split",
        headers=auth_headers,
        params={"portfolioName": name},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["currency"] == seeded_currency.code
    assert body["items"] == [{"currency": seeded_currency.code, "value": 500.0}]
    assert body["unpriced"] == 0


def test_an_unknown_portfolio_is_not_found(
    integration_client: TestClient,
    integration_data: IntegrationData,
    auth_headers: dict[str, str],
) -> None:
    response = integration_client.get(
        "/portfolios/currency-split",
        headers=auth_headers,
        params={"portfolioName": integration_data.value("missing")},
    )

    assert response.status_code == 404
    assert response.json()["code"] == "PORTFOLIO_NOT_FOUND"
