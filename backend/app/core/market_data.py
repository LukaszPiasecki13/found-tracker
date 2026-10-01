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


class MarketDataUnavailableError(APIError):
    """The market-data provider failed (network, rate limit, unexpected payload)."""

    def __init__(self, message: str = "Market data provider is unavailable") -> None:
        super().__init__(
            message,
            status.HTTP_502_BAD_GATEWAY,
            code="MARKET_DATA_UNAVAILABLE",
        )
