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


# --- Conflict (409): uniqueness ---


class AssetAlreadyExistsError(ConflictError):
    def __init__(self) -> None:
        super().__init__(
            "Asset with this ticker already exists", code="ASSET_ALREADY_EXISTS"
        )


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


class AssetInUseError(ConflictError):
    """Positions or operations still reference the asset."""

    def __init__(self) -> None:
        super().__init__(
            "Asset is used by positions or operations", code="ASSET_IN_USE"
        )


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
