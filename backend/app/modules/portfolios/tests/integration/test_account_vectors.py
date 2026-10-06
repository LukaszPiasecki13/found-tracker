"""`GET /portfolios/account-vectors` over real HTTP and the test database: the
user's portfolios summed in the user's base currency (DEC-01, DEC-08)."""

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.conftest import IntegrationData
from app.modules.assets import entrypoints as assets_entrypoints
from app.modules.assets.models import Currency
from app.modules.core_data.models.user import User


@pytest.fixture(autouse=True)
def _no_background_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    """The first request of a day starts the market-data refresh; this test reads
    stored history only, so the refresh is switched off."""
    monkeypatch.setattr(assets_entrypoints, "daily_refresh", lambda *args, **kw: None)


def _when(day: int, hour: int = 9) -> str:
    return datetime(2025, 1, day, hour, tzinfo=UTC).isoformat()


def _get(client: TestClient, headers: dict[str, str], **params: Any) -> Any:
    return client.get("/portfolios/account-vectors", headers=headers, params=params)


def test_account_vectors_sum_the_portfolios_in_the_users_currency(
    integration_client: TestClient,
    integration_session: Session,
    integration_data: IntegrationData,
    auth_headers: dict[str, str],
    seeded_currency: Currency,
) -> None:
    user = (
        integration_session.query(User)
        .filter_by(email=f"{integration_data.value('user')}@example.com")
        .one()
    )
    user.base_currency_id = seeded_currency.id
    integration_session.flush()

    for suffix, amount in (("acc_a", "1000"), ("acc_b", "250")):
        created = integration_client.post(
            "/portfolios/",
            headers=auth_headers,
            json={
                "name": integration_data.value(suffix),
                "base_currency_id": seeded_currency.id,
            },
        )
        assert created.status_code == 201, created.text
        deposit = integration_client.post(
            "/portfolios/operations",
            headers=auth_headers,
            json={
                "portfolio_id": created.json()["id"],
                "operation_type": "deposit",
                "amount": amount,
                "operation_date": _when(1),
            },
        )
        assert deposit.status_code == 201, deposit.text

    response = _get(
        integration_client,
        auth_headers,
        startDate="2025-01-01",
        endDate="2025-01-03",
        vectors='["net_deposits_vector","free_cash_vector"]',
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "date": [
            "2025-01-01T00:00:00",
            "2025-01-02T00:00:00",
            "2025-01-03T00:00:00",
        ],
        "net_deposits_vector": [1250.0, 1250.0, 1250.0],
        "free_cash_vector": [1250.0, 1250.0, 1250.0],
    }

    reversed_range = _get(
        integration_client,
        auth_headers,
        startDate="2025-01-03",
        endDate="2025-01-01",
    )
    assert reversed_range.status_code == 400
    assert reversed_range.json()["code"] == "INVALID_DATE_RANGE"


def test_an_owner_without_operations_gets_an_empty_body(
    integration_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = _get(
        integration_client,
        auth_headers,
        startDate="2025-01-01",
        endDate="2025-01-03",
    )

    assert response.status_code == 200, response.text
    assert response.json() == {}


def test_a_portfolio_name_parameter_is_ignored(
    integration_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """The account takes no portfolio name: `portfolio-vectors` is the per-portfolio
    endpoint (DEC-02). The name is ignored, so the request still returns the account."""
    response = _get(
        integration_client,
        auth_headers,
        portfolioName="anything",
        startDate="2025-01-01",
        endDate="2025-01-03",
    )

    assert response.status_code == 200, response.text
    assert response.json() == {}
