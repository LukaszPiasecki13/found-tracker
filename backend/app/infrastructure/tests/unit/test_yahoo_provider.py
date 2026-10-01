"""`YahooFinanceProvider` with `yfinance.Ticker` replaced - never hits the network."""

from datetime import date
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
        "end": date(2026, 1, 8),
        "interval": "1d",
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
