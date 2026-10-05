"""Daily snapshots of a portfolio and its time-weighted return (ADR-0004, ADR-0016).

Level 2 of the domain (DOM-9): a component (DOM-10). `DailySnapshotBuilder`
replays a portfolio's history day by day through `PortfolioLedger`, values the
open positions at each day's close and chains the daily returns into
`twr_index`. Exact `Decimal` arithmetic, nothing rounded (ADR-0010, ADR-0014).

Daily return, Portfolio Performance convention (ADR-0004): a deposit counts from
the start of the day, a withdrawal from its end, and the flows of one day are
netted, so `1 + r = (end value + outflow) / (start value + inflow)`. A zero
denominator gives `r = 0` (the series restarts). Dividends, interest and fees are
part of the value, never an external flow.
"""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from app.modules.portfolios.domain.enums import OperationType
from app.modules.portfolios.domain.errors import PortfolioDomainError
from app.modules.portfolios.domain.ledger import (
    LedgerState,
    OperationInput,
    PortfolioLedger,
)

_ZERO = Decimal("0")
_ONE = Decimal("1")
_HUNDRED = Decimal("100")

# Name of the return methodology reported next to the number (ADR-0004 section 7).
TWR_METHOD = "daily_pp_v1"


def twr_method(*, last_trade: bool, trade_fx: bool) -> str:
    """The method name for the approximations used: `last_trade` - an asset with no
    market price at all was valued at its last trade price; `trade_fx` - an asset
    quoted in another currency than the portfolio's was converted at the rate of
    its last trade (there is no historical FX series). Each is an approximation,
    so each gives the number a method of its own."""
    parts = [
        name
        for used, name in ((last_trade, "last_trade"), (trade_fx, "trade_fx"))
        if used
    ]
    return "+".join([TWR_METHOD, *parts])


# Closes by asset id, then by day.
Closes = Mapping[int, Mapping[date, Decimal]]


class MissingPriceError(PortfolioDomainError):
    """A held asset has no close on a day the snapshot has to value."""

    code = "PRICE_MISSING"

    def __init__(self, asset_id: int, day: date) -> None:
        super().__init__(f"Asset {asset_id} has no close on {day}")
        self.asset_id = asset_id
        self.day = day


@dataclass(frozen=True, slots=True)
class DatedOperation:
    """An operation with the calendar day (UTC) it lands on."""

    day: date
    operation: OperationInput


@dataclass(frozen=True, slots=True)
class DailyRow:
    """One portfolio day: value at the close, cash, the netted external flow
    (`inflow` or `outflow`), the day's return and the cumulative index."""

    day: date
    value: Decimal
    cash: Decimal
    inflow: Decimal
    outflow: Decimal
    r_day: Decimal
    twr_index: Decimal


def external_flow(operation: OperationInput) -> Decimal:
    """What the operation moves across the portfolio's border: a deposit adds its
    amount, a withdrawal takes it; anything else is internal."""
    amount = operation.amount or _ZERO
    match operation.operation_type:
        case OperationType.DEPOSIT:
            return amount
        case OperationType.WITHDRAWAL:
            return -amount
    return _ZERO


def daily_return(previous_value: Decimal, flow: Decimal, value: Decimal) -> Decimal:
    """`r` of one day for a net external `flow` (positive: money in)."""
    inflow = max(flow, _ZERO)
    outflow = max(-flow, _ZERO)
    denominator = previous_value + inflow
    if denominator == _ZERO:
        return _ZERO
    return (value + outflow) / denominator - _ONE


def return_pct(twr_index: Decimal) -> Decimal:
    """The cumulative return in percent."""
    return (twr_index - _ONE) * _HUNDRED


class DailySnapshotBuilder:
    """Builds the daily rows of one portfolio (built in `wiring.py`, DOM-10)."""

    def __init__(self, ledger: PortfolioLedger) -> None:
        self._ledger = ledger

    def build(
        self,
        operations: Sequence[DatedOperation],
        closes: Closes,
        *,
        start: date,
        end: date,
        previous: DailyRow | None,
        foreign: Collection[int] = (),
    ) -> list[DailyRow]:
        """Rows for `start <= day <= end`. `operations` is the whole history in
        ledger order; the days before `start` are only replayed, so only
        `start..end` need closes (in the units of their day). `previous` is the
        stored row just before `start` (`None` when `start` is the portfolio's
        first day). An asset with no closes at all (the provider does not know it)
        is valued at its last trade price; one with closes but none for a day
        raises MissingPriceError, as do the ledger's `PortfolioDomainError`s.
        `foreign` are the assets quoted in another currency than the portfolio's:
        their value is converted at the
        `fx_rate` of their last trade."""
        if not operations:
            return []
        last_trade: dict[int, Decimal] = {}
        last_fx: dict[int, Decimal] = {}
        state = LedgerState()
        previous_value = previous.value if previous else _ZERO
        index = previous.twr_index if previous else _ONE
        rows: list[DailyRow] = []
        position = 0
        day = operations[0].day
        while day <= end:
            flow = _ZERO
            while position < len(operations) and operations[position].day <= day:
                operation = operations[position].operation
                state = self._ledger.apply(state, operation)
                flow += external_flow(operation)
                _track_trade(last_trade, last_fx, operation)
                position += 1
            if day >= start:
                value = _value(state, closes, day, last_trade, last_fx, foreign)
                r_day = daily_return(previous_value, flow, value)
                index *= _ONE + r_day
                rows.append(
                    DailyRow(
                        day=day,
                        value=value,
                        cash=state.cash_balance,
                        inflow=max(flow, _ZERO),
                        outflow=max(-flow, _ZERO),
                        r_day=r_day,
                        twr_index=index,
                    )
                )
                previous_value = value
            day += timedelta(days=1)
        return rows

    def index_after(
        self, previous: DailyRow | None, flow: Decimal, value: Decimal
    ) -> Decimal:
        """The cumulative index once one more day with a net external `flow`
        ends at `value`: the live "today" that is not stored yet."""
        previous_value = previous.value if previous else _ZERO
        index = previous.twr_index if previous else _ONE
        return index * (_ONE + daily_return(previous_value, flow, value))


def _track_trade(
    last_trade: dict[int, Decimal],
    last_fx: dict[int, Decimal],
    operation: OperationInput,
) -> None:
    """The last trade price (in the units of the day: a split divides it by its
    ratio, as it does the held price) and the last trade `fx_rate` of each asset."""
    asset_id = operation.asset_id
    if asset_id is None:
        return
    match operation.operation_type:
        case OperationType.BUY | OperationType.SELL:
            last_trade[asset_id] = operation.price
            last_fx[asset_id] = operation.fx_rate
        case OperationType.SPLIT if asset_id in last_trade and operation.ratio:
            last_trade[asset_id] /= operation.ratio


def _value(
    state: LedgerState,
    closes: Closes,
    day: date,
    last_trade: Mapping[int, Decimal],
    last_fx: Mapping[int, Decimal],
    foreign: Collection[int],
) -> Decimal:
    """Cash plus each position at the day's close. Closes and the ledger's
    quantities are both in the units of the day (the provider adapter undoes the
    split adjustment, a recorded `split` multiplies the ledger's quantity), so no
    scaling is needed here. An asset with no closes at all is valued at its last
    trade price (also in the day's units). A foreign asset's value is converted at
    the rate of its last trade."""
    total = state.cash_balance
    for held in state.positions:
        rate = last_fx.get(held.asset_id, _ONE) if held.asset_id in foreign else _ONE
        history = closes.get(held.asset_id)
        if not history and held.asset_id in last_trade:
            total += held.quantity * last_trade[held.asset_id] * rate
            continue
        close = history.get(day) if history else None
        if close is None:
            raise MissingPriceError(held.asset_id, day)
        total += held.quantity * close * rate
    return total
