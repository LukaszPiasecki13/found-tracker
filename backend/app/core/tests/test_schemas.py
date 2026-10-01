"""`DecimalNumber`: `Decimal` in Python, a JSON number on the wire (ADR-0010)."""

import json
from decimal import Decimal

from pydantic import BaseModel

from app.core.schemas import DecimalNumber


class _Price(BaseModel):
    value: DecimalNumber


def test_json_carries_a_number_not_a_string() -> None:
    payload = json.loads(_Price(value=Decimal("123.450000000")).model_dump_json())

    assert payload == {"value": 123.45}
    assert isinstance(payload["value"], float)


def test_python_dump_keeps_the_decimal() -> None:
    assert _Price(value=Decimal("1.10")).model_dump() == {"value": Decimal("1.10")}


def test_json_number_input_becomes_an_exact_decimal() -> None:
    assert _Price.model_validate_json('{"value": 0.1}').value == Decimal("0.1")
