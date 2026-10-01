"""Operations: recording, editing and deleting them, and keeping the
portfolio's cash and positions consistent with them.

`OperationService` is the orchestrator of a multi-module unit of work
(ADR-0008): recording a buy of an unknown ticker creates the asset through
`AssetService`'s no-commit core and commits it together with the operation, the
new cash balance and the position - or rolls all of it back.
"""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager

from sqlalchemy.exc import IntegrityError

from app.modules.assets.services.assets import AssetService
from app.modules.portfolios.domain import (
    LedgerState,
    OperationInput,
    PortfolioDomainError,
    PortfolioLedger,
)
from app.modules.portfolios.exceptions import (
    AssetClassRequiredError,
    ConcurrentChangeError,
    OperationRejectedError,
    UnknownAssetError,
)
from app.modules.portfolios.models import Operation, Portfolio, Position
from app.modules.portfolios.repositories.operations import OperationRepository
from app.modules.portfolios.repositories.portfolios import PortfolioRepository
from app.modules.portfolios.repositories.positions import PositionRepository
from app.modules.portfolios.schemas.operations import (
    OperationCreateRequest,
    OperationUpdateRequest,
)

# `OperationUpdateRequest` fields that are NOT NULL columns: `null` = unchanged.
_NULLABLE_UPDATE_FIELDS = frozenset({"notes"})


@contextmanager
def _ledger_errors_rejected() -> Iterator[None]:
    """The one translation of the ledger's verdict for the client: a
    `PortfolioDomainError` becomes a 400 carrying the domain's `code`."""
    try:
        yield
    except PortfolioDomainError as err:
        raise OperationRejectedError(str(err), err.code) from err


class OperationService:
    """Operations of the owner's portfolios; another owner's operation or
    portfolio is reported as not found (404).

    Every write is one transaction. The ledger's verdict (`PortfolioLedger`) is
    the only validation of an operation's numbers; its errors reach the client
    as `OperationRejectedError` (400) with the domain's `code`.
    """

    def __init__(
        self,
        portfolio_repo: PortfolioRepository,
        position_repo: PositionRepository,
        operation_repo: OperationRepository,
        asset_service: AssetService,
        ledger: PortfolioLedger,
    ) -> None:
        self._portfolio_repo = portfolio_repo
        self._position_repo = position_repo
        self._operation_repo = operation_repo
        self._assets = asset_service
        self._ledger = ledger

    # --- Reads ---

    def list_operations(
        self, owner_id: int, portfolio_name: str | None = None
    ) -> list[Operation]:
        """The owner's operations, newest first; `portfolio_name` narrows."""
        return self._operation_repo.list_by_owner(owner_id, portfolio_name)

    # --- Writes ---

    def record(self, data: OperationCreateRequest, owner_id: int) -> Operation:
        """Apply a new operation to the portfolio's current state and store it.

        Raises PortfolioNotFoundError, UnknownAssetError,
        AssetClassRequiredError, OperationRejectedError (ledger rules,
        insufficient cash or quantity); nothing is stored then - including an
        asset created for an unknown ticker. A unique-constraint race with a
        concurrent writer (same new ticker, class or currency) is a
        ConcurrentChangeError (409).
        """
        try:
            return self._record(data, owner_id)
        except IntegrityError as err:
            raise ConcurrentChangeError from err

    def _record(self, data: OperationCreateRequest, owner_id: int) -> Operation:
        with self._operation_repo.transaction():
            portfolio = self._portfolio_repo.get_owned(data.portfolio_id, owner_id)
            asset_id = self._resolve_asset_id(data, portfolio)
            positions = self._position_repo.list_by_portfolio(portfolio.id)
            operation = OperationInput(
                operation_type=data.operation_type,
                asset_id=asset_id,
                quantity=data.quantity,
                price=data.price,
                amount=data.amount,
                fee=data.fee,
                fx_rate=data.fx_rate,
            )
            state = self._apply(LedgerState.of(portfolio, positions), operation)
            self._store_state(portfolio, positions, state)
            return self._operation_repo.create(
                portfolio_id=portfolio.id,
                asset_id=asset_id,
                operation_type=data.operation_type.value,
                quantity=data.quantity,
                price=data.price,
                amount=data.amount,
                fee=data.fee,
                fx_rate=data.fx_rate,
                notes=data.notes,
                operation_date=data.operation_date,
            )

    def update(
        self, operation_id: int, data: OperationUpdateRequest, owner_id: int
    ) -> Operation:
        """Change the given fields, then rebuild the portfolio from its whole
        history. Raises OperationNotFoundError, OperationRejectedError (the
        resulting history breaks a ledger rule - nothing is stored)."""
        values = {
            field: value
            for field, value in data.model_dump(exclude_unset=True).items()
            if value is not None or field in _NULLABLE_UPDATE_FIELDS
        }
        with self._operation_repo.transaction():
            operation = self._operation_repo.get_owned(operation_id, owner_id)
            for field, value in values.items():
                setattr(operation, field, value)
            operation = self._operation_repo.update(operation)
            self._rebuild(operation.portfolio_id, owner_id)
            return operation

    def delete(self, operation_id: int, owner_id: int) -> None:
        """Delete the operation, then rebuild the portfolio from the remaining
        history. Raises OperationNotFoundError, OperationRejectedError (e.g.
        deleting a deposit later buys depended on - nothing is deleted)."""
        with self._operation_repo.transaction():
            operation = self._operation_repo.get_owned(operation_id, owner_id)
            portfolio_id = operation.portfolio_id
            self._operation_repo.delete(operation)
            self._rebuild(portfolio_id, owner_id)

    # --- Helpers ---

    def _resolve_asset_id(
        self, data: OperationCreateRequest, portfolio: Portfolio
    ) -> int | None:
        """`asset_id` if it names an asset; else the asset with `ticker`,
        created (no-commit core, ADR-0008) in class `asset_class` and the
        portfolio's base currency when unknown; else no asset."""
        if data.asset_id is not None:
            asset = self._assets.find_by_id(data.asset_id)
            if asset is None:
                raise UnknownAssetError
            return asset.id
        if data.ticker is None:
            return None
        asset = self._assets.find_by_ticker(data.ticker)
        if asset is None:
            if data.asset_class is None:
                raise AssetClassRequiredError
            asset = self._assets.get_or_create_by_ticker(
                data.ticker,
                asset_class_name=data.asset_class,
                currency_id=portfolio.base_currency_id,
            )
        return asset.id

    def _apply(self, state: LedgerState, operation: OperationInput) -> LedgerState:
        with _ledger_errors_rejected():
            return self._ledger.apply(state, operation)

    def _rebuild(self, portfolio_id: int, owner_id: int) -> None:
        """Replay the portfolio's history (`operation_date`, `created_at`, `id`)
        and store the resulting state."""
        portfolio = self._portfolio_repo.get_owned(portfolio_id, owner_id)
        history = self._operation_repo.list_by_portfolio(portfolio_id)
        with _ledger_errors_rejected():
            state = self._ledger.rebuild(
                OperationInput.from_operation(operation) for operation in history
            )
        positions = self._position_repo.list_by_portfolio(portfolio_id)
        self._store_state(portfolio, positions, state)

    def _store_state(
        self, portfolio: Portfolio, positions: Sequence[Position], state: LedgerState
    ) -> None:
        """Write `state` over the stored portfolio and positions: update the
        rows of assets still held (keeping their id and `opened_at`), delete
        closed ones, create new ones."""
        portfolio.cash_balance = state.cash_balance
        portfolio.total_deposited = state.total_deposited
        self._portfolio_repo.update(portfolio)

        rows = {row.asset_id: row for row in positions}
        held = {position.asset_id for position in state.positions}
        for asset_id, closed in rows.items():
            if asset_id not in held:
                self._position_repo.delete(closed)
        for position in state.positions:
            row = rows.get(position.asset_id)
            if row is None:
                self._position_repo.create(
                    portfolio_id=portfolio.id,
                    asset_id=position.asset_id,
                    quantity=position.quantity,
                    average_buy_price=position.average_buy_price,
                    average_fx_rate=position.average_fx_rate,
                    total_fees=position.total_fees,
                    total_dividends=position.total_dividends,
                )
                continue
            row.quantity = position.quantity
            row.average_buy_price = position.average_buy_price
            row.average_fx_rate = position.average_fx_rate
            row.total_fees = position.total_fees
            row.total_dividends = position.total_dividends
            self._position_repo.update(row)
