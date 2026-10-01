"""Closed catalogs of the portfolios domain.

Level 0 of the domain (DOM-9): the dictionary - imports nothing from `domain/`.
"""

from enum import StrEnum


class OperationType(StrEnum):
    BUY = "buy"
    SELL = "sell"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    DIVIDEND = "dividend"


# Operations that concern one asset (and therefore require one).
ASSET_OPERATIONS: frozenset[OperationType] = frozenset(
    {OperationType.BUY, OperationType.SELL, OperationType.DIVIDEND}
)
# Operations that move cash in or out of the portfolio (never with an asset).
CASH_OPERATIONS: frozenset[OperationType] = frozenset(
    {OperationType.DEPOSIT, OperationType.WITHDRAWAL}
)
# Operations that change a position's quantity.
TRADE_OPERATIONS: frozenset[OperationType] = frozenset(
    {OperationType.BUY, OperationType.SELL}
)
