"""Operations: recording, editing and deleting them, and keeping the
portfolio's cash and positions consistent with them.

`OperationService` is the orchestrator of a multi-module unit of work
(ADR-0008): recording a buy of an unknown ticker creates the asset through
`AssetService`'s no-commit core and commits it together with the operation, the
new cash balance and the position - or rolls all of it back.
"""

from collections.abc import Collection, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from app.core.entities import apply_changes
from app.modules.assets.exceptions import AssetArchivedError
from app.modules.assets.services.assets import AssetService
from app.modules.portfolios.domain import (
    LedgerState,
    OperationInput,
    OperationType,
    PortfolioDomainError,
    PortfolioLedger,
)
from app.modules.portfolios.exceptions import (
    AssetClassRequiredError,
    ConcurrentChangeError,
    ImportBatchHasEditsError,
    ImportCommitRejectedError,
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


@dataclass(frozen=True, slots=True)
class OperationDraft:
    """An operation to record that the caller has already resolved (the asset
    is an id): what an importer hands to `record_many_core`. `row_number` is
    the caller's own label, reported back when the ledger rejects the draft."""

    row_number: int
    operation_type: str
    operation_date: datetime
    asset_id: int | None = None
    quantity: Decimal = Decimal("0")
    price: Decimal = Decimal("0")
    amount: Decimal | None = None
    fee: Decimal = Decimal("0")
    fx_rate: Decimal = Decimal("1")
    notes: str | None = None
    external_ref: str | None = None
    ratio: Decimal | None = None

    def to_input(self) -> OperationInput:
        return OperationInput(
            operation_type=OperationType(self.operation_type),
            asset_id=self.asset_id,
            quantity=self.quantity,
            price=self.price,
            amount=self.amount,
            fee=self.fee,
            fx_rate=self.fx_rate,
            ratio=self.ratio,
        )


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

    def existing_external_refs(
        self, portfolio_id: int, external_refs: Collection[str]
    ) -> set[str]:
        """Which of the source ids the portfolio already has an operation for."""
        return self._operation_repo.existing_external_refs(portfolio_id, external_refs)

    def preview_state(
        self, portfolio_id: int, owner_id: int, drafts: Sequence[OperationDraft] = ()
    ) -> LedgerState:
        """The portfolio's state if `drafts` were recorded now, replayed with
        its history in date order; nothing is stored. Raises
        PortfolioNotFoundError, OperationRejectedError (`row_number` names the
        draft row refused, if it is one)."""
        entries = self._replay_entries(portfolio_id, owner_id, drafts)
        replaying: list[int | None] = []

        def replay() -> Iterator[OperationInput]:
            for operation, row_number in entries:
                replaying[:] = [row_number]
                yield operation

        try:
            with _ledger_errors_rejected():
                return self._ledger.rebuild(replay())
        except OperationRejectedError as err:
            # The draft's row when it is the one refused (None: a stored one).
            err.row_number = replaying[0] if replaying else None
            raise

    def dividends_without_position(
        self, portfolio_id: int, owner_id: int, drafts: Sequence[OperationDraft]
    ) -> set[int]:
        """Row numbers of the dividend `drafts` the ledger would refuse because
        the asset has no open position on the payout date (the history and the
        other drafts replayed in date order). The replay books such a dividend
        as income without an asset - what the importer will do with it - so the
        cash of later rows is right. It stops at any other refusal;
        `preview_state` reports that one."""
        entries = self._replay_entries(portfolio_id, owner_id, drafts)
        state = LedgerState()
        refused: set[int] = set()
        for operation, row_number in entries:
            is_dividend = operation.operation_type == OperationType.DIVIDEND
            if is_dividend and (
                operation.asset_id is None or state.position(operation.asset_id) is None
            ):
                if row_number is not None:
                    refused.add(row_number)
                operation = OperationInput(
                    OperationType.INTEREST, amount=operation.amount, fee=operation.fee
                )
            try:
                state = self._ledger.apply(state, operation)
            except PortfolioDomainError:
                break
        return refused

    def _replay_entries(
        self, portfolio_id: int, owner_id: int, drafts: Sequence[OperationDraft]
    ) -> list[tuple[OperationInput, int | None]]:
        """The stored history and `drafts` (with their row numbers) in the order
        the ledger replays them: date, stored before new, then as given."""
        self._portfolio_repo.get_owned(portfolio_id, owner_id)
        entries = [
            (op.operation_date, 0, index, OperationInput.from_operation(op), None)
            for index, op in enumerate(
                self._operation_repo.list_by_portfolio(portfolio_id)
            )
        ] + [
            (draft.operation_date, 1, index, draft.to_input(), draft.row_number)
            for index, draft in enumerate(drafts)
        ]
        entries.sort(key=lambda entry: entry[:3])
        return [(entry[3], entry[4]) for entry in entries]

    # --- Writes ---

    def record(self, data: OperationCreateRequest, owner_id: int) -> Operation:
        """Store a new operation and rebuild the portfolio from its whole history
        (the operation may be back-dated), under a row lock on the portfolio.

        Raises PortfolioNotFoundError, UnknownAssetError, AssetArchivedError,
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
            self._portfolio_repo.lock_owned(data.portfolio_id, owner_id)
            portfolio = self._portfolio_repo.get_owned(data.portfolio_id, owner_id)
            asset_id = self._resolve_asset_id(data, portfolio)
            operation = self._operation_repo.create(
                portfolio_id=portfolio.id,
                asset_id=asset_id,
                operation_type=data.operation_type.value,
                quantity=data.quantity,
                price=data.price,
                amount=data.amount,
                fee=data.fee,
                fx_rate=data.fx_rate,
                ratio=data.ratio,
                notes=data.notes,
                operation_date=data.operation_date,
            )
            self._rebuild(portfolio.id, owner_id)
            return operation

    def record_many_core(
        self,
        drafts: Sequence[OperationDraft],
        portfolio_id: int,
        owner_id: int,
        import_batch_id: int,
    ) -> list[Operation]:
        """Store `drafts` as operations of an import batch and rebuild the
        portfolio once. A no-commit core (ADR-0008): the caller owns the
        transaction (`with repo.transaction()`) and rolls everything back on
        an exception. Raises PortfolioNotFoundError and ImportCommitRejectedError
        (the ledger rejects the resulting history; carries the draft's row)."""
        self._portfolio_repo.lock_owned(portfolio_id, owner_id)
        if not drafts:
            return []
        operations = [
            Operation(
                portfolio_id=portfolio_id,
                asset_id=draft.asset_id,
                operation_type=draft.operation_type,
                quantity=draft.quantity,
                price=draft.price,
                amount=draft.amount,
                fee=draft.fee,
                fx_rate=draft.fx_rate,
                notes=draft.notes,
                operation_date=draft.operation_date,
                external_ref=draft.external_ref,
                import_batch_id=import_batch_id,
                ratio=draft.ratio,
            )
            for draft in drafts
        ]
        created = self._operation_repo.create_many(operations)
        try:
            self._rebuild(portfolio_id, owner_id)
        except OperationRejectedError as err:
            rows = {
                op.id: draft.row_number
                for op, draft in zip(created, drafts, strict=True)
            }
            row_number = rows.get(err.operation_id or 0)
            raise ImportCommitRejectedError(
                row_number, err.message, err.code or ""
            ) from err
        return created

    def revert_import_batch_core(
        self, import_batch_id: int, portfolio_id: int, owner_id: int
    ) -> None:
        """Delete the operations an import batch recorded and rebuild the
        portfolio (a no-commit core, like `record_many_core`). Raises
        ImportBatchHasEditsError (some were edited by hand - nothing is
        deleted) and OperationRejectedError (the remaining history breaks a
        ledger rule)."""
        self._portfolio_repo.lock_owned(portfolio_id, owner_id)
        operations = self._operation_repo.list_by_import_batch(import_batch_id)
        edited = [op.id for op in operations if op.edited_at is not None]
        if edited:
            raise ImportBatchHasEditsError(edited)
        for operation in operations:
            self._operation_repo.delete(operation)
        self._rebuild(portfolio_id, owner_id)

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
            self._portfolio_repo.lock_owned(operation.portfolio_id, owner_id)
            if any(getattr(operation, f) != v for f, v in values.items()):
                # A hand edit protects the operation from an import revert.
                operation.edited_at = datetime.now(UTC)
            apply_changes(operation, values)
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
            self._portfolio_repo.lock_owned(portfolio_id, owner_id)
            self._operation_repo.delete(operation)
            self._rebuild(portfolio_id, owner_id)

    # --- Helpers ---

    def _resolve_asset_id(
        self, data: OperationCreateRequest, portfolio: Portfolio
    ) -> int | None:
        """`asset_id` if it names an asset; else the asset with `ticker`,
        created (no-commit core, ADR-0008) in class `asset_class` and the
        provider's quote currency (the portfolio's base currency when the
        provider has no quote) when unknown; else no asset."""
        if data.asset_id is not None:
            asset = self._assets.find_by_id(data.asset_id)
            if asset is None:
                raise UnknownAssetError
            if asset.archived_at is not None:
                raise AssetArchivedError
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
                fallback_currency_id=portfolio.base_currency_id,
            )
        # An archived asset takes no new operations (its history stays).
        if asset.archived_at is not None:
            raise AssetArchivedError
        return asset.id

    def _rebuild(self, portfolio_id: int, owner_id: int) -> None:
        """Replay the portfolio's history (`operation_date`, `created_at`, `id`)
        and store the resulting state."""
        portfolio = self._portfolio_repo.get_owned(portfolio_id, owner_id)
        history = self._operation_repo.list_by_portfolio(portfolio_id)
        replaying: list[int] = []

        def replay() -> Iterator[OperationInput]:
            for operation in history:
                replaying[:] = [operation.id]
                yield OperationInput.from_operation(operation)

        try:
            with _ledger_errors_rejected():
                state = self._ledger.rebuild(replay())
        except OperationRejectedError as err:
            # The operation being applied when the ledger refused it.
            err.operation_id = replaying[0] if replaying else None
            raise
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
