"""Pydantic schemas for imports (responses only: the upload is a multipart
file, the commit and revert actions have no body)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.core.schemas import DecimalNumber


class ReconciliationDifference(BaseModel):
    """One place where the file and the portfolio disagree; `field` is
    `cash_balance` or `position:<ticker>`."""

    field: str
    expected: DecimalNumber | None = None
    actual: DecimalNumber | None = None


class ReconciliationReport(BaseModel):
    """The file's own totals (cash, open positions) against the portfolio as it
    is (committed batch) or would be (draft). `ledger_error` is set when the
    ledger would reject the history, so no state could be compared."""

    matched: bool
    differences: list[ReconciliationDifference] = []
    closed_profit_reported: DecimalNumber | None = None
    ledger_error: str | None = None


class ImportRowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None  # a preview's rows are not stored: no id
    row_number: int
    row_status: str
    message: str | None = None
    payload: dict[str, Any]
    asset_id: int | None = None
    operation_id: int | None = None


class ImportBatchSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    portfolio_id: int
    parser_id: str
    filename: str
    sha256: str
    status: str
    created_at: datetime


class ImportBatchResponse(ImportBatchSummaryResponse):
    rows: list[ImportRowResponse]
    reconciliation: ReconciliationReport | None = None


class ImportPreviewResponse(BaseModel):
    """What an import would do; nothing of it is stored. `existing_batch_id` is
    the batch of this very file when it was already imported."""

    parser_id: str
    filename: str
    sha256: str
    existing_batch_id: int | None = None
    rows: list[ImportRowResponse]
    reconciliation: ReconciliationReport | None = None
