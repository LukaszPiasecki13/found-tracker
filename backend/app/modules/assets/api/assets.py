"""Asset API endpoints, including provider (Yahoo Finance) search and import.

`{asset_id:int}` only matches digits, so `/assets/search-yahoo`,
`/assets/asset-classes` and `/assets/currencies` can never be captured by it,
whatever the router include order.
"""

from fastapi import APIRouter, Depends

from app.modules.assets.dependencies import get_asset_service
from app.modules.assets.schemas.assets import (
    AssetCreateRequest,
    AssetDetailResponse,
    AssetFromProviderRequest,
    AssetListQuery,
    AssetResponse,
    AssetSearchQuery,
    AssetSearchResponse,
    AssetUpdateRequest,
)
from app.modules.assets.services.assets import AssetService
from app.modules.security.dependencies import get_current_user

router = APIRouter(
    prefix="/assets",
    tags=["assets"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/", response_model=list[AssetResponse])
def list_assets(
    query: AssetListQuery = Depends(),
    service: AssetService = Depends(get_asset_service),
):
    return service.list_assets(query.search)


@router.post("/", response_model=AssetResponse, status_code=201)
def create_asset(
    data: AssetCreateRequest,
    service: AssetService = Depends(get_asset_service),
):
    return service.create(data)


@router.get("/search-yahoo", response_model=AssetSearchResponse)
def search_yahoo(
    query: AssetSearchQuery = Depends(),
    service: AssetService = Depends(get_asset_service),
):
    """Local assets plus provider hits not stored locally yet."""
    return service.search_local_and_provider(query.q)


@router.post("/create-from-yahoo", response_model=AssetDetailResponse, status_code=201)
def create_from_yahoo(
    data: AssetFromProviderRequest,
    service: AssetService = Depends(get_asset_service),
):
    return service.create_from_provider(data)


@router.get("/{asset_id:int}", response_model=AssetDetailResponse)
def get_asset(
    asset_id: int,
    service: AssetService = Depends(get_asset_service),
):
    return service.get_by_id(asset_id)


@router.put("/{asset_id:int}", response_model=AssetResponse)
@router.patch("/{asset_id:int}", response_model=AssetResponse)
def update_asset(
    asset_id: int,
    data: AssetUpdateRequest,
    service: AssetService = Depends(get_asset_service),
):
    return service.update(asset_id, data)


@router.delete("/{asset_id:int}", status_code=204)
def delete_asset(
    asset_id: int,
    service: AssetService = Depends(get_asset_service),
):
    service.delete(asset_id)
