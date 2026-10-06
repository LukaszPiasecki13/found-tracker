"""Portfolio metrics API endpoints: vectors for charts."""

from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends

from app.modules.assets import entrypoints as assets_entrypoints
from app.modules.assets.dependencies import get_daily_refresh_service
from app.modules.assets.services.job_runs import DailyRefreshService
from app.modules.core_data.models.user import User
from app.modules.portfolios.dependencies import (
    get_account_metrics_service,
    get_currency_split_service,
    get_metrics_service,
)
from app.modules.portfolios.schemas.currency_split import (
    CurrencySplitQuery,
    CurrencySplitResponse,
)
from app.modules.portfolios.schemas.metrics import (
    AccountVectorsQuery,
    PortfolioVectorsQuery,
    PortfolioVectorsResponse,
)
from app.modules.portfolios.services.account_metrics import AccountMetricsService
from app.modules.portfolios.services.currency_split import CurrencySplitService
from app.modules.portfolios.services.metrics import MetricsService
from app.modules.security.dependencies import get_current_user

router = APIRouter(
    prefix="/portfolios",
    tags=["portfolios"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/portfolio-vectors", response_model=PortfolioVectorsResponse)
def portfolio_vectors(
    background_tasks: BackgroundTasks,
    query: PortfolioVectorsQuery = Depends(),
    user: User = Depends(get_current_user),
    service: MetricsService = Depends(get_metrics_service),
    daily_refresh: DailyRefreshService = Depends(get_daily_refresh_service),
):
    """The first request of a day also starts the day's market-data refresh in the
    background (ADR-0017); the vectors themselves read the stored history."""
    if daily_refresh.claim(date.today()):
        background_tasks.add_task(assets_entrypoints.daily_refresh)
    return service.portfolio_vectors(user.id, query)


@router.get("/account-vectors", response_model=PortfolioVectorsResponse)
def account_vectors(
    background_tasks: BackgroundTasks,
    query: AccountVectorsQuery = Depends(),
    user: User = Depends(get_current_user),
    service: AccountMetricsService = Depends(get_account_metrics_service),
    daily_refresh: DailyRefreshService = Depends(get_daily_refresh_service),
):
    """All the user's portfolios summed in the user's base currency (DEC-01). Starts
    the day's refresh like `portfolio-vectors` (ADR-0017)."""
    if daily_refresh.claim(date.today()):
        background_tasks.add_task(assets_entrypoints.daily_refresh)
    return service.account_vectors(user.id, query, user.base_currency_id)


@router.get("/currency-split", response_model=CurrencySplitResponse)
def currency_split(
    query: CurrencySplitQuery = Depends(),
    user: User = Depends(get_current_user),
    service: CurrencySplitService = Depends(get_currency_split_service),
):
    """The current holdings by currency: one portfolio's, or all of them in the
    account currency when no portfolio is named."""
    return service.split(user.id, query.portfolio_name, user.base_currency_id)
