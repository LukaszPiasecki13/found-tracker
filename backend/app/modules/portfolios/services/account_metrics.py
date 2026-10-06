"""Account vectors: the portfolios' vectors added up in the account currency (DEC-01,
DEC-03, DEC-05).

Money that moved (deposits and withdrawals as net deposits, transaction costs,
dividends) keeps the rate of the day it moved: each day's change is converted at
that day's rate and added up, so a deposit never changes with the exchange rate.
Money held (the assets, the free cash) is valued at each day's rate. The change
that the rate causes on what is held therefore lands in the profit, and the
account's return is the profit over the net deposits, both in the account currency.

Each portfolio is valued by the same `VectorCalculator` as its own chart. The
return indices of portfolios are not added up (DEC-06).

The account currency is the owner's `base_currency` (DEC-08); a user without one
gets `ACCOUNT_FALLBACK_CURRENCY`.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Any

import numpy as np

from app.modules.assets.services.currencies import CurrencyService
from app.modules.assets.services.fx_rates import FxRateService
from app.modules.assets.services.market_data import MarketDataService
from app.modules.assets.services.prices import PriceService
from app.modules.portfolios.models import Operation
from app.modules.portfolios.repositories.operations import OperationRepository
from app.modules.portfolios.schemas.metrics import (
    AccountVectorsQuery,
    PortfolioVectorsResponse,
)
from app.modules.portfolios.services.metrics import (
    Vector,
    VectorCalculator,
    as_json_value,
    requested_vectors,
    validated_range,
)

ACCOUNT_FALLBACK_CURRENCY = "PLN"
# The account's vectors: every portfolio vector except the per-ticker `assets`
# (DEC-05). `pocket_value_vector` is the frontend's historical name of the value.
ACCOUNT_VECTOR_KEYS = (
    "asset_classes",
    "net_deposits_vector",
    "transaction_cost_vector",
    "dividend_income_vector",
    "free_cash_vector",
    "profit_vector",
    "portfolio_value_vector",
    "pocket_value_vector",
)


def _by_portfolio(operations: Sequence[Operation]) -> dict[int, list[Operation]]:
    groups: dict[int, list[Operation]] = {}
    for operation in operations:
        groups.setdefault(operation.portfolio_id, []).append(operation)
    return groups


def _booked(total: Vector, rate: Vector) -> Vector:
    """A cumulative flow in the account currency: each day's change at that day's
    rate, added up. Its value is fixed on the day the change happened."""
    return np.cumsum(np.diff(total, prepend=0.0) * rate)


def _in_account_currency(
    calculator: VectorCalculator, currency: str
) -> dict[str, Vector | dict[str, Vector]]:
    """One portfolio's account vectors. `rate` is units of the account currency per
    unit of the portfolio's base currency, day by day."""
    rate = calculator.rate_vector(calculator.base_currency, currency)
    net_deposits = _booked(calculator.net_deposits(), rate)
    transaction_cost = _booked(calculator.transaction_cost(), rate)
    dividend_income = _booked(calculator.dividend_income(), rate)
    free_cash = calculator.free_cash() * rate
    value = free_cash + calculator.sum_value() * rate
    return {
        "asset_classes": {
            name: series * rate for name, series in calculator.asset_classes().items()
        },
        "net_deposits_vector": net_deposits,
        "transaction_cost_vector": transaction_cost,
        "dividend_income_vector": dividend_income,
        "free_cash_vector": free_cash,
        "profit_vector": value - net_deposits,
        "portfolio_value_vector": value,
        "pocket_value_vector": value,
    }


def _add(
    total: Vector | dict[str, Vector] | None, part: Vector | dict[str, Vector]
) -> Vector | dict[str, Vector]:
    """The running sum of one vector over the portfolios; a per-class dict is summed
    class by class (a class held in only some portfolios counts from those)."""
    if total is None:
        return part
    if isinstance(total, dict) and isinstance(part, dict):
        merged = dict(total)
        for name, series in part.items():
            merged[name] = merged[name] + series if name in merged else series
        return merged
    if isinstance(total, np.ndarray) and isinstance(part, np.ndarray):
        return total + part
    raise TypeError("A vector and a per-class vector cannot be summed")


class AccountMetricsService:
    """Read model of the account vectors (ADR-0003: a DTO, no entity behind it)."""

    def __init__(
        self,
        operation_repo: OperationRepository,
        currencies: CurrencyService,
        market_data: MarketDataService,
        prices: PriceService,
        fx_rates: FxRateService,
    ) -> None:
        self._operation_repo = operation_repo
        self._currencies = currencies
        self._market_data = market_data
        self._prices = prices
        self._fx_rates = fx_rates

    def account_vectors(
        self, owner_id: int, query: AccountVectorsQuery, base_currency_id: int | None
    ) -> PortfolioVectorsResponse:
        """`date` plus the requested vectors (all account vectors when none are named)
        summed over all the owner's portfolios, in the account currency; `{}` when
        there are no operations. Errors are those of `MetricsService.portfolio_vectors`
        plus whatever the rate lookup raises (RATE_MISSING, CURRENCY_NOT_FOUND)."""
        operations = self._operation_repo.list_by_owner(owner_id)
        if not operations:
            return PortfolioVectorsResponse({})

        requested = requested_vectors(query.vectors)
        start, end = validated_range(query.start_date, query.end_date, query.interval)
        currency = self._account_currency(base_currency_id)
        wanted = requested or ACCOUNT_VECTOR_KEYS
        names = [key for key in wanted if key in ACCOUNT_VECTOR_KEYS]

        totals: dict[str, Vector | dict[str, Vector]] = {}
        dates: list[datetime] = []
        for portfolio_operations in _by_portfolio(operations).values():
            calculator = VectorCalculator(
                portfolio_operations,
                start,
                end,
                self._market_data,
                self._prices,
                self._fx_rates,
            )
            dates = calculator.dates()
            parts = _in_account_currency(calculator, currency)
            for name in names:
                totals[name] = _add(totals.get(name), parts[name])

        result: dict[str, Any] = {"date": dates}
        for name, series in totals.items():
            result[name] = as_json_value(series)
        return PortfolioVectorsResponse(result)

    def _account_currency(self, base_currency_id: int | None) -> str:
        if base_currency_id is None:
            return ACCOUNT_FALLBACK_CURRENCY
        currency = self._currencies.find_by_id(base_currency_id)
        return currency.code if currency is not None else ACCOUNT_FALLBACK_CURRENCY
