"""`FxMapBuilder` - cross rates between currencies, from the stored
"USD per one unit" rates of `assets` (E0.1)."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.portfolios.services.fx import FxMapBuilder

D = Decimal
USD, EUR, PLN, GBP = 1, 2, 3, 4


def _currency(currency_id: int, code: str, rate: str) -> SimpleNamespace:
    return SimpleNamespace(id=currency_id, code=code, exchange_rate=D(rate))


@pytest.fixture
def currencies() -> MagicMock:
    service = MagicMock()
    service.list_currencies.return_value = [
        _currency(USD, "USD", "1"),
        _currency(EUR, "EUR", "1.08"),
        _currency(PLN, "PLN", "0.25"),
    ]
    return service


@pytest.fixture
def builder(currencies: MagicMock) -> FxMapBuilder:
    return FxMapBuilder(currencies)


def test_builds_cross_rates_for_a_pln_base(builder: FxMapBuilder) -> None:
    rates = builder.build([PLN])

    assert rates == {(USD, PLN): D("4"), (EUR, PLN): D("4.32")}


def test_builds_the_rates_of_every_requested_base(builder: FxMapBuilder) -> None:
    rates = builder.build([PLN, USD])

    assert rates[(EUR, PLN)] == D("4.32")
    assert rates[(PLN, USD)] == D("0.25")
    assert rates[(EUR, USD)] == D("1.08")
    assert set(rates) == {
        (USD, PLN),
        (EUR, PLN),
        (PLN, USD),
        (EUR, USD),
    }


def test_rates_keep_the_full_decimal_precision(builder: FxMapBuilder) -> None:
    rates = builder.build([EUR])

    assert rates[(PLN, EUR)] == D("0.25") / D("1.08")
    assert str(rates[(PLN, EUR)]) == "0.2314814814814814814814814815"


def test_a_currency_is_never_paired_with_itself(builder: FxMapBuilder) -> None:
    rates = builder.build([PLN, EUR])

    assert (PLN, PLN) not in rates
    assert (EUR, EUR) not in rates


def test_a_currency_still_at_the_default_rate_has_no_rate(
    currencies: MagicMock,
) -> None:
    currencies.list_currencies.return_value.append(_currency(GBP, "GBP", "1"))

    rates = FxMapBuilder(currencies).build([PLN, GBP])

    assert all(GBP not in pair for pair in rates)


def test_usd_counts_as_having_a_rate_even_at_one(currencies: MagicMock) -> None:
    rates = FxMapBuilder(currencies).build([PLN])

    assert rates[(USD, PLN)] == D("4")


def test_usd_is_always_one_whatever_its_stored_rate(currencies: MagicMock) -> None:
    currencies.list_currencies.return_value[0] = _currency(USD, "USD", "7")

    rates = FxMapBuilder(currencies).build([PLN])

    assert rates[(USD, PLN)] == D("4")


def test_a_base_without_a_rate_gets_no_rates(currencies: MagicMock) -> None:
    currencies.list_currencies.return_value.append(_currency(GBP, "GBP", "1"))

    rates = FxMapBuilder(currencies).build([GBP])

    assert rates == {}


def test_a_zero_rate_is_skipped_without_dividing_by_zero(
    currencies: MagicMock,
) -> None:
    currencies.list_currencies.return_value.append(_currency(GBP, "GBP", "0"))

    rates = FxMapBuilder(currencies).build([PLN, GBP])

    assert all(GBP not in pair for pair in rates)


def test_currencies_are_read_once_per_build(
    builder: FxMapBuilder, currencies: MagicMock
) -> None:
    builder.build([PLN, EUR, USD])

    currencies.list_currencies.assert_called_once_with()


def test_no_requested_base_gives_an_empty_map(builder: FxMapBuilder) -> None:
    assert builder.build([]) == {}
