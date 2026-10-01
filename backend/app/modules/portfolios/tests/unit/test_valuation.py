"""`PortfolioValuator` - pure domain over ORM-like views (DOM-8)."""

from decimal import Decimal
from types import SimpleNamespace

from app.modules.portfolios.domain import PortfolioValuator

D = Decimal
PLN, USD = 1, 2


def _portfolio(
    cash: str = "0", deposited: str = "0", *, base_rate: str = "1"
) -> SimpleNamespace:
    return SimpleNamespace(
        base_currency_id=PLN,
        base_currency=SimpleNamespace(exchange_rate=D(base_rate)),
        cash_balance=D(cash),
        total_deposited=D(deposited),
    )


def _holding(
    quantity: str,
    average_price: str,
    current_price: str,
    *,
    currency_id: int = PLN,
    exchange_rate: str = "1",
    average_fx: str = "1",
    fees: str = "0",
) -> SimpleNamespace:
    return SimpleNamespace(
        quantity=D(quantity),
        average_buy_price=D(average_price),
        average_fx_rate=D(average_fx),
        total_fees=D(fees),
        asset=SimpleNamespace(
            current_price=D(current_price),
            currency_id=currency_id,
            currency=SimpleNamespace(exchange_rate=D(exchange_rate)),
        ),
    )


def test_position_in_the_base_currency_is_valued_without_fx() -> None:
    holding = _holding("10", "20", "25", exchange_rate="999")

    valuation = PortfolioValuator().value(_portfolio(), [holding])

    position = valuation.positions[0]
    assert position.cost_basis == D("200")
    assert position.cost_basis_in_portfolio_currency == D("200")
    assert position.market_value == D("250")
    assert position.unrealized_pnl == D("50")
    assert position.return_pct == D("25")


def test_foreign_position_uses_current_rate_for_value_and_average_fx_for_cost() -> None:
    holding = _holding(
        "10", "20", "25", currency_id=USD, exchange_rate="4.1", average_fx="3.9"
    )

    position = PortfolioValuator().value(_portfolio(), [holding]).positions[0]

    assert position.cost_basis == D("200")
    assert position.cost_basis_in_portfolio_currency == D("780.0")
    assert position.market_value == D("1025.0")
    assert position.unrealized_pnl == D("245.0")
    assert position.return_pct == D("245.0") / D("780.0") * 100


def test_portfolio_totals_include_cash_and_compare_with_net_deposits() -> None:
    holdings = [
        _holding("10", "20", "25", fees="1.5"),
        _holding("2", "100", "90", currency_id=USD, exchange_rate="4", fees="2"),
    ]

    valuation = PortfolioValuator().value(_portfolio("250", "1000"), holdings)

    assert valuation.positions_value == D("250") + D("720")
    assert valuation.total_value == D("1220")
    assert valuation.total_profit_loss == D("220")
    assert valuation.total_return_pct == D("22")
    assert valuation.total_fees == D("3.5")
    assert [p.portfolio_weight_pct for p in valuation.positions] == [
        D("250") / D("1220") * 100,
        D("720") / D("1220") * 100,
    ]


def test_zero_denominators_give_zero_percentages() -> None:
    free_gift = _holding("1", "0", "0")

    valuation = PortfolioValuator().value(_portfolio(), [free_gift])

    assert valuation.positions[0].return_pct == 0
    assert valuation.positions[0].portfolio_weight_pct == 0
    assert valuation.total_return_pct == 0
    assert valuation.total_value == 0


def test_empty_portfolio_is_its_cash() -> None:
    valuation = PortfolioValuator().value(_portfolio("100", "80"), [])

    assert valuation.positions == ()
    assert valuation.positions_value == 0
    assert valuation.total_value == D("100")
    assert valuation.total_profit_loss == D("20")
    assert valuation.total_return_pct == D("25")
    assert valuation.total_fees == 0


def test_values_are_exact_not_rounded() -> None:
    holding = _holding("3", "0.1", "0.111111111")

    position = PortfolioValuator().value(_portfolio(), [holding]).positions[0]

    assert position.market_value == D("0.333333333")
    assert position.return_pct == (D("0.333333333") - D("0.3")) / D("0.3") * 100


def test_foreign_position_is_converted_through_the_cross_rate() -> None:
    # Rates are against a common reference: 1 USD = 4 ref, 1 PLN = 0.5 ref, so
    # 1 USD = 8 PLN. The portfolio's own rate is not assumed to be 1.
    holding = _holding("10", "20", "25", currency_id=USD, exchange_rate="4")

    position = (
        PortfolioValuator().value(_portfolio(base_rate="0.5"), [holding]).positions[0]
    )

    assert position.market_value == D("2000")
