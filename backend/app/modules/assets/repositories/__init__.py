"""Assets repositories - data access layer."""

from app.modules.assets.repositories.asset_classes import AssetClassRepository
from app.modules.assets.repositories.assets import AssetRepository
from app.modules.assets.repositories.currencies import CurrencyRepository
from app.modules.assets.repositories.fx_rates import FxRateRepository
from app.modules.assets.repositories.prices import PriceRepository

__all__ = [
    "AssetClassRepository",
    "AssetRepository",
    "CurrencyRepository",
    "FxRateRepository",
    "PriceRepository",
]
