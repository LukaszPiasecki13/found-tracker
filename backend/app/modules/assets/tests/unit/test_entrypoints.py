"""`assets.entrypoints`: the non-HTTP refresh jobs open their own session scope
(ADR-0002) and delegate to the services; no commit happens here."""

from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from app.modules.assets import entrypoints


@pytest.fixture
def scope(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    session = MagicMock()
    opened: list[MagicMock] = []

    @contextmanager
    def session_scope():
        opened.append(session)
        yield session

    monkeypatch.setattr(entrypoints, "session_scope", session_scope)
    session.opened = opened
    return session


@pytest.fixture
def services(monkeypatch: pytest.MonkeyPatch) -> tuple[MagicMock, MagicMock]:
    assets, market_data = MagicMock(), MagicMock()
    monkeypatch.setattr(entrypoints, "build_asset_service", lambda session: assets)
    monkeypatch.setattr(
        entrypoints, "build_market_data_service", lambda session: market_data
    )
    return assets, market_data


def test_refresh_prices_of_given_ids_loads_them_and_refreshes(
    scope: MagicMock, services: tuple[MagicMock, MagicMock]
) -> None:
    assets, market_data = services
    loaded = [MagicMock(), MagicMock()]
    assets.list_by_ids.return_value = loaded
    market_data.refresh_asset_prices.return_value = 2

    assert entrypoints.refresh_prices([4, 5]) == 2

    assets.list_by_ids.assert_called_once_with([4, 5])
    market_data.refresh_asset_prices.assert_called_once_with(loaded)
    scope.commit.assert_not_called()
    assert len(scope.opened) == 1


def test_refresh_prices_without_ids_takes_every_active_asset(
    scope: MagicMock, services: tuple[MagicMock, MagicMock]
) -> None:
    assets, market_data = services
    active = [MagicMock()]
    assets.list_assets.return_value = active
    market_data.refresh_asset_prices.return_value = 1

    assert entrypoints.refresh_prices() == 1

    assets.list_assets.assert_called_once_with()
    assets.list_by_ids.assert_not_called()
    market_data.refresh_asset_prices.assert_called_once_with(active)


def test_refresh_fx_rates_delegates_to_the_market_data_service(
    scope: MagicMock, services: tuple[MagicMock, MagicMock]
) -> None:
    _, market_data = services
    market_data.refresh_currency_rates.return_value = 3

    assert entrypoints.refresh_fx_rates() == 3

    market_data.refresh_currency_rates.assert_called_once_with()
    scope.commit.assert_not_called()
