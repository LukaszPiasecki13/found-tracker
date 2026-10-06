"""Portfolio vectors: daily series of a portfolio's metrics for charts.

ADR-0005 variant (a): the vector arithmetic stays here, in `services/`, on
`numpy` - `domain/` is standard library only. Prices and rates are read from the
stored history (`assets`' `PriceService`, `FxRateService`, ADR-0015); the provider
is called only to backfill a missing history (`MarketDataService.backfill_closes`)
and for a stale current price or rate, never for a value the database holds
(Decision DEC-01, DEC-13).

Money is `Decimal` until a running total is written into a chart vector; the
vectors themselves are `float` (ADR-0010). Semantics carried over from the
previous implementation:

- the date vector is every day from `start` to `end`, both included;
- an operation lands on day `max(0, (operation_date - start) // 1 day)` (UTC)
  and sets its running total from that day on; operations after `end` count
  for nothing visible;
- an asset's daily value in the portfolio's base currency is quantity x close x
  rate: closes are the provider's (`end` exclusive) laid over the full calendar
  range, the last day takes the current price when `end` is a weekday, then gaps
  are filled forward and backward; the rate is the daily FX rate from the asset's
  currency to the base currency, built the same way; an asset already in the base
  currency has rate 1 and no FX lookup;
- an asset never held in the range is worth 0 and is not looked up; an asset held
  in the range with no market price at all (delisted, unknown to the provider) is
  valued at the prices of its own buys and sells, which is an estimate and is
  logged; a currency pair with no rate at all fails its vector;
- a vector that cannot be computed (provider down, no price or rate at all)
  fails the request - zeros would draw a worthless portfolio;
- the cost and cash vectors follow the ledger: buy/sell/dividend amounts carry
  the operation's `fx_rate`, a dividend adds its income to free cash and profit.
  The operation's `fx_rate` is the rate of the day it was booked; the value uses
  the daily rate. On the day of a buy with a constant price and rate, the profit
  moves by exactly the fee, not by the cost;
- all operations of one request share one base currency; mixed bases fail.
"""

import json
import logging
from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from itertools import groupby
from typing import Any

import numpy as np
from numpy.typing import NDArray

from app.modules.assets.constants import SOURCE_MANUAL
from app.modules.assets.exceptions import RateMissingError
from app.modules.assets.models.assets import Asset
from app.modules.assets.models.fx_rates import FxRate
from app.modules.assets.services.fx_rates import FxRateService
from app.modules.assets.services.market_data import MarketDataService
from app.modules.assets.services.prices import PriceService
from app.modules.portfolios.domain import OperationType
from app.modules.portfolios.exceptions import (
    InvalidDateError,
    InvalidDateRangeError,
    InvalidVectorsError,
    MixedBaseCurrenciesError,
    PriceDataMissingError,
    UnsupportedIntervalError,
)
from app.modules.portfolios.models import Operation
from app.modules.portfolios.repositories.operations import OperationRepository
from app.modules.portfolios.schemas.metrics import (
    PortfolioVectorsQuery,
    PortfolioVectorsResponse,
)

logger = logging.getLogger(__name__)

_DAY_SECONDS = 24 * 60 * 60
SUPPORTED_INTERVAL = "1d"
_DATE_FORMAT = "%Y-%m-%d"
_SATURDAY = 5
_ZERO = Decimal("0")
_ONE = Decimal("1")
# Longest range of daily points one request may ask for (about ten years).
MAX_RANGE_DAYS = 3660

type Vector = NDArray[np.float64]


def _naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _ticker(operation: Operation) -> str:
    if operation.asset is None:
        raise ValueError(f"Operation {operation.id} has no asset")
    return operation.asset.ticker


def _asset_class_name(operation: Operation) -> str:
    if operation.asset is None:
        raise ValueError(f"Operation {operation.id} has no asset")
    return operation.asset.asset_class.name


def _asset_currency(operation: Operation) -> str:
    if operation.asset is None:
        raise ValueError(f"Operation {operation.id} has no asset")
    return operation.asset.currency.code


def _base_currency(operations: Sequence[Operation]) -> str:
    """The one base currency every operation of the request is booked in."""
    codes = {operation.portfolio.base_currency.code for operation in operations}
    if len(codes) != 1:
        raise MixedBaseCurrenciesError(sorted(codes))
    return codes.pop()


def _asset_of(operation: Operation) -> Asset:
    if operation.asset is None:
        raise ValueError(f"Operation {operation.id} has no asset")
    return operation.asset


def _daily_rates(rows: Iterable[FxRate]) -> dict[date, Decimal]:
    """One rate per day; a manual observation outranks a provider's (ADR-0015)."""
    rates: dict[date, Decimal] = {}
    for row in sorted(rows, key=lambda row: row.source != SOURCE_MANUAL):
        rates.setdefault(row.rate_date, row.rate)
    return rates


def _quantity_change(operation: Operation) -> Decimal:
    match operation.operation_type:
        case OperationType.BUY:
            return operation.quantity
        case OperationType.SELL:
            return -operation.quantity
    return _ZERO


def _net_deposit_change(operation: Operation) -> Decimal:
    amount = operation.amount or _ZERO
    match operation.operation_type:
        case OperationType.DEPOSIT:
            return amount
        case OperationType.WITHDRAWAL:
            return -amount
    return _ZERO


def _transaction_cost_change(operation: Operation) -> Decimal:
    """What the operation cost, in the portfolio's currency like the ledger's
    cash: a buy its price and fee, a sell gives back its proceeds net of the fee,
    a dividend costs its fee, a cash operation its fee; interest is a negative
    cost (its amount less the fee) and a charge costs its amount and fee."""
    fx_rate = operation.fx_rate
    match operation.operation_type:
        case OperationType.BUY:
            return (operation.quantity * operation.price + operation.fee) * fx_rate
        case OperationType.SELL:
            return -(operation.quantity * operation.price - operation.fee) * fx_rate
        case OperationType.DIVIDEND:
            return operation.fee * fx_rate
        case OperationType.INTEREST:
            return -(operation.amount or _ZERO) + operation.fee
        case OperationType.FEE:
            return (operation.amount or _ZERO) + operation.fee
    return operation.fee


def _dividend_income_change(operation: Operation) -> Decimal:
    """The gross dividend paid, in the portfolio's currency."""
    if operation.operation_type != OperationType.DIVIDEND:
        return _ZERO
    return (operation.amount or _ZERO) * operation.fx_rate


class VectorCalculator:
    """The vectors of one request; each ticker's prices are fetched once."""

    def __init__(
        self,
        operations: Sequence[Operation],
        start: datetime,
        end: datetime,
        market_data: MarketDataService,
        prices: PriceService,
        fx_rates: FxRateService,
    ) -> None:
        self._operations = operations
        self._start = start
        self._end = end
        self._market_data = market_data
        self._prices = prices
        self._fx = fx_rates
        self._base = _base_currency(operations)
        self.length = int((end - start).total_seconds() // _DAY_SECONDS) + 1
        self._closes: dict[str, Vector] = {}
        self._rates: dict[tuple[str, str], Vector] = {}
        self._assets: dict[str, Vector] | None = None
        self._transaction_cost: Vector | None = None
        self._dividend_income: Vector | None = None
        self._net_deposits: Vector | None = None

    # --- Building blocks ---

    def dates(self) -> list[datetime]:
        return [self._start + timedelta(days=day) for day in range(self.length)]

    def zeros(self) -> Vector:
        return np.zeros(self.length, dtype=float)

    def _day_index(self, operation: Operation) -> int:
        elapsed = _naive_utc(operation.operation_date) - self._start
        return max(0, int(elapsed.total_seconds() / _DAY_SECONDS))

    def _running_total(
        self,
        operations: Iterable[Operation],
        change: Callable[[Operation], Decimal],
    ) -> Vector:
        """From each operation's day on, the running total of `change`."""
        vector = self.zeros()
        total = _ZERO
        ordered = sorted(operations, key=lambda op: _naive_utc(op.operation_date))
        for operation in ordered:
            total += change(operation)
            index = self._day_index(operation)
            if index < self.length:
                vector[index:] = float(total)
        return vector

    def _daily_series(
        self,
        label: str,
        history: dict[date, Decimal],
        current: Callable[[], Decimal | None],
    ) -> Vector:
        """One value per day of the calendar range from `history`; the last day
        takes `current` when `end` is a weekday and history has no value for it,
        then gaps are filled forward and backward. `label` names the series in
        the error when it has no value at all."""
        first_day = self._start.date()
        values: list[float | None] = []
        for offset in range(self.length):
            value = history.get(first_day + timedelta(days=offset))
            values.append(float(value) if value is not None else None)
        if self._end.weekday() < _SATURDAY and values[-1] is None:
            latest = current()
            if latest is not None:
                values[-1] = float(latest)
        return np.array(_filled(values, label), dtype=float)

    def _close_vector(self, ticker: str, ordered: Sequence[Operation]) -> Vector:
        cached = self._closes.get(ticker)
        if cached is not None:
            return cached

        asset = _asset_of(ordered[0])
        history = self._stored_closes(asset, ordered)
        try:
            vector = self._daily_series(
                ticker, history, lambda: self._current_close(asset)
            )
        except PriceDataMissingError:
            # Delisted or unknown to the provider: value the held days at the
            # prices of the ledger's own trades (an estimate, logged).
            logger.warning(
                "No market price for %s; valuing held days at trade prices", ticker
            )
            vector = self._trade_price_vector(ticker, ordered)
        self._closes[ticker] = vector
        return vector

    def _trade_price_vector(self, ticker: str, ordered: Sequence[Operation]) -> Vector:
        """Daily price of the last trade on or before each day, in the asset's
        currency; forward-filled. Only buys and sells carry a trade price."""
        values: list[float | None] = [None] * self.length
        for operation in ordered:
            if operation.operation_type not in (OperationType.BUY, OperationType.SELL):
                continue
            index = self._day_index(operation)
            if index < self.length and operation.price:
                values[index] = float(operation.price)
        return np.array(_filled(values, ticker), dtype=float)

    def _stored_closes(
        self, asset: Asset, ordered: Sequence[Operation]
    ) -> dict[date, Decimal]:
        """Decision DEC-03: the stored closes of the range. A history that does not
        reach the first held day is backfilled from the provider first
        (`MarketDataService.backfill_closes` commits its own transaction, ADR-0015),
        then read again. A provider failure propagates as MarketDataUnavailableError."""
        start, end = self._start.date(), self._end.date()
        history = self._read_closes(asset.id, start, end)
        first_held = max(start, _naive_utc(ordered[0].operation_date).date())
        if not history or min(history) > first_held:
            self._market_data.backfill_closes([asset], start, end)
            history = self._read_closes(asset.id, start, end)
        return history

    def _read_closes(
        self, asset_id: int, start: date, end: date
    ) -> dict[date, Decimal]:
        """Stored closes for `start <= day < end`, one per day (the winning source);
        a single-day range (`start == end`) reads that day."""
        last = max(start, end - timedelta(days=1))
        series = self._prices.series(asset_id, from_date=start, to_date=last)
        return {item.day: item.close for item in series.items}

    def _current_close(self, asset: Asset) -> Decimal | None:
        """Decision DEC-14: the latest stored close while it is fresh, the provider's
        current price only when that close is stale or missing."""
        quote = self._prices.find_close(asset.id, self._end.date())
        if quote is not None and not quote.stale:
            return quote.close
        return self._market_data.current_price(asset.ticker)

    @property
    def base_currency(self) -> str:
        return self._base

    def rate_vector(self, currency: str, target: str | None = None) -> Vector:
        """Units of `target` (the base currency by default) per one unit of
        `currency`, day by day. A currency already in `target` needs no rate and
        no lookup."""
        target = target or self._base
        if currency == target:
            return np.ones(self.length, dtype=float)
        key = (currency, target)
        cached = self._rates.get(key)
        if cached is not None:
            return cached
        vector = self._daily_series(
            f"{currency}{target}",
            self._stored_rates(currency, target),
            lambda: self._current_rate(currency, target),
        )
        self._rates[key] = vector
        return vector

    def _stored_rates(self, currency: str, target: str) -> dict[date, Decimal]:
        """Decision DEC-13: the stored daily rates of the pair, used only when they
        reach the start of the range. The refresh stores today's rate alone, so a
        short history would be stretched over the whole range by the fill; then the
        provider's history is read instead, without storing it (no FX backfill yet)."""
        start, end = self._start.date(), self._end.date()
        last = max(start, end - timedelta(days=1))
        rows = self._fx.history(currency, target, from_date=start, to_date=last)
        history = _daily_rates(rows)
        if history and min(history) <= start:
            return history
        return self._market_data.fx_history(currency, target, start, end)

    def _current_rate(self, currency: str, target: str) -> Decimal | None:
        """Decision DEC-14 for rates: the stored rate while fresh, else the provider."""
        try:
            quote = self._fx.get_rate(currency, target, self._end.date())
        except RateMissingError:
            quote = None
        if quote is not None and not quote.stale:
            return quote.rate
        return self._market_data.current_fx_rate(currency, target)

    def _value_vector(self, ticker: str, operations: Iterable[Operation]) -> Vector:
        """Quantity x close x rate: the value of one asset in the base currency.
        An asset never held in the range is worth zero and needs no price or rate,
        so a sold-out, delisted ticker cannot fail the whole request."""
        ordered = sorted(operations, key=lambda op: _naive_utc(op.operation_date))
        quantity = self._quantity_vector(ordered)
        if not quantity.any():
            return self.zeros()
        rate = self.rate_vector(_asset_currency(ordered[0]))
        return quantity * self._close_vector(ticker, ordered) * rate

    def _quantity_vector(self, ordered: Sequence[Operation]) -> Vector:
        """The quantity held each day, in the units of that day: a buy or sell
        moves it, a split multiplies it from its day on. The closes are in the
        units of their day too (the provider adapter undoes Yahoo's split
        adjustment), so quantity x close is the value."""
        vector = self.zeros()
        total = _ZERO
        for operation in ordered:
            if operation.operation_type == OperationType.SPLIT:
                total *= operation.ratio or _ONE
            else:
                total += _quantity_change(operation)
            index = self._day_index(operation)
            if index < self.length:
                vector[index:] = float(total)
        return vector

    def _trades(self) -> list[Operation]:
        return [
            op
            for op in self._operations
            if op.operation_type
            in (OperationType.BUY, OperationType.SELL, OperationType.SPLIT)
        ]

    def sum_value(self) -> Vector:
        total = self.zeros()
        for vector in self.assets().values():
            total += vector
        return total

    # --- Vectors ---

    def assets(self) -> dict[str, Vector]:
        """Value of each held asset, by ticker (alphabetical)."""
        if self._assets is None:
            trades = sorted(self._trades(), key=_ticker)
            self._assets = {
                ticker: self._value_vector(ticker, group)
                for ticker, group in groupby(trades, key=_ticker)
            }
        return self._assets

    def asset_classes(self) -> dict[str, Vector]:
        """Value of the assets of each asset class, by class name."""
        result: dict[str, Vector] = {}
        trades = sorted(self._trades(), key=_asset_class_name)
        for class_name, class_trades in groupby(trades, key=_asset_class_name):
            total = self.zeros()
            by_ticker = sorted(class_trades, key=_ticker)
            for ticker, group in groupby(by_ticker, key=_ticker):
                total += self._value_vector(ticker, group)
            result[class_name] = total
        return result

    def net_deposits(self) -> Vector:
        if self._net_deposits is None:
            cash_operations = [
                op
                for op in self._operations
                if op.operation_type
                in (OperationType.DEPOSIT, OperationType.WITHDRAWAL)
            ]
            self._net_deposits = self._running_total(
                cash_operations, _net_deposit_change
            )
        return self._net_deposits

    def transaction_cost(self) -> Vector:
        if self._transaction_cost is None:
            self._transaction_cost = self._running_total(
                self._operations, _transaction_cost_change
            )
        return self._transaction_cost

    def dividend_income(self) -> Vector:
        if self._dividend_income is None:
            self._dividend_income = self._running_total(
                self._operations, _dividend_income_change
            )
        return self._dividend_income

    def profit(self) -> Vector:
        return self.sum_value() - self.transaction_cost() + self.dividend_income()

    def free_cash(self) -> Vector:
        return self.net_deposits() - self.transaction_cost() + self.dividend_income()

    def portfolio_value(self) -> Vector:
        return self.free_cash() + self.sum_value()


def _filled(closes: list[float | None], ticker: str) -> list[float]:
    """Gaps filled forward, then the leading ones backward."""
    filled: list[float | None] = []
    last: float | None = None
    for close in closes:
        if close is not None:
            last = close
        filled.append(last)
    first = next((close for close in filled if close is not None), None)
    if first is None:
        raise PriceDataMissingError(ticker)
    return [close if close is not None else first for close in filled]


# Request key -> vector. `pocket_value_vector` is the frontend's historical name.
VECTORS: dict[str, Callable[[VectorCalculator], Vector | dict[str, Vector]]] = {
    "assets": VectorCalculator.assets,
    "asset_classes": VectorCalculator.asset_classes,
    "net_deposits_vector": VectorCalculator.net_deposits,
    "transaction_cost_vector": VectorCalculator.transaction_cost,
    "profit_vector": VectorCalculator.profit,
    "dividend_income_vector": VectorCalculator.dividend_income,
    "free_cash_vector": VectorCalculator.free_cash,
    "pocket_value_vector": VectorCalculator.portfolio_value,
    "portfolio_value_vector": VectorCalculator.portfolio_value,
}


def requested_vectors(raw: str) -> list[Any]:
    try:
        requested = json.loads(raw)
    except json.JSONDecodeError as err:
        raise InvalidVectorsError from err
    if not isinstance(requested, list):
        raise InvalidVectorsError
    return requested


def parse_date(value: str | None) -> datetime:
    if not value:
        raise InvalidDateError
    try:
        return datetime.strptime(value, _DATE_FORMAT)
    except ValueError as err:
        raise InvalidDateError from err


def validated_range(
    start_date: str | None, end_date: str | None, interval: str
) -> tuple[datetime, datetime]:
    """Both dates of a request, checked: parsed, ordered, not over
    `MAX_RANGE_DAYS`, and the interval the only one supported."""
    start = parse_date(start_date)
    end = parse_date(end_date)
    if start > end or (end - start).days >= MAX_RANGE_DAYS:
        raise InvalidDateRangeError
    if interval != SUPPORTED_INTERVAL:
        raise UnsupportedIntervalError
    return start, end


def as_json_value(value: Vector | dict[str, Vector]) -> list[float] | dict[str, Any]:
    if isinstance(value, dict):
        return {name: series.tolist() for name, series in value.items()}
    series_list: list[float] = value.tolist()
    return series_list


class MetricsService:
    """Read model of portfolio vectors (ADR-0003: a DTO, no entity behind it)."""

    def __init__(
        self,
        operation_repo: OperationRepository,
        market_data: MarketDataService,
        prices: PriceService,
        fx_rates: FxRateService,
    ) -> None:
        self._operation_repo = operation_repo
        self._market_data = market_data
        self._prices = prices
        self._fx_rates = fx_rates

    def portfolio_vectors(
        self, owner_id: int, query: PortfolioVectorsQuery
    ) -> PortfolioVectorsResponse:
        """`date` plus the requested vectors (all when none are named) of the
        owner's portfolio `query.portfolio_name` (all portfolios when absent);
        `{}` when there are no operations.

        Raises InvalidVectorsError, InvalidDateError, InvalidDateRangeError
        (also for a range over `MAX_RANGE_DAYS`), UnsupportedIntervalError,
        PriceDataMissingError, MarketDataUnavailableError.
        """
        operations = self._operation_repo.list_by_owner(
            owner_id, portfolio_name=query.portfolio_name
        )
        if not operations:
            return PortfolioVectorsResponse({})

        requested = requested_vectors(query.vectors)
        start, end = validated_range(query.start_date, query.end_date, query.interval)

        calculator = VectorCalculator(
            operations,
            start,
            end,
            self._market_data,
            self._prices,
            self._fx_rates,
        )
        result: dict[str, Any] = {"date": calculator.dates()}
        for key in requested or list(VECTORS):
            if not isinstance(key, str) or key not in VECTORS:
                continue
            result[key] = as_json_value(VECTORS[key](calculator))
        return PortfolioVectorsResponse(result)
