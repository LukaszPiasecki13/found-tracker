"""Domain errors of the `portfolios` module.

Each subclasses a generic `app.core.errors` type, so the global handler and any
`except` on the base class keep working; the subclass names the reason and owns
its message and `code` (ADR-0007). Violations of the ledger's rules come from
`domain/` as `PortfolioDomainError` and reach the client as
`OperationRejectedError` with the domain's own `code`.
"""

from collections.abc import Sequence

from fastapi import status

from app.core.errors import (
    APIError,
    BadRequestError,
    ConflictError,
    NotFoundError,
    ValidationException,
)

# --- Not found (404): the resource does not exist or is not the caller's ---


class PortfolioNotFoundError(NotFoundError):
    """Also raised for another user's portfolio - its existence stays hidden."""

    def __init__(self) -> None:
        super().__init__("Portfolio not found", code="PORTFOLIO_NOT_FOUND")


class OperationNotFoundError(NotFoundError):
    """Also raised for another user's operation."""

    def __init__(self) -> None:
        super().__init__("Operation not found", code="OPERATION_NOT_FOUND")


class RateMissingError(NotFoundError):
    """A currency of the pair has no quote yet (see `services/fx.py`)."""

    def __init__(self) -> None:
        super().__init__("Currency rate not available", code="RATE_MISSING")


# --- Conflict (409): uniqueness ---


class PortfolioAlreadyExistsError(ConflictError):
    def __init__(self) -> None:
        super().__init__(
            "Portfolio with this name already exists",
            code="PORTFOLIO_ALREADY_EXISTS",
        )


class PortfolioCurrencyLockedError(ConflictError):
    def __init__(self) -> None:
        super().__init__(
            "Base currency cannot change once the portfolio has operations",
            code="PORTFOLIO_CURRENCY_LOCKED",
        )


# --- Bad request (400): references in the body ---


class UnknownCurrencyError(BadRequestError):
    def __init__(self) -> None:
        super().__init__("Currency not found", code="CURRENCY_NOT_FOUND")


class UnknownAssetError(BadRequestError):
    """`asset_id` in the body names no asset."""

    def __init__(self) -> None:
        super().__init__("Asset not found", code="ASSET_NOT_FOUND")


class AssetClassRequiredError(BadRequestError):
    """An unknown `ticker` without the `asset_class` to create it with."""

    def __init__(self) -> None:
        super().__init__(
            "Asset does not exist. Provide asset_class to create it.",
            code="ASSET_NOT_FOUND",
        )


# --- Bad request (400): the ledger rejects the operation or the history ---


class OperationRejectedError(BadRequestError):
    """A `PortfolioDomainError` translated for the client; `code` is the
    domain's (`INVALID_OPERATION`, `INSUFFICIENT_CASH`, ...)."""

    def __init__(self, message: str, code: str) -> None:
        super().__init__(message, code=code)
        # Set by `OperationService._rebuild`: the operation the ledger refused.
        self.operation_id: int | None = None
        # Set by `OperationService.preview_state`: the draft row refused.
        self.row_number: int | None = None


# --- Bad request (400): portfolio vector parameters ---


class InvalidVectorsError(BadRequestError):
    def __init__(self) -> None:
        super().__init__(
            "Invalid vectors payload. Expected a JSON list of vector names.",
            code="INVALID_VECTORS",
        )


class InvalidDateError(BadRequestError):
    def __init__(self) -> None:
        super().__init__("Invalid date format. Use YYYY-MM-DD.", code="INVALID_DATE")


class InvalidDateRangeError(BadRequestError):
    def __init__(self) -> None:
        super().__init__(
            "Start date cannot be after end date, and the range is limited to "
            "about ten years.",
            code="INVALID_DATE_RANGE",
        )


class UnsupportedIntervalError(BadRequestError):
    def __init__(self) -> None:
        super().__init__(
            "Only daily interval is supported now.", code="UNSUPPORTED_INTERVAL"
        )


# --- Conflict (409): a concurrent writer got there first ---


class ConcurrentChangeError(ConflictError):
    """A unique constraint failed while recording an operation (e.g. two first
    buys of the same new ticker at once); retrying the request succeeds."""

    def __init__(self) -> None:
        super().__init__(
            "The data changed concurrently; retry the request",
            code="CONCURRENT_CHANGE",
        )


class PriceDataMissingError(APIError):
    """A held ticker has no price at all, so its value cannot be drawn."""

    def __init__(self, ticker: str) -> None:
        super().__init__(
            f"No price data for {ticker}",
            status.HTTP_502_BAD_GATEWAY,
            code="PRICE_DATA_MISSING",
        )


class MixedBaseCurrenciesError(ConflictError):
    """The vectors span portfolios in different base currencies: their values
    cannot be summed into one series. Narrow the request to one portfolio."""

    def __init__(self, currency_codes: Sequence[str]) -> None:
        super().__init__(
            "Portfolios with different base currencies "
            f"({', '.join(currency_codes)}) cannot be charted together",
            code="MIXED_BASE_CURRENCIES",
        )


# --- Import (ADR-0018) ---


class ImportBatchNotFoundError(NotFoundError):
    """Also raised for another user's import batch."""

    def __init__(self) -> None:
        super().__init__("Import batch not found", code="IMPORT_BATCH_NOT_FOUND")


class ImportParserUnknownError(ValidationException):
    """No registered parser reads the uploaded file."""

    def __init__(self) -> None:
        super().__init__(
            "The file format is not supported by any import parser",
            code="IMPORT_PARSER_UNKNOWN",
        )


class ImportFileTooLargeError(APIError):
    def __init__(self, limit_bytes: int) -> None:
        super().__init__(
            f"The file exceeds the {limit_bytes // (1024 * 1024)} MB import limit",
            status.HTTP_413_CONTENT_TOO_LARGE,
            code="IMPORT_FILE_TOO_LARGE",
        )


class ImportUnresolvedRowsError(ConflictError):
    """Rows the importer could not turn into operations block the commit."""

    def __init__(self, row_numbers: Sequence[int]) -> None:
        self.row_numbers = list(row_numbers)
        super().__init__(
            "Resolve or remove unrecognized rows before committing: "
            + ", ".join(str(n) for n in self.row_numbers),
            code="IMPORT_UNRESOLVED_ROWS",
        )


class ImportBatchStateInvalidError(ConflictError):
    def __init__(self, status_value: str) -> None:
        super().__init__(
            f"The import batch is {status_value}; this action needs another state",
            code="IMPORT_BATCH_STATE_INVALID",
        )


class ImportBatchHasEditsError(ConflictError):
    """Reverting would discard operations the user edited by hand."""

    def __init__(self, operation_ids: Sequence[int]) -> None:
        self.operation_ids = list(operation_ids)
        super().__init__(
            "Operations of this import were edited: "
            + ", ".join(str(i) for i in self.operation_ids),
            code="IMPORT_BATCH_HAS_EDITS",
        )


class ImportCommitRejectedError(BadRequestError):
    """The ledger rejected the imported history; nothing was stored."""

    def __init__(self, row_number: int | None, message: str, code: str) -> None:
        """`row_number` is `None` when the ledger refused an operation that is
        not part of the import (the history around it is what breaks)."""
        self.row_number = row_number
        prefix = "" if row_number is None else f"Row {row_number}: "
        super().__init__(prefix + message, code="IMPORT_COMMIT_REJECTED")
        self.reason_code = code


class ImportAlreadyUploadedError(ConflictError):
    """The same file is already an import batch of another portfolio."""

    def __init__(self) -> None:
        super().__init__(
            "This file was already uploaded to another portfolio",
            code="IMPORT_ALREADY_UPLOADED",
        )
