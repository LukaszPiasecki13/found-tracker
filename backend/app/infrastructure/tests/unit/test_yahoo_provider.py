"""`YahooFinanceProvider` with `yfinance.Ticker` replaced - never hits the network."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, ClassVar

import pandas as pd
import pytest

from app.core.market_data import MarketDataUnavailableError
from app.infrastructure.market_data import yahoo
from app.infrastructure.market_data.yahoo import YahooFinanceProvider


class FakeTicker:
    """Stands in for `yfinance.Ticker`; class attributes configure every instance."""

    infos: ClassVar[dict[str, Any]] = {}
    frame: ClassVar[pd.DataFrame | None] = None
    error: ClassVar[Exception | None] = None
    requested: ClassVar[list[str]] = []
    history_kwargs: ClassVar[dict[str, Any]] = {}

    def __init__(self, symbol: str) -> None:
        FakeTicker.requested.append(symbol)
        self.symbol = symbol

    @property
    def info(self) -> Any:
        if FakeTicker.error is not None:
            raise FakeTicker.error
        return FakeTicker.infos.get(self.symbol, {"trailingPegRatio": None})

    def history(self, **kwargs: Any) -> pd.DataFrame | None:
        FakeTicker.history_kwargs = kwargs
        if FakeTicker.error is not None:
            raise FakeTicker.error
        return FakeTicker.frame


@pytest.fixture(autouse=True)
def fake_ticker(monkeypatch: pytest.MonkeyPatch) -> type[FakeTicker]:
    FakeTicker.infos = {}
    FakeTicker.frame = None
    FakeTicker.error = None
    FakeTicker.requested = []
    FakeTicker.history_kwargs = {}
    monkeypatch.setattr(yahoo.yf, "Ticker", FakeTicker)
    return FakeTicker


@pytest.fixture
def provider() -> YahooFinanceProvider:
    return YahooFinanceProvider()


# --- fetch_quote ---


def test_fetch_quote_maps_the_info_payload(provider: YahooFinanceProvider) -> None:
    FakeTicker.infos["AAPL"] = {
        "symbol": "AAPL",
        "longName": "Apple Inc.",
        "shortName": "Apple",
        "exchange": "NMS",
        "quoteType": "EQUITY",
        "currency": "USD",
        "sector": "Technology",
        "currentPrice": 0.1,
        "regularMarketPrice": 190,
        "previousClose": "189.5",
    }

    quote = provider.fetch_quote("AAPL")

    assert quote is not None
    assert (quote.symbol, quote.name, quote.exchange) == ("AAPL", "Apple Inc.", "NMS")
    assert (quote.quote_type, quote.currency, quote.sector) == (
        "EQUITY",
        "USD",
        "Technology",
    )
    # Through `str`, so 0.1 is exactly 0.1 - not Decimal(0.1)'s binary expansion.
    assert quote.current_price == Decimal("0.1")
    assert quote.regular_market_price == Decimal("190")
    assert quote.previous_close == Decimal("189.5")


def test_fetch_quote_tolerates_missing_and_non_numeric_fields(
    provider: YahooFinanceProvider,
) -> None:
    FakeTicker.infos["XYZ"] = {
        "symbol": "XYZ",
        "shortName": "Xyz Corp",
        "currentPrice": float("nan"),
        "regularMarketPrice": "n/a",
        "previousClose": True,
    }

    quote = provider.fetch_quote("XYZ")

    assert quote is not None
    assert quote.name == "Xyz Corp"
    assert (quote.exchange, quote.quote_type, quote.currency, quote.sector) == (
        "",
        "",
        "",
        "",
    )
    assert quote.current_price is None
    assert quote.regular_market_price is None
    assert quote.previous_close is None
    assert quote.price is None


def test_fetch_quote_of_unknown_symbol_is_none(provider: YahooFinanceProvider) -> None:
    assert provider.fetch_quote("NOPE") is None


def test_fetch_quote_wraps_library_errors(provider: YahooFinanceProvider) -> None:
    FakeTicker.error = ConnectionError("network down")

    with pytest.raises(MarketDataUnavailableError) as exc_info:
        provider.fetch_quote("AAPL")

    assert exc_info.value.status_code == 502
    assert exc_info.value.code == "MARKET_DATA_UNAVAILABLE"
    assert isinstance(exc_info.value.__cause__, ConnectionError)


def test_fetch_quote_wraps_errors_raised_by_the_ticker_constructor(
    provider: YahooFinanceProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken_ticker(symbol: str) -> None:
        raise ValueError("bad symbol")

    monkeypatch.setattr(yahoo.yf, "Ticker", broken_ticker)

    with pytest.raises(MarketDataUnavailableError):
        provider.fetch_quote("AAPL")


# --- fetch_fx_rate ---


def test_fetch_fx_rate_uses_the_pair_symbol_and_first_non_zero_value(
    provider: YahooFinanceProvider,
) -> None:
    FakeTicker.infos["EURUSD=X"] = {
        "bid": 0,
        "regularMarketPrice": 1.0842,
        "previousClose": 1.08,
    }

    assert provider.fetch_fx_rate("EUR", "USD") == Decimal("1.0842")
    assert FakeTicker.requested == ["EURUSD=X"]


def test_fetch_fx_rate_without_data_is_none(provider: YahooFinanceProvider) -> None:
    assert provider.fetch_fx_rate("ABC", "USD") is None


def test_fetch_fx_rate_wraps_library_errors(provider: YahooFinanceProvider) -> None:
    FakeTicker.error = RuntimeError("rate limited")

    with pytest.raises(MarketDataUnavailableError):
        provider.fetch_fx_rate("EUR", "USD")


# --- fetch_close_history ---


def test_fetch_close_history_is_end_exclusive_and_drops_gaps(
    provider: YahooFinanceProvider,
) -> None:
    index = pd.DatetimeIndex(
        [
            "2026-01-05 00:00:00-05:00",
            "2026-01-06 00:00:00-05:00",
            "2026-01-07 00:00:00-05:00",
            "2026-01-08 00:00:00-05:00",
        ]
    )
    FakeTicker.frame = pd.DataFrame(
        {"Close": [101.1, float("nan"), 103.3, 104.4]}, index=index
    )

    closes = provider.fetch_close_history("AAPL", date(2026, 1, 5), date(2026, 1, 8))

    assert closes == {
        date(2026, 1, 5): Decimal("101.1"),
        date(2026, 1, 7): Decimal("103.3"),
    }
    assert FakeTicker.history_kwargs == {
        "start": date(2026, 1, 5),
        "end": date.today() + timedelta(days=1),
        "interval": "1d",
        "auto_adjust": False,
        "actions": True,
    }


@pytest.mark.parametrize(
    "frame", [None, pd.DataFrame(), pd.DataFrame({"Open": [1.0]}, index=[0])]
)
def test_fetch_close_history_without_closes_is_empty(
    provider: YahooFinanceProvider, frame: pd.DataFrame | None
) -> None:
    FakeTicker.frame = frame

    assert (
        provider.fetch_close_history("AAPL", date(2026, 1, 1), date(2026, 2, 1)) == {}
    )


def test_fetch_close_history_wraps_library_errors(
    provider: YahooFinanceProvider,
) -> None:
    FakeTicker.error = TimeoutError("slow")

    with pytest.raises(MarketDataUnavailableError) as exc_info:
        provider.fetch_close_history("AAPL", date(2026, 1, 1), date(2026, 2, 1))

    assert isinstance(exc_info.value.__cause__, TimeoutError)


def test_fetch_fx_close_history_uses_the_pair_symbol_and_is_end_exclusive(
    provider: YahooFinanceProvider,
) -> None:
    index = pd.DatetimeIndex(
        [
            "2026-01-05 00:00:00+01:00",
            "2026-01-06 00:00:00+01:00",
            "2026-01-07 00:00:00+01:00",
        ]
    )
    FakeTicker.frame = pd.DataFrame({"Close": [3.61, float("nan"), 3.7]}, index=index)

    rates = provider.fetch_fx_close_history(
        "USD", "PLN", date(2026, 1, 5), date(2026, 1, 7)
    )

    assert rates == {date(2026, 1, 5): Decimal("3.61")}
    assert FakeTicker.requested == ["USDPLN=X"]
    assert FakeTicker.history_kwargs == {
        "start": date(2026, 1, 5),
        "end": date(2026, 1, 7),
        "interval": "1d",
        "auto_adjust": False,
    }


def test_fetch_fx_close_history_wraps_library_errors(
    provider: YahooFinanceProvider,
) -> None:
    FakeTicker.error = TimeoutError("slow")

    with pytest.raises(MarketDataUnavailableError) as exc_info:
        provider.fetch_fx_close_history(
            "EUR", "PLN", date(2026, 1, 1), date(2026, 2, 1)
        )

    assert isinstance(exc_info.value.__cause__, TimeoutError)


def _closes_frame(
    prices: list[float], days: list[str], splits: list[float] | None = None
) -> pd.DataFrame:
    index = pd.DatetimeIndex(
        [f"{day} 00:00:00+02:00" for day in days], tz="Europe/Warsaw"
    )
    frame = pd.DataFrame({"Close": prices}, index=index)
    if splits is not None:
        frame["Stock Splits"] = splits
    return frame


def test_closes_before_a_split_are_returned_in_the_units_of_their_day(
    provider: YahooFinanceProvider,
) -> None:
    # Yahoo's Close is split-adjusted even with auto_adjust=False: the 10:1 split
    # of 31 July made the earlier ~500 look like ~50. Raw prices are restored.
    FakeTicker.frame = _closes_frame(
        [50.2, 49.61, 47.51],
        ["2025-07-30", "2025-07-31", "2025-08-01"],
        splits=[0.0, 10.0, 0.0],
    )

    closes = provider.fetch_close_history("DNP.WA", date(2025, 7, 30), date(2025, 8, 2))

    assert closes == {
        date(2025, 7, 30): Decimal("502.0"),
        date(2025, 7, 31): Decimal("49.61"),  # the split day trades post-split
        date(2025, 8, 1): Decimal("47.51"),
    }


def test_a_split_after_end_still_rescales_the_closes_before_it(
    provider: YahooFinanceProvider,
) -> None:
    # The window ends on 31 July, the split is on 31 July: it lies outside the
    # requested range but the window is fetched up to today, so 30 July is raw.
    FakeTicker.frame = _closes_frame(
        [50.0, 49.0], ["2025-07-30", "2025-07-31"], splits=[0.0, 10.0]
    )

    closes = provider.fetch_close_history(
        "DNP.WA", date(2025, 7, 30), date(2025, 7, 31)
    )

    assert closes == {date(2025, 7, 30): Decimal("500.0")}


def test_several_later_splits_multiply(provider: YahooFinanceProvider) -> None:
    # Two splits: one inside the range, one after it (both come from the window).
    FakeTicker.frame = _closes_frame(
        [10.0, 10.0, 10.0],
        ["2021-07-19", "2021-07-20", "2024-06-10"],
        splits=[0.0, 4.0, 10.0],
    )

    closes = provider.fetch_close_history("NVDA", date(2021, 7, 19), date(2021, 7, 21))

    # The 19th precedes both splits (x40); the 20th is after the first (x10).
    assert closes == {
        date(2021, 7, 19): Decimal("400.0"),
        date(2021, 7, 20): Decimal("100.0"),
    }
