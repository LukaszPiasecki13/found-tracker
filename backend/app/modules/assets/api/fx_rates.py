"""Exchange-rate history endpoints (mounted under `/assets/fx-rates`).

Reading is open to every signed-in user; a manual rate changes valuations for
everyone, so writing it is administrator-only.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.modules.assets.dependencies import get_fx_rate_service
from app.modules.assets.schemas.fx_rates import (
    FxRateHistoryQuery,
    FxRateHistoryResponse,
    FxRateResponse,
    ManualFxRateRequest,
)
from app.modules.assets.services.fx_rates import FxRateService
from app.modules.security.dependencies import get_current_admin, get_current_user

router = APIRouter(
    prefix="/assets/fx-rates",
    tags=["fx-rates"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=FxRateHistoryResponse)
def get_fx_rate_history(
    query: Annotated[FxRateHistoryQuery, Query()],
    service: FxRateService = Depends(get_fx_rate_service),
):
    """Stored observations of the directed pair, oldest first."""
    rows = service.history(
        query.from_currency,
        query.to_currency,
        from_date=query.from_date,
        to_date=query.to_date,
        source=query.source,
    )
    return FxRateHistoryResponse(items=rows)  # type: ignore[arg-type]


@router.put(
    "",
    dependencies=[Depends(get_current_admin)],
    response_model=FxRateResponse,
)
def put_manual_fx_rate(
    data: ManualFxRateRequest,
    service: FxRateService = Depends(get_fx_rate_service),
):
    """Record or replace the manual rate of a day."""
    return service.set_manual_rate(
        data.from_currency_id, data.to_currency_id, data.rate_date, data.rate
    )
