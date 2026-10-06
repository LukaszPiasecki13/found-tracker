"""Positions of a portfolio valued at freshly refreshed market data."""

from app.modules.portfolios.domain import PortfolioValuator
from app.modules.portfolios.models import Portfolio
from app.modules.portfolios.repositories.positions import PositionRepository
from app.modules.portfolios.schemas.positions import PositionResponse
from app.modules.portfolios.services.fx import FxMapBuilder
from app.modules.portfolios.services.mappers import position_response
from app.modules.portfolios.services.portfolios import PortfolioService


class PositionService:
    """Read model of a portfolio's positions (ADR-0003: DTOs)."""

    def __init__(
        self,
        portfolio_service: PortfolioService,
        position_repo: PositionRepository,
        valuator: PortfolioValuator,
        fx_map_builder: FxMapBuilder,
    ) -> None:
        self._portfolios = portfolio_service
        self._repo = position_repo
        self._valuator = valuator
        self._fx = fx_map_builder

    def list_valued(self, owner_id: int, portfolio_name: str) -> list[PositionResponse]:
        """The positions of the owner's portfolio `portfolio_name`, most recently
        updated first, valued at the stored prices and rates - a pure read.
        Raises PortfolioNotFoundError."""
        portfolio = self._portfolios.get_owned_by_name(owner_id, portfolio_name)
        return self._valued(portfolio)

    def held_asset_ids(self, owner_id: int, portfolio_name: str) -> list[int]:
        """The assets the owner's portfolio `portfolio_name` holds positions in, for
        the background price refresh (DEC-04). Raises PortfolioNotFoundError."""
        portfolio = self._portfolios.get_owned_by_name(owner_id, portfolio_name)
        return [
            position.asset_id for position in self._repo.list_by_portfolio(portfolio.id)
        ]

    def _valued(self, portfolio: Portfolio) -> list[PositionResponse]:
        positions = self._repo.list_by_portfolio(portfolio.id)
        fx_rates = self._fx.build([portfolio.base_currency_id])
        valuation = self._valuator.value(portfolio, positions, fx_rates)
        return [
            position_response(position, position_valuation)
            for position, position_valuation in zip(
                positions, valuation.positions, strict=True
            )
        ]
