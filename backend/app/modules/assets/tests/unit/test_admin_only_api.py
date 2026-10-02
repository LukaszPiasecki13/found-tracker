"""Shared reference data (assets, asset classes, currencies, prices, exchange
rates) may be changed only by an administrator; reading, creating an asset,
importing one and queuing a price refresh stay open to every signed-in user."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.modules.assets.api import router
from app.modules.assets.dependencies import (
    get_asset_class_service,
    get_asset_service,
    get_currency_service,
    get_fx_rate_service,
    get_price_service,
)
from app.modules.security.dependencies import get_current_user


def _client(email: str) -> TestClient:
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)
    for dependency in (
        get_asset_service,
        get_asset_class_service,
        get_currency_service,
        get_price_service,
        get_fx_rate_service,
    ):
        app.dependency_overrides[dependency] = lambda: MagicMock()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=1, email=email
    )
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def admins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        get_settings(), "admin_emails", ["Boss@Example.com"], raising=False
    )


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("patch", "/assets/1"),
        ("put", "/assets/1"),
        ("delete", "/assets/1"),
        ("post", "/assets/currencies"),
        ("patch", "/assets/currencies/1"),
        ("delete", "/assets/currencies/1"),
        ("post", "/assets/asset-classes"),
        ("patch", "/assets/asset-classes/1"),
        ("delete", "/assets/asset-classes/1"),
        ("post", "/assets/1/archive"),
        ("post", "/assets/1/unarchive"),
        ("put", "/assets/1/prices/2026-10-01"),
        ("delete", "/assets/1/prices/2026-10-01"),
        ("put", "/assets/fx-rates"),
    ],
)
def test_a_regular_user_cannot_change_shared_data(method: str, path: str) -> None:
    response = _client("user@example.com").request(method.upper(), path, json={})

    assert response.status_code == 403
    assert response.json()["code"] == "ADMIN_REQUIRED"


def test_an_administrator_passes_the_guard_whatever_the_email_case() -> None:
    response = _client("boss@example.com").delete("/assets/1")

    assert response.status_code == 204


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/assets/currencies"),
        ("get", "/assets/fx-rates?from_currency=PLN&to_currency=USD"),
        ("get", "/assets/currencies/rate?from_currency=PLN&to_currency=USD"),
        ("get", "/assets/1/prices"),
        ("get", "/assets/data-status"),
    ],
)
def test_a_regular_user_can_still_read(method: str, path: str) -> None:
    response = _client("user@example.com").request(method.upper(), path)

    assert response.status_code != 403


def test_a_regular_user_can_queue_a_price_refresh() -> None:
    """A refresh changes nothing a user could not also trigger from a position
    view, so it is open to everyone signed in."""
    response = _client("user@example.com").post(
        "/assets/refresh-prices", json={"asset_ids": [1]}
    )

    assert response.status_code != 403
