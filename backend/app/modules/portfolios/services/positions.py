"""Positions of a portfolio valued at freshly refreshed market data."""

from app.modules.assets.services.market_data import MarketDataService
from app.modules.portfolios.domain import PortfolioValuator
from app.modules.portfolios.repositories.positions import PositionRepository
from app.modules.portfolios.schemas.positions import PositionResponse
from app.modules.portfolios.services.portfolios import (
    PortfolioService,
    position_response,
)


class PositionService:
    """Read model of a portfolio's positions (ADR-0003: DTOs)."""

    def __init__(
        self,
        portfolio_service: PortfolioService,
        position_repo: PositionRepository,
        market_data: MarketDataService,
        valuator: PortfolioValuator,
    ) -> None:
        self._portfolios = portfolio_service
        self._repo = position_repo
        self._market_data = market_data
        self._valuator = valuator

    def list_valued(self, owner_id: int, portfolio_name: str) -> list[PositionResponse]:
        """The positions of the owner's portfolio `portfolio_name`, most recently
        updated first, valued after refreshing currency rates and the positions'
        asset prices. Raises PortfolioNotFoundError.

        Both refreshes are best-effort per item and commit on their own (inside
        `MarketDataService`); a provider failure leaves the stored value.
        """
        portfolio = self._portfolios.get_owned_by_name(owner_id, portfolio_name)
        self._market_data.refresh_currency_rates()
        positions = self._repo.list_by_portfolio(portfolio.id)
        self._market_data.refresh_asset_prices(position.asset for position in positions)

        valuation = self._valuator.value(portfolio, positions)
        return [
            position_response(position, position_valuation)
            for position, position_valuation in zip(
                positions, valuation.positions, strict=True
            )
        ]
