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
    INTEREST = "interest"
    FEE = "fee"
    SPLIT = "split"


class ImportStatus(StrEnum):
    """Life of an import batch: recorded as operations, undone. `draft` is only
    a preview's state - a draft is never stored."""

    DRAFT = "draft"
    COMMITTED = "committed"
    REVERTED = "reverted"


class ImportRowStatus(StrEnum):
    """What the importer made of one row: record it (`ok`), recorded already
    (`duplicate`), a thing it does not know (`unrecognized`), numbers that do
    not add up (`error`), or nothing to record (`skip`)."""

    OK = "ok"
    DUPLICATE = "duplicate"
    UNRECOGNIZED = "unrecognized"
    ERROR = "error"
    SKIP = "skip"


# Operations that concern one asset (and therefore require one).
ASSET_OPERATIONS: frozenset[OperationType] = frozenset(
    {
        OperationType.BUY,
        OperationType.SELL,
        OperationType.DIVIDEND,
        OperationType.SPLIT,
    }
)
# Operations that move cash in or out of the portfolio (never with an asset).
CASH_OPERATIONS: frozenset[OperationType] = frozenset(
    {OperationType.DEPOSIT, OperationType.WITHDRAWAL}
)
# Operations that move cash without touching deposits or an asset: interest
# earned on free funds and charges (e.g. tax on that interest).
INCOME_COST_OPERATIONS: frozenset[OperationType] = frozenset(
    {OperationType.INTEREST, OperationType.FEE}
)
# Operations that change a position's quantity.
TRADE_OPERATIONS: frozenset[OperationType] = frozenset(
    {OperationType.BUY, OperationType.SELL}
)
