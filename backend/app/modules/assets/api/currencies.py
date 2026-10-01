"""Currency API endpoints (mounted under `/assets/currencies`)."""

from fastapi import APIRouter, Depends

from app.modules.assets.dependencies import get_currency_service
from app.modules.assets.schemas.currencies import (
    CurrencyCreateRequest,
    CurrencyResponse,
    CurrencyUpdateRequest,
)
from app.modules.assets.services.currencies import CurrencyService
from app.modules.security.dependencies import get_current_admin, get_current_user

router = APIRouter(
    prefix="/assets/currencies",
    tags=["currencies"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[CurrencyResponse])
def list_currencies(service: CurrencyService = Depends(get_currency_service)):
    return service.list_currencies()


@router.post(
    "",
    dependencies=[Depends(get_current_admin)],
    response_model=CurrencyResponse,
    status_code=201,
)
def create_currency(
    data: CurrencyCreateRequest,
    service: CurrencyService = Depends(get_currency_service),
):
    return service.create(data)


@router.get("/{currency_id:int}", response_model=CurrencyResponse)
def get_currency(
    currency_id: int,
    service: CurrencyService = Depends(get_currency_service),
):
    return service.get_by_id(currency_id)


@router.put(
    "/{currency_id:int}",
    dependencies=[Depends(get_current_admin)],
    response_model=CurrencyResponse,
)
@router.patch(
    "/{currency_id:int}",
    dependencies=[Depends(get_current_admin)],
    response_model=CurrencyResponse,
)
def update_currency(
    currency_id: int,
    data: CurrencyUpdateRequest,
    service: CurrencyService = Depends(get_currency_service),
):
    return service.update(currency_id, data)


@router.delete(
    "/{currency_id:int}", dependencies=[Depends(get_current_admin)], status_code=204
)
def delete_currency(
    currency_id: int,
    service: CurrencyService = Depends(get_currency_service),
):
    service.delete(currency_id)
