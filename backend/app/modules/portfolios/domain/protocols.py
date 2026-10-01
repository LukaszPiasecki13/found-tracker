"""Read-only views of the ORM rows the domain works on (DOM-8).

Level 1 of the domain (DOM-9). `Operation`, `Position`, `Portfolio`, `Asset`
and `Currency` (ORM) satisfy these structurally: the domain reads attributes,
never imports a model, never adds behaviour to one.
"""

from decimal import Decimal
from typing import Protocol


class OperationLike(Protocol):
    """What the ledger reads from a recorded operation."""

    @property
    def operation_type(self) -> str: ...
    @property
    def asset_id(self) -> int | None: ...
    @property
    def quantity(self) -> Decimal: ...
    @property
    def price(self) -> Decimal: ...
    @property
    def amount(self) -> Decimal | None: ...
    @property
    def fee(self) -> Decimal: ...
    @property
    def fx_rate(self) -> Decimal: ...


class PositionLike(Protocol):
    """What the ledger reads from a stored position."""

    @property
    def asset_id(self) -> int: ...
    @property
    def quantity(self) -> Decimal: ...
    @property
    def average_buy_price(self) -> Decimal: ...
    @property
    def average_fx_rate(self) -> Decimal: ...
    @property
    def total_fees(self) -> Decimal: ...
    @property
    def total_dividends(self) -> Decimal: ...


class PortfolioBalanceLike(Protocol):
    """A portfolio's cash figures."""

    @property
    def cash_balance(self) -> Decimal: ...
    @property
    def total_deposited(self) -> Decimal: ...


class CurrencyRateLike(Protocol):
    @property
    def exchange_rate(self) -> Decimal: ...


class QuotedAssetLike(Protocol):
    """An asset with its current price and quote currency."""

    @property
    def current_price(self) -> Decimal: ...
    @property
    def currency_id(self) -> int: ...
    @property
    def currency(self) -> CurrencyRateLike: ...


class HoldingLike(Protocol):
    """A position as the valuator sees it: amounts plus the quoted asset."""

    @property
    def quantity(self) -> Decimal: ...
    @property
    def average_buy_price(self) -> Decimal: ...
    @property
    def average_fx_rate(self) -> Decimal: ...
    @property
    def total_fees(self) -> Decimal: ...
    @property
    def asset(self) -> QuotedAssetLike: ...


class ValuedPortfolioLike(Protocol):
    """A portfolio as the valuator sees it."""

    @property
    def base_currency_id(self) -> int: ...
    @property
    def cash_balance(self) -> Decimal: ...
    @property
    def total_deposited(self) -> Decimal: ...
