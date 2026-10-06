"""Yahoo Finance adapter (`yfinance`) for the `MarketDataProvider` port."""

from datetime import date, datetime, timedelta
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
        """Daily closes for `start <= day < end` in the units of each day.

        Yahoo's `Close` is adjusted for splits even with `auto_adjust=False` (only
        dividends are left alone): after a 10:1 split every earlier close is a tenth
        of what the stock traded at. A ledger holds the quantities of the day, so
        each close is multiplied back by the splits that came after it - the raw
        price, which also never changes when a later split happens (ADR-0015).

        Decision DEC-02: Fetch splits from the `Stock Splits` column in the
        history response (with `actions=True`), not from `handle.splits`."""
        try:
            handle = yf.Ticker(ticker)
            # `auto_adjust=False`: a dividend-adjusted close would count a payout
            # twice next to the dividend operation.
            # `actions=True`: the `Stock Splits` column carries the splits. The window
            # reaches today, not just `end`: a split after `end` still rescales the
            # closes before it (DEC-02, ADR-0015), and the rows from `end` on are
            # dropped below.
            frame = handle.history(
                start=start,
                end=max(end, date.today() + timedelta(days=1)),
                interval="1d",
                auto_adjust=False,
                actions=True,
            )
            if frame is None or frame.empty or "Close" not in frame.columns:
                return {}
            splits = self._splits_from_frame(frame)
        except Exception as exc:
            raise MarketDataUnavailableError(
                f"Could not fetch price history for {ticker}"
            ) from exc

        closes: dict[date, Decimal] = {}
        for stamp, value in frame["Close"].items():
            # Exchange-local calendar day: drop the time zone, keep the wall date.
            day = stamp.date() if isinstance(stamp, datetime) else stamp
            close = _to_decimal(value)
            # `end` is exclusive by contract, whatever the library returns.
            if close is None or not isinstance(day, date) or not start <= day < end:
                continue
            for split_day, ratio in splits:
                if split_day > day:
                    close *= ratio
            closes[day] = close
        return closes

    def fetch_fx_close_history(
        self, from_code: str, to_code: str, start: date, end: date
    ) -> dict[date, Decimal]:
        """Daily rates for `start <= day < end` (`end` exclusive). Yahoo quotes a
        pair as `<from><to>=X`, e.g. `USDPLN=X`, in units of `to` per one `from`;
        a currency pair has no splits, so the close is the rate as it stood."""
        symbol = f"{from_code}{to_code}=X"
        try:
            frame = yf.Ticker(symbol).history(
                start=start, end=end, interval="1d", auto_adjust=False
            )
        except Exception as exc:
            raise MarketDataUnavailableError(
                f"Could not fetch FX history for {symbol}"
            ) from exc
        if frame is None or frame.empty or "Close" not in frame.columns:
            return {}

        rates: dict[date, Decimal] = {}
        for stamp, value in frame["Close"].items():
            day = stamp.date() if isinstance(stamp, datetime) else stamp
            rate = _to_decimal(value)
            if rate is None or not isinstance(day, date) or not start <= day < end:
                continue
            rates[day] = rate
        return rates

    @staticmethod
    def _splits_from_frame(frame: Any) -> list[tuple[date, Decimal]]:
        """Every split in the window as (day, ratio new:old) from the `Stock
        Splits` column in the history response (Decision DEC-02)."""
        if frame is None or "Stock Splits" not in getattr(frame, "columns", ()):
            return []
        column = frame["Stock Splits"]
        series = column[column > 0]
        splits: list[tuple[date, Decimal]] = []
        for stamp, value in series.items():
            ratio = _to_decimal(value)
            day = stamp.date() if isinstance(stamp, datetime) else stamp
            if ratio is not None and ratio > 0 and isinstance(day, date):
                splits.append((day, ratio))
        return splits

    @staticmethod
    def _info(symbol: str) -> dict[str, Any]:
        try:
            info = yf.Ticker(symbol).info
        except Exception as exc:
            raise MarketDataUnavailableError(
                f"Could not fetch market data for {symbol}"
            ) from exc
        return info if isinstance(info, dict) else {}
