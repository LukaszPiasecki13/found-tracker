"""Pure helpers of the import pipeline: how a parsed row is stored as an
`ImportRow` payload, hashed for deduplication and turned back into an
`OperationDraft` - and how a source ticker becomes the app's ticker."""

import hashlib
from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.core.import_parser import ParsedRow
from app.modules.portfolios.domain import TRADE_OPERATIONS, ImportRowStatus
from app.modules.portfolios.models import ImportRow
from app.modules.portfolios.services.operations import OperationDraft

# The source's exchange suffix -> the app's (Yahoo) ticker suffix.
_EXCHANGE_SUFFIX = {"PL": ".WA", "US": "", "DE": ".DE"}
# A trade's amount may differ from quantity x price by rounding only; more means
# the amount is in another currency than the price.
_AMOUNT_TOLERANCE = Decimal("0.01")
_ONE = Decimal("1")
_FX_PLACES = Decimal("0.000000001")


def exchange_hint(raw_ticker: str) -> str | None:
    _, dot, suffix = raw_ticker.rpartition(".")
    return suffix.upper() if dot else None


def app_ticker(raw_ticker: str, hint: str | None) -> str:
    """The app's ticker for a source ticker (`DNP.PL` -> `DNP.WA`); a ticker
    whose exchange is not mapped is returned unchanged."""
    app_suffix = _EXCHANGE_SUFFIX.get(hint or "")
    if app_suffix is None or not raw_ticker.upper().endswith(f".{hint}"):
        return raw_ticker
    return raw_ticker[: -(len(hint or "") + 1)] + app_suffix


def derived_fx_rate(row: ParsedRow) -> Decimal:
    """The rate that turns a trade's price into its amount: 1 when the amount is
    quantity x price (rounding aside), else `amount / (quantity x price)` - a
    foreign asset bought in the account's currency. The ledger then books the
    amount the source booked."""
    gross = row.quantity * row.price
    if row.operation_type not in TRADE_OPERATIONS or gross <= 0:
        return _ONE
    if abs(row.amount - gross) <= _AMOUNT_TOLERANCE:
        return _ONE
    return (row.amount / gross).quantize(_FX_PLACES)


def _plain(value: Decimal) -> str:
    return format(value.normalize(), "f")


def dedup_key(row: ParsedRow) -> str:
    """SHA-256 of what makes an operation "the same" when a source gives no
    reliable id: when, which asset, how much, what kind."""
    parts = (
        row.operation_date.isoformat(),
        row.ticker or "",
        _plain(row.quantity),
        _plain(row.amount),
        row.operation_type,
        _plain(row.ratio) if row.ratio is not None else "",
    )
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def row_payload(row: ParsedRow) -> dict[str, Any]:
    """JSON-safe form of a parsed row (money as strings, ADR-0010)."""
    return {
        "operation_type": row.operation_type,
        "operation_date": row.operation_date.isoformat(),
        "amount": str(row.amount),
        "quantity": str(row.quantity),
        "price": str(row.price),
        "fee": str(row.fee),
        "fx_rate": str(derived_fx_rate(row)),
        "ticker": row.ticker,
        "exchange_hint": row.exchange_hint,
        "notes": row.notes,
        "external_ref": row.external_ref,
        "asset_class": row.asset_class,
        "ratio": None if row.ratio is None else str(row.ratio),
    }


def draft_from_payload(
    row_number: int, payload: dict[str, Any], asset_id: int | None
) -> OperationDraft:
    """The operation a stored row stands for. Amounts are in the portfolio's
    currency; `fx_rate` is 1 unless the trade's price is in another currency."""
    return OperationDraft(
        row_number=row_number,
        operation_type=payload["operation_type"],
        operation_date=datetime.fromisoformat(payload["operation_date"]),
        asset_id=asset_id,
        quantity=Decimal(payload["quantity"]),
        price=Decimal(payload["price"]),
        amount=Decimal(payload["amount"]),
        fee=Decimal(payload["fee"]),
        fx_rate=Decimal(payload.get("fx_rate", "1")),
        notes=payload["notes"] or None,
        external_ref=payload["external_ref"],
        ratio=Decimal(payload["ratio"]) if payload.get("ratio") else None,
    )


def _row_app_ticker(row: ImportRow) -> str | None:
    ticker = row.payload.get("ticker")
    if not ticker:
        return None
    return app_ticker(ticker, row.payload.get("exchange_hint"))


def pseudo_asset_ids(rows: Iterable[ImportRow]) -> dict[str, int]:
    """Negative placeholder ids for assets the commit will create, by the app's
    ticker: lets a preview replay rows whose asset does not exist yet."""
    ids: dict[str, int] = {}
    for row in rows:
        if row.row_status != ImportRowStatus.OK or row.asset_id is not None:
            continue
        ticker = _row_app_ticker(row)
        if ticker is not None:
            ids.setdefault(ticker, -(len(ids) + 1))
    return ids


def preview_drafts(
    rows: Iterable[ImportRow], pseudo_ids: dict[str, int]
) -> list[OperationDraft]:
    """The `ok` rows as drafts for a preview (assets still to be created get
    their placeholder id)."""
    drafts: list[OperationDraft] = []
    for row in rows:
        if row.row_status != ImportRowStatus.OK:
            continue
        ticker = _row_app_ticker(row)
        asset_id = row.asset_id
        if asset_id is None and ticker is not None:
            asset_id = pseudo_ids[ticker]
        drafts.append(draft_from_payload(row.row_number, row.payload, asset_id))
    return drafts
