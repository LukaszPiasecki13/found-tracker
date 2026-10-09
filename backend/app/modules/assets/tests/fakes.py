"""Test doubles for the market-data port - no test may reach the network."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from app.core.errors import BondDataUnavailableError
from app.core.market_data import BondTerms, MarketDataUnavailableError, Quote


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
    fx_history: dict[tuple[str, str], dict[date, Decimal]] = field(default_factory=dict)
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

    def fetch_fx_close_history(
        self, from_code: str, to_code: str, start: date, end: date
    ) -> dict[date, Decimal]:
        self.calls.append(("fx_history", from_code, to_code))
        self._fail_if_listed(from_code)
        return {
            day: rate
            for day, rate in self.fx_history.get((from_code, to_code), {}).items()
            if start <= day < end
        }


def make_bond_terms(series_code: str = "EDO1036", **overrides: Any) -> BondTerms:
    values: dict[str, Any] = {
        "bond_symbol": "EDO",
        "series_code": series_code,
        "nominal_value": Decimal("100.00"),
        "issue_date": date(2026, 10, 1),
        "maturity_date": date(2036, 10, 1),
        "capitalization": "annual",
        "first_period_rate": Decimal("5.35"),
        "reference_type": "cpi",
        "margin": Decimal("2.00"),
        "redemption_fee": Decimal("3.00"),
    }
    values.update(overrides)
    return BondTerms(**values)


@dataclass
class FakeBondDataProvider:
    """In-memory `BondDataProvider`. A series code listed in `failing` raises
    `BondDataUnavailableError`, like a network failure."""

    series: dict[str, BondTerms] = field(default_factory=dict)
    reference_rate: Decimal = Decimal("3.75")
    cpi_history: dict[date, Decimal] = field(default_factory=dict)
    failing: set[str] = field(default_factory=set)
    calls: list[tuple[str, ...]] = field(default_factory=list)

    def fetch_series(self, symbol: str) -> BondTerms | None:
        self.calls.append(("series", symbol))
        if symbol in self.failing:
            raise BondDataUnavailableError(f"fake outage for {symbol}")
        return self.series.get(symbol)

    def fetch_reference_rate(self) -> Decimal:
        self.calls.append(("reference_rate",))
        if "reference_rate" in self.failing:
            raise BondDataUnavailableError("fake outage for reference rate")
        return self.reference_rate

    def fetch_cpi(self) -> Decimal | None:
        self.calls.append(("cpi",))
        if "cpi" in self.failing:
            raise BondDataUnavailableError("fake outage for cpi")
        if not self.cpi_history:
            return None
        return self.cpi_history[max(self.cpi_history)]

    def fetch_cpi_history(self) -> dict[date, Decimal]:
        self.calls.append(("cpi_history",))
        if "cpi" in self.failing:
            raise BondDataUnavailableError("fake outage for cpi")
        return dict(self.cpi_history)
