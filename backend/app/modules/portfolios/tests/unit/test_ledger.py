"""`PortfolioLedger` - pure domain, no database, no mocks."""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.modules.portfolios.domain import (
    AssetNotAllowedError,
    AssetRequiredError,
    InsufficientCashError,
    InsufficientQuantityError,
    InvalidOperationError,
    LedgerState,
    OperationInput,
    OperationType,
    PortfolioDomainError,
    PortfolioLedger,
    PositionNotFoundError,
    PositionState,
)

D = Decimal
ASSET = 7


@pytest.fixture
def ledger() -> PortfolioLedger:
    return PortfolioLedger()


def deposit(amount: str, fee: str = "0") -> OperationInput:
    return OperationInput(OperationType.DEPOSIT, amount=D(amount), fee=D(fee))


def withdrawal(amount: str, fee: str = "0") -> OperationInput:
    return OperationInput(OperationType.WITHDRAWAL, amount=D(amount), fee=D(fee))


def buy(
    quantity: str, price: str, fee: str = "0", fx_rate: str = "1", asset: int = ASSET
) -> OperationInput:
    return OperationInput(
        OperationType.BUY,
        asset_id=asset,
        quantity=D(quantity),
        price=D(price),
        fee=D(fee),
        fx_rate=D(fx_rate),
    )


def sell(
    quantity: str, price: str, fee: str = "0", fx_rate: str = "1", asset: int = ASSET
) -> OperationInput:
    return OperationInput(
        OperationType.SELL,
        asset_id=asset,
        quantity=D(quantity),
        price=D(price),
        fee=D(fee),
        fx_rate=D(fx_rate),
    )


def dividend(
    amount: str, fee: str = "0", fx_rate: str = "1", asset: int = ASSET
) -> OperationInput:
    return OperationInput(
        OperationType.DIVIDEND,
        asset_id=asset,
        amount=D(amount),
        fee=D(fee),
        fx_rate=D(fx_rate),
    )


def cash(amount: str) -> LedgerState:
    return LedgerState(cash_balance=D(amount))


# --- Deposit / withdrawal ---


def test_deposit_adds_amount_net_of_fee_and_counts_the_gross_deposit(
    ledger: PortfolioLedger,
) -> None:
    state = ledger.apply(cash("100"), deposit("50", fee="1.5"))

    assert state.cash_balance == D("148.5")
    assert state.total_deposited == D("50")


def test_withdrawal_takes_amount_and_fee_and_reduces_net_deposits(
    ledger: PortfolioLedger,
) -> None:
    start = LedgerState(cash_balance=D("100"), total_deposited=D("100"))

    state = ledger.apply(start, withdrawal("40", fee="2"))

    assert state.cash_balance == D("58")
    assert state.total_deposited == D("60")


def test_withdrawal_may_empty_the_cash_exactly(ledger: PortfolioLedger) -> None:
    assert ledger.apply(cash("100"), withdrawal("99", fee="1")).cash_balance == 0


def test_withdrawal_beyond_cash_is_insufficient_cash(ledger: PortfolioLedger) -> None:
    with pytest.raises(InsufficientCashError) as exc_info:
        ledger.apply(cash("100"), withdrawal("100", fee="0.01"))

    assert exc_info.value.code == "INSUFFICIENT_CASH"
    assert exc_info.value.required == D("100.01")
    assert exc_info.value.available == D("100")


# --- Buy ---


def test_first_buy_opens_a_position_with_the_fee_in_the_average_price(
    ledger: PortfolioLedger,
) -> None:
    state = ledger.apply(cash("1000"), buy("10", "20", fee="2", fx_rate="4"))

    assert state.cash_balance == D("1000") - D("808")  # (10 * 20 + 2) * 4
    assert state.positions == (
        PositionState(
            asset_id=ASSET,
            quantity=D("10"),
            average_buy_price=D("20.2"),
            average_fx_rate=D("4"),
            total_fees=D("2"),
            total_dividends=D("0"),
        ),
    )


def test_next_buy_weights_price_and_fx_rate_by_quantity(
    ledger: PortfolioLedger,
) -> None:
    state = ledger.apply(cash("10000"), buy("10", "20", fee="2"))

    state = ledger.apply(state, buy("5", "26", fee="1", fx_rate="1.5"))

    position = state.position(ASSET)
    assert position is not None
    assert position.quantity == D("15")
    # (10 * 20.2 + 5 * 26 + 1) / 15 = 333 / 15
    assert position.average_buy_price == D("22.2")
    # (10 * 1 + 5 * 1.5) / 15, at full Decimal precision - no rounding inside
    assert position.average_fx_rate == D("17.5") / D("15")
    assert position.total_fees == D("3")
    assert state.cash_balance == D("10000") - D("202") - D("196.5")


def test_buy_may_spend_the_cash_exactly(ledger: PortfolioLedger) -> None:
    assert ledger.apply(cash("202"), buy("10", "20", fee="2")).cash_balance == 0


def test_buy_beyond_cash_is_insufficient_cash(ledger: PortfolioLedger) -> None:
    with pytest.raises(InsufficientCashError) as exc_info:
        ledger.apply(cash("201.99"), buy("10", "20", fee="2"))

    assert exc_info.value.code == "INSUFFICIENT_CASH"


def test_buy_of_a_second_asset_keeps_the_first_position(
    ledger: PortfolioLedger,
) -> None:
    state = ledger.apply(cash("1000"), buy("1", "10", asset=1))

    state = ledger.apply(state, buy("2", "10", asset=2))

    assert [p.asset_id for p in state.positions] == [1, 2]


# --- Sell ---


def test_partial_sell_keeps_the_average_price_and_adds_the_fee(
    ledger: PortfolioLedger,
) -> None:
    state = ledger.apply(cash("1000"), buy("10", "20", fee="2"))

    state = ledger.apply(state, sell("4", "25", fee="1", fx_rate="2"))

    position = state.position(ASSET)
    assert position is not None
    assert position.quantity == D("6")
    assert position.average_buy_price == D("20.2")
    assert position.total_fees == D("3")
    assert state.cash_balance == D("798") + D("198")  # (4 * 25 - 1) * 2


def test_selling_everything_closes_the_position(ledger: PortfolioLedger) -> None:
    state = ledger.apply(cash("1000"), buy("10", "20", fee="2"))

    state = ledger.apply(state, sell("10", "25", fee="1"))

    assert state.positions == ()
    assert state.cash_balance == D("1047")


def test_sell_without_a_position_is_position_not_found(
    ledger: PortfolioLedger,
) -> None:
    with pytest.raises(PositionNotFoundError) as exc_info:
        ledger.apply(cash("1000"), sell("1", "10"))

    assert exc_info.value.code == "POSITION_NOT_FOUND"


def test_selling_more_than_held_is_insufficient_quantity(
    ledger: PortfolioLedger,
) -> None:
    state = ledger.apply(cash("1000"), buy("10", "20"))

    with pytest.raises(InsufficientQuantityError) as exc_info:
        ledger.apply(state, sell("10.000000001", "20"))

    assert exc_info.value.code == "INSUFFICIENT_QUANTITY"
    assert exc_info.value.held == D("10")


# --- Dividend ---


def test_dividend_adds_net_amount_at_fx_and_counts_the_gross(
    ledger: PortfolioLedger,
) -> None:
    held = PositionState(ASSET, D("10"), D("20"), D("1"))
    start = LedgerState(cash_balance=D("1000"), positions=(held,))

    state = ledger.apply(start, dividend("10", fee="1", fx_rate="2"))

    assert state.cash_balance == D("1018")
    position = state.position(ASSET)
    assert position is not None
    assert position.total_dividends == D("10")
    assert position.quantity == D("10")


def test_dividend_without_a_position_is_position_not_found(
    ledger: PortfolioLedger,
) -> None:
    with pytest.raises(PositionNotFoundError):
        ledger.apply(cash("1000"), dividend("10"))


# --- Validation: one place, one code per rule ---


@pytest.mark.parametrize(
    ("operation", "error", "code"),
    [
        (
            OperationInput(OperationType.BUY, quantity=D(1), price=D(1)),
            AssetRequiredError,
            "OPERATION_REQUIRES_ASSET",
        ),
        (
            OperationInput(OperationType.SELL, quantity=D(1), price=D(1)),
            AssetRequiredError,
            "OPERATION_REQUIRES_ASSET",
        ),
        (
            OperationInput(OperationType.DIVIDEND, amount=D(1)),
            AssetRequiredError,
            "OPERATION_REQUIRES_ASSET",
        ),
        (
            OperationInput(OperationType.DEPOSIT, asset_id=1, amount=D(1)),
            AssetNotAllowedError,
            "OPERATION_FORBIDS_ASSET",
        ),
        (
            OperationInput(OperationType.WITHDRAWAL, asset_id=1, amount=D(1)),
            AssetNotAllowedError,
            "OPERATION_FORBIDS_ASSET",
        ),
    ],
)
def test_asset_rules(
    ledger: PortfolioLedger,
    operation: OperationInput,
    error: type[PortfolioDomainError],
    code: str,
) -> None:
    with pytest.raises(error) as exc_info:
        ledger.validate(operation)

    assert exc_info.value.code == code


@pytest.mark.parametrize(
    ("operation", "field"),
    [
        (buy("0", "1"), "quantity"),
        (buy("-1", "1"), "quantity"),
        (buy("1", "0"), "price"),
        (buy("1", "-5"), "price"),
        (buy("1", "1", fee="-0.01"), "fee"),
        (buy("1", "1", fx_rate="0"), "fx_rate"),
        (sell("0", "1"), "quantity"),
        (sell("1", "0"), "price"),
        (sell("1", "1", fee="-1"), "fee"),
        (sell("1", "1", fx_rate="-1"), "fx_rate"),
        (deposit("0"), "amount"),
        (deposit("-10"), "amount"),
        (deposit("10", fee="-1"), "fee"),
        (OperationInput(OperationType.DEPOSIT), "amount"),
        (withdrawal("0"), "amount"),
        (withdrawal("10", fee="-1"), "fee"),
        (dividend("0"), "amount"),
        (dividend("1", fee="-1"), "fee"),
        (dividend("1", fx_rate="0"), "fx_rate"),
        (OperationInput(OperationType.DIVIDEND, asset_id=ASSET), "amount"),
        (buy("NaN", "1"), "quantity"),
        (buy("1", "Infinity"), "price"),
    ],
)
def test_sign_rules_name_the_offending_field(
    ledger: PortfolioLedger, operation: OperationInput, field: str
) -> None:
    with pytest.raises(InvalidOperationError) as exc_info:
        ledger.validate(operation)

    assert exc_info.value.code == "INVALID_OPERATION"
    assert exc_info.value.field == field
    assert field in str(exc_info.value)


@pytest.mark.parametrize(
    "operation",
    [
        buy("1", "1", fee="0"),
        sell("0.5", "1", fee="0"),
        deposit("0.01"),
        withdrawal("1", fee="0"),
        dividend("0.01", fee="0", fx_rate="0.5"),
        # `amount` is not read by buy and sell: anything goes.
        OperationInput(
            OperationType.BUY,
            asset_id=ASSET,
            quantity=D(1),
            price=D(1),
            amount=D(-5),
        ),
    ],
)
def test_valid_operations_pass_validation(
    ledger: PortfolioLedger, operation: OperationInput
) -> None:
    ledger.validate(operation)


def test_apply_validates_before_touching_the_state(ledger: PortfolioLedger) -> None:
    with pytest.raises(InvalidOperationError):
        ledger.apply(cash("1000"), buy("1", "1", fee="-1"))


def test_domain_errors_are_value_errors() -> None:
    assert issubclass(PortfolioDomainError, ValueError)


# --- Immutability and rebuild ---


def test_apply_returns_a_new_state_and_leaves_the_input_untouched(
    ledger: PortfolioLedger,
) -> None:
    start = ledger.apply(cash("1000"), buy("10", "20"))

    after = ledger.apply(start, sell("10", "20"))

    assert start.position(ASSET) is not None
    assert start.cash_balance == D("800")
    assert after.positions == ()


def test_rebuild_folds_the_history_from_an_empty_portfolio(
    ledger: PortfolioLedger,
) -> None:
    state = ledger.rebuild(
        [deposit("1000"), buy("10", "20"), dividend("5"), sell("4", "30", fee="1")]
    )

    assert state.total_deposited == D("1000")
    assert state.cash_balance == D("1000") - D("200") + D("5") + D("119")
    position = state.position(ASSET)
    assert position is not None
    assert (position.quantity, position.total_dividends, position.total_fees) == (
        D("6"),
        D("5"),
        D("1"),
    )


def test_rebuild_of_an_empty_history_is_an_empty_portfolio(
    ledger: PortfolioLedger,
) -> None:
    assert ledger.rebuild([]) == LedgerState()


def test_rebuild_respects_the_order_it_is_given(ledger: PortfolioLedger) -> None:
    with pytest.raises(InsufficientCashError):
        ledger.rebuild([buy("1", "10"), deposit("100")])

    with pytest.raises(PositionNotFoundError):
        ledger.rebuild([deposit("100"), sell("1", "10"), buy("1", "10")])


def test_rebuild_after_removing_a_buy_has_no_position(ledger: PortfolioLedger) -> None:
    state = ledger.rebuild([deposit("1000")])

    assert state == LedgerState(cash_balance=D("1000"), total_deposited=D("1000"))


def test_rebuild_reopened_position_starts_from_scratch(ledger: PortfolioLedger) -> None:
    state = ledger.rebuild(
        [
            deposit("1000"),
            buy("1", "10", fee="1"),
            dividend("2"),
            sell("1", "10"),
            buy("2", "30", fee="0.5"),
        ]
    )

    assert state.positions == (
        PositionState(ASSET, D("2"), D("30.25"), D("1"), D("0.5"), D("0")),
    )


# --- Boundary with stored rows (DOM-8) ---


def test_state_and_inputs_read_orm_like_rows() -> None:
    portfolio = SimpleNamespace(cash_balance=D("10.5"), total_deposited=D("12"))
    row = SimpleNamespace(
        asset_id=3,
        quantity=D("2"),
        average_buy_price=D("4"),
        average_fx_rate=D("1.1"),
        total_fees=D("0.2"),
        total_dividends=D("0.3"),
    )
    stored = SimpleNamespace(
        operation_type="dividend",
        asset_id=3,
        quantity=D("0"),
        price=D("0"),
        amount=D("1"),
        fee=D("0"),
        fx_rate=D("1"),
    )

    state = LedgerState.of(portfolio, [row])
    operation = OperationInput.from_operation(stored)

    assert state.position(3) == PositionState(
        3, D("2"), D("4"), D("1.1"), D("0.2"), D("0.3")
    )
    assert operation.operation_type is OperationType.DIVIDEND
    assert PortfolioLedger().apply(state, operation).cash_balance == D("11.5")


def test_unknown_stored_operation_type_is_an_invalid_operation() -> None:
    stored = SimpleNamespace(
        operation_type="transfer",
        asset_id=None,
        quantity=D("0"),
        price=D("0"),
        amount=None,
        fee=D("0"),
        fx_rate=D("1"),
    )

    with pytest.raises(InvalidOperationError) as exc_info:
        OperationInput.from_operation(stored)

    assert exc_info.value.field == "operation_type"
