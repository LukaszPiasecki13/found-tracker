"""`assets.entrypoints`: the non-HTTP refresh jobs run in the given session scope
(ADR-0002), delegate to the services and report `ok`/`failed`; no commit here."""

from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.assets import entrypoints
from app.modules.assets.entrypoints import RefreshResult


class Scope:
    """A `SessionScope` double that records how often it was opened."""

    def __init__(self) -> None:
        self.session = MagicMock()
        self.opened = 0

    @contextmanager
    def __call__(self):
        self.opened += 1
        yield self.session


@pytest.fixture
def scope() -> Scope:
    return Scope()


@pytest.fixture
def services(monkeypatch: pytest.MonkeyPatch) -> tuple[MagicMock, MagicMock]:
    assets, market_data = MagicMock(), MagicMock()
    monkeypatch.setattr(entrypoints, "build_asset_service", lambda session: assets)
    monkeypatch.setattr(
        entrypoints, "build_market_data_service", lambda session: market_data
    )
    return assets, market_data


def _asset(archived: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        archived_at=datetime(2026, 1, 1, tzinfo=UTC) if archived else None
    )


def test_refresh_prices_of_given_ids_loads_them_and_counts_the_outcome(
    scope: Scope, services: tuple[MagicMock, MagicMock]
) -> None:
    assets, market_data = services
    loaded = [_asset(), _asset(), _asset()]
    assets.list_by_ids.return_value = loaded
    market_data.refresh_asset_prices.return_value = 2

    result = entrypoints.refresh_prices([4, 5, 6], scope)

    assert result == RefreshResult(ok=2, failed=1)
    assets.list_by_ids.assert_called_once_with([4, 5, 6])
    market_data.refresh_asset_prices.assert_called_once_with(loaded)
    scope.session.commit.assert_not_called()
    assert scope.opened == 1


def test_refresh_prices_without_ids_takes_every_active_asset(
    scope: Scope, services: tuple[MagicMock, MagicMock]
) -> None:
    assets, market_data = services
    active = [_asset()]
    assets.list_assets.return_value = active
    market_data.refresh_asset_prices.return_value = 1

    assert entrypoints.refresh_prices(None, scope) == RefreshResult(ok=1, failed=0)

    assets.list_assets.assert_called_once_with()
    assets.list_by_ids.assert_not_called()
    market_data.refresh_asset_prices.assert_called_once_with(active)


def test_archived_assets_are_not_refreshed_nor_counted_as_failures(
    scope: Scope, services: tuple[MagicMock, MagicMock]
) -> None:
    assets, market_data = services
    live = _asset()
    assets.list_by_ids.return_value = [live, _asset(archived=True)]
    market_data.refresh_asset_prices.return_value = 1

    result = entrypoints.refresh_prices([1, 2], scope)

    assert result == RefreshResult(ok=1, failed=0)
    market_data.refresh_asset_prices.assert_called_once_with([live])


def test_refresh_fx_rates_counts_currencies_without_a_rate_as_failed(
    scope: Scope, services: tuple[MagicMock, MagicMock]
) -> None:
    _, market_data = services
    market_data.list_currency_codes.return_value = ["USD", "EUR", "XXX"]
    market_data.refresh_currency_rates.return_value = 2

    result = entrypoints.refresh_fx_rates(scope)

    assert result == RefreshResult(ok=2, failed=1)
    market_data.refresh_currency_rates.assert_called_once_with()
    scope.session.commit.assert_not_called()
    assert scope.opened == 1
