"""Valuing a portfolio at current prices: cost basis, market value, profit,
returns and weights.

Level 2 of the domain (DOM-9): a component (DOM-10). Exact `Decimal`
arithmetic, nothing rounded - the read models round at the schema boundary.
A position quoted in the portfolio's base currency is valued without FX;
otherwise at the cross rate of the two currencies' `exchange_rate`s (each is a
rate against the same reference currency, so the portfolio's own rate cancels
it out). A percentage of zero is zero.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from decimal import Decimal

from app.modules.portfolios.domain.protocols import HoldingLike, ValuedPortfolioLike

_ZERO = Decimal("0")
_HUNDRED = Decimal("100")


def _percent(part: Decimal, whole: Decimal) -> Decimal:
    if whole == _ZERO:
        return _ZERO
    return part / whole * _HUNDRED


@dataclass(frozen=True, slots=True)
class PositionValuation:
    """One position at current prices; money in the portfolio's currency except
    `cost_basis` (asset currency)."""

    cost_basis: Decimal
    cost_basis_in_portfolio_currency: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    return_pct: Decimal
    portfolio_weight_pct: Decimal


@dataclass(frozen=True, slots=True)
class PortfolioValuation:
    """A portfolio at current prices; `positions` follows the order of the
    holdings it was computed from."""

    positions_value: Decimal
    total_value: Decimal
    total_profit_loss: Decimal
    total_return_pct: Decimal
    total_fees: Decimal
    positions: tuple[PositionValuation, ...]


def _value_holding(
    holding: HoldingLike, portfolio: ValuedPortfolioLike
) -> PositionValuation:
    cost_basis = holding.quantity * holding.average_buy_price
    cost_in_portfolio = cost_basis * holding.average_fx_rate
    market_value = holding.quantity * holding.asset.current_price
    if holding.asset.currency_id != portfolio.base_currency_id:
        market_value = (
            market_value
            * holding.asset.currency.exchange_rate
            / portfolio.base_currency.exchange_rate
        )
    unrealized = market_value - cost_in_portfolio
    return PositionValuation(
        cost_basis=cost_basis,
        cost_basis_in_portfolio_currency=cost_in_portfolio,
        market_value=market_value,
        unrealized_pnl=unrealized,
        return_pct=_percent(unrealized, cost_in_portfolio),
        portfolio_weight_pct=_ZERO,
    )


class PortfolioValuator:
    """Values a portfolio and its positions - the domain surface of the
    portfolio and position read models (DOM-10), built in `wiring.py`.

    Weights are relative to the total value, cash included; the profit and
    return compare the total value with the net deposits.
    """

    def value(
        self, portfolio: ValuedPortfolioLike, holdings: Sequence[HoldingLike]
    ) -> PortfolioValuation:
        valued = [_value_holding(h, portfolio) for h in holdings]
        positions_value = sum((v.market_value for v in valued), _ZERO)
        total_value = portfolio.cash_balance + positions_value
        profit_loss = total_value - portfolio.total_deposited
        return PortfolioValuation(
            positions_value=positions_value,
            total_value=total_value,
            total_profit_loss=profit_loss,
            total_return_pct=_percent(profit_loss, portfolio.total_deposited),
            total_fees=sum((h.total_fees for h in holdings), _ZERO),
            positions=tuple(
                replace(v, portfolio_weight_pct=_percent(v.market_value, total_value))
                for v in valued
            ),
        )
