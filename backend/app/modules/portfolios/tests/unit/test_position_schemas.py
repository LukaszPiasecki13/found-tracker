"""Rounding of the valued figures at the response boundary (DEC-12)."""

from decimal import Decimal

from pydantic import TypeAdapter

from app.modules.portfolios.schemas.positions import RoundedPositionRate


def test_position_rate_keeps_six_places() -> None:
    rounded = TypeAdapter(RoundedPositionRate).validate_python(Decimal("4.32123456789"))

    assert rounded == Decimal("4.321235")
