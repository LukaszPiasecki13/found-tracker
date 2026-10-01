import logging
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.market_data import MarketDataUnavailableError
from app.modules.assets.exceptions import AssetNotFoundOnProviderError
from app.modules.assets.services.market_data import MarketDataService
from app.modules.assets.tests.fakes import FakeMarketDataProvider, make_quote


@pytest.fixture
def provider() -> FakeMarketDataProvider:
    return FakeMarketDataProvider()


@pytest.fixture
def service(
    asset_repo: MagicMock, currency_repo: MagicMock, provider: FakeMarketDataProvider
) -> MarketDataService:
    return MarketDataService(asset_repo, currency_repo, provider)


# --- search ---


def test_search_takes_the_ticker_before_the_name_and_uppercases_it(
    service: MarketDataService, provider: FakeMarketDataProvider
) -> None:
    provider.quotes["AAPL"] = make_quote("AAPL")

    hits = service.search("  aapl - Apple Inc. ")

    assert [hit.symbol for hit in hits] == ["AAPL"]
    assert provider.calls == [("quote", "AAPL")]


def test_search_fills_provider_gaps_with_defaults(
    service: MarketDataService, provider: FakeMarketDataProvider
) -> None:
    provider.quotes["XYZ"] = make_quote("XYZ", currency="", quote_type="")

    (hit,) = service.search("xyz")

    assert (hit.currency, hit.quote_type) == ("USD", "EQUITY")


def test_search_requires_a_market_price_or_previous_close(
    service: MarketDataService, provider: FakeMarketDataProvider
) -> None:
    provider.quotes["XYZ"] = make_quote(
        "XYZ",
        current_price=Decimal("1"),
        regular_market_price=None,
        previous_close=Decimal("0"),
    )

    assert service.search("XYZ") == []


def test_search_of_unknown_ticker_is_empty(service: MarketDataService) -> None:
    assert service.search("NOPE") == []


def test_search_of_blank_query_does_not_call_the_provider(
    service: MarketDataService, provider: FakeMarketDataProvider
) -> None:
    assert service.search("   ") == []
    assert provider.calls == []


def test_search_degrades_to_empty_on_provider_outage(
    service: MarketDataService,
    provider: FakeMarketDataProvider,
    caplog: pytest.LogCaptureFixture,
) -> None:
    provider.failing.add("AAPL")

    with caplog.at_level(logging.WARNING):
        assert service.search("AAPL") == []

    assert "AAPL" in caplog.text


# --- quotes and pass-throughs ---


def test_get_quote_raises_when_provider_has_no_such_ticker(
    service: MarketDataService,
) -> None:
    with pytest.raises(AssetNotFoundOnProviderError):
        service.get_quote("NOPE")


def test_get_quote_propagates_provider_outage(
    service: MarketDataService, provider: FakeMarketDataProvider
) -> None:
    provider.failing.add("AAPL")

    with pytest.raises(MarketDataUnavailableError):
        service.get_quote("AAPL")


def test_current_price_follows_the_quote_price_rule(
    service: MarketDataService, provider: FakeMarketDataProvider
) -> None:
    provider.quotes["AAPL"] = make_quote(current_price=None)

    assert service.current_price("AAPL") == Decimal("190.4")
    assert service.current_price("NOPE") is None


def test_close_history_is_end_exclusive(
    service: MarketDataService, provider: FakeMarketDataProvider
) -> None:
    provider.history["AAPL"] = {
        date(2026, 1, 1): Decimal("10"),
        date(2026, 1, 2): Decimal("11"),
        date(2026, 1, 3): Decimal("12"),
    }

    closes = service.close_history("AAPL", date(2026, 1, 1), date(2026, 1, 3))

    assert closes == {date(2026, 1, 1): Decimal("10"), date(2026, 1, 2): Decimal("11")}


# --- refresh_asset_prices ---


def test_refresh_asset_prices_skips_failing_and_priceless_assets(
    service: MarketDataService,
    provider: FakeMarketDataProvider,
    session: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    apple = SimpleNamespace(id=1, ticker="AAPL", current_price=Decimal("1"))
    broken = SimpleNamespace(id=2, ticker="BRKN", current_price=Decimal("2"))
    delisted = SimpleNamespace(id=3, ticker="GONE", current_price=Decimal("3"))
    provider.quotes["AAPL"] = make_quote("AAPL")
    provider.failing.add("BRKN")

    with caplog.at_level(logging.WARNING):
        updated = service.refresh_asset_prices([apple, broken, delisted, apple])

    assert updated == 1
    assert apple.current_price == Decimal("190.5")
    assert broken.current_price == Decimal("2")
    assert delisted.current_price == Decimal("3")
    assert provider.calls.count(("quote", "AAPL")) == 1
    assert "BRKN" in caplog.text
    session.commit.assert_called_once()
    session.rollback.assert_not_called()


def test_refresh_asset_prices_of_nothing_updates_nothing(
    service: MarketDataService,
) -> None:
    assert service.refresh_asset_prices([]) == 0


# --- refresh_currency_rates ---


def test_refresh_currency_rates_is_best_effort_per_currency(
    service: MarketDataService,
    currency_repo: MagicMock,
    provider: FakeMarketDataProvider,
    session: MagicMock,
) -> None:
    usd = SimpleNamespace(code="USD", exchange_rate=Decimal("0.9"))
    eur = SimpleNamespace(code="EUR", exchange_rate=Decimal("1"))
    gbp = SimpleNamespace(code="GBP", exchange_rate=Decimal("1.2"))
    xxx = SimpleNamespace(code="XXX", exchange_rate=Decimal("5"))
    currency_repo.list_all.return_value = [usd, eur, gbp, xxx]
    provider.rates[("EUR", "USD")] = Decimal("1.08")
    provider.failing.add("GBP")

    updated = service.refresh_currency_rates("usd")

    assert updated == 2
    assert usd.exchange_rate == Decimal("1")
    assert eur.exchange_rate == Decimal("1.08")
    assert gbp.exchange_rate == Decimal("1.2")
    assert xxx.exchange_rate == Decimal("5")
    assert ("fx", "USD", "USD") not in provider.calls
    session.commit.assert_called_once()
