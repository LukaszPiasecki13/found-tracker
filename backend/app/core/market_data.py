"""Market-data contract shared by business modules (port, no business logic).

Services depend on `MarketDataProvider`; the adapter that talks to the outside
world lives in `app.infrastructure.market_data` and is injected by a module's
`wiring.py`, so services stay testable without network access.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

from fastapi import status

from app.core.errors import APIError


@dataclass(frozen=True, slots=True)
class Quote:
    """One instrument as the provider describes it.

    Text fields the provider did not report are empty strings; prices it did not
    report (or reported as non-numbers) are `None`.
    """

    symbol: str
    name: str
    exchange: str
    quote_type: str
    currency: str
    sector: str
    current_price: Decimal | None
    regular_market_price: Decimal | None
    previous_close: Decimal | None

    @property
    def price(self) -> Decimal | None:
        """The instrument's current price: the first non-zero of the current
        price, the regular-market price and the previous close."""
        for candidate in (
            self.current_price,
            self.regular_market_price,
            self.previous_close,
        ):
            if candidate:
                return candidate
        return None


class MarketDataProvider(Protocol):
    """Read contract of an external market-data source.

    Every provider or network failure is raised as `MarketDataUnavailableError`;
    "the provider has no such instrument" is `None`/empty, not an error.
    """

    def fetch_quote(self, ticker: str) -> Quote | None:
        """Quote for `ticker`, or `None` when the provider knows no such symbol."""
        ...

    def fetch_fx_rate(self, from_code: str, to_code: str) -> Decimal | None:
        """Units of `to_code` per one unit of `from_code`, or `None` when unknown."""
        ...

    def fetch_close_history(
        self, ticker: str, start: date, end: date
    ) -> dict[date, Decimal]:
        """Daily closing prices for `start <= day < end` (`end` exclusive).

        Days without a close (holidays, missing data) are absent from the result.
        """
        ...

    def fetch_fx_close_history(
        self, from_code: str, to_code: str, start: date, end: date
    ) -> dict[date, Decimal]:
        """Daily rates of `to_code` per one unit of `from_code` for
        `start <= day < end` (`end` exclusive). Days without a rate are absent."""
        ...


class MarketDataUnavailableError(APIError):
    """The market-data provider failed (network, rate limit, unexpected payload)."""

    def __init__(self, message: str = "Market data provider is unavailable") -> None:
        super().__init__(
            message,
            status.HTTP_502_BAD_GATEWAY,
            code="MARKET_DATA_UNAVAILABLE",
        )


@dataclass(frozen=True, slots=True)
class BondTerms:
    """Bond series terms (port, not ORM). Parameters needed to calculate accrual.

    Used by BondDataProvider implementations to return bond series metadata.
    """

    bond_symbol: str  # OTS, ROR, DOR, TOS, COI, EDO, ROS, ROD
    series_code: str  # e.g., "EDO1036"
    nominal_value: Decimal  # Par value, e.g., 100.00
    issue_date: date
    maturity_date: date
    capitalization: str  # "none" / "monthly" / "annual"
    first_period_rate: Decimal | None  # Fixed rate for first period, nullable
    reference_type: str | None  # "fixed" / "nbp_reference" / "cpi", nullable
    margin: Decimal | None  # Margin over reference rate/CPI, nullable
    redemption_fee: Decimal  # Early redemption fee in PLN per bond


class BondDataProvider(Protocol):
    """Read contract of a bond-data source.

    Returns bond series parameters or None; provider failures are raised as
    BondDataUnavailableError (network, format error, etc).
    """

    def fetch_series(self, symbol: str) -> BondTerms | None:
        """Bond terms for `symbol`, or `None` when series is unknown."""
        ...

    def fetch_reference_rate(self) -> Decimal:
        """Current NBP reference rate (percent per year). ROR/DOR key their
        coupon off it, but pay that coupon out in cash rather than
        capitalizing it into price, so `accrue_interest` does not consume
        this value; reserved for a future coupon-amount calculator."""
        ...

    def fetch_cpi(self) -> Decimal | None:
        """Most recently published monthly CPI y/y (percent), used by
        COI/EDO/ROS/ROD. `None` if none is published yet."""
        ...

    def fetch_cpi_history(self) -> dict[date, Decimal]:
        """Every published monthly CPI y/y (percent), keyed by that month's
        first day - a multi-year EDO/ROS/ROD must look up each
        capitalization year's own reading, not one "current" value."""
        ...
