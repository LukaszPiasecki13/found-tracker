"""Public API of the `portfolios` domain layer (ADR-0005).

Pure code: no ORM, no `Session`, no clock, no I/O - only the standard library
(`decimal` money, frozen dataclasses, `StrEnum`). Files are layered (DOM-9):
dictionary (`enums`, `errors`) -> ORM-boundary views (`protocols`) ->
components (`ledger`, `valuation`); imports go only downward, never in a cycle.

Services talk to the domain only through the **components** exported here -
`PortfolioLedger` (validate and apply operations, rebuild from history) and
`PortfolioValuator` (value a portfolio at current prices) - built in
`wiring.py` and injected through constructors (DOM-10). This `__init__.py`
exports only what a consumer outside `domain/` holds in hand: the components,
the values that cross their boundary, the enums and the errors (DOM-11).

Only `services/`, `models/`, `schemas/` (dictionary only: enums), `wiring.py`
and this module's own tests import from `domain/`, and only through this file,
never a submodule (ADR-0006). Vector metrics (numpy) are not here: ADR-0005
variant (a) keeps them in `services/metrics.py`.
"""

from app.modules.portfolios.domain.enums import (
    ASSET_OPERATIONS,
    CASH_OPERATIONS,
    TRADE_OPERATIONS,
    OperationType,
)
from app.modules.portfolios.domain.errors import (
    AssetNotAllowedError,
    AssetRequiredError,
    InsufficientCashError,
    InsufficientQuantityError,
    InvalidOperationError,
    PortfolioDomainError,
    PositionNotFoundError,
)
from app.modules.portfolios.domain.ledger import (
    LedgerState,
    OperationInput,
    PortfolioLedger,
    PositionState,
)
from app.modules.portfolios.domain.valuation import (
    FxMap,
    PortfolioValuation,
    PortfolioValuator,
    PositionValuation,
)

__all__ = [
    "ASSET_OPERATIONS",
    "CASH_OPERATIONS",
    "TRADE_OPERATIONS",
    "AssetNotAllowedError",
    "AssetRequiredError",
    "FxMap",
    "InsufficientCashError",
    "InsufficientQuantityError",
    "InvalidOperationError",
    "LedgerState",
    "OperationInput",
    "OperationType",
    "PortfolioDomainError",
    "PortfolioLedger",
    "PortfolioValuation",
    "PortfolioValuator",
    "PositionNotFoundError",
    "PositionState",
    "PositionValuation",
]
