"""Position API endpoints (mounted under `/portfolios/positions`)."""

from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, Request

from app.core.rate_limit import limiter
from app.modules.assets import entrypoints as assets_entrypoints
from app.modules.assets.constants import REFRESH_RATE_LIMIT
from app.modules.assets.dependencies import get_daily_refresh_service
from app.modules.assets.services.job_runs import DailyRefreshService
from app.modules.core_data.models.user import User
from app.modules.portfolios.dependencies import get_position_service
from app.modules.portfolios.schemas.positions import (
    PositionListQuery,
    PositionResponse,
)
from app.modules.portfolios.services.positions import PositionService
from app.modules.security.dependencies import get_current_user

router = APIRouter(
    prefix="/portfolios/positions",
    tags=["portfolios"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[PositionResponse])
def list_positions(
    background_tasks: BackgroundTasks,
    query: PositionListQuery = Depends(),
    user: User = Depends(get_current_user),
    service: PositionService = Depends(get_position_service),
    daily_refresh: DailyRefreshService = Depends(get_daily_refresh_service),
):
    """Valued positions at the stored prices. The first request of a day also
    starts the day's market-data refresh in the background (ADR-0017)."""
    if daily_refresh.claim(date.today()):
        background_tasks.add_task(assets_entrypoints.daily_refresh)
    return service.list_valued(user.id, query.portfolio_name)


@router.post("/refresh", response_model=list[PositionResponse])
@limiter.limit(REFRESH_RATE_LIMIT)
def refresh_positions(
    request: Request,
    background_tasks: BackgroundTasks,
    query: PositionListQuery = Depends(),
    user: User = Depends(get_current_user),
    service: PositionService = Depends(get_position_service),
):
    """Answer at once with the stored positions; the rates and the prices of the
    portfolio's assets are refreshed from the provider in the background (DEC-04,
    ADR-0017). The caller polls `GET /portfolios/positions` for the new `price_date`."""
    asset_ids = service.held_asset_ids(user.id, query.portfolio_name)
    background_tasks.add_task(assets_entrypoints.refresh_fx_rates)
    background_tasks.add_task(assets_entrypoints.refresh_prices, asset_ids)
    return service.list_valued(user.id, query.portfolio_name)
