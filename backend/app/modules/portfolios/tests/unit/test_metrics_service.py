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
from app.modules.assets.services.market_data import MarketDataService
from app.modules.assets.tests.fakes import FakeMarketDataProvider, make_quote
from app.modules.portfolios.exceptions import (
    InvalidDateError,
    InvalidDateRangeError,
    InvalidVectorsError,
    PriceDataMissingError,
    UnsupportedIntervalError,
)
from app.modules.portfolios.schemas.metrics import PortfolioVectorsQuery
from app.modules.portfolios.services.metrics import MetricsService

D = Decimal
_ids = count(1)


@dataclass
class FakePrices:
    """`PriceHistoryProvider` with fixed closes; `failing` tickers raise."""

    history: dict[str, dict[date, Decimal]] = field(default_factory=dict)
    current: dict[str, Decimal] = field(default_factory=dict)
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


def _op(
    operation_type: str,
    when: datetime,
    *,
    ticker: str | None = None,
    asset_class: str = "Stock",
    quantity: str = "0",
    price: str = "0",
    amount: str | None = None,
    fee: str = "0",
    fx_rate: str = "1",
    ratio: str | None = None,
) -> SimpleNamespace:
    asset = (
        SimpleNamespace(ticker=ticker, asset_class=SimpleNamespace(name=asset_class))
        if ticker
        else None
    )
    return SimpleNamespace(
        id=next(_ids),
        operation_type=operation_type,
        operation_date=when,
        asset=asset,
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
    return MetricsService(operation_repo, prices)


AAA = [0.0, 210.0, 220.0, 220.0, 220.0, 144.0, 150.0]
BBB = [0.0, 0.0, 52.5, 52.5, 52.5, 52.5, 52.5]
NET_DEPOSITS = [1000.0] * 6 + [900.0]
TRANSACTION_COST = [0.0, 202.0, 252.0, 252.0, 252.0, 153.5, 153.5]


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
    assert list(body) == [
        "date",
        "assets",
        "asset_classes",
        "net_deposits_vector",
        "transaction_cost_vector",
        "profit_vector",
        "free_cash_vector",
        "pocket_value_vector",
        "portfolio_value_vector",
    ]


def test_each_ticker_history_is_fetched_once_per_request(
    operation_repo: MagicMock, operations: list, prices: FakePrices
) -> None:
    _service(operation_repo, operations, prices).portfolio_vectors(7, _query())

    assert sorted(prices.calls) == [
        ("current", "AAA"),
        ("current", "BBB"),
        ("history", "AAA"),
        ("history", "BBB"),
    ]


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


def test_ticker_without_any_price_fails_the_request(
    operation_repo: MagicMock, prices: FakePrices
) -> None:
    operations = [_op("buy", _at(2), ticker="ZZZ", quantity="1", price="1")]

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


def test_market_data_service_satisfies_the_price_port(
    operation_repo: MagicMock,
) -> None:
    """The production adapter: `MarketDataService` over the provider port,
    `end` exclusive and the quote's price as the current price."""
    provider = FakeMarketDataProvider(
        history={"AAA": {date(2025, 1, 6): D("24"), date(2025, 1, 7): D("99")}},
        quotes={
            "AAA": make_quote("AAA", current_price=None, regular_market_price=D("25"))
        },
    )
    market_data = MarketDataService(
        MagicMock(), MagicMock(), provider, MagicMock(), MagicMock()
    )
    operations = [_op("buy", _at(6), ticker="AAA", quantity="2", price="20")]
    operation_repo.list_by_owner.return_value = operations

    body = MetricsService(operation_repo, market_data).portfolio_vectors(
        1, _query('["assets"]', start="2025-01-06", end="2025-01-07")
    )

    assert body.root["assets"] == {"AAA": [48.0, 50.0]}


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


def test_a_split_scales_the_quantity_held_before_it(
    operation_repo: MagicMock, prices: FakePrices
) -> None:
    """The provider's closes are already adjusted for the split, so the 2 shares
    bought before the 10:1 split are valued as the 20 they became."""
    prices.history["AAA"] = {
        date(2025, 1, 2): D("10"),
        date(2025, 1, 3): D("10.5"),
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
