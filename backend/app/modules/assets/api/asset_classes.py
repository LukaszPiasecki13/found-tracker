"""Asset class API endpoints."""

from fastapi import APIRouter, Depends

from app.modules.assets.dependencies import get_asset_class_service
from app.modules.assets.schemas.asset_classes import (
    AssetClassCreateRequest,
    AssetClassResponse,
    AssetClassUpdateRequest,
)
from app.modules.assets.services.asset_classes import AssetClassService
from app.modules.security.dependencies import get_current_user

router = APIRouter(
    prefix="/assets/asset-classes",
    tags=["assets"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[AssetClassResponse])
def list_asset_classes(
    service: AssetClassService = Depends(get_asset_class_service),
):
    return service.list_asset_classes()


@router.post("", response_model=AssetClassResponse, status_code=201)
def create_asset_class(
    data: AssetClassCreateRequest,
    service: AssetClassService = Depends(get_asset_class_service),
):
    return service.create(data)


@router.put("/{ac_id:int}", response_model=AssetClassResponse)
@router.patch("/{ac_id:int}", response_model=AssetClassResponse)
def update_asset_class(
    ac_id: int,
    data: AssetClassUpdateRequest,
    service: AssetClassService = Depends(get_asset_class_service),
):
    return service.update(ac_id, data)


@router.delete("/{ac_id:int}", status_code=204)
def delete_asset_class(
    ac_id: int,
    service: AssetClassService = Depends(get_asset_class_service),
):
    service.delete(ac_id)
