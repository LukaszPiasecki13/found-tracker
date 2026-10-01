"""Test doubles for the market-data port - no test may reach the network."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from app.core.market_data import MarketDataUnavailableError, Quote


def make_quote(symbol: str = "AAPL", **overrides: Any) -> Quote:
    values: dict[str, Any] = {
        "symbol": symbol,
        "name": "Apple Inc.",
        "exchange": "NMS",
        "quote_type": "EQUITY",
        "currency": "USD",
        "sector": "Technology",
        "current_price": Decimal("190.5"),
        "regular_market_price": Decimal("190.4"),
        "previous_close": Decimal("189.0"),
    }
    values.update(overrides)
    return Quote(**values)


@dataclass
class FakeMarketDataProvider:
    """In-memory `MarketDataProvider`. A symbol or currency code listed in
    `failing` raises `MarketDataUnavailableError`, like a network failure."""

    quotes: dict[str, Quote] = field(default_factory=dict)
    rates: dict[tuple[str, str], Decimal] = field(default_factory=dict)
    history: dict[str, dict[date, Decimal]] = field(default_factory=dict)
    failing: set[str] = field(default_factory=set)
    calls: list[tuple[str, ...]] = field(default_factory=list)

    def _fail_if_listed(self, key: str) -> None:
        if key in self.failing:
            raise MarketDataUnavailableError(f"fake outage for {key}")

    def fetch_quote(self, ticker: str) -> Quote | None:
        self.calls.append(("quote", ticker))
        self._fail_if_listed(ticker)
        return self.quotes.get(ticker)

    def fetch_fx_rate(self, from_code: str, to_code: str) -> Decimal | None:
        self.calls.append(("fx", from_code, to_code))
        self._fail_if_listed(from_code)
        return self.rates.get((from_code, to_code))

    def fetch_close_history(
        self, ticker: str, start: date, end: date
    ) -> dict[date, Decimal]:
        self.calls.append(("history", ticker))
        self._fail_if_listed(ticker)
        return {
            day: close
            for day, close in self.history.get(ticker, {}).items()
            if start <= day < end
        }
