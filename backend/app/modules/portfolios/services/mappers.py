"""Mapping stored rows plus their valuation onto response DTOs, shared by the
portfolio and position read models."""

from app.modules.portfolios.domain import PositionValuation
from app.modules.portfolios.models import Position
from app.modules.portfolios.schemas.positions import PositionFields, PositionResponse


def position_response(
    position: Position, valuation: PositionValuation
) -> PositionResponse:
    """A stored position plus its valuation as the response DTO; the schema
    rounds the computed figures. The valuation already holds the split and the
    asset-currency view (DEC-10), so this only copies them."""
    return PositionResponse(
        **dict(PositionFields.model_validate(position)),
        cost_basis=valuation.cost_basis,
        cost_basis_in_portfolio_currency=valuation.cost_basis_in_portfolio_currency,
        market_value=valuation.market_value,
        unrealized_pnl=valuation.unrealized_pnl,
        return_pct=valuation.return_pct,
        portfolio_weight_pct=valuation.portfolio_weight_pct,
        rate_missing=valuation.rate_missing,
        market_value_asset_currency=valuation.market_value_asset_currency,
        unrealized_pnl_asset_currency=valuation.unrealized_pnl_asset_currency,
        price_change_pct=valuation.price_change_pct,
        fx_rate_applied=valuation.fx_rate_applied,
        price_effect=valuation.price_effect,
        fx_effect=valuation.fx_effect,
    )
