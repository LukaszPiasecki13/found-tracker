"""Constants of the `assets` module."""

from app.modules.assets.domain import MANUAL_SOURCE

# Defaults applied when the market-data provider leaves a field empty.
DEFAULT_CURRENCY_CODE = "USD"
DEFAULT_QUOTE_TYPE = "EQUITY"

# Provider `quoteType` -> asset class name for assets created from the provider.
QUOTE_TYPE_ASSET_CLASSES: dict[str, str] = {
    "ETF": "ETF",
    "CRYPTOCURRENCY": "Crypto",
    "CRYPTO": "Crypto",
    "MUTUALFUND": "Mutual Fund",
}
DEFAULT_ASSET_CLASS_NAME = "Stock"

# The closed set of asset types (the behaviour axis, next to the user-editable
# asset class). `user_asset` is for assets the user prices by hand.
ASSET_TYPES: tuple[str, ...] = (
    "stock",
    "etf",
    "fund",
    "treasury_bond",
    "bond",
    "crypto",
    "currency",
    "commodity",
    "deposit",
    "user_asset",
)
DEFAULT_ASSET_TYPE = "user_asset"

# Provider `quoteType` -> asset type for assets created from the provider.
QUOTE_TYPE_ASSET_TYPES: dict[str, str] = {
    "EQUITY": "stock",
    "ETF": "etf",
    "MUTUALFUND": "fund",
    "CRYPTOCURRENCY": "crypto",
    "CRYPTO": "crypto",
    "CURRENCY": "currency",
    "FUTURE": "commodity",
}
DEFAULT_PROVIDER_ASSET_TYPE = "stock"

# Sources of price and FX-rate observations.
SOURCE_MANUAL = MANUAL_SOURCE
SOURCE_YAHOO = "yahoo"
# Providers the module can write today; `manual` outranks them all.
KNOWN_PROVIDER_SOURCES: frozenset[str] = frozenset({SOURCE_YAHOO})

# An observation older than this many days marks a price or rate as stale.
STALE_AFTER_DAYS = 7

# `Numeric(18, 9)` holds at most 9 integer digits.
MAX_PRICE_OR_RATE = 10**9

# How many local assets the combined local + provider search returns.
LOCAL_SEARCH_LIMIT = 10

# `POST /assets/refresh-prices` accepts 1..this many asset ids.
MAX_REFRESH_ASSETS = 50
