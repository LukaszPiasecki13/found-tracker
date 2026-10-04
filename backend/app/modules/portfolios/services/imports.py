"""File imports (ADR-0018): upload a bank's export, review what it would record,
commit it as operations, or revert it.

`ImportService` knows no file format: a parser (a `core.import_parser` adapter
picked from the registry by `sniff`) turns bytes into source-neutral rows, and
everything here - resolving assets, validating, deduplicating, recording - works
on those. A new source is a new adapter plus an entry in the registry built in
`wiring.py`; nothing in this module changes.

Commit and revert are one transaction each (ADR-0008): `ImportService` holds it
and calls the no-commit cores of `OperationService`.
"""

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.core.import_parser import ImportParser, ParsedRow, ParseResult
from app.modules.assets.services.assets import AssetService
from app.modules.portfolios.domain import (
    ASSET_OPERATIONS,
    ImportRowStatus,
    ImportStatus,
    OperationType,
)
from app.modules.portfolios.exceptions import (
    ConcurrentChangeError,
    ImportAlreadyUploadedError,
    ImportBatchNotFoundError,
    ImportBatchStateInvalidError,
    ImportFileTooLargeError,
    ImportParserUnknownError,
    ImportUnresolvedRowsError,
)
from app.modules.portfolios.models import ImportBatch, ImportRow, Portfolio
from app.modules.portfolios.repositories.imports import ImportRepository
from app.modules.portfolios.schemas.imports import (
    ImportBatchResponse,
    ImportBatchSummaryResponse,
    ImportPreviewResponse,
    ImportRowResponse,
)
from app.modules.portfolios.services.import_mapping import (
    app_ticker,
    dedup_key,
    derived_fx_rate,
    draft_from_payload,
    preview_drafts,
    pseudo_asset_ids,
    row_payload,
)
from app.modules.portfolios.services.import_reconciliation import ImportReconciler
from app.modules.portfolios.services.operations import OperationDraft, OperationService
from app.modules.portfolios.services.portfolios import PortfolioService

MAX_IMPORT_FILE_BYTES = 10 * 1024 * 1024
_ZERO = Decimal("0")
_BLOCKING = frozenset({ImportRowStatus.UNRECOGNIZED, ImportRowStatus.ERROR})


@dataclass(frozen=True, slots=True)
class _Prepared:
    """A parsed and classified file, not stored anywhere."""

    parser_id: str
    digest: str
    rows: list[ImportRow]
    payload: dict[str, Any]


class ImportService:
    """Imports of one owner's portfolios; another owner's portfolio or batch is
    reported as not found (404)."""

    def __init__(
        self,
        import_repo: ImportRepository,
        operation_service: OperationService,
        asset_service: AssetService,
        portfolio_service: PortfolioService,
        parsers: Sequence[ImportParser],
    ) -> None:
        self._imports = import_repo
        self._operations = operation_service
        self._assets = asset_service
        self._portfolios = portfolio_service
        self._parsers = tuple(parsers)
        self._reconciler = ImportReconciler(operation_service, asset_service)

    # --- Reads ---

    def list_batches(
        self, portfolio_id: int, owner_id: int
    ) -> list[ImportBatchSummaryResponse]:
        self._portfolios.get_owned(portfolio_id, owner_id)
        batches = self._imports.list_by_portfolio(portfolio_id, owner_id)
        return [ImportBatchSummaryResponse.model_validate(b) for b in batches]

    def get_detail(
        self, batch_id: int, portfolio_id: int, owner_id: int
    ) -> ImportBatchResponse:
        """The batch with its rows and the reconciliation report."""
        return self._detail(self._owned_batch(batch_id, portfolio_id, owner_id))

    # --- Writes ---

    def preview(
        self, portfolio_id: int, owner_id: int, filename: str, content: bytes
    ) -> ImportPreviewResponse:
        """What importing the file would do: its rows with statuses and the
        reconciliation report. **Nothing is stored** - not the file, not the
        rows. Raises PortfolioNotFoundError, ImportFileTooLargeError,
        ImportParserUnknownError, ImportParseError."""
        prepared = self._prepare(portfolio_id, owner_id, filename, content)
        existing = self._imports.find_by_sha256(owner_id, prepared.digest)
        # A transient batch (never added to a session) in the `draft` state: the
        # reconciler previews a draft as it would be once recorded.
        batch = ImportBatch(
            owner_id=owner_id,
            portfolio_id=portfolio_id,
            parser_id=prepared.parser_id,
            filename=filename[-255:],
            sha256=prepared.digest,
            status=ImportStatus.DRAFT.value,
            payload=prepared.payload,
            rows=prepared.rows,
        )
        return ImportPreviewResponse(
            parser_id=prepared.parser_id,
            filename=batch.filename,
            sha256=prepared.digest,
            existing_batch_id=(
                existing.id
                if existing is not None and existing.status == ImportStatus.COMMITTED
                else None
            ),
            rows=[ImportRowResponse.model_validate(row) for row in prepared.rows],
            reconciliation=self._reconciler.report(batch),
        )

    def confirm(
        self, portfolio_id: int, owner_id: int, filename: str, content: bytes
    ) -> ImportBatchResponse:
        """Import the file: the batch, its rows, the operations and the assets
        they need are stored in one transaction, with one rebuild of the
        portfolio. The same file again returns its batch (idempotent). Raises
        PortfolioNotFoundError, ImportFileTooLargeError, ImportParserUnknownError,
        ImportParseError, ImportAlreadyUploadedError (another portfolio's),
        ImportUnresolvedRowsError, ImportCommitRejectedError (the ledger refuses
        the history - nothing is stored), ConcurrentChangeError."""
        prepared = self._prepare(portfolio_id, owner_id, filename, content)
        existing = self._imports.find_by_sha256(owner_id, prepared.digest)
        if existing is not None and existing.status == ImportStatus.COMMITTED:
            if existing.portfolio_id != portfolio_id:
                raise ImportAlreadyUploadedError
            return self._detail(existing)
        blocking = [r.row_number for r in prepared.rows if r.row_status in _BLOCKING]
        if blocking:
            raise ImportUnresolvedRowsError(blocking)
        try:
            with self._imports.transaction():
                if existing is not None:  # a leftover that is not committed
                    self._imports.delete(existing)
                batch = self._imports.create(
                    owner_id=owner_id,
                    portfolio_id=portfolio_id,
                    parser_id=prepared.parser_id,
                    filename=filename[-255:],
                    sha256=prepared.digest,
                    file=content,
                    status=ImportStatus.COMMITTED.value,
                    payload=prepared.payload,
                    rows=prepared.rows,
                )
                portfolio = self._portfolios.get_owned(portfolio_id, owner_id)
                self._resolve_missing_assets(batch.rows, portfolio)
                ok_rows = [r for r in batch.rows if r.row_status == ImportRowStatus.OK]
                created = self._operations.record_many_core(
                    [_draft(row) for row in ok_rows], portfolio_id, owner_id, batch.id
                )
                for row, operation in zip(ok_rows, created, strict=True):
                    row.operation_id = operation.id
                self._imports.update(batch)
        except IntegrityError as err:  # a source id recorded meanwhile
            raise ConcurrentChangeError from err
        return self._detail(self._owned_batch(batch.id, portfolio_id, owner_id))

    def revert(
        self, batch_id: int, portfolio_id: int, owner_id: int
    ) -> ImportBatchResponse:
        """Delete the operations the batch recorded, rebuild the portfolio and
            delete the batch itself (file and rows included).
        Raises ImportBatchStateInvalidError, ImportBatchHasEditsError (some
        operations were edited by hand - nothing is deleted),
        OperationRejectedError."""
        batch = self._owned_batch(batch_id, portfolio_id, owner_id)
        if batch.status != ImportStatus.COMMITTED:
            raise ImportBatchStateInvalidError(batch.status)
        with self._imports.transaction():
            for row in batch.rows:
                row.operation_id = None
            self._operations.revert_import_batch_core(
                batch.id, batch.portfolio_id, owner_id
            )
            # Nothing of an undone import stays: the batch, its file and its
            # rows go with its operations. The answer says what happened.
            response = ImportBatchResponse.model_validate(batch).model_copy(
                update={"status": ImportStatus.REVERTED.value, "reconciliation": None}
            )
            self._imports.delete(batch)
        return response

    # --- Preparing a file ---

    def _prepare(
        self, portfolio_id: int, owner_id: int, filename: str, content: bytes
    ) -> _Prepared:
        """Validate and parse the file and classify its rows; touches nothing."""
        self._portfolios.get_owned(portfolio_id, owner_id)
        if len(content) > MAX_IMPORT_FILE_BYTES:
            raise ImportFileTooLargeError(MAX_IMPORT_FILE_BYTES)
        parser = self._parser_for(filename, content)
        result = parser.parse(content)
        rows = self._build_rows(portfolio_id, result)
        self._book_orphan_dividends_as_income(portfolio_id, owner_id, rows)
        return _Prepared(
            parser_id=parser.parser_id,
            digest=hashlib.sha256(content).hexdigest(),
            rows=rows,
            payload=_expectations_payload(result),
        )

    def _parser_for(self, filename: str, content: bytes) -> ImportParser:
        for parser in self._parsers:
            if parser.sniff(filename, content):
                return parser
        raise ImportParserUnknownError

    def _build_rows(self, portfolio_id: int, result: ParseResult) -> list[ImportRow]:
        existing = self._operations.existing_external_refs(
            portfolio_id, [row.external_ref for row in result.rows]
        )
        rows = [self._classified(row, existing) for row in result.rows]
        rows += [
            ImportRow(
                row_number=issue.row_number,
                row_status=ImportRowStatus.UNRECOGNIZED.value,
                message=issue.message,
                payload=dict(issue.raw),
            )
            for issue in result.issues
        ]
        return sorted(rows, key=lambda row: row.row_number)

    def _book_orphan_dividends_as_income(
        self, portfolio_id: int, owner_id: int, rows: list[ImportRow]
    ) -> None:
        """The ledger refuses a dividend without an open position (the payout
        came after the position was closed). Such a dividend is still cash the
        account received: it is booked as income without an asset, and the row
        says so."""
        ok_rows = [r for r in rows if r.row_status == ImportRowStatus.OK]
        if not any(r.payload.get("operation_type") == "dividend" for r in ok_rows):
            return
        drafts = preview_drafts(ok_rows, pseudo_asset_ids(ok_rows))
        refused = self._operations.dividends_without_position(
            portfolio_id, owner_id, drafts
        )
        for row in ok_rows:
            if row.row_number in refused:
                ticker = row.payload.get("ticker")
                row.payload = {
                    **row.payload,
                    "operation_type": OperationType.INTEREST.value,
                    "ticker": None,
                    "exchange_hint": None,
                    "asset_class": None,
                    "notes": f"Dividend {ticker}: {row.payload.get('notes', '')}",
                }
                row.asset_id = None
                row.message = (
                    f"Dividend of {ticker} booked as income: "
                    "no open position on the payout date"
                )

    def _classified(self, row: ParsedRow, existing_refs: set[str]) -> ImportRow:
        status, message, asset_id = self._classify(row, existing_refs)
        return ImportRow(
            row_number=row.row_number,
            row_status=status.value,
            message=message,
            payload=row_payload(row),
            dedup_key=dedup_key(row),
            asset_id=asset_id,
        )

    def _classify(
        self, row: ParsedRow, existing_refs: set[str]
    ) -> tuple[ImportRowStatus, str | None, int | None]:
        """What to do with a row: (status, why, asset id).

        Unknown assets in ASSET_OPERATIONS are marked OK with asset_id=None and a
        message that they will be created at commit time.
        """
        try:
            operation_type = OperationType(row.operation_type)
        except ValueError:
            message = f"Unknown operation type '{row.operation_type}'"
            return ImportRowStatus.UNRECOGNIZED, message, None
        if row.amount == _ZERO:
            return ImportRowStatus.SKIP, "Zero amount - nothing to record", None
        if row.external_ref in existing_refs:
            return ImportRowStatus.DUPLICATE, "Already recorded", None
        if operation_type not in ASSET_OPERATIONS:
            return ImportRowStatus.OK, None, None
        # Asset operation: need to check if asset exists
        if not row.ticker:
            message = "No ticker - cannot identify the asset"
            return ImportRowStatus.UNRECOGNIZED, message, None
        app_tick = app_ticker(row.ticker, row.exchange_hint)
        asset = self._assets.find_by_ticker(app_tick)
        if asset is not None and asset.archived_at is not None:
            # Asset exists but is archived: cannot record operations
            message = f"Asset '{app_tick}' is archived"
            return ImportRowStatus.UNRECOGNIZED, message, None
        if asset is None:
            # Asset does not exist: will be created at commit time
            message = f"Asset '{app_tick}' will be created"
            return ImportRowStatus.OK, _join(message, _fx_message(row)), None
        # Asset exists and is not archived
        return ImportRowStatus.OK, _fx_message(row), asset.id

    # --- Assets ---

    def _resolve_missing_assets(
        self, rows: Sequence[ImportRow], portfolio: Portfolio
    ) -> None:
        """Create any assets that rows reference but do not yet exist in the
        database. For each OK row with asset_id=None, looks up the asset by app
        ticker and creates it if needed, using the asset_class from the payload
        or defaulting to "Stock". Raises ImportUnresolvedRowsError if a required
        asset is already archived."""
        ok_rows = [r for r in rows if r.row_status == ImportRowStatus.OK]
        ticker_cache: dict[str, int] = {}
        failed_rows: list[int] = []
        for row in ok_rows:
            if row.asset_id is not None:
                continue
            ticker_str = row.payload.get("ticker")
            if not ticker_str:
                continue
            app_tick = app_ticker(ticker_str, row.payload.get("exchange_hint"))
            if app_tick not in ticker_cache:
                asset_class_name = row.payload.get("asset_class") or "Stock"
                asset = self._assets.get_or_create_by_ticker(
                    app_tick,
                    asset_class_name=asset_class_name,
                    fallback_currency_id=portfolio.base_currency_id,
                )
                if asset.archived_at is not None:
                    failed_rows.append(row.row_number)
                else:
                    ticker_cache[app_tick] = asset.id
            if app_tick in ticker_cache:
                row.asset_id = ticker_cache[app_tick]
        if failed_rows:
            raise ImportUnresolvedRowsError(failed_rows)

    # --- Read model ---

    def _owned_batch(
        self, batch_id: int, portfolio_id: int, owner_id: int
    ) -> ImportBatch:
        batch = self._imports.get_owned(batch_id, owner_id)
        if batch.portfolio_id != portfolio_id:
            raise ImportBatchNotFoundError
        return batch

    def _detail(self, batch: ImportBatch) -> ImportBatchResponse:
        response = ImportBatchResponse.model_validate(batch)
        response.reconciliation = self._reconciler.report(batch)
        return response


def _draft(row: ImportRow) -> OperationDraft:
    return draft_from_payload(row.row_number, row.payload, row.asset_id)


def _expectations_payload(result: ParseResult) -> dict[str, Any]:
    expectations = result.expectations
    return {
        "expectations": {
            "open_positions": {
                ticker: str(quantity)
                for ticker, quantity in expectations.open_positions.items()
            },
            "cash_total": _text(expectations.cash_total),
            "closed_profit": _text(expectations.closed_profit),
        }
    }


def _text(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _fx_message(row: ParsedRow) -> str | None:
    rate = derived_fx_rate(row)
    if rate == 1:
        return None
    return f"Price is in another currency: rate {rate:.4f} taken from the amount"


def _join(*parts: str | None) -> str:
    return "; ".join(part for part in parts if part)
