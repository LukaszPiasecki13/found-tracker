"""Reusable Pydantic field types shared by module schemas."""

from decimal import Decimal
from typing import Annotated

from pydantic import PlainSerializer

# Money, prices and rates are `Decimal` end to end (ADR-0010), but the JSON
# contract with the frontend carries them as numbers. Use in response schemas;
# Python-mode dumps (`model_dump()`) keep the `Decimal`.
DecimalNumber = Annotated[
    Decimal, PlainSerializer(float, return_type=float, when_used="json")
]
