"""Portfolio API endpoints: CRUD and the valued views.

`{portfolio_id:int}` only matches digits, so `/portfolios/positions`,
`/portfolios/operations` and `/portfolios/portfolio-vectors` can never be
captured by it, whatever the router include order.
"""

from fastapi import APIRouter, Depends

from app.modules.core_data.models.user import User
from app.modules.portfolios.dependencies import get_portfolio_service
from app.modules.portfolios.schemas.portfolios import (
    PortfolioCreateRequest,
    PortfolioDetailResponse,
    PortfolioListQuery,
    PortfolioResponse,
    PortfolioSummaryResponse,
    PortfolioUpdateRequest,
)
from app.modules.portfolios.services.portfolios import PortfolioService
from app.modules.security.dependencies import get_current_user

router = APIRouter(
    prefix="/portfolios",
    tags=["portfolios"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/", response_model=list[PortfolioSummaryResponse])
def list_portfolios(
    query: PortfolioListQuery = Depends(),
    user: User = Depends(get_current_user),
    service: PortfolioService = Depends(get_portfolio_service),
):
    return service.list_summaries(user.id, name=query.name)


@router.post("/", response_model=PortfolioResponse, status_code=201)
def create_portfolio(
    data: PortfolioCreateRequest,
    user: User = Depends(get_current_user),
    service: PortfolioService = Depends(get_portfolio_service),
):
    return service.create(data, owner_id=user.id)


@router.get("/{portfolio_id:int}", response_model=PortfolioDetailResponse)
def get_portfolio(
    portfolio_id: int,
    user: User = Depends(get_current_user),
    service: PortfolioService = Depends(get_portfolio_service),
):
    return service.get_detail(portfolio_id, owner_id=user.id)


@router.put("/{portfolio_id:int}", response_model=PortfolioResponse)
@router.patch("/{portfolio_id:int}", response_model=PortfolioResponse)
def update_portfolio(
    portfolio_id: int,
    data: PortfolioUpdateRequest,
    user: User = Depends(get_current_user),
    service: PortfolioService = Depends(get_portfolio_service),
):
    return service.update(portfolio_id, data, owner_id=user.id)


@router.delete("/{portfolio_id:int}", status_code=204)
def delete_portfolio(
    portfolio_id: int,
    user: User = Depends(get_current_user),
    service: PortfolioService = Depends(get_portfolio_service),
):
    service.delete(portfolio_id, owner_id=user.id)
