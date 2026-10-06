"""`AccountMetricsService` - the portfolios' vectors summed in the account currency.

Reuses the fakes of `test_metrics_service`: the store plays the price, FX and market
data services, the provider holds the closes and rates. A portfolio's operations
carry their `portfolio_id`, as the repository returns them.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from app.modules.portfolios.exceptions import (
    PriceDataMissingError,
    UnsupportedIntervalError,
)
from app.modules.portfolios.schemas.metrics import AccountVectorsQuery
from app.modules.portfolios.services.account_metrics import (
    ACCOUNT_FALLBACK_CURRENCY,
    AccountMetricsService,
)
from app.modules.portfolios.services.metrics import MetricsService
from app.modules.portfolios.tests.unit import test_metrics_service as metrics_tests
from app.modules.portfolios.tests.unit.test_metrics_service import (
    D,
    FakePrices,
    FakeStore,
    _at,
    _op,
)

# The metrics tests' fixtures, shared with these tests.
operations = metrics_tests.operations
prices = metrics_tests.prices


class FakeOperations:
    def __init__(self, operations: list[SimpleNamespace]) -> None:
        self._operations = operations

    def list_by_owner(
        self, owner_id: int, portfolio_name: str | None = None
    ) -> list[SimpleNamespace]:
        return self._operations


class FakeCurrencies:
    def __init__(self, codes: dict[int, str]) -> None:
        self._codes = codes

    def find_by_id(self, currency_id: int) -> SimpleNamespace | None:
        code = self._codes.get(currency_id)
        return SimpleNamespace(code=code) if code is not None else None


def _query(
    vectors: str = "[]",
    start: str = "2025-01-01",
    end: str = "2025-01-07",
    interval: str = "1d",
) -> AccountVectorsQuery:
    return AccountVectorsQuery.model_validate(
        {"startDate": start, "endDate": end, "interval": interval, "vectors": vectors}
    )


def _rate_history(first: date, last: date, rate: str) -> dict[date, Decimal]:
    return {first + timedelta(days=n): D(rate) for n in range((last - first).days + 1)}


def _assert_close(actual: Any, expected: Any) -> None:
    """Vectors are lists of floats, or dicts of them (`asset_classes`)."""
    if isinstance(expected, dict):
        assert actual.keys() == expected.keys()
        for name in expected:
            _assert_close(actual[name], expected[name])
    else:
        assert actual == pytest.approx(expected)


def _account(
    operations: list[SimpleNamespace],
    *,
    provider: FakePrices | None = None,
    currencies: dict[int, str] | None = None,
) -> tuple[AccountMetricsService, FakeStore]:
    store = FakeStore(provider=provider or FakePrices(), operations=operations)
    service = AccountMetricsService(
        FakeOperations(operations),
        FakeCurrencies(currencies or {2: "PLN", 3: "EUR"}),
        store,
        store,
        store,
    )
    return service, store


def test_one_portfolio_matches_its_own_vectors(
    operations: list[SimpleNamespace], prices: FakePrices
) -> None:
    """AC-02: an account of one portfolio in its own currency equals the portfolio."""
    for operation in operations:
        operation.portfolio_id = 1
    # One store plays all three services, as the database does for them in production.
    store = FakeStore(provider=prices, operations=operations)
    own = MetricsService(
        FakeOperations(operations), store, store, store
    ).portfolio_vectors(
        1,
        SimpleNamespace(
            portfolio_name="Main",
            start_date="2025-01-01",
            end_date="2025-01-07",
            interval="1d",
            vectors="[]",
        ),
    )
    account, _ = _account(operations, provider=prices, currencies={2: "PLN"})

    result = account.account_vectors(1, _query(), base_currency_id=2).root

    expected = own.root
    assert result["date"] == expected["date"]
    assert "assets" not in result
    for name in result:
        if name != "date":
            _assert_close(result[name], expected[name])


def test_portfolios_in_two_currencies_are_converted_and_summed(
    prices: FakePrices,
) -> None:
    """AC-03: a 1000 PLN deposit and a 100 USD deposit at USD/PLN 4 add up to 1400."""
    pln = _op("deposit", datetime(2024, 12, 30, tzinfo=UTC), amount="1000")
    pln.portfolio_id = 1
    usd = _op("deposit", datetime(2024, 12, 30, tzinfo=UTC), amount="100", base="USD")
    usd.portfolio_id = 2
    operations = [pln, usd]
    account, store = _account(operations, provider=prices)
    store.stored_fx["USDPLN"] = _rate_history(date(2024, 12, 1), date(2025, 1, 7), "4")
    prices.fx_current["USDPLN"] = D("4")

    result = account.account_vectors(1, _query('["net_deposits_vector"]'), 2).root

    assert result["net_deposits_vector"] == [1400.0] * 7


def test_a_missing_rate_fails_the_request(prices: FakePrices) -> None:
    """AC-03: no rate at all for the pair is an error with a code, never a zero."""
    usd = _op("deposit", datetime(2024, 12, 30, tzinfo=UTC), amount="100", base="USD")
    usd.portfolio_id = 1
    pln = _op("deposit", datetime(2024, 12, 30, tzinfo=UTC), amount="1000")
    pln.portfolio_id = 2
    account, _ = _account([usd, pln], provider=prices)

    with pytest.raises(PriceDataMissingError) as raised:
        account.account_vectors(1, _query('["net_deposits_vector"]'), 2)

    assert raised.value.code == "PRICE_DATA_MISSING"


def test_no_operations_gives_an_empty_response(prices: FakePrices) -> None:
    """AC-05: an owner without operations gets `{}`."""
    account, _ = _account([], provider=prices)

    assert account.account_vectors(1, _query(), 2).root == {}


def test_the_per_ticker_vector_is_not_part_of_the_account(
    operations: list[SimpleNamespace], prices: FakePrices
) -> None:
    """DEC-05: asking for `assets` yields the date only, no per-ticker series."""
    for operation in operations:
        operation.portfolio_id = 1
    account, _ = _account(operations, provider=prices)

    result = account.account_vectors(1, _query('["assets"]'), 2).root

    assert set(result) == {"date"}


def test_an_unknown_currency_id_falls_back_to_pln(prices: FakePrices) -> None:
    """DEC-08: a user without a base currency gets the fallback currency."""
    pln = _op("deposit", datetime(2024, 12, 30, tzinfo=UTC), amount="1000")
    pln.portfolio_id = 1
    account, _ = _account([pln], provider=prices, currencies={})

    assert account._account_currency(None) == ACCOUNT_FALLBACK_CURRENCY
    assert account._account_currency(99) == ACCOUNT_FALLBACK_CURRENCY


def test_an_unsupported_interval_is_refused(prices: FakePrices) -> None:
    pln = _op("deposit", _at(2, 12, year=2024), amount="1000")
    pln.portfolio_id = 1
    account, _ = _account([pln], provider=prices)

    with pytest.raises(UnsupportedIntervalError):
        account.account_vectors(1, _query(interval="1w"), 2)


def test_a_deposit_keeps_its_day_rate_and_the_rate_moves_the_profit(
    prices: FakePrices,
) -> None:
    """A 100 USD deposit on 2024-12-30 stays 400 PLN (the rate of 2025-01-01) while
    the USD/PLN rate moves each day; the move lands in the profit."""
    usd = _op("deposit", datetime(2024, 12, 30, tzinfo=UTC), amount="100", base="USD")
    usd.portfolio_id = 1
    account, store = _account([usd], provider=prices)
    store.stored_fx["USDPLN"] = {
        date(2025, 1, 1) + timedelta(days=n): D(4 + n) for n in range(-5, 10)
    }
    # The stored history ends the day before `end`; 2025-01-07 takes today's rate.
    prices.fx_current["USDPLN"] = D(10)

    result = account.account_vectors(
        1,
        _query('["net_deposits_vector","profit_vector","portfolio_value_vector"]'),
        2,
    ).root

    assert result["net_deposits_vector"] == [400.0] * 7
    assert result["portfolio_value_vector"] == [100.0 * (4 + n) for n in range(7)]
    assert result["profit_vector"] == [100.0 * (4 + n) - 400.0 for n in range(7)]
