"""Price history endpoints of an asset (mounted under `/assets/{id}/prices`).

Reading is open to every signed-in user; recording or removing a manual close
changes valuations for everyone, so it is administrator-only.
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.modules.assets.dependencies import get_price_service
from app.modules.assets.schemas.prices import (
    ManualPriceRequest,
    PriceResponse,
    PriceSeriesQuery,
    PriceSeriesResponse,
)
from app.modules.assets.services.prices import PriceService
from app.modules.security.dependencies import get_current_admin, get_current_user

router = APIRouter(
    prefix="/assets",
    tags=["prices"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/{asset_id:int}/prices", response_model=PriceSeriesResponse)
def get_price_series(
    asset_id: int,
    query: Annotated[PriceSeriesQuery, Query()],
    service: PriceService = Depends(get_price_service),
):
    """Closes of the asset: the winning source per day (`manual` first), or only
    `source`; `fill=forward` carries the last close over days without one."""
    return service.series(
        asset_id,
        from_date=query.from_date,
        to_date=query.to_date,
        source=query.source,
        fill=query.fill,
    )


@router.put(
    "/{asset_id:int}/prices/{price_date}",
    dependencies=[Depends(get_current_admin)],
    response_model=PriceResponse,
)
def put_manual_price(
    asset_id: int,
    price_date: date,
    data: ManualPriceRequest,
    service: PriceService = Depends(get_price_service),
):
    """Record or replace the manual close of a day."""
    return service.set_manual_price(asset_id, price_date, data.close, data.currency_id)


@router.delete(
    "/{asset_id:int}/prices/{price_date}",
    dependencies=[Depends(get_current_admin)],
    status_code=204,
)
def delete_manual_price(
    asset_id: int,
    price_date: date,
    service: PriceService = Depends(get_price_service),
) -> Response:
    service.delete_manual_price(asset_id, price_date)
    return Response(status_code=204)
