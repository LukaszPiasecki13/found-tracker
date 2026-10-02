"""FX rate API endpoint: a rate hint for the UI."""

from fastapi import APIRouter, Depends

from app.modules.portfolios.dependencies import get_fx_rate_service
from app.modules.portfolios.schemas.fx_rates import FxRateQuery, FxRateResponse
from app.modules.portfolios.services.fx import FxRateService
from app.modules.security.dependencies import get_current_user

router = APIRouter(
    prefix="/portfolios",
    tags=["portfolios"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/fx-rate", response_model=FxRateResponse)
def fx_rate(
    query: FxRateQuery = Depends(),
    service: FxRateService = Depends(get_fx_rate_service),
):
    return service.quote(query.from_currency, query.to_currency)
