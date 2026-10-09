"""Integration tests of `portfolios` never reach the network: reading a portfolio
computes its return, which stores the provider's price history first, so every
test gets an empty fake provider unless it installs its own. `GET
/portfolios/positions` can also trigger `daily_refresh()` as a background task
(ADR-0017), which now touches the bond data provider too - stubbed here for
the same reason."""

import pytest

from app.modules.assets import wiring as assets_wiring
from app.modules.assets.tests.fakes import FakeBondDataProvider, FakeMarketDataProvider


@pytest.fixture(autouse=True)
def _offline_market_data(monkeypatch: pytest.MonkeyPatch) -> FakeMarketDataProvider:
    provider = FakeMarketDataProvider()
    monkeypatch.setattr(assets_wiring, "build_market_data_provider", lambda: provider)
    return provider


@pytest.fixture(autouse=True)
def _offline_bond_data(monkeypatch: pytest.MonkeyPatch) -> FakeBondDataProvider:
    provider = FakeBondDataProvider()
    monkeypatch.setattr(assets_wiring, "build_bond_data_provider", lambda: provider)
    return provider
