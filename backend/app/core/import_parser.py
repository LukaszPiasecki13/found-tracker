"""Port for file-import parsers (ADR-0018).

A parser turns the bytes of one bank's export into source-neutral rows. It knows
nothing about the database, assets or portfolios: mapping a raw ticker to an
asset, deduplicating and recording belong to `portfolios`' `ImportService`. A
new source is a new adapter in `infrastructure/import_parsers/` plus one entry
in the registry built in `portfolios/wiring.py` (Strategy + Registry).
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from fastapi import status

from app.core.errors import APIError


class ImportParseError(APIError):
    """The file is not a readable export of the expected format (422)."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="IMPORT_PARSE_FAILED",
        )


@dataclass(frozen=True, slots=True)
class ParsedRow:
    """One source row as one operation.

    `operation_type` is the value of the app's `OperationType` ("buy",
    "interest", ...): this module must not import `modules/`, so the service
    validates it. `ticker` is the source's own symbol (e.g. "DNP.PL") and
    `exchange_hint` its exchange suffix ("PL"); `amount` is the signed-free
    cash amount from the source. `external_ref` identifies the row in the
    source and is stable across exports. `asset_class` is the asset's class
    name when known from the source (e.g. from XTB's Category column); for
    asset-bound operations (buy/sell/dividend) with unknown ticker, this guides
    automatic asset creation.
    """

    row_number: int
    operation_type: str
    operation_date: datetime
    amount: Decimal
    external_ref: str
    ticker: str | None = None
    exchange_hint: str | None = None
    quantity: Decimal = Decimal("0")
    price: Decimal = Decimal("0")
    fee: Decimal = Decimal("0")
    notes: str = ""
    asset_class: str | None = None


@dataclass(frozen=True, slots=True)
class ParseIssue:
    """A row the parser could not turn into an operation (unknown type,
    unreadable comment, ...). It blocks the commit until resolved."""

    row_number: int
    message: str
    raw: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ImportExpectations:
    """What the file says the account looks like - the data to verify the
    imported operations against (reconciliation report).

    `open_positions` maps the source's tickers to held quantity, `cash_total`
    is the sum of all cash operations, `closed_profit` the source's realised
    profit (informational).
    """

    open_positions: dict[str, Decimal] = field(default_factory=dict)
    cash_total: Decimal | None = None
    closed_profit: Decimal | None = None


@dataclass(frozen=True, slots=True)
class ParseResult:
    rows: list[ParsedRow]
    issues: list[ParseIssue] = field(default_factory=list)
    expectations: ImportExpectations = field(default_factory=ImportExpectations)


class ImportParser(Protocol):
    """One source format (an adapter; the registry picks it with `sniff`)."""

    parser_id: str

    def sniff(self, filename: str, content: bytes) -> bool:
        """Whether this parser reads that file. Never raises."""
        ...

    def parse(self, content: bytes) -> ParseResult:
        """Raises `ImportParseError` when the file is unreadable."""
        ...
