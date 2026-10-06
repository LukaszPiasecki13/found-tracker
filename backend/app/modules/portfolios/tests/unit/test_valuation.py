"""`PortfolioValuator` - pure domain over ORM-like views (DOM-8)."""

from decimal import Decimal
from types import SimpleNamespace

from app.modules.portfolios.domain import FxMap, PortfolioValuator

D = Decimal
PLN, USD, EUR, GBP = 1, 2, 3, 4


def _portfolio(
    cash: str = "0", deposited: str = "0", *, base: int = PLN
) -> SimpleNamespace:
    return SimpleNamespace(
        base_currency_id=base, cash_balance=D(cash), total_deposited=D(deposited)
    )


def _holding(
    quantity: str,
    average_price: str,
    current_price: str,
    *,
    currency_id: int = PLN,
    average_fx: str = "1",
    fees: str = "0",
) -> SimpleNamespace:
    return SimpleNamespace(
        quantity=D(quantity),
        average_buy_price=D(average_price),
        average_fx_rate=D(average_fx),
        total_fees=D(fees),
        asset=SimpleNamespace(current_price=D(current_price), currency_id=currency_id),
    )


def test_position_in_the_base_currency_is_valued_without_fx() -> None:
    holding = _holding("10", "20", "25")

    # A rate for the base currency itself is never read.
    valuation = PortfolioValuator().value(
        _portfolio(), [holding], {(PLN, PLN): D("999")}
    )

    position = valuation.positions[0]
    assert position.cost_basis == D("200")
    assert position.cost_basis_in_portfolio_currency == D("200")
    assert position.market_value == D("250")
    assert position.unrealized_pnl == D("50")
    assert position.return_pct == D("25")
    assert position.rate_missing is False


def test_foreign_position_uses_the_mapped_rate_for_value_and_average_fx_for_cost() -> (
    None
):
    holding = _holding("10", "20", "25", currency_id=USD, average_fx="3.9")

    position = (
        PortfolioValuator()
        .value(_portfolio(), [holding], {(USD, PLN): D("4.1")})
        .positions[0]
    )

    assert position.cost_basis == D("200")
    assert position.cost_basis_in_portfolio_currency == D("780.0")
    assert position.market_value == D("1025.0")
    assert position.unrealized_pnl == D("245.0")
    assert position.return_pct == D("245.0") / D("780.0") * 100


def test_a_eur_position_in_a_pln_portfolio_uses_the_cross_rate() -> None:
    holding = _holding("10", "90", "100", currency_id=EUR, average_fx="4")
    rates: FxMap = {(EUR, PLN): D("4.32")}

    position = PortfolioValuator().value(_portfolio(), [holding], rates).positions[0]

    assert position.market_value == D("4320")
    assert position.unrealized_pnl == D("720")
    assert position.return_pct == D("20")


def test_price_and_fx_effects_sum_to_the_unrealized_profit() -> None:
    holding = _holding("10", "20", "25", currency_id=USD, average_fx="3.9")

    position = (
        PortfolioValuator()
        .value(_portfolio(), [holding], {(USD, PLN): D("4.1")})
        .positions[0]
    )

    assert position.price_effect == D("205")  # 10 * (25 - 20) * 4.1
    assert position.fx_effect == D("40")  # 10 * 20 * (4.1 - 3.9)
    assert position.price_effect + position.fx_effect == position.unrealized_pnl


def test_base_currency_position_has_no_fx_effect() -> None:
    holding = _holding("10", "20", "25")

    position = PortfolioValuator().value(_portfolio(), [holding], {}).positions[0]

    assert position.price_effect == D("50")  # 10 * (25 - 20) at rate 1
    assert position.fx_effect == D("0")
    assert position.fx_rate_applied == D("1")


def test_base_currency_fx_effect_stays_zero_for_a_stored_average_rate_near_one() -> (
    None
):
    holding = _holding("10", "20", "25", average_fx="1.0000001")

    position = PortfolioValuator().value(_portfolio(), [holding], {}).positions[0]

    assert position.fx_effect == D("0")


def test_missing_rate_keeps_the_asset_currency_view() -> None:
    holding = _holding("10", "90", "100", currency_id=EUR)

    position = PortfolioValuator().value(_portfolio(), [holding], {}).positions[0]

    assert position.rate_missing is True
    assert position.market_value is None
    assert position.market_value_asset_currency == D("1000")
    assert position.unrealized_pnl_asset_currency == D("100")
    assert position.price_change_pct == D("10") / D("90") * 100
    assert position.fx_rate_applied is None
    assert position.price_effect is None
    assert position.fx_effect is None


def test_zero_price_or_zero_average_gives_no_price_change() -> None:
    no_quote = _holding("10", "20", "0", currency_id=USD)
    no_average = _holding("10", "0", "25")

    valuation = PortfolioValuator().value(
        _portfolio(), [no_quote, no_average], {(USD, PLN): D("4")}
    )

    no_quote_position = valuation.positions[0]
    assert no_quote_position.price_change_pct is None
    assert no_quote_position.market_value_asset_currency is None
    assert no_quote_position.unrealized_pnl_asset_currency is None
    assert no_quote_position.price_effect is None
    assert no_quote_position.fx_effect is None
    assert valuation.positions[1].price_change_pct is None


def test_a_usd_position_in_a_pln_portfolio_uses_the_cross_rate() -> None:
    holding = _holding("10", "80", "100", currency_id=USD, average_fx="4")

    position = (
        PortfolioValuator()
        .value(_portfolio(), [holding], {(USD, PLN): D("4")})
        .positions[0]
    )

    assert position.market_value == D("4000")
    assert position.unrealized_pnl == D("800")
    assert position.return_pct == D("25")


def test_a_pln_position_in_a_usd_portfolio_is_valued_at_the_inverse_rate() -> None:
    holding = _holding("10", "20", "100", currency_id=PLN, average_fx="0.25")

    position = (
        PortfolioValuator()
        .value(_portfolio(base=USD), [holding], {(PLN, USD): D("0.25")})
        .positions[0]
    )

    assert position.cost_basis_in_portfolio_currency == D("50.00")
    assert position.market_value == D("250.00")


def test_a_position_without_a_rate_is_flagged_and_keeps_its_cost() -> None:
    holding = _holding("10", "2", "2.5", currency_id=GBP, average_fx="5")

    position = (
        PortfolioValuator()
        .value(_portfolio(), [holding], {(USD, PLN): D("4")})
        .positions[0]
    )

    assert position.rate_missing is True
    assert position.market_value is None
    assert position.unrealized_pnl is None
    assert position.return_pct is None
    assert position.portfolio_weight_pct is None
    assert position.cost_basis == D("20")
    assert position.cost_basis_in_portfolio_currency == D("100")


def test_one_position_without_a_rate_nulls_the_portfolio_totals() -> None:
    holdings = [
        _holding("10", "20", "25", fees="1.5"),
        _holding("2", "100", "90", currency_id=GBP, fees="2"),
    ]

    valuation = PortfolioValuator().value(
        _portfolio("250", "1000"), holdings, {(USD, PLN): D("4")}
    )

    assert valuation.rate_missing is True
    assert valuation.positions_value is None
    assert valuation.total_value is None
    assert valuation.total_profit_loss is None
    assert valuation.total_fees == D("3.5")
    priced, unpriced = valuation.positions
    assert priced.market_value == D("250")
    assert priced.rate_missing is False
    assert unpriced.market_value is None
    assert [p.portfolio_weight_pct for p in valuation.positions] == [None, None]


def test_portfolio_totals_include_cash_and_compare_with_net_deposits() -> None:
    holdings = [
        _holding("10", "20", "25", fees="1.5"),
        _holding("2", "100", "90", currency_id=USD, fees="2"),
    ]

    valuation = PortfolioValuator().value(
        _portfolio("250", "1000"), holdings, {(USD, PLN): D("4")}
    )

    assert valuation.rate_missing is False
    assert valuation.positions_value == D("250") + D("720")
    assert valuation.total_value == D("1220")
    assert valuation.total_profit_loss == D("220")
    assert valuation.total_fees == D("3.5")
    assert [p.portfolio_weight_pct for p in valuation.positions] == [
        D("250") / D("1220") * 100,
        D("720") / D("1220") * 100,
    ]


def test_golden_portfolio_in_pln_with_eur_usd_and_pln_positions() -> None:
    """Z1 of the E0.1 plan: rates USD=1, EUR=1.08, PLN=0.25 (USD per unit)."""
    holdings = [
        _holding("10", "90", "100", currency_id=EUR, average_fx="4"),
        _holding("10", "80", "100", currency_id=USD, average_fx="4"),
        _holding("5", "50", "60", currency_id=PLN, average_fx="1"),
    ]
    rates: FxMap = {(EUR, PLN): D("1.08") / D("0.25"), (USD, PLN): D("1") / D("0.25")}

    valuation = PortfolioValuator().value(_portfolio("1000", "10000"), holdings, rates)

    eur, usd, pln = valuation.positions
    assert [eur.market_value, usd.market_value, pln.market_value] == [
        D("4320"),
        D("4000"),
        D("300"),
    ]
    assert [eur.unrealized_pnl, eur.return_pct] == [D("720"), D("20")]
    assert [usd.unrealized_pnl, usd.return_pct] == [D("800"), D("25")]
    assert valuation.positions_value == D("8620")
    assert valuation.total_value == D("9620")
    assert valuation.total_profit_loss == D("-380")
    assert [p.portfolio_weight_pct for p in valuation.positions] == [
        D("4320") / D("9620") * 100,
        D("4000") / D("9620") * 100,
        D("300") / D("9620") * 100,
    ]


def test_zero_denominators_give_zero_percentages() -> None:
    free_gift = _holding("1", "0", "0")

    valuation = PortfolioValuator().value(_portfolio(), [free_gift], {})

    assert valuation.positions[0].return_pct == 0
    assert valuation.positions[0].portfolio_weight_pct == 0
    assert valuation.total_value == 0


def test_empty_portfolio_is_its_cash() -> None:
    valuation = PortfolioValuator().value(_portfolio("100", "80"), [], {})

    assert valuation.positions == ()
    assert valuation.positions_value == 0
    assert valuation.total_value == D("100")
    assert valuation.total_profit_loss == D("20")
    assert valuation.total_fees == 0
    assert valuation.rate_missing is False


def test_values_are_exact_not_rounded() -> None:
    holding = _holding("3", "0.1", "0.111111111")

    position = PortfolioValuator().value(_portfolio(), [holding], {}).positions[0]

    assert position.market_value == D("0.333333333")
    assert position.return_pct == (D("0.333333333") - D("0.3")) / D("0.3") * 100


def test_a_rate_with_many_digits_stays_exact_in_the_domain() -> None:
    holding = _holding("300", "1", "1", currency_id=PLN)
    rate = D("0.25") / D("1.08")

    position = (
        PortfolioValuator()
        .value(_portfolio(base=EUR), [holding], {(PLN, EUR): rate})
        .positions[0]
    )

    assert position.market_value == D("300") * rate
    assert str(position.market_value) == "69.44444444444444444444444445"
