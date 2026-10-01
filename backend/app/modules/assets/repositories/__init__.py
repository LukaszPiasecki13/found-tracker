"""Assets repositories - data access layer."""

from app.modules.assets.repositories.asset_classes import AssetClassRepository
from app.modules.assets.repositories.assets import AssetRepository
from app.modules.assets.repositories.currencies import CurrencyRepository

__all__ = ["AssetClassRepository", "AssetRepository", "CurrencyRepository"]
