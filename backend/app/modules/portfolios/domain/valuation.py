"""Valuing a portfolio at current prices: cost basis, market value, profit,
returns and weights.

Level 2 of the domain (DOM-9): a component (DOM-10). Exact `Decimal`
arithmetic, nothing rounded - the read models round at the schema boundary.
A position quoted in the portfolio's base currency is valued without FX;
otherwise at the rate the caller supplies for (asset currency, base currency).
A position whose rate is unknown is not valued - it is flagged `rate_missing`,
its value, profit, return and weight are `None`, and so are the portfolio
totals that would need it (a partial sum would silently understate the
portfolio). A percentage of zero is zero.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from decimal import Decimal

from app.modules.portfolios.domain.protocols import HoldingLike, ValuedPortfolioLike

_ZERO = Decimal("0")
_ONE = Decimal("1")
_HUNDRED = Decimal("100")

# Rate that turns one unit of the first currency into the second, by currency id.
FxMap = Mapping[tuple[int, int], Decimal]


def _percent(part: Decimal, whole: Decimal) -> Decimal:
    if whole == _ZERO:
        return _ZERO
    return part / whole * _HUNDRED


@dataclass(frozen=True, slots=True)
class PositionValuation:
    """One position at current prices; money in the portfolio's currency except
    `cost_basis` (asset currency). The cost needs no rate; everything else is
    `None` when `rate_missing`."""

    cost_basis: Decimal
    cost_basis_in_portfolio_currency: Decimal
    market_value: Decimal | None
    unrealized_pnl: Decimal | None
    return_pct: Decimal | None
    portfolio_weight_pct: Decimal | None
    rate_missing: bool = False


@dataclass(frozen=True, slots=True)
class PortfolioValuation:
    """A portfolio at current prices; `positions` follows the order of the
    holdings it was computed from. When any position lacks a rate the value
    totals are `None` and `rate_missing` is set; `total_fees` never needs one."""

    positions_value: Decimal | None
    total_value: Decimal | None
    total_profit_loss: Decimal | None
    total_return_pct: Decimal | None
    total_fees: Decimal
    positions: tuple[PositionValuation, ...]
    rate_missing: bool = False


def _rate_into_base(
    holding: HoldingLike, base_currency_id: int, fx_rates: FxMap
) -> Decimal | None:
    """The rate turning one unit of the asset's currency into the base currency,
    `None` when the map has none."""
    if holding.asset.currency_id == base_currency_id:
        return _ONE
    return fx_rates.get((holding.asset.currency_id, base_currency_id))


def _value_holding(
    holding: HoldingLike, base_currency_id: int, fx_rates: FxMap
) -> PositionValuation:
    cost_basis = holding.quantity * holding.average_buy_price
    cost_in_portfolio = cost_basis * holding.average_fx_rate
    rate = _rate_into_base(holding, base_currency_id, fx_rates)
    if rate is None:
        return PositionValuation(
            cost_basis=cost_basis,
            cost_basis_in_portfolio_currency=cost_in_portfolio,
            market_value=None,
            unrealized_pnl=None,
            return_pct=None,
            portfolio_weight_pct=None,
            rate_missing=True,
        )
    market_value = holding.quantity * holding.asset.current_price
    if holding.asset.currency_id != base_currency_id:
        market_value = market_value * rate
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
        self,
        portfolio: ValuedPortfolioLike,
        holdings: Sequence[HoldingLike],
        fx_rates: FxMap,
    ) -> PortfolioValuation:
        """`fx_rates` maps (asset currency id, base currency id) to the rate
        that converts one unit of the first into the second."""
        valued = [
            _value_holding(h, portfolio.base_currency_id, fx_rates) for h in holdings
        ]
        total_fees = sum((h.total_fees for h in holdings), _ZERO)
        market_values = [v.market_value for v in valued if v.market_value is not None]
        if len(market_values) != len(valued):
            return PortfolioValuation(
                positions_value=None,
                total_value=None,
                total_profit_loss=None,
                total_return_pct=None,
                total_fees=total_fees,
                positions=tuple(replace(v, portfolio_weight_pct=None) for v in valued),
                rate_missing=True,
            )
        positions_value = sum(market_values, _ZERO)
        total_value = portfolio.cash_balance + positions_value
        profit_loss = total_value - portfolio.total_deposited
        return PortfolioValuation(
            positions_value=positions_value,
            total_value=total_value,
            total_profit_loss=profit_loss,
            total_return_pct=_percent(profit_loss, portfolio.total_deposited),
            total_fees=total_fees,
            positions=tuple(
                replace(v, portfolio_weight_pct=_percent(market_value, total_value))
                for v, market_value in zip(valued, market_values, strict=True)
            ),
        )
