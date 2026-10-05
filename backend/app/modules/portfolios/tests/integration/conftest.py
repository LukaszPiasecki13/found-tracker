"""Integration tests of `portfolios` never reach the network: reading a portfolio
computes its return, which stores the provider's price history first, so every
test gets an empty fake provider unless it installs its own."""

import pytest

from app.modules.assets import wiring as assets_wiring
from app.modules.assets.tests.fakes import FakeMarketDataProvider


@pytest.fixture(autouse=True)
def _offline_market_data(monkeypatch: pytest.MonkeyPatch) -> FakeMarketDataProvider:
    provider = FakeMarketDataProvider()
    monkeypatch.setattr(assets_wiring, "build_market_data_provider", lambda: provider)
    return provider
