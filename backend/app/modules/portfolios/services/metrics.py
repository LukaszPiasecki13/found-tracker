"""Portfolio vectors: daily series of a portfolio's metrics for charts.

ADR-0005 variant (a): the vector arithmetic stays here, in `services/`, on
`numpy` - `domain/` is standard library only. Price history comes through the
`PriceHistoryProvider` port (satisfied by `assets`' `MarketDataService`), never
from a market-data library inside the computation.

Money is `Decimal` until a running total is written into a chart vector; the
vectors themselves are `float` (ADR-0010). Semantics carried over from the
previous implementation:

- the date vector is every day from `start` to `end`, both included;
- an operation lands on day `max(0, (operation_date - start) // 1 day)` (UTC)
  and sets its running total from that day on; operations after `end` count
  for nothing visible;
- an asset's daily value is quantity x close; closes are the provider's
  (`end` exclusive) laid over the full calendar range, the last day takes the
  current price when `end` is a weekday, then gaps are filled forward and
  backward; a ticker with no price at all fails its vector;
- a vector that fails is logged and returned as zeros, the others still are.
"""

import json
import logging
from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from itertools import groupby
from typing import Any, Protocol

import numpy as np
from numpy.typing import NDArray

from app.modules.portfolios.domain import OperationType
from app.modules.portfolios.exceptions import (
    InvalidDateError,
    InvalidDateRangeError,
    InvalidVectorsError,
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
_SUPPORTED_INTERVAL = "1d"
_DATE_FORMAT = "%Y-%m-%d"
_SATURDAY = 5
_ZERO = Decimal("0")

type Vector = NDArray[np.float64]


class PriceHistoryProvider(Protocol):
    """Prices the vectors need - a port; `MarketDataService` satisfies it."""

    def close_history(self, ticker: str, start: date, end: date) -> dict[date, Decimal]:
        """Daily closes for `start <= day < end`."""
        ...

    def current_price(self, ticker: str) -> Decimal | None:
        """The current price, `None` when there is none."""
        ...


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
    """What the operation cost: a buy its price and fee, a sell gives back its
    proceeds net of the fee, anything else costs its fee."""
    match operation.operation_type:
        case OperationType.BUY:
            return operation.quantity * operation.price + operation.fee
        case OperationType.SELL:
            return -(operation.quantity * operation.price - operation.fee)
    return operation.fee


class _VectorCalculator:
    """The vectors of one request; each ticker's prices are fetched once."""

    def __init__(
        self,
        operations: Sequence[Operation],
        start: datetime,
        end: datetime,
        prices: PriceHistoryProvider,
    ) -> None:
        self._operations = operations
        self._start = start
        self._end = end
        self._prices = prices
        self.length = int((end - start).total_seconds() // _DAY_SECONDS) + 1
        self._closes: dict[str, Vector] = {}
        self._assets: dict[str, Vector] | None = None
        self._transaction_cost: Vector | None = None
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

    def _close_vector(self, ticker: str) -> Vector:
        cached = self._closes.get(ticker)
        if cached is not None:
            return cached
        first_day = self._start.date()
        history = self._prices.close_history(ticker, first_day, self._end.date())
        closes: list[float | None] = []
        for offset in range(self.length):
            close = history.get(first_day + timedelta(days=offset))
            closes.append(float(close) if close is not None else None)
        if self._end.weekday() < _SATURDAY and closes[-1] is None:
            current = self._prices.current_price(ticker)
            if current is not None:
                closes[-1] = float(current)
        vector = np.array(_filled(closes, ticker), dtype=float)
        self._closes[ticker] = vector
        return vector

    def _value_vector(self, ticker: str, trades: Iterable[Operation]) -> Vector:
        quantity = self._running_total(trades, _quantity_change)
        return quantity * self._close_vector(ticker)

    def _trades(self) -> list[Operation]:
        return [
            op
            for op in self._operations
            if op.operation_type in (OperationType.BUY, OperationType.SELL)
        ]

    def _sum_value(self) -> Vector:
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

    def profit(self) -> Vector:
        return self._sum_value() - self.transaction_cost()

    def free_cash(self) -> Vector:
        return self.net_deposits() - self.transaction_cost()

    def portfolio_value(self) -> Vector:
        return self.free_cash() + self._sum_value()


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
        raise ValueError(f"No price data for {ticker}")
    return [close if close is not None else first for close in filled]


# Request key -> vector. `pocket_value_vector` is the frontend's historical name.
_VECTORS: dict[str, Callable[[_VectorCalculator], Vector | dict[str, Vector]]] = {
    "assets": _VectorCalculator.assets,
    "asset_classes": _VectorCalculator.asset_classes,
    "net_deposits_vector": _VectorCalculator.net_deposits,
    "transaction_cost_vector": _VectorCalculator.transaction_cost,
    "profit_vector": _VectorCalculator.profit,
    "free_cash_vector": _VectorCalculator.free_cash,
    "pocket_value_vector": _VectorCalculator.portfolio_value,
    "portfolio_value_vector": _VectorCalculator.portfolio_value,
}


def _requested_vectors(raw: str) -> list[Any]:
    try:
        requested = json.loads(raw)
    except json.JSONDecodeError as err:
        raise InvalidVectorsError from err
    if not isinstance(requested, list):
        raise InvalidVectorsError
    return requested


def _parse_date(value: str | None) -> datetime:
    if not value:
        raise InvalidDateError
    try:
        return datetime.strptime(value, _DATE_FORMAT)
    except ValueError as err:
        raise InvalidDateError from err


def _as_json_value(value: Vector | dict[str, Vector]) -> list[float] | dict[str, Any]:
    if isinstance(value, dict):
        return {name: series.tolist() for name, series in value.items()}
    return value.tolist()


class MetricsService:
    """Read model of portfolio vectors (ADR-0003: a DTO, no entity behind it)."""

    def __init__(
        self, operation_repo: OperationRepository, prices: PriceHistoryProvider
    ) -> None:
        self._operation_repo = operation_repo
        self._prices = prices

    def portfolio_vectors(
        self, owner_id: int, query: PortfolioVectorsQuery
    ) -> PortfolioVectorsResponse:
        """`date` plus the requested vectors (all when none are named) of the
        owner's portfolio `query.portfolio_name` (all portfolios when absent);
        `{}` when there are no operations.

        Raises InvalidVectorsError, InvalidDateError, InvalidDateRangeError,
        UnsupportedIntervalError.
        """
        operations = self._operation_repo.list_by_owner(
            owner_id, portfolio_name=query.portfolio_name
        )
        if not operations:
            return PortfolioVectorsResponse({})

        requested = _requested_vectors(query.vectors)
        start = _parse_date(query.start_date)
        end = _parse_date(query.end_date)
        if start > end:
            raise InvalidDateRangeError
        if query.interval != _SUPPORTED_INTERVAL:
            raise UnsupportedIntervalError

        calculator = _VectorCalculator(operations, start, end, self._prices)
        result: dict[str, Any] = {"date": calculator.dates()}
        for key in requested or list(_VECTORS):
            if not isinstance(key, str) or key not in _VECTORS:
                continue
            try:
                value = _VECTORS[key](calculator)
            except Exception:
                logger.exception(
                    "Failed to compute portfolio vector %s for portfolio %s",
                    key,
                    query.portfolio_name,
                )
                value = calculator.zeros()
            result[key] = _as_json_value(value)
        return PortfolioVectorsResponse(result)
