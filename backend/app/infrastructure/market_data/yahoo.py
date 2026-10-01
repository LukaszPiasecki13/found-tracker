"""Yahoo Finance adapter (`yfinance`) for the `MarketDataProvider` port."""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import yfinance as yf

from app.core.market_data import MarketDataUnavailableError, Quote


def _to_decimal(value: object) -> Decimal | None:
    """Provider number -> `Decimal` via `str` (never `Decimal(float)`, ADR-0010);
    missing, non-numeric, NaN and infinite values become `None`."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except InvalidOperation, ValueError:
        return None
    return number if number.is_finite() else None


def _to_text(value: object) -> str:
    return "" if value is None else str(value)


class YahooFinanceProvider:
    """`MarketDataProvider` backed by Yahoo Finance.

    Every `yfinance` or network exception is re-raised as
    `MarketDataUnavailableError`, so callers never see library-specific errors.
    """

    def fetch_quote(self, ticker: str) -> Quote | None:
        info = self._info(ticker)
        symbol = info.get("symbol")
        if not symbol:
            return None
        return Quote(
            symbol=str(symbol),
            name=_to_text(info.get("longName") or info.get("shortName")),
            exchange=_to_text(info.get("exchange")),
            quote_type=_to_text(info.get("quoteType")),
            currency=_to_text(info.get("currency")),
            sector=_to_text(info.get("sector")),
            current_price=_to_decimal(info.get("currentPrice")),
            regular_market_price=_to_decimal(info.get("regularMarketPrice")),
            previous_close=_to_decimal(info.get("previousClose")),
        )

    def fetch_fx_rate(self, from_code: str, to_code: str) -> Decimal | None:
        info = self._info(f"{from_code}{to_code}=X")
        for key in ("bid", "regularMarketPrice", "previousClose"):
            rate = _to_decimal(info.get(key))
            if rate:
                return rate
        return None

    def fetch_close_history(
        self, ticker: str, start: date, end: date
    ) -> dict[date, Decimal]:
        try:
            frame = yf.Ticker(ticker).history(start=start, end=end, interval="1d")
        except Exception as exc:
            raise MarketDataUnavailableError(
                f"Could not fetch price history for {ticker}"
            ) from exc
        if frame is None or frame.empty or "Close" not in frame.columns:
            return {}

        closes: dict[date, Decimal] = {}
        for stamp, value in frame["Close"].items():
            # Exchange-local calendar day: drop the time zone, keep the wall date.
            day = stamp.date() if isinstance(stamp, datetime) else stamp
            close = _to_decimal(value)
            # `end` is exclusive by contract, whatever the library returns.
            if close is None or not isinstance(day, date) or not start <= day < end:
                continue
            closes[day] = close
        return closes

    @staticmethod
    def _info(symbol: str) -> dict[str, Any]:
        try:
            info = yf.Ticker(symbol).info
        except Exception as exc:
            raise MarketDataUnavailableError(
                f"Could not fetch market data for {symbol}"
            ) from exc
        return info if isinstance(info, dict) else {}
