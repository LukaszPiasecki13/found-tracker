"""Contract of `app.core.market_data`: the quote price rule and the provider error."""

from decimal import Decimal

import pytest

from app.core.errors import APIError
from app.core.market_data import MarketDataUnavailableError, Quote


def _quote(
    current: Decimal | None, regular: Decimal | None, previous: Decimal | None
) -> Quote:
    return Quote(
        symbol="AAPL",
        name="Apple",
        exchange="NMS",
        quote_type="EQUITY",
        currency="USD",
        sector="",
        current_price=current,
        regular_market_price=regular,
        previous_close=previous,
    )


@pytest.mark.parametrize(
    ("current", "regular", "previous", "expected"),
    [
        (Decimal("3"), Decimal("2"), Decimal("1"), Decimal("3")),
        (None, Decimal("2"), Decimal("1"), Decimal("2")),
        (Decimal("0"), None, Decimal("1"), Decimal("1")),
        (None, None, None, None),
        (Decimal("0"), Decimal("0"), Decimal("0"), None),
    ],
)
def test_price_is_the_first_non_zero_price(
    current: Decimal | None,
    regular: Decimal | None,
    previous: Decimal | None,
    expected: Decimal | None,
) -> None:
    assert _quote(current, regular, previous).price == expected


def test_quote_is_immutable() -> None:
    quote = _quote(None, None, None)

    with pytest.raises(AttributeError):
        quote.symbol = "MSFT"  # type: ignore[misc]


def test_provider_failure_is_a_502_api_error_with_code() -> None:
    error = MarketDataUnavailableError()

    assert isinstance(error, APIError)
    assert error.status_code == 502
    assert error.code == "MARKET_DATA_UNAVAILABLE"
