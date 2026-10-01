"""Parity with the Django application (`backend-old/portfolios/tests/integration/
test_views.py`, R-08): the same operations give the same cash and positions.

The Django tests post random operations through the API and compare the stored
state with sums over what they posted; here the draws are seeded (repeatable)
and go straight through the ledger. Known deliberate differences, kept on the
FastAPI side:

- Django's `Pocket.total_fees` sums the fees of all operations; FastAPI's
  `total_fees` sums the positions' fees (deposits/withdrawals not included) -
  not asserted here;
- deleting a buy/sell was not implemented in Django (skipped tests); FastAPI
  rebuilds from history, covered in `test_ledger.py`.
"""

import random
from collections import defaultdict
from decimal import Decimal

import pytest

from app.modules.portfolios.domain import (
    InsufficientCashError,
    InsufficientQuantityError,
    InvalidOperationError,
    LedgerState,
    OperationInput,
    OperationType,
    PortfolioLedger,
)

D = Decimal
LOOP_COUNT = 50
START_CASH = D("10000000")
TICKERS = 20  # the factory draws from ~100 tickers; fewer means more repeats


@pytest.fixture
def ledger() -> PortfolioLedger:
    return PortfolioLedger()


def _draw_trade(rng: random.Random, operation_type: OperationType) -> OperationInput:
    """`TransactionFactory.draw_buy/draw_sell`: price 50-500, quantity 1-100,
    fee 0-10, fx 0.5-5.0."""
    return OperationInput(
        operation_type,
        asset_id=rng.randint(1, TICKERS),
        quantity=D(rng.randint(1, 100)),
        price=D(rng.randint(50, 500)),
        fee=D(rng.randint(0, 10)),
        fx_rate=D(rng.randint(5, 50)) / 10,
    )


def _buys(ledger: PortfolioLedger, seed: int) -> tuple[LedgerState, list]:
    rng = random.Random(seed)
    state = LedgerState(cash_balance=START_CASH)
    buys = []
    for _ in range(LOOP_COUNT):
        operation = _draw_trade(rng, OperationType.BUY)
        state = ledger.apply(state, operation)
        buys.append(operation)
    return state, buys


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_buy_random_assets_with_replacement(ledger: PortfolioLedger, seed: int) -> None:
    """`test_buy_random_assets_with_replacement` (+ `test_asset_allocation_list`)."""
    state, buys = _buys(ledger, seed)

    by_asset: dict[int, list[OperationInput]] = defaultdict(list)
    for operation in buys:
        by_asset[operation.asset_id or 0].append(operation)
    assert {p.asset_id for p in state.positions} == set(by_asset)
    for position in state.positions:
        bought = by_asset[position.asset_id]
        quantity = sum((op.quantity for op in bought), D(0))
        cost = sum((op.quantity * op.price + op.fee for op in bought), D(0))
        assert position.quantity == quantity
        assert position.total_fees == sum((op.fee for op in bought), D(0))
        # Django: approx(abs=0.01); the running weighted average equals the
        # one-shot average up to Decimal's 28 significant digits.
        assert abs(position.average_buy_price - cost / quantity) < D("1e-20")

    total_cost = sum((op.quantity * op.price + op.fee) * op.fx_rate for op in buys)
    assert state.cash_balance == START_CASH - total_cost  # exact, not approx


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_buy_sell_random(ledger: PortfolioLedger, seed: int) -> None:
    """`test_buy_sell_random` / `_sell_assets`: one sell per held asset; more
    than held is rejected, exactly as much closes the position."""
    state, buys = _buys(ledger, seed)
    rng = random.Random(seed + 1000)
    bought: dict[int, D] = defaultdict(D)
    fees: dict[int, D] = defaultdict(D)
    for operation in buys:
        bought[operation.asset_id or 0] += operation.quantity
        fees[operation.asset_id or 0] += operation.fee
    average_before = {p.asset_id: p.average_buy_price for p in state.positions}

    expected_cash = state.cash_balance
    for asset_id in sorted(bought):
        drawn = _draw_trade(rng, OperationType.SELL)
        operation = OperationInput(
            OperationType.SELL,
            asset_id=asset_id,
            quantity=drawn.quantity,
            price=drawn.price,
            fee=drawn.fee,
            fx_rate=drawn.fx_rate,
        )
        if bought[asset_id] < operation.quantity:
            with pytest.raises(InsufficientQuantityError):
                ledger.apply(state, operation)
            continue
        state = ledger.apply(state, operation)
        expected_cash += (operation.quantity * operation.price - operation.fee) * (
            operation.fx_rate
        )
        position = state.position(asset_id)
        if bought[asset_id] == operation.quantity:
            assert position is None
        else:
            assert position is not None
            assert position.quantity == bought[asset_id] - operation.quantity
            assert position.total_fees == fees[asset_id] + operation.fee
            # Weighted average, unchanged by a sell (Django's FIFO check in this
            # test was disabled - `except: ...`).
            assert position.average_buy_price == average_before[asset_id]

    assert state.cash_balance == expected_cash


@pytest.mark.parametrize("amount", ["-1", "0", "1", "1.1", "100"])
@pytest.mark.parametrize("fee", ["-1", "0", "1", "1.1", "100"])
def test_add_funds(ledger: PortfolioLedger, amount: str, fee: str) -> None:
    """`test_add_funds`: cash 100, every amount x fee combination."""
    operation = OperationInput(OperationType.DEPOSIT, amount=D(amount), fee=D(fee))

    if D(amount) <= 0 or D(fee) < 0:
        with pytest.raises(InvalidOperationError):
            ledger.apply(LedgerState(cash_balance=D(100)), operation)
        return
    state = ledger.apply(LedgerState(cash_balance=D(100)), operation)
    assert state.cash_balance == D(100) + D(amount) - D(fee)


@pytest.mark.parametrize("amount", ["-1", "0", "1", "1.1", "100", "100.01"])
def test_withdraw_funds(ledger: PortfolioLedger, amount: str) -> None:
    """`test_withdraw_funds`: cash 100, fee 0."""
    operation = OperationInput(OperationType.WITHDRAWAL, amount=D(amount))
    start = LedgerState(cash_balance=D(100))

    if D(amount) <= 0:
        with pytest.raises(InvalidOperationError):
            ledger.apply(start, operation)
    elif D(100) - D(amount) < 0:
        with pytest.raises(InsufficientCashError):
            ledger.apply(start, operation)
    else:
        assert ledger.apply(start, operation).cash_balance == D(100) - D(amount)


@pytest.mark.parametrize(
    ("field", "values"),
    [
        ("price", ["-10", "-1", "0"]),
        ("quantity", ["-10", "-1", "0"]),
        ("fee", ["-10", "-1"]),
        ("fx_rate", ["-10", "-1", "0"]),
    ],
)
def test_operations_wrong_data(
    ledger: PortfolioLedger, field: str, values: list[str]
) -> None:
    """`test_operations_wrong_data`: a buy of 1 @ 1, fee 1, fx 1 with one field
    broken is rejected, naming that field."""
    for value in values:
        fields = {"quantity": D(1), "price": D(1), "fee": D(1), "fx_rate": D(1)}
        fields[field] = D(value)
        operation = OperationInput(OperationType.BUY, asset_id=1, **fields)

        with pytest.raises(InvalidOperationError) as exc_info:
            ledger.apply(LedgerState(cash_balance=START_CASH), operation)

        assert exc_info.value.field == field


def _deposits(rng: random.Random) -> list[OperationInput]:
    """`TransactionFactory.draw_add_founds`: amount 100-10000 in hundreds,
    fee 0-10."""
    return [
        OperationInput(
            OperationType.DEPOSIT,
            amount=D(rng.randint(1, 100) * 100),
            fee=D(rng.randint(0, 10)),
        )
        for _ in range(LOOP_COUNT)
    ]


def test_add_funds_destroy(ledger: PortfolioLedger) -> None:
    """`test_add_funds_destroy`: deleting a deposit takes back its net amount
    (rebuild of the remaining history = Django's reversal)."""
    history = _deposits(random.Random(7))
    state = ledger.rebuild(history)
    assert state.cash_balance == sum((op.amount - op.fee for op in history), D(0))

    while history:
        removed = history.pop(0)
        rebuilt = ledger.rebuild(history)
        assert rebuilt.cash_balance == state.cash_balance - (
            removed.amount - removed.fee
        )
        assert rebuilt.total_deposited == state.total_deposited - removed.amount
        state = rebuilt


def test_withdraw_funds_destroy(ledger: PortfolioLedger) -> None:
    """`test_withdraw_funds_destroy`: deleting a withdrawal gives back its
    amount and fee. Django set the starting cash directly; here it is an
    initial deposit."""
    rng = random.Random(11)
    initial = OperationInput(OperationType.DEPOSIT, amount=START_CASH)
    withdrawals = [
        OperationInput(
            OperationType.WITHDRAWAL,
            amount=D(rng.randint(1, 100) * 100),
            fee=D(rng.randint(0, 10)),
        )
        for _ in range(LOOP_COUNT)
    ]
    state = ledger.rebuild([initial, *withdrawals])
    assert state.cash_balance == START_CASH - sum(
        (op.amount + op.fee for op in withdrawals), D(0)
    )

    while withdrawals:
        removed = withdrawals.pop()
        rebuilt = ledger.rebuild([initial, *withdrawals])
        assert rebuilt.cash_balance == state.cash_balance + removed.amount + removed.fee
        state = rebuilt
