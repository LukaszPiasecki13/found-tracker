"""Domain errors of the `portfolios` module.

Each subclasses a generic `app.core.errors` type, so the global handler and any
`except` on the base class keep working; the subclass names the reason and owns
its message and `code` (ADR-0007). Violations of the ledger's rules come from
`domain/` as `PortfolioDomainError` and reach the client as
`OperationRejectedError` with the domain's own `code`.
"""

from app.core.errors import BadRequestError, ConflictError, NotFoundError

# --- Not found (404): the resource does not exist or is not the caller's ---


class PortfolioNotFoundError(NotFoundError):
    """Also raised for another user's portfolio - its existence stays hidden."""

    def __init__(self) -> None:
        super().__init__("Portfolio not found", code="PORTFOLIO_NOT_FOUND")


class OperationNotFoundError(NotFoundError):
    """Also raised for another user's operation."""

    def __init__(self) -> None:
        super().__init__("Operation not found", code="OPERATION_NOT_FOUND")


# --- Conflict (409): uniqueness ---


class PortfolioAlreadyExistsError(ConflictError):
    def __init__(self) -> None:
        super().__init__(
            "Portfolio with this name already exists",
            code="PORTFOLIO_ALREADY_EXISTS",
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
            "Start date cannot be after end date.", code="INVALID_DATE_RANGE"
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
