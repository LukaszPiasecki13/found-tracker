"""Position API endpoints (mounted under `/portfolios/positions`)."""

from fastapi import APIRouter, Depends

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
    query: PositionListQuery = Depends(),
    user: User = Depends(get_current_user),
    service: PositionService = Depends(get_position_service),
):
    """Valued positions; refreshes currency rates and asset prices first."""
    return service.list_valued(user.id, query.portfolio_name)
