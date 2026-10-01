"""Constants of the `assets` module."""

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

# How many local assets the combined local + provider search returns.
LOCAL_SEARCH_LIMIT = 10
