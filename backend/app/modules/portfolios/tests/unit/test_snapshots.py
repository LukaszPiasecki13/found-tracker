"""`DailySnapshotBuilder` - daily rows and the time-weighted return (ADR-0004)."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.modules.portfolios.domain import (
    DailyRow,
    DailySnapshotBuilder,
    DatedOperation,
    MissingPriceError,
    OperationInput,
    OperationType,
    PortfolioLedger,
    external_flow,
    return_pct,
    twr_method,
)

D = Decimal
DAY0 = date(2026, 1, 5)
ASSET = 1


def day(offset: int) -> date:
    return DAY0 + timedelta(days=offset)


def deposit(offset: int, amount: str) -> DatedOperation:
    return DatedOperation(
        day(offset), OperationInput(OperationType.DEPOSIT, amount=D(amount))
    )


def withdrawal(offset: int, amount: str) -> DatedOperation:
    return DatedOperation(
        day(offset), OperationInput(OperationType.WITHDRAWAL, amount=D(amount))
    )


def buy(
    offset: int, quantity: str, price: str, operation_id: int = 0
) -> DatedOperation:
    return DatedOperation(
        day(offset),
        OperationInput(
            OperationType.BUY,
            asset_id=ASSET,
            quantity=D(quantity),
            price=D(price),
        ),
    )


def dividend(offset: int, amount: str) -> DatedOperation:
    return DatedOperation(
        day(offset),
        OperationInput(OperationType.DIVIDEND, asset_id=ASSET, amount=D(amount)),
    )


def closes(*prices: str) -> dict[int, dict[date, Decimal]]:
    """One close per day from DAY0 on."""
    return {ASSET: {day(i): D(price) for i, price in enumerate(prices)}}


def build(
    operations: list[DatedOperation],
    prices: dict[int, dict[date, Decimal]],
    *,
    last: int,
    start: int = 0,
    previous: DailyRow | None = None,
) -> list[DailyRow]:
    builder = DailySnapshotBuilder(PortfolioLedger())
    return builder.build(
        operations, prices, start=day(start), end=day(last), previous=previous
    )


def build_foreign(
    operations: list[DatedOperation],
    prices: dict[int, dict[date, Decimal]],
    *,
    last: int,
) -> list[DailyRow]:
    """As `build`, with the asset quoted in another currency than the portfolio's."""
    builder = DailySnapshotBuilder(PortfolioLedger())
    return builder.build(
        operations,
        prices,
        start=day(0),
        end=day(last),
        previous=None,
        foreign={ASSET},
    )


def test_a_lone_deposit_has_no_return() -> None:
    rows = build([deposit(0, "1000")], {}, last=2)

    assert [row.r_day for row in rows] == [0, 0, 0]
    assert rows[-1].twr_index == 1
    assert rows[-1].value == D("1000")
    assert rows[0].inflow == D("1000")
    assert rows[1].inflow == 0


def test_price_growth_chains_into_the_index() -> None:
    operations = [deposit(0, "1000"), buy(0, "10", "100")]

    rows = build(operations, closes("100", "110", "121"), last=2)

    assert [row.r_day for row in rows] == [D("0"), D("0.1"), D("0.1")]
    assert return_pct(rows[-1].twr_index) == D("21")


def test_a_deposit_in_the_middle_does_not_change_the_return() -> None:
    operations = [
        deposit(0, "1000"),
        buy(0, "10", "100"),
        deposit(2, "1100"),
    ]

    rows = build(operations, closes("100", "110", "110"), last=2)

    # Day 2: value 2200 = 1100 + 1100 in cash; the money in is not a gain.
    assert rows[2].value == D("2200")
    assert rows[2].r_day == 0
    assert return_pct(rows[2].twr_index) == D("10")


def test_a_withdrawal_in_the_middle_does_not_change_the_return() -> None:
    operations = [
        deposit(0, "1000"),
        buy(0, "5", "100"),
        withdrawal(2, "500"),
    ]

    rows = build(operations, closes("100", "120", "120"), last=2)

    assert rows[2].value == D("600")
    assert rows[2].outflow == D("500")
    assert rows[2].r_day == 0
    # Half of the money sat in cash, so +20% on the shares is +10% overall.
    assert return_pct(rows[2].twr_index) == D("10")


def test_flows_of_one_day_are_netted() -> None:
    operations = [deposit(0, "100"), deposit(1, "100"), withdrawal(1, "40")]

    rows = build(operations, {}, last=1)

    assert rows[1].inflow == D("60")
    assert rows[1].outflow == 0
    assert rows[1].r_day == 0


def test_an_empty_portfolio_restarts_the_series() -> None:
    operations = [deposit(0, "100"), withdrawal(1, "100"), deposit(3, "100")]

    rows = build(operations, {}, last=3)

    assert [row.value for row in rows] == [D("100"), D("0"), D("0"), D("100")]
    assert [row.r_day for row in rows] == [0, 0, 0, 0]
    assert rows[-1].twr_index == 1


def test_a_dividend_is_value_not_a_flow() -> None:
    operations = [deposit(0, "1000"), buy(0, "10", "100"), dividend(1, "50")]

    rows = build(operations, closes("100", "100"), last=1)

    assert rows[1].value == D("1050")
    assert rows[1].inflow == 0
    assert return_pct(rows[1].twr_index) == D("5")


def test_a_split_does_not_change_the_value() -> None:
    split = DatedOperation(
        day(1),
        OperationInput(OperationType.SPLIT, asset_id=ASSET, ratio=D("2")),
    )
    operations = [deposit(0, "1000"), buy(0, "10", "100"), split]

    # Closes are in the units of their day: 100 before the split, 50 from its day.
    rows = build(operations, closes("100", "50"), last=1)

    assert [row.value for row in rows] == [D("1000"), D("1000")]
    assert rows[-1].twr_index == 1


def test_a_split_that_happened_while_the_asset_was_not_held_changes_nothing() -> None:
    # Sold before the split, bought again after it: a recorded split is not needed,
    # the closes of the holdings are simply the raw ones of their days.
    sell = DatedOperation(
        day(1),
        OperationInput(
            OperationType.SELL, asset_id=ASSET, quantity=D("10"), price=D("100")
        ),
    )
    operations = [
        deposit(0, "1000"),
        buy(0, "10", "100"),
        sell,
        buy(3, "100", "10", operation_id=0),
    ]

    rows = build(operations, closes("100", "100", "10", "10"), last=3)

    assert [row.value for row in rows] == [D("1000")] * 4


def test_a_loss_is_negative() -> None:
    operations = [deposit(0, "1000"), buy(0, "10", "100")]

    rows = build(operations, closes("100", "90"), last=1)

    assert return_pct(rows[-1].twr_index) == D("-10")


def test_a_missing_close_of_a_held_asset_is_an_error() -> None:
    operations = [deposit(0, "1000"), buy(0, "10", "100")]

    with pytest.raises(MissingPriceError) as raised:
        build(operations, closes("100"), last=1)

    assert (raised.value.asset_id, raised.value.day) == (ASSET, day(1))
    assert raised.value.code == "PRICE_MISSING"


def test_an_asset_without_closes_is_valued_at_its_last_trade_price() -> None:
    sell = DatedOperation(
        day(2),
        OperationInput(
            OperationType.SELL, asset_id=ASSET, quantity=D("10"), price=D("120")
        ),
    )
    operations = [deposit(0, "1000"), buy(0, "10", "100"), sell]

    rows = build(operations, {}, last=3)

    assert [row.value for row in rows] == [D("1000"), D("1000"), D("1200"), D("1200")]
    assert return_pct(rows[-1].twr_index) == D("20")


def test_the_last_trade_price_follows_a_split() -> None:
    split = DatedOperation(
        day(1), OperationInput(OperationType.SPLIT, asset_id=ASSET, ratio=D("2"))
    )
    operations = [deposit(0, "1000"), buy(0, "10", "100"), split]

    rows = build(operations, {}, last=1)

    # 20 shares at 50 after the split: the value does not move.
    assert [row.value for row in rows] == [D("1000"), D("1000")]


def test_a_foreign_asset_is_converted_at_the_fx_rate_of_its_last_trade() -> None:
    first = DatedOperation(
        day(0),
        OperationInput(
            OperationType.BUY,
            asset_id=ASSET,
            quantity=D("10"),
            price=D("100"),
            fx_rate=D("4"),
        ),
    )
    operations = [deposit(0, "4000"), first]

    rows = build_foreign(operations, closes("100", "110"), last=1)

    assert [row.value for row in rows] == [D("4000"), D("4400")]
    assert return_pct(rows[-1].twr_index) == D("10")


def test_the_fx_rate_of_a_same_currency_asset_is_not_applied() -> None:
    operations = [
        deposit(0, "1000"),
        DatedOperation(
            day(0),
            OperationInput(
                OperationType.BUY,
                asset_id=ASSET,
                quantity=D("10"),
                price=D("100"),
                fx_rate=D("1"),
            ),
        ),
    ]

    rows = build(operations, closes("100", "110"), last=1)

    assert rows[-1].value == D("1100")


def test_a_foreign_asset_without_closes_uses_its_last_trade_price_and_rate() -> None:
    operations = [
        deposit(0, "4000"),
        DatedOperation(
            day(0),
            OperationInput(
                OperationType.BUY,
                asset_id=ASSET,
                quantity=D("10"),
                price=D("100"),
                fx_rate=D("4"),
            ),
        ),
    ]

    rows = build_foreign(operations, {}, last=1)

    assert [row.value for row in rows] == [D("4000"), D("4000")]


def test_the_method_names_the_approximations_used() -> None:
    assert twr_method(last_trade=False, trade_fx=False) == "daily_pp_v1"
    assert twr_method(last_trade=True, trade_fx=False) == "daily_pp_v1+last_trade"
    assert twr_method(last_trade=False, trade_fx=True) == "daily_pp_v1+trade_fx"
    assert (
        twr_method(last_trade=True, trade_fx=True) == "daily_pp_v1+last_trade+trade_fx"
    )


def test_days_before_start_need_no_closes() -> None:
    operations = [deposit(0, "1000"), buy(0, "10", "100")]
    prices = {ASSET: {day(2): D("120")}}
    previous = DailyRow(
        day=day(1),
        value=D("1000"),
        cash=D("0"),
        inflow=D("0"),
        outflow=D("0"),
        r_day=D("0"),
        twr_index=D("1"),
    )

    rows = build(operations, prices, last=2, start=2, previous=previous)

    assert [row.day for row in rows] == [day(2)]
    assert return_pct(rows[0].twr_index) == D("20")


def test_building_incrementally_gives_the_same_rows() -> None:
    operations = [
        deposit(0, "1000"),
        buy(0, "5", "100"),
        withdrawal(2, "100"),
        deposit(3, "300"),
    ]
    prices = closes("100", "110", "90", "95", "130")

    full = build(operations, prices, last=4)
    head = build(operations, prices, last=2)
    tail = build(operations, prices, last=4, start=3, previous=head[-1])

    assert head + tail == full


def test_nothing_to_build_without_operations() -> None:
    assert build([], {}, last=3) == []


def test_index_after_extends_the_last_row() -> None:
    operations = [deposit(0, "1000"), buy(0, "10", "100")]
    rows = build(operations, closes("100", "110"), last=1)
    builder = DailySnapshotBuilder(PortfolioLedger())

    # Today: 1100 -> 1210 with no flow is another +10%.
    index = builder.index_after(rows[-1], D("0"), D("1210"))

    assert return_pct(index) == D("21")


def test_index_after_without_history_starts_from_one() -> None:
    builder = DailySnapshotBuilder(PortfolioLedger())

    # The first day: 500 deposited, worth 500 now.
    assert builder.index_after(None, D("500"), D("500")) == 1


def test_external_flow_is_only_a_deposit_or_a_withdrawal() -> None:
    assert external_flow(OperationInput(OperationType.DEPOSIT, amount=D("5"))) == 5
    assert external_flow(OperationInput(OperationType.WITHDRAWAL, amount=D("5"))) == -5
    assert external_flow(OperationInput(OperationType.INTEREST, amount=D("5"))) == 0
