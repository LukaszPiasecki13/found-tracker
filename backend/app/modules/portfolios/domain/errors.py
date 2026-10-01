"""Domain errors of the portfolio ledger.

Level 0 of the domain (DOM-9). Every error is a `ValueError` (ADR-0005: an
invariant violation, no dependency on `app.core`) and carries a stable machine
`code`, so a service translates any of them generically into a
`BadRequestError(str(err), code=err.code)` - the domain knows nothing of HTTP.
"""

from decimal import Decimal
from typing import ClassVar


class PortfolioDomainError(ValueError):
    """Base of every portfolio ledger error."""

    code: ClassVar[str] = "INVALID_OPERATION"


class InvalidOperationError(PortfolioDomainError):
    """A field of the operation breaks a sign or relationship rule, or the
    operation type is unknown."""

    code: ClassVar[str] = "INVALID_OPERATION"

    def __init__(self, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field


class AssetRequiredError(PortfolioDomainError):
    code: ClassVar[str] = "OPERATION_REQUIRES_ASSET"

    def __init__(self, operation_type: str) -> None:
        super().__init__(f"'{operation_type}' requires an asset")


class AssetNotAllowedError(PortfolioDomainError):
    code: ClassVar[str] = "OPERATION_FORBIDS_ASSET"

    def __init__(self, operation_type: str) -> None:
        super().__init__(f"'{operation_type}' should not have an asset")


class InsufficientCashError(PortfolioDomainError):
    code: ClassVar[str] = "INSUFFICIENT_CASH"

    def __init__(self, available: Decimal, required: Decimal) -> None:
        super().__init__(
            f"Insufficient cash balance. Available: {available}, Required: {required}"
        )
        self.available = available
        self.required = required


class InsufficientQuantityError(PortfolioDomainError):
    code: ClassVar[str] = "INSUFFICIENT_QUANTITY"

    def __init__(self, held: Decimal, requested: Decimal) -> None:
        super().__init__(
            f"Insufficient quantity. Have {held}, trying to sell {requested}"
        )
        self.held = held
        self.requested = requested


class PositionNotFoundError(PortfolioDomainError):
    """A sell or dividend for an asset the portfolio holds no position in."""

    code: ClassVar[str] = "POSITION_NOT_FOUND"

    def __init__(self, operation_type: str, asset_id: int) -> None:
        super().__init__(
            f"'{operation_type}' needs an open position in asset {asset_id}"
        )
        self.asset_id = asset_id
