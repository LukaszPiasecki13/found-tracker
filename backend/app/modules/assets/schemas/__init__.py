"""Assets Pydantic schemas - request/response models."""

from app.modules.assets.schemas.asset_classes import (
    AssetClassCreateRequest,
    AssetClassResponse,
    AssetClassUpdateRequest,
)
from app.modules.assets.schemas.assets import (
    AssetCreateRequest,
    AssetDetailResponse,
    AssetFromProviderRequest,
    AssetListQuery,
    AssetResponse,
    AssetSearchQuery,
    AssetSearchResponse,
    AssetUpdateRequest,
    ProviderQuoteResponse,
)
from app.modules.assets.schemas.currencies import (
    CurrencyCreateRequest,
    CurrencyResponse,
    CurrencyUpdateRequest,
)

__all__ = [
    "AssetClassCreateRequest",
    "AssetClassResponse",
    "AssetClassUpdateRequest",
    "AssetCreateRequest",
    "AssetDetailResponse",
    "AssetFromProviderRequest",
    "AssetListQuery",
    "AssetResponse",
    "AssetSearchQuery",
    "AssetSearchResponse",
    "AssetUpdateRequest",
    "CurrencyCreateRequest",
    "CurrencyResponse",
    "CurrencyUpdateRequest",
    "ProviderQuoteResponse",
]
