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

# The closed set of asset types (the instrument kind; the user-editable asset
# class is a separate axis). The module covers stocks, ETFs, and bonds.
ASSET_TYPES: tuple[str, ...] = ("stock", "etf", "bond", "index")
DEFAULT_ASSET_TYPE = "stock"

# Provider `quoteType` -> asset type for assets created from the provider; any
# other quote type is a stock.
QUOTE_TYPE_ASSET_TYPES: dict[str, str] = {"ETF": "etf"}

# Sources of price and FX-rate observations.
SOURCE_MANUAL = MANUAL_SOURCE
SOURCE_YAHOO = "yahoo"
SOURCE_BONDS = "bonds"
# Providers the module can write today; `manual` outranks them all.
KNOWN_PROVIDER_SOURCES: frozenset[str] = frozenset({SOURCE_YAHOO, SOURCE_BONDS})

# An observation older than this many days marks a price or rate as stale.
STALE_AFTER_DAYS = 7

# `Numeric(18, 9)` holds at most 9 integer digits.
MAX_PRICE_OR_RATE = 10**9

# How many local assets the combined local + provider search returns.
LOCAL_SEARCH_LIMIT = 10

# `POST /assets/refresh-prices` accepts 1..this many asset ids.
MAX_REFRESH_ASSETS = 50

# Per client IP (see `core/rate_limit.py`): endpoints that reach the market-data
# providers or grow the shared catalogue, open to every signed-up user.
PROVIDER_SEARCH_RATE_LIMIT = "30/minute"
ASSET_WRITE_RATE_LIMIT = "10/minute"
REFRESH_RATE_LIMIT = "6/minute"
