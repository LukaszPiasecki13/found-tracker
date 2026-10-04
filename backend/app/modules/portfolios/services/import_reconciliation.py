"""The reconciliation report of an import: what the file says the account looks
like (cash, open positions) against the portfolio - as it is once the batch is
committed, as it would be while the batch is a draft."""

from decimal import Decimal
from typing import Any

from app.modules.assets.services.assets import AssetService
from app.modules.portfolios.domain import (
    TRADE_OPERATIONS,
    ImportRowStatus,
    ImportStatus,
    LedgerState,
)
from app.modules.portfolios.exceptions import OperationRejectedError
from app.modules.portfolios.models import ImportBatch
from app.modules.portfolios.schemas.imports import (
    ReconciliationDifference,
    ReconciliationReport,
)
from app.modules.portfolios.services.import_mapping import (
    app_ticker,
    exchange_hint,
    preview_drafts,
    pseudo_asset_ids,
)
from app.modules.portfolios.services.operations import OperationDraft, OperationService

# The source rounds every amount to cents, so a trade may be off by a cent; the
# cash tolerance grows with the number of trades.
_CENT = Decimal("0.01")
_QUANTITY_TOLERANCE = Decimal("0.000001")
_ZERO = Decimal("0")


def _decimal(value: str | None) -> Decimal | None:
    return None if value is None else Decimal(value)


class ImportReconciler:
    def __init__(
        self, operation_service: OperationService, asset_service: AssetService
    ) -> None:
        self._operations = operation_service
        self._assets = asset_service

    def report(self, batch: ImportBatch) -> ReconciliationReport | None:
        """While the batch is a draft, assets it will create get negative
        placeholder ids so the ledger can replay their rows."""
        expected = batch.payload.get("expectations") or {}
        closed_profit = _decimal(expected.get("closed_profit"))
        pseudo_ids = pseudo_asset_ids(batch.rows)
        drafts: list[OperationDraft] = []
        if batch.status == ImportStatus.DRAFT:
            drafts = preview_drafts(batch.rows, pseudo_ids)
        try:
            state = self._operations.preview_state(
                batch.portfolio_id, batch.owner_id, drafts
            )
        except OperationRejectedError as err:
            return ReconciliationReport(
                matched=False,
                ledger_error=(
                    err.message
                    if err.row_number is None
                    else f"Row {err.row_number}: {err.message}"
                ),
                closed_profit_reported=closed_profit,
            )
        differences = self._differences(state, expected, batch, pseudo_ids)
        return ReconciliationReport(
            matched=not differences,
            differences=differences,
            closed_profit_reported=closed_profit,
        )

    def _differences(
        self,
        state: LedgerState,
        expected: dict[str, Any],
        batch: ImportBatch,
        pseudo_ids: dict[str, int],
    ) -> list[ReconciliationDifference]:
        differences: list[ReconciliationDifference] = []
        cash_total = _decimal(expected.get("cash_total"))
        trades = sum(
            1
            for row in batch.rows
            if row.row_status == ImportRowStatus.OK
            and row.payload.get("operation_type") in TRADE_OPERATIONS
        )
        if cash_total is not None and (
            abs(state.cash_balance - cash_total) > _CENT * max(1, trades)
        ):
            differences.append(
                ReconciliationDifference(
                    field="cash_balance",
                    expected=cash_total,
                    actual=state.cash_balance,
                )
            )
        if "open_positions" in expected:
            differences += self._position_differences(
                state, expected["open_positions"], pseudo_ids
            )
        return differences

    def _position_differences(
        self,
        state: LedgerState,
        expected_positions: dict[str, str],
        pseudo_ids: dict[str, int],
    ) -> list[ReconciliationDifference]:
        differences: list[ReconciliationDifference] = []
        matched_assets: set[int] = set()
        for raw_ticker, text in expected_positions.items():
            expected = Decimal(text)
            ticker = app_ticker(raw_ticker, exchange_hint(raw_ticker))
            asset = self._assets.find_by_ticker(ticker)
            asset_id = asset.id if asset is not None else pseudo_ids.get(ticker)
            actual: Decimal | None = None
            if asset_id is not None:
                matched_assets.add(asset_id)
                held = state.position(asset_id)
                actual = held.quantity if held is not None else _ZERO
            if actual is None or abs(actual - expected) > _QUANTITY_TOLERANCE:
                differences.append(
                    ReconciliationDifference(
                        field=f"position:{raw_ticker}",
                        expected=expected,
                        actual=actual,
                    )
                )
        placeholders = {asset_id: ticker for ticker, asset_id in pseudo_ids.items()}
        for position in state.positions:
            if position.asset_id in matched_assets:
                continue
            asset = self._assets.find_by_id(position.asset_id)
            name = (
                asset.ticker
                if asset is not None
                else placeholders.get(position.asset_id, str(position.asset_id))
            )
            differences.append(
                ReconciliationDifference(
                    field=f"position:{name}", expected=_ZERO, actual=position.quantity
                )
            )
        return differences
