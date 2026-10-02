"""Domain errors of the `assets` module.

Each subclasses a generic `app.core.errors` type, so the global handler and any
`except` on the base class keep working; the subclass names the reason and owns
its message and `code` (ADR-0007).
"""

from app.core.errors import BadRequestError, ConflictError, NotFoundError

# --- Not found (404): the resource addressed by the URL does not exist ---


class AssetNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__("Asset not found", code="ASSET_NOT_FOUND")


class AssetClassNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__("Asset class not found", code="ASSET_CLASS_NOT_FOUND")


class CurrencyNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__("Currency not found", code="CURRENCY_NOT_FOUND")


class PriceNotFoundError(NotFoundError):
    """No manual price exists for the asset on that day."""

    def __init__(self) -> None:
        super().__init__("Price not found", code="PRICE_NOT_FOUND")


class RateMissingError(NotFoundError):
    """No stored rate, direct or inverse, links the two currencies."""

    def __init__(self) -> None:
        super().__init__("No exchange rate available", code="RATE_MISSING")


class AssetNotFoundOnProviderError(NotFoundError):
    """The market-data provider knows no instrument with this ticker."""

    def __init__(self) -> None:
        super().__init__(
            "Could not find asset on the market data provider",
            code="ASSET_NOT_FOUND_ON_PROVIDER",
        )


# --- Bad request (400): the body references a row that does not exist ---


class UnknownAssetClassError(BadRequestError):
    def __init__(self) -> None:
        super().__init__("Asset class not found", code="ASSET_CLASS_NOT_FOUND")


class UnknownCurrencyError(BadRequestError):
    def __init__(self) -> None:
        super().__init__("Currency not found", code="CURRENCY_NOT_FOUND")


class UnknownBaseCurrencyError(BadRequestError):
    def __init__(self) -> None:
        super().__init__("Base currency not found", code="BASE_CURRENCY_NOT_FOUND")


class InvalidDateRangeError(BadRequestError):
    """`from` is after `to`, or the range is too long to serve."""

    def __init__(self, message: str = "Invalid date range") -> None:
        super().__init__(message, code="INVALID_DATE_RANGE")


class PriceCurrencyMismatchError(BadRequestError):
    """A price must be quoted in the asset's own currency."""

    def __init__(self) -> None:
        super().__init__(
            "Price currency must match the asset currency",
            code="PRICE_CURRENCY_MISMATCH",
        )


class FutureDateError(BadRequestError):
    """Manual prices and rates record what happened; they cannot be dated ahead."""

    def __init__(self) -> None:
        super().__init__("Date cannot be in the future", code="DATE_IN_FUTURE")


class InvalidIdentifierError(BadRequestError):
    """An ISIN, MIC or country code that does not have the standard's shape."""

    def __init__(self, field: str) -> None:
        super().__init__(f"Invalid {field}", code="INVALID_IDENTIFIER")


# --- Conflict (409): uniqueness ---


class AssetAlreadyExistsError(ConflictError):
    def __init__(self, message: str = "Asset with this ticker already exists") -> None:
        super().__init__(message, code="ASSET_ALREADY_EXISTS")


class AssetClassAlreadyExistsError(ConflictError):
    def __init__(self) -> None:
        super().__init__(
            "Asset class with this name already exists",
            code="ASSET_CLASS_ALREADY_EXISTS",
        )


class CurrencyAlreadyExistsError(ConflictError):
    def __init__(self) -> None:
        super().__init__(
            "Currency with this code already exists", code="CURRENCY_ALREADY_EXISTS"
        )


# --- Conflict (409): delete blocked by rows that still reference the resource ---


class AssetHasHistoryError(ConflictError):
    """Operations, positions or prices still reference the asset; archive it
    instead of deleting."""

    def __init__(self) -> None:
        super().__init__(
            "Asset has history (operations, positions or prices); archive it instead",
            code="ASSET_HAS_HISTORY",
        )


class AssetArchivedError(ConflictError):
    """The asset is archived: no new operations or prices."""

    def __init__(self) -> None:
        super().__init__("Asset is archived", code="ASSET_ARCHIVED")


class AssetClassInUseError(ConflictError):
    """Assets still belong to the class."""

    def __init__(self) -> None:
        super().__init__("Asset class is used by assets", code="ASSET_CLASS_IN_USE")


class CurrencyInUseError(ConflictError):
    """Assets, portfolios or other currencies still reference the currency."""

    def __init__(self) -> None:
        super().__init__(
            "Currency is used by assets, portfolios or other currencies",
            code="CURRENCY_IN_USE",
        )
