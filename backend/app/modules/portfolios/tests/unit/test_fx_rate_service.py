"""`FxRateService` - one currency rate for the UI (a hint in the buy dialog)."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.assets.exceptions import CurrencyNotFoundError
from app.modules.portfolios.exceptions import RateMissingError
from app.modules.portfolios.services.fx import FxMapBuilder, FxRateService

D = Decimal


def _currency(currency_id: int, code: str, rate: str) -> SimpleNamespace:
    return SimpleNamespace(id=currency_id, code=code, exchange_rate=D(rate))


@pytest.fixture
def service() -> FxRateService:
    currencies = MagicMock()
    currencies.list_currencies.return_value = [
        _currency(1, "USD", "1"),
        _currency(2, "EUR", "1.08"),
        _currency(3, "PLN", "0.25"),
        _currency(4, "GBP", "1"),
    ]
    return FxRateService(currencies, FxMapBuilder(currencies))


def test_a_cross_rate_is_composed_from_the_two_stored_rates(
    service: FxRateService,
) -> None:
    quote = service.quote("EUR", "PLN")

    assert (quote.from_currency, quote.to_currency) == ("EUR", "PLN")
    assert quote.rate == D("4.32")
    assert quote.via == "cross"


def test_into_usd_the_stored_rate_is_used_directly(service: FxRateService) -> None:
    quote = service.quote("EUR", "USD")

    assert quote.rate == D("1.08")
    assert quote.via == "direct"


def test_out_of_usd_the_stored_rate_is_inverted(service: FxRateService) -> None:
    quote = service.quote("USD", "PLN")

    assert quote.rate == D("4")
    assert quote.via == "inverse"


def test_a_currency_into_itself_is_one(service: FxRateService) -> None:
    quote = service.quote("PLN", "PLN")

    assert quote.rate == D("1")
    assert quote.via == "identity"


def test_codes_are_case_insensitive_and_returned_uppercase(
    service: FxRateService,
) -> None:
    quote = service.quote(" eur ", "pln")

    assert (quote.from_currency, quote.to_currency) == ("EUR", "PLN")
    assert quote.rate == D("4.32")


def test_the_response_rounds_the_rate_to_nine_places(service: FxRateService) -> None:
    quote = service.quote("PLN", "EUR")

    assert quote.rate == D("0.231481481")


@pytest.mark.parametrize(("source", "target"), [("XXX", "PLN"), ("EUR", "XXX")])
def test_an_unknown_currency_code_is_not_found(
    service: FxRateService, source: str, target: str
) -> None:
    with pytest.raises(CurrencyNotFoundError) as exc_info:
        service.quote(source, target)

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "CURRENCY_NOT_FOUND"


@pytest.mark.parametrize(("source", "target"), [("GBP", "PLN"), ("EUR", "GBP")])
def test_a_currency_without_a_quote_has_no_rate(
    service: FxRateService, source: str, target: str
) -> None:
    with pytest.raises(RateMissingError) as exc_info:
        service.quote(source, target)

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "RATE_MISSING"


def test_a_quote_reads_the_currencies_once() -> None:
    currencies = MagicMock()
    currencies.list_currencies.return_value = [
        _currency(1, "USD", "1"),
        _currency(2, "EUR", "1.08"),
        _currency(3, "PLN", "0.25"),
    ]

    FxRateService(currencies, FxMapBuilder(currencies)).quote("EUR", "PLN")

    currencies.list_currencies.assert_called_once_with()
