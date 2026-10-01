"""Operation API endpoints (mounted under `/portfolios/operations`)."""

from fastapi import APIRouter, Depends

from app.modules.core_data.models.user import User
from app.modules.portfolios.dependencies import get_operation_service
from app.modules.portfolios.schemas.operations import (
    OperationCreateRequest,
    OperationListQuery,
    OperationResponse,
    OperationUpdateRequest,
)
from app.modules.portfolios.services.operations import OperationService
from app.modules.security.dependencies import get_current_user

router = APIRouter(
    prefix="/portfolios/operations",
    tags=["portfolios"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[OperationResponse])
def list_operations(
    query: OperationListQuery = Depends(),
    user: User = Depends(get_current_user),
    service: OperationService = Depends(get_operation_service),
):
    return service.list_operations(user.id, query.portfolio_name)


@router.post("", response_model=OperationResponse, status_code=201)
def create_operation(
    data: OperationCreateRequest,
    user: User = Depends(get_current_user),
    service: OperationService = Depends(get_operation_service),
):
    return service.record(data, owner_id=user.id)


@router.put("/{operation_id:int}", response_model=OperationResponse)
@router.patch("/{operation_id:int}", response_model=OperationResponse)
def update_operation(
    operation_id: int,
    data: OperationUpdateRequest,
    user: User = Depends(get_current_user),
    service: OperationService = Depends(get_operation_service),
):
    return service.update(operation_id, data, owner_id=user.id)


@router.delete("/{operation_id:int}", status_code=204)
def delete_operation(
    operation_id: int,
    user: User = Depends(get_current_user),
    service: OperationService = Depends(get_operation_service),
):
    service.delete(operation_id, owner_id=user.id)
