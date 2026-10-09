"""`MetricsService` - vectors from operations and a fake price port.

Expected vectors are worked out by hand from the rules the Django
`PocketMetrics` and the pre-migration `PortfolioMetrics` share (see the
`services/metrics.py` docstring), with fixed prices instead of Yahoo Finance.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from itertools import count
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.market_data import MarketDataUnavailableError
from app.modules.assets.exceptions import RateMissingError
from app.modules.portfolios.exceptions import (
    InvalidDateError,
    InvalidDateRangeError,
    InvalidVectorsError,
    MixedBaseCurrenciesError,
    PriceDataMissingError,
    UnsupportedIntervalError,
)
from app.modules.portfolios.schemas.metrics import PortfolioVectorsQuery
from app.modules.portfolios.services.metrics import MetricsService, VectorCalculator

D = Decimal
_ids = count(1)


@dataclass
class FakePrices:
    """`PriceHistoryProvider` with fixed closes; `failing` tickers raise."""

    history: dict[str, dict[date, Decimal]] = field(default_factory=dict)
    current: dict[str, Decimal] = field(default_factory=dict)
    fx_rates: dict[str, dict[date, Decimal]] = field(default_factory=dict)
    fx_current: dict[str, Decimal] = field(default_factory=dict)
    failing: set[str] = field(default_factory=set)
    calls: list[tuple[str, str]] = field(default_factory=list)

    def close_history(self, ticker: str, start: date, end: date) -> dict[date, Decimal]:
        self.calls.append(("history", ticker))
        if ticker in self.failing:
            raise MarketDataUnavailableError
        return {
            day: close
            for day, close in self.history.get(ticker, {}).items()
            if start <= day < end
        }

    def current_price(self, ticker: str) -> Decimal | None:
        self.calls.append(("current", ticker))
        return self.current.get(ticker)

    def fx_history(
        self, from_code: str, to_code: str, start: date, end: date
    ) -> dict[date, Decimal]:
        pair = f"{from_code}{to_code}"
        self.calls.append(("fx_history", pair))
        return {
            day: rate
            for day, rate in self.fx_rates.get(pair, {}).items()
            if start <= day < end
        }

    def current_fx_rate(self, from_code: str, to_code: str) -> Decimal | None:
        pair = f"{from_code}{to_code}"
        self.calls.append(("current_fx", pair))
        return self.fx_current.get(pair)


_ASSET_IDS: dict[str, int] = {}


def _asset_id(ticker: str) -> int:
    return _ASSET_IDS.setdefault(ticker, len(_ASSET_IDS) + 1)


@dataclass
class FakeStore:
    """The stored history the vectors read - `PriceService` and `FxRateService` -
    and the `MarketDataService` calls they may make, over `FakePrices` as the
    provider. A backfill copies the provider's closes into the store; the current
    price is stored on the day asked for, as the daily refresh would have done
    (DEC-01, DEC-03, DEC-14)."""

    provider: FakePrices
    operations: list[SimpleNamespace] = field(default_factory=list)
    stored: dict[str, dict[date, Decimal]] = field(default_factory=dict)
    stored_fx: dict[str, dict[date, Decimal]] = field(default_factory=dict)

    def _ticker(self, asset_id: int) -> str:
        for operation in self.operations:
            if operation.asset is not None and operation.asset.id == asset_id:
                return operation.asset.ticker
        raise KeyError(asset_id)

    # PriceService
    def series(
        self, asset_id: int, *, from_date: date, to_date: date
    ) -> SimpleNamespace:
        closes = self.stored.get(self._ticker(asset_id), {})
        items = [
            SimpleNamespace(day=day, close=close)
            for day, close in sorted(closes.items())
            if from_date <= day <= to_date
        ]
        return SimpleNamespace(items=items)

    def find_close(self, asset_id: int, as_of: date) -> SimpleNamespace | None:
        ticker = self._ticker(asset_id)
        closes = self.stored.setdefault(ticker, {})
        if ticker in self.provider.current:
            closes.setdefault(as_of, self.provider.current[ticker])
        days = [day for day in closes if day <= as_of]
        if not days:
            return None
        day = max(days)
        return SimpleNamespace(close=closes[day], stale=(as_of - day).days > 7)

    # MarketDataService
    def backfill_closes(
        self, assets: list[SimpleNamespace], start: date, end: date
    ) -> int:
        for asset in assets:
            closes = self.provider.close_history(asset.ticker, start, end)
            self.stored.setdefault(asset.ticker, {}).update(closes)
        return 0

    def current_price(self, ticker: str) -> Decimal | None:
        return self.provider.current_price(ticker)

    def fx_history(
        self, from_code: str, to_code: str, start: date, end: date
    ) -> dict[date, Decimal]:
        return self.provider.fx_history(from_code, to_code, start, end)

    def current_fx_rate(self, from_code: str, to_code: str) -> Decimal | None:
        return self.provider.current_fx_rate(from_code, to_code)

    # FxRateService - the stored FX rows of the pair, as observations
    def history(
        self,
        from_code: str,
        to_code: str,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        source: str | None = None,
    ) -> list[SimpleNamespace]:
        rates = self.stored_fx.get(f"{from_code}{to_code}", {})
        return [
            SimpleNamespace(rate_date=day, rate=rate, source="yahoo")
            for day, rate in sorted(rates.items())
            if (from_date is None or day >= from_date)
            and (to_date is None or day <= to_date)
        ]

    def get_rate(self, from_code: str, to_code: str, as_of: date) -> object:
        raise RateMissingError


def _op(
    operation_type: str,
    when: datetime,
    *,
    ticker: str | None = None,
    asset_class: str = "Stock",
    currency: str = "PLN",
    base: str = "PLN",
    quantity: str = "0",
    price: str = "0",
    amount: str | None = None,
    fee: str = "0",
    fx_rate: str = "1",
    ratio: str | None = None,
) -> SimpleNamespace:
    asset = (
        SimpleNamespace(
            id=_asset_id(ticker),
            ticker=ticker,
            asset_class=SimpleNamespace(name=asset_class),
            currency=SimpleNamespace(code=currency),
        )
        if ticker
        else None
    )
    return SimpleNamespace(
        id=next(_ids),
        operation_type=operation_type,
        operation_date=when,
        asset=asset,
        portfolio=SimpleNamespace(base_currency=SimpleNamespace(code=base)),
        quantity=D(quantity),
        price=D(price),
        amount=D(amount) if amount is not None else None,
        fee=D(fee),
        fx_rate=D(fx_rate),
        ratio=D(ratio) if ratio is not None else None,
    )


def _at(day: int, hour: int = 12, month: int = 1, year: int = 2025) -> datetime:
    return datetime(year, month, day, hour, tzinfo=UTC)


def _query(
    vectors: str = "[]",
    start: str | None = "2025-01-01",
    end: str | None = "2025-01-07",
    interval: str = "1d",
) -> PortfolioVectorsQuery:
    return PortfolioVectorsQuery.model_validate(
        {
            "portfolioName": "Main",
            "startDate": start,
            "endDate": end,
            "interval": interval,
            "vectors": vectors,
        }
    )


@pytest.fixture
def operations() -> list[SimpleNamespace]:
    """2025-01-01 (Wed) .. 2025-01-07 (Tue); newest first, like the repository."""
    history = [
        _op("deposit", datetime(2024, 12, 30, tzinfo=UTC), amount="1000"),
        _op("buy", _at(2, 15), ticker="AAA", quantity="10", price="20", fee="2"),
        _op("buy", _at(3), ticker="BBB", asset_class="ETF", quantity="5", price="10"),
        _op("dividend", _at(6, 10), ticker="AAA", amount="3", fee="0.5"),
        _op("sell", _at(6, 12), ticker="AAA", quantity="4", price="25", fee="1"),
        _op("withdrawal", _at(7), amount="100"),
        # After `end`: counted in no visible day.
        _op("buy", _at(9), ticker="AAA", quantity="100", price="1"),
    ]
    return list(reversed(history))


@pytest.fixture
def prices() -> FakePrices:
    return FakePrices(
        history={
            # 01-01 holiday, 01-04/05 weekend, 01-07 excluded (`end` exclusive)
            "AAA": {
                date(2025, 1, 2): D("21"),
                date(2025, 1, 3): D("22"),
                date(2025, 1, 6): D("24"),
                date(2025, 1, 7): D("99"),
            },
            "BBB": {date(2025, 1, 1): D("10"), date(2025, 1, 2): D("10.5")},
        },
        current={"AAA": D("25")},  # BBB has no current price
    )


@pytest.fixture
def operation_repo() -> MagicMock:
    return MagicMock()


def _service(
    operation_repo: MagicMock, operations: list, prices: FakePrices
) -> MetricsService:
    operation_repo.list_by_owner.return_value = operations
    store = FakeStore(prices, operations)
    return MetricsService(operation_repo, store, store, store)


AAA = [0.0, 210.0, 220.0, 220.0, 220.0, 144.0, 150.0]
BBB = [0.0, 0.0, 52.5, 52.5, 52.5, 52.5, 52.5]
NET_DEPOSITS = [1000.0] * 6 + [900.0]
TRANSACTION_COST = [0.0, 202.0, 252.0, 252.0, 252.0, 153.5, 153.5]
DIVIDEND_INCOME = [0.0, 0.0, 0.0, 0.0, 0.0, 3.0, 3.0]


def test_all_vectors_by_default(
    operation_repo: MagicMock, operations: list, prices: FakePrices
) -> None:
    result = _service(operation_repo, operations, prices).portfolio_vectors(7, _query())

    body = result.model_dump(mode="json")
    operation_repo.list_by_owner.assert_called_once_with(7, portfolio_name="Main")
    assert body["date"] == [f"2025-01-0{day}T00:00:00" for day in range(1, 8)]
    assert body["assets"] == {"AAA": AAA, "BBB": BBB}
    assert body["asset_classes"] == {"ETF": BBB, "Stock": AAA}
    assert body["net_deposits_vector"] == NET_DEPOSITS
    assert body["transaction_cost_vector"] == TRANSACTION_COST
    assert body["profit_vector"] == [0.0, 8.0, 20.5, 20.5, 20.5, 46.0, 52.0]
    assert body["dividend_income_vector"] == DIVIDEND_INCOME
    assert body["free_cash_vector"] == [
        1000.0,
        798.0,
        748.0,
        748.0,
        748.0,
        849.5,
        749.5,
    ]
    portfolio_value = [1000.0, 1008.0, 1020.5, 1020.5, 1020.5, 1046.0, 952.0]
    assert body["portfolio_value_vector"] == portfolio_value
    assert body["pocket_value_vector"] == portfolio_value
    # No `asset_service` wired in this test's service, so benchmarks() short-circuits.
    assert body["benchmarks"] == {}
    assert list(body) == [
        "date",
        "assets",
        "asset_classes",
        "net_deposits_vector",
        "transaction_cost_vector",
        "profit_vector",
        "dividend_income_vector",
        "free_cash_vector",
        "pocket_value_vector",
        "portfolio_value_vector",
        "twr_index_vector",
        "drawdown_vector",
        "xirr_vector",
        "benchmarks",
    ]


def test_dividend_income_vector_with_fx_rate(
    operation_repo: MagicMock, prices: FakePrices
) -> None:
    operations = [
        _op("deposit", _at(1), amount="1000"),
        _op("buy", _at(2), ticker="AAA", quantity="10", price="20", fx_rate="4"),
        _op("dividend", _at(3), ticker="AAA", amount="5", fee="1", fx_rate="4"),
    ]

    body = _service(operation_repo, operations, prices).portfolio_vectors(
        1, _query('["dividend_income_vector"]', end="2025-01-03")
    )

    assert body.root["dividend_income_vector"] == [0.0, 0.0, 20.0]


def test_negative_transaction_cost_from_profitable_sell(
    operation_repo: MagicMock, prices: FakePrices
) -> None:
    operations = [
        _op("deposit", _at(1), amount="1000"),
        _op("buy", _at(2), ticker="AAA", quantity="10", price="100", fee="10"),
        _op("sell", _at(3), ticker="AAA", quantity="10", price="120", fee="5"),
    ]

    body = _service(operation_repo, operations, prices).portfolio_vectors(
        1, _query('["transaction_cost_vector"]', end="2025-01-03")
    )

    assert body.root["transaction_cost_vector"] == [0.0, 1010.0, -185.0]


def test_each_ticker_history_is_fetched_once_per_request(
    operation_repo: MagicMock, operations: list, prices: FakePrices
) -> None:
    _service(operation_repo, operations, prices).portfolio_vectors(7, _query())

    # The stored history is backfilled once per ticker; the current price is read
    # from the store (DEC-14), so the provider is not asked for it.
    assert sorted(prices.calls) == [("history", "AAA"), ("history", "BBB")]


def test_only_requested_vectors_unknown_names_skipped(
    operation_repo: MagicMock, operations: list, prices: FakePrices
) -> None:
    query = _query('["free_cash_vector", "nope", 3, "free_cash_vector"]')

    body = _service(operation_repo, operations, prices).portfolio_vectors(1, query)

    assert set(body.root) == {"date", "free_cash_vector"}
    assert prices.calls == []  # no asset vector asked for, no price fetched


def test_a_request_naming_only_unknown_vectors_gets_only_dates(
    operation_repo: MagicMock, operations: list, prices: FakePrices
) -> None:
    body = _service(operation_repo, operations, prices).portfolio_vectors(
        1, _query("[1]")
    )

    assert set(body.root) == {"date"}


def test_weekend_end_carries_the_friday_close_without_current_price(
    operation_repo: MagicMock, prices: FakePrices
) -> None:
    operations = [_op("buy", _at(2), ticker="AAA", quantity="1", price="1")]
    query = _query('["assets"]', start="2025-01-02", end="2025-01-05")  # Sunday

    body = _service(operation_repo, operations, prices).portfolio_vectors(1, query)

    assert body.root["assets"] == {"AAA": [21.0, 22.0, 22.0, 22.0]}
    assert ("current", "AAA") not in prices.calls


def test_provider_outage_fails_the_request_instead_of_drawing_zeros(
    operation_repo: MagicMock, operations: list, prices: FakePrices
) -> None:
    prices.failing.add("BBB")
    query = _query('["assets", "profit_vector"]')

    with pytest.raises(MarketDataUnavailableError):
        _service(operation_repo, operations, prices).portfolio_vectors(1, query)


def test_sold_out_ticker_without_any_price_does_not_fail_the_request(
    operation_repo: MagicMock, prices: FakePrices
) -> None:
    operations = [
        _op("buy", _at(2, month=12, year=2024), ticker="ZZZ", quantity="1", price="1"),
        _op("sell", _at(3, month=12, year=2024), ticker="ZZZ", quantity="1", price="1"),
        _op("buy", _at(2), ticker="AAA", quantity="1", price="1"),
    ]
    prices.history = {"AAA": {date(2025, 1, 2): D("20")}}
    prices.current = {}

    body = _service(operation_repo, operations, prices).portfolio_vectors(
        1, _query('["assets"]', start="2025-01-01", end="2025-01-03")
    )

    assert body.root["assets"] == {
        "AAA": [0.0, 20.0, 20.0],
        "ZZZ": [0.0, 0.0, 0.0],
    }
    assert ("history", "ZZZ") not in prices.calls


def test_held_ticker_without_market_price_is_valued_at_its_trade_prices(
    operation_repo: MagicMock, prices: FakePrices
) -> None:
    operations = [
        _op("buy", _at(2), ticker="ZZZ", quantity="2", price="10"),
        _op("sell", _at(4), ticker="ZZZ", quantity="1", price="12"),
    ]

    body = _service(operation_repo, operations, prices).portfolio_vectors(
        1, _query('["assets"]', start="2025-01-01", end="2025-01-05")
    )

    # Held from 01-02 at 10, from 01-04 one unit left, last trade price 12.
    assert body.root["assets"]["ZZZ"] == [0.0, 20.0, 20.0, 12.0, 12.0]


def test_held_ticker_without_any_usable_price_fails_the_request(
    operation_repo: MagicMock, prices: FakePrices
) -> None:
    operations = [_op("buy", _at(2), ticker="ZZZ", quantity="1", price="0")]

    with pytest.raises(PriceDataMissingError) as exc_info:
        _service(operation_repo, operations, prices).portfolio_vectors(
            1, _query('["assets"]')
        )

    assert (exc_info.value.status_code, exc_info.value.code) == (
        502,
        "PRICE_DATA_MISSING",
    )


def test_the_cost_and_cash_vectors_carry_the_operations_fx_rate(
    operation_repo: MagicMock, prices: FakePrices
) -> None:
    operations = [
        _op("deposit", _at(1), amount="1000"),
        _op("buy", _at(2), ticker="AAA", quantity="10", price="20", fx_rate="4"),
        _op("dividend", _at(3), ticker="AAA", amount="5", fee="1", fx_rate="4"),
    ]

    body = _service(operation_repo, operations, prices).portfolio_vectors(
        1, _query('["transaction_cost_vector", "free_cash_vector"]', end="2025-01-03")
    )

    assert body.root["transaction_cost_vector"] == [0.0, 800.0, 804.0]
    # The ledger's cash: 1000 - 200 * 4, then + (5 - 1) * 4.
    assert body.root["free_cash_vector"] == [1000.0, 200.0, 216.0]


def test_timezone_aware_operation_lands_on_its_utc_day(
    operation_repo: MagicMock,
) -> None:
    """Ported from the pre-migration `test_portfolio_metrics_handles_timezone_
    aware_operations`: closes 10 then (current, Monday) 10.5."""
    operations = [
        _op(
            "buy",
            datetime(2025, 5, 25, 12, tzinfo=UTC),
            ticker="CDR",
            quantity="2",
            price="10",
        ),
    ]
    prices = FakePrices(
        history={"CDR": {date(2025, 5, 25): D("10")}}, current={"CDR": D("10.5")}
    )
    query = _query('["profit_vector"]', start="2025-05-25", end="2025-05-26")

    body = _service(operation_repo, operations, prices).portfolio_vectors(1, query)

    assert body.root["profit_vector"] == [0.0, 1.0]


def test_operations_before_start_land_on_the_first_day(
    operation_repo: MagicMock, prices: FakePrices
) -> None:
    operations = [_op("deposit", datetime(2020, 1, 1, tzinfo=UTC), amount="5")]

    body = _service(operation_repo, operations, prices).portfolio_vectors(
        1, _query('["net_deposits_vector"]', start="2025-01-01", end="2025-01-03")
    )

    assert body.root["net_deposits_vector"] == [5.0, 5.0, 5.0]


def test_money_is_summed_as_decimal_before_becoming_a_float(
    operation_repo: MagicMock, prices: FakePrices
) -> None:
    operations = [
        _op("deposit", _at(1), amount="0.1"),
        _op("deposit", _at(1), amount="0.2"),
    ]

    body = _service(operation_repo, operations, prices).portfolio_vectors(
        1, _query('["net_deposits_vector"]', start="2025-01-01", end="2025-01-01")
    )

    assert body.root["net_deposits_vector"] == [0.3]  # float sum: 0.30000000000000004


def test_no_operations_is_an_empty_object_whatever_the_parameters(
    operation_repo: MagicMock, prices: FakePrices
) -> None:
    query = _query("not json", start=None, end="bad", interval="1wk")

    body = _service(operation_repo, [], prices).portfolio_vectors(1, query)

    assert body.root == {}


@pytest.mark.parametrize(
    ("query", "error", "code"),
    [
        (_query("not json"), InvalidVectorsError, "INVALID_VECTORS"),
        (_query('{"assets": 1}'), InvalidVectorsError, "INVALID_VECTORS"),
        (_query(start=None), InvalidDateError, "INVALID_DATE"),
        (_query(end="2025-13-01"), InvalidDateError, "INVALID_DATE"),
        (_query(start="01.01.2025"), InvalidDateError, "INVALID_DATE"),
        (_query(start="2025-01-08"), InvalidDateRangeError, "INVALID_DATE_RANGE"),
        (
            _query(start="1900-01-01", end="2025-01-01"),
            InvalidDateRangeError,
            "INVALID_DATE_RANGE",
        ),
        (_query(interval="1wk"), UnsupportedIntervalError, "UNSUPPORTED_INTERVAL"),
    ],
)
def test_invalid_parameters_are_400_with_a_code(
    operation_repo: MagicMock,
    operations: list,
    prices: FakePrices,
    query: PortfolioVectorsQuery,
    error: type[Exception],
    code: str,
) -> None:
    with pytest.raises(error) as exc_info:
        _service(operation_repo, operations, prices).portfolio_vectors(1, query)

    assert exc_info.value.status_code == 400  # type: ignore[attr-defined]
    assert exc_info.value.code == code  # type: ignore[attr-defined]


def test_a_buy_in_a_foreign_currency_moves_the_profit_by_its_fee_only(
    operation_repo: MagicMock,
) -> None:
    """Bought 10 @ 20 USD at fx 4 with a fee of 2 PLN, the price and the rate
    unchanged: the value is 800 PLN, the cost 808 PLN, the profit -8 (the fee)."""
    days = [date(2025, 1, d) for d in range(1, 6)]
    prices = FakePrices(
        history={"AAA": {day: D("20") for day in days}},
        fx_rates={"USDPLN": {day: D("4") for day in days}},
    )
    operations = [
        _op("deposit", _at(1), amount="1000"),
        _op(
            "buy",
            _at(2),
            ticker="AAA",
            currency="USD",
            quantity="10",
            price="20",
            fee="2",
            fx_rate="4",
        ),
    ]
    query = _query('["assets", "profit_vector"]', start="2025-01-01", end="2025-01-05")

    body = _service(operation_repo, operations, prices).portfolio_vectors(1, query)

    assert body.root["assets"] == {"AAA": [0.0, 800.0, 800.0, 800.0, 800.0]}
    assert body.root["profit_vector"] == [0.0, -8.0, -8.0, -8.0, -8.0]


def test_the_last_day_takes_the_current_rate_when_history_has_none(
    operation_repo: MagicMock,
) -> None:
    days = [date(2025, 1, d) for d in range(1, 7)]
    prices = FakePrices(
        history={"AAA": {day: D("20") for day in [*days, date(2025, 1, 7)]}},
        fx_rates={"USDPLN": {day: D("4") for day in days}},
        fx_current={"USDPLN": D("5")},
    )
    operations = [
        _op(
            "buy",
            _at(2),
            ticker="AAA",
            currency="USD",
            quantity="10",
            price="20",
            fx_rate="4",
        ),
    ]
    query = _query('["assets"]', start="2025-01-01", end="2025-01-07")

    body = _service(operation_repo, operations, prices).portfolio_vectors(1, query)

    assert body.root["assets"] == {
        "AAA": [0.0, 800.0, 800.0, 800.0, 800.0, 800.0, 1000.0]
    }
    assert ("current_fx", "USDPLN") in prices.calls


def test_a_currency_pair_without_any_rate_fails_the_vector(
    operation_repo: MagicMock,
) -> None:
    prices = FakePrices(history={"AAA": {date(2025, 1, 2): D("20")}})
    operations = [
        _op(
            "buy",
            _at(2),
            ticker="AAA",
            currency="USD",
            quantity="1",
            price="20",
            fx_rate="4",
        ),
    ]

    with pytest.raises(PriceDataMissingError) as exc_info:
        _service(operation_repo, operations, prices).portfolio_vectors(
            1, _query('["assets"]', start="2025-01-01", end="2025-01-03")
        )

    assert exc_info.value.code == "PRICE_DATA_MISSING"


def test_portfolios_in_different_base_currencies_cannot_be_charted_together(
    operation_repo: MagicMock, prices: FakePrices
) -> None:
    operations = [
        _op("deposit", _at(1), amount="1000"),
        _op("deposit", _at(1), amount="100", base="USD"),
    ]

    with pytest.raises(MixedBaseCurrenciesError) as exc_info:
        _service(operation_repo, operations, prices).portfolio_vectors(
            1, _query('["net_deposits_vector"]')
        )

    assert (exc_info.value.status_code, exc_info.value.code) == (
        409,
        "MIXED_BASE_CURRENCIES",
    )


def test_interest_and_fee_move_cash_and_profit_but_not_the_net_deposits(
    operation_repo: MagicMock, prices: FakePrices
) -> None:
    operations = [
        _op("deposit", _at(1), amount="1000"),
        _op("interest", _at(2), amount="5"),
        _op("fee", _at(3), amount="2"),
    ]

    body = _service(operation_repo, operations, prices).portfolio_vectors(
        1,
        _query(
            '["net_deposits_vector", "free_cash_vector", "profit_vector"]',
            end="2025-01-03",
        ),
    )

    assert body.root["net_deposits_vector"] == [1000.0, 1000.0, 1000.0]
    # The ledger's cash: 1000, + 5 interest, - 2 charge.
    assert body.root["free_cash_vector"] == [1000.0, 1005.0, 1003.0]
    assert body.root["profit_vector"] == [0.0, 5.0, 3.0]


def test_a_split_multiplies_the_quantity_from_its_day_on(
    operation_repo: MagicMock, prices: FakePrices
) -> None:
    """Closes are in the units of their day: 100-ish before the 10:1 split, 10-ish
    from its day; the 2 shares bought before it become 20."""
    prices.history["AAA"] = {
        date(2025, 1, 2): D("100"),
        date(2025, 1, 3): D("105"),
        date(2025, 1, 4): D("11"),
    }
    operations = [
        _op("deposit", _at(1), amount="1000"),
        _op("buy", _at(2), ticker="AAA", quantity="2", price="100"),
        _op("split", _at(4), ticker="AAA", ratio="10"),
    ]

    body = _service(operation_repo, operations, prices).portfolio_vectors(
        1, _query('["assets"]', end="2025-01-05")
    )

    assert body.root["assets"] == {"AAA": [0.0, 200.0, 210.0, 220.0, 220.0]}


def test_stored_closes_and_a_fresh_current_price_need_no_provider_call(
    operation_repo: MagicMock, prices: FakePrices
) -> None:
    """AC-01: the history is in the store and the current price is stored for
    the day, so the vector is computed without asking the provider."""
    operations = [_op("buy", _at(1), ticker="AAA", quantity="1", price="10")]
    operation_repo.list_by_owner.return_value = operations
    prices.current = {"AAA": D("25")}
    store = FakeStore(
        prices,
        operations,
        stored={"AAA": {date(2025, 1, day): D("10") for day in range(1, 7)}},
    )

    body = MetricsService(operation_repo, store, store, store).portfolio_vectors(
        1, _query('["assets"]')
    )

    assert prices.calls == []
    assert body.root["assets"] == {"AAA": [10.0] * 6 + [25.0]}


def test_missing_history_is_backfilled_once_then_read_from_the_store(
    operation_repo: MagicMock, prices: FakePrices
) -> None:
    """AC-03: the first request backfills the asset's history; the second one reads
    it from the store and the provider is not asked again."""
    operations = [_op("buy", _at(1), ticker="AAA", quantity="1", price="10")]
    operation_repo.list_by_owner.return_value = operations
    prices.history = {"AAA": {date(2025, 1, day): D("10") for day in range(1, 7)}}
    prices.current = {"AAA": D("25")}
    store = FakeStore(prices, operations)
    service = MetricsService(operation_repo, store, store, store)

    first = service.portfolio_vectors(1, _query('["assets"]'))
    assert ("history", "AAA") in prices.calls
    prices.calls.clear()
    second = service.portfolio_vectors(1, _query('["assets"]'))

    assert prices.calls == []
    assert first.root["assets"] == second.root["assets"] == {"AAA": [10.0] * 6 + [25.0]}


def test_a_stored_rate_history_that_starts_late_is_not_stretched_over_the_range(
    operation_repo: MagicMock, prices: FakePrices
) -> None:
    """The refresh stores today's rate only; that single row must not become the
    rate of the whole range. The provider's history is read instead (DEC-13)."""
    operations = [
        _op("buy", _at(1), ticker="AAA", currency="USD", quantity="1", price="10")
    ]
    operation_repo.list_by_owner.return_value = operations
    prices.history = {"AAA": {date(2025, 1, day): D("10") for day in range(1, 7)}}
    prices.fx_rates = {"USDPLN": {date(2025, 1, day): D("4") for day in range(1, 7)}}
    store = FakeStore(
        prices,
        operations,
        stored_fx={"USDPLN": {date(2025, 1, 7): D("5")}},
    )

    body = MetricsService(operation_repo, store, store, store).portfolio_vectors(
        1, _query('["assets"]')
    )

    # Six days at 10 x 4 from the provider; today at the current 25 x 4.
    assert body.root["assets"] == {"AAA": [40.0] * 6 + [100.0]}
    assert ("fx_history", "USDPLN") in prices.calls


# --- benchmarks (DEC-05, AC-03, AC-04: comparison benchmarks on portfolio_vectors) ---


def test_benchmarks_empty_when_none_requested() -> None:
    """AC-03: no `benchmarks` query param means no benchmark series at all,
    even with an asset service wired in."""
    operations = [_op("deposit", _at(1), amount="1000")]
    calculator = VectorCalculator(
        operations,
        _at(1),
        _at(3),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        asset_service=MagicMock(),
    )

    assert calculator.benchmarks() == {}


def test_benchmarks_empty_when_no_asset_service_wired() -> None:
    """AC-03: a `benchmarks` param with no asset service (e.g. the account-
    vectors path, which does not wire one in) degrades to no series, not a
    crash."""
    operations = [_op("deposit", _at(1), amount="1000")]
    calculator = VectorCalculator(
        operations,
        _at(1),
        _at(3),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        benchmarks_json='["sp500"]',
    )

    assert calculator.benchmarks() == {}


def test_benchmarks_normalizes_to_one_at_range_start_and_forward_fills() -> None:
    """AC-03/AC-04: a requested benchmark is normalized to 1.0 at the range
    start, forward-filled for a day with no close, and keyed by its short name
    (not its ticker)."""
    operations = [_op("deposit", _at(1), amount="1000")]
    asset_service = MagicMock()
    asset_service.find_by_ticker.return_value = SimpleNamespace(
        id=99, asset_type="index", currency=SimpleNamespace(code="PLN")
    )
    prices = MagicMock()
    prices.series.return_value = SimpleNamespace(
        items=[
            SimpleNamespace(day=date(2025, 1, 1), close=D("100")),
            # 2025-01-02 has no close: forward-filled from 01-01's 100.
            SimpleNamespace(day=date(2025, 1, 3), close=D("110")),
        ]
    )

    calculator = VectorCalculator(
        operations,
        _at(1),
        _at(3),
        MagicMock(),
        prices,
        MagicMock(),
        asset_service=asset_service,
        benchmarks_json='["sp500"]',
    )

    result = calculator.benchmarks()

    asset_service.find_by_ticker.assert_called_once_with("^GSPC")
    assert list(result) == ["sp500"]
    assert result["sp500"].tolist() == pytest.approx([1.0, 1.0, 1.1])


def test_benchmarks_skips_a_ticker_the_service_does_not_know(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """AC-03: an unresolved index asset (not seeded yet) is skipped, not an
    error - the other requested benchmarks still come back."""
    operations = [_op("deposit", _at(1), amount="1000")]
    asset_service = MagicMock()
    asset_service.find_by_ticker.return_value = None
    calculator = VectorCalculator(
        operations,
        _at(1),
        _at(3),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        asset_service=asset_service,
        benchmarks_json='["sp500"]',
    )

    assert calculator.benchmarks() == {}
