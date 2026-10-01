"""Portfolio metrics API endpoints: vectors for charts."""

from fastapi import APIRouter, Depends

from app.modules.core_data.models.user import User
from app.modules.portfolios.dependencies import get_metrics_service
from app.modules.portfolios.schemas.metrics import (
    PortfolioVectorsQuery,
    PortfolioVectorsResponse,
)
from app.modules.portfolios.services.metrics import MetricsService
from app.modules.security.dependencies import get_current_user

router = APIRouter(
    prefix="/portfolios",
    tags=["portfolios"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/portfolio-vectors", response_model=PortfolioVectorsResponse)
def portfolio_vectors(
    query: PortfolioVectorsQuery = Depends(),
    user: User = Depends(get_current_user),
    service: MetricsService = Depends(get_metrics_service),
):
    return service.portfolio_vectors(user.id, query)
