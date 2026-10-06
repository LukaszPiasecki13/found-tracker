import logging
from datetime import UTC, date, datetime
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


TODAY = date(2026, 10, 2)


@pytest.fixture
def prices() -> MagicMock:
    mock = MagicMock()
    mock.record_closes.return_value = 1
    return mock


@pytest.fixture
def fx_rates() -> MagicMock:
    return MagicMock()


@pytest.fixture
def service(
    asset_repo: MagicMock,
    currency_repo: MagicMock,
    provider: FakeMarketDataProvider,
    prices: MagicMock,
    fx_rates: MagicMock,
) -> MarketDataService:
    return MarketDataService(
        asset_repo, currency_repo, provider, prices, fx_rates, today=lambda: TODAY
    )


# --- fx history and current rate (read by portfolios' metrics) ---


def test_fx_history_is_the_providers_daily_rates_in_the_requested_window(
    service: MarketDataService, provider: FakeMarketDataProvider
) -> None:
    provider.fx_history[("USD", "PLN")] = {
        date(2026, 10, 1): Decimal("3.6"),
        date(2026, 10, 2): Decimal("3.7"),
    }

    rates = service.fx_history("USD", "PLN", date(2026, 10, 2), date(2026, 10, 3))

    assert rates == {date(2026, 10, 2): Decimal("3.7")}
    assert provider.calls == [("fx_history", "USD", "PLN")]


def test_current_fx_rate_asks_the_provider_for_the_pair(
    service: MarketDataService, provider: FakeMarketDataProvider
) -> None:
    provider.rates[("USD", "PLN")] = Decimal("3.65")

    assert service.current_fx_rate("USD", "PLN") == Decimal("3.65")
    assert service.current_fx_rate("EUR", "PLN") is None


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
    prices: MagicMock,
    session: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    apple = SimpleNamespace(id=1, ticker="AAPL", archived_at=None)
    broken = SimpleNamespace(id=2, ticker="BRKN", archived_at=None)
    delisted = SimpleNamespace(id=3, ticker="GONE", archived_at=None)
    provider.quotes["AAPL"] = make_quote("AAPL")
    provider.failing.add("BRKN")

    with caplog.at_level(logging.WARNING):
        updated = service.refresh_asset_prices([apple, broken, delisted, apple])

    assert updated == 1
    prices.record_closes.assert_called_once_with(
        apple, {TODAY: Decimal("190.5")}, source="yahoo", is_synthetic=True
    )
    assert provider.calls.count(("quote", "AAPL")) == 1
    assert "BRKN" in caplog.text
    session.commit.assert_called_once()
    session.rollback.assert_not_called()


def test_refresh_asset_prices_leaves_archived_assets_alone(
    service: MarketDataService,
    provider: FakeMarketDataProvider,
    prices: MagicMock,
) -> None:
    archived = SimpleNamespace(
        id=1, ticker="AAPL", archived_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    provider.quotes["AAPL"] = make_quote("AAPL")

    assert service.refresh_asset_prices([archived]) == 0

    assert provider.calls == []
    prices.record_closes.assert_not_called()


def test_refresh_asset_prices_ignores_a_non_positive_price(
    service: MarketDataService,
    provider: FakeMarketDataProvider,
    prices: MagicMock,
) -> None:
    asset = SimpleNamespace(id=1, ticker="NEG", archived_at=None)
    provider.quotes["NEG"] = make_quote("NEG", current_price=Decimal("-1"))

    assert service.refresh_asset_prices([asset]) == 0

    prices.record_closes.assert_not_called()


def test_refresh_asset_prices_of_nothing_updates_nothing(
    service: MarketDataService,
) -> None:
    assert service.refresh_asset_prices([]) == 0


# --- backfill_closes ---


def test_backfill_closes_stores_each_assets_provider_history_once(
    service: MarketDataService,
    provider: FakeMarketDataProvider,
    prices: MagicMock,
    session: MagicMock,
) -> None:
    apple = SimpleNamespace(id=1, ticker="AAPL")
    provider.history["AAPL"] = {
        date(2026, 1, 1): Decimal("10"),
        date(2026, 1, 2): Decimal("11"),
        date(2026, 1, 3): Decimal("12"),
    }

    stored = service.backfill_closes([apple, apple], date(2026, 1, 1), date(2026, 1, 3))

    assert stored == 1  # `record_closes` is mocked: one call, one stored
    prices.record_closes.assert_called_once_with(
        apple,
        {date(2026, 1, 1): Decimal("10"), date(2026, 1, 2): Decimal("11")},
        source="yahoo",
        is_synthetic=False,
    )
    assert provider.calls.count(("history", "AAPL")) == 1
    session.commit.assert_called_once()


def test_backfill_closes_stores_nothing_when_the_provider_fails_for_any_asset(
    service: MarketDataService,
    provider: FakeMarketDataProvider,
    prices: MagicMock,
    session: MagicMock,
) -> None:
    apple = SimpleNamespace(id=1, ticker="AAPL")
    broken = SimpleNamespace(id=2, ticker="BRKN")
    provider.history["AAPL"] = {date(2026, 1, 1): Decimal("10")}
    provider.failing.add("BRKN")

    with pytest.raises(MarketDataUnavailableError):
        service.backfill_closes([apple, broken], date(2026, 1, 1), date(2026, 1, 3))

    prices.record_closes.assert_not_called()
    session.commit.assert_not_called()


def test_backfill_closes_skips_an_asset_the_provider_has_no_history_for(
    service: MarketDataService, prices: MagicMock
) -> None:
    unknown = SimpleNamespace(id=3, ticker="GONE")

    assert service.backfill_closes([unknown], date(2026, 1, 1), date(2026, 1, 3)) == 0

    prices.record_closes.assert_not_called()


# --- refresh_currency_rates ---


def test_refresh_currency_rates_records_history_best_effort_per_currency(
    service: MarketDataService,
    currency_repo: MagicMock,
    provider: FakeMarketDataProvider,
    fx_rates: MagicMock,
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
    # The cache of a non-base currency is derived from the history, not assigned.
    assert eur.exchange_rate == Decimal("1")
    fx_rates.record_rate.assert_called_once_with(
        eur,
        usd,
        Decimal("1.08"),
        rate_date=TODAY,
        source="yahoo",
        is_synthetic=True,
    )
    assert gbp.exchange_rate == Decimal("1.2")
    assert xxx.exchange_rate == Decimal("5")
    assert ("fx", "USD", "USD") not in provider.calls
    session.commit.assert_called_once()


def test_refresh_currency_rates_to_another_base_assigns_the_rate_directly(
    service: MarketDataService,
    currency_repo: MagicMock,
    provider: FakeMarketDataProvider,
    fx_rates: MagicMock,
) -> None:
    pln = SimpleNamespace(id=1, code="PLN", exchange_rate=Decimal("1"))
    usd = SimpleNamespace(id=2, code="USD", exchange_rate=Decimal("1"))
    currency_repo.list_all.return_value = [pln, usd]
    provider.rates[("USD", "PLN")] = Decimal("3.9")

    assert service.refresh_currency_rates("PLN") == 2

    assert usd.exchange_rate == Decimal("3.9")
    assert pln.exchange_rate == Decimal("1")
    fx_rates.record_rate.assert_called_once()


def test_refresh_currency_rates_without_the_base_row_still_sets_the_cache(
    service: MarketDataService,
    currency_repo: MagicMock,
    provider: FakeMarketDataProvider,
    fx_rates: MagicMock,
) -> None:
    eur = SimpleNamespace(id=1, code="EUR", exchange_rate=Decimal("1"))
    currency_repo.list_all.return_value = [eur]
    provider.rates[("EUR", "USD")] = Decimal("1.08")

    assert service.refresh_currency_rates() == 1

    assert eur.exchange_rate == Decimal("1.08")
    fx_rates.record_rate.assert_not_called()


# --- data_status ---


def test_data_status_reports_stale_and_priceless_assets(
    service: MarketDataService,
    asset_repo: MagicMock,
    prices: MagicMock,
    fx_rates: MagicMock,
) -> None:
    fresh = SimpleNamespace(id=1, ticker="AAA")
    old = SimpleNamespace(id=2, ticker="BBB")
    none = SimpleNamespace(id=3, ticker="CCC")
    asset_repo.list_all.return_value = [fresh, old, none]
    fetched = datetime(2026, 10, 2, 8, 0, tzinfo=UTC)
    prices.latest_quotes.return_value = {
        1: SimpleNamespace(price_date=TODAY, source="yahoo", stale=False),
        2: SimpleNamespace(price_date=date(2026, 9, 1), source="manual", stale=True),
    }
    prices.last_provider_fetch.return_value = {1: fetched}
    fx_rates.last_provider_fetch.return_value = fetched

    status = service.data_status()

    assert status.fx_last_success_at == fetched
    assert [(a.ticker, a.stale, a.source, a.price_date) for a in status.assets] == [
        ("AAA", False, "yahoo", TODAY),
        ("BBB", True, "manual", date(2026, 9, 1)),
        ("CCC", True, None, None),
    ]
    assert status.assets[0].last_success_at == fetched
    assert status.assets[1].last_success_at is None


def test_data_status_can_list_only_the_problems(
    service: MarketDataService,
    asset_repo: MagicMock,
    prices: MagicMock,
    fx_rates: MagicMock,
) -> None:
    asset_repo.list_all.return_value = [
        SimpleNamespace(id=1, ticker="AAA"),
        SimpleNamespace(id=2, ticker="CCC"),
    ]
    prices.latest_quotes.return_value = {
        1: SimpleNamespace(price_date=TODAY, source="yahoo", stale=False)
    }
    prices.last_provider_fetch.return_value = {}
    fx_rates.last_provider_fetch.return_value = None

    status = service.data_status(only_problems=True)

    assert [a.ticker for a in status.assets] == ["CCC"]


def test_a_price_the_column_cannot_hold_is_skipped_not_fatal(
    service: MarketDataService,
    provider: FakeMarketDataProvider,
    prices: MagicMock,
) -> None:
    tiny = SimpleNamespace(id=1, ticker="TINY", archived_at=None)
    ok = SimpleNamespace(id=2, ticker="OKAY", archived_at=None)
    provider.quotes["TINY"] = make_quote("TINY", current_price=Decimal("3e-11"))
    provider.quotes["OKAY"] = make_quote("OKAY", current_price=Decimal("5"))

    assert service.refresh_asset_prices([tiny, ok]) == 1

    prices.record_closes.assert_called_once()
    assert prices.record_closes.call_args.args[0] is ok


def test_a_database_failure_on_one_asset_does_not_lose_the_others(
    service: MarketDataService,
    provider: FakeMarketDataProvider,
    prices: MagicMock,
    session: MagicMock,
) -> None:
    from sqlalchemy.exc import IntegrityError

    bad = SimpleNamespace(id=1, ticker="BAD", archived_at=None)
    good = SimpleNamespace(id=2, ticker="GOOD", archived_at=None)
    provider.quotes["BAD"] = make_quote("BAD")
    provider.quotes["GOOD"] = make_quote("GOOD")
    prices.record_closes.side_effect = [IntegrityError("x", {}, Exception("c")), 1]

    assert service.refresh_asset_prices([bad, good]) == 1

    session.commit.assert_called_once()
