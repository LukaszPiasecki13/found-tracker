"""Pydantic schemas for currencies."""

from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.schemas import DecimalNumber

_CURRENCY_CODE_PATTERN = r"^[A-Za-z]{3}$"
# `Numeric(18, 9)` holds at most 9 integer digits.
_MAX_RATE = Decimal("1e9")


class CurrencyCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(pattern=_CURRENCY_CODE_PATTERN)
    exchange_rate: Decimal = Field(default=Decimal("1"), gt=0, lt=_MAX_RATE)
    base_currency_id: int | None = None


class CurrencyUpdateRequest(BaseModel):
    """Partial update; `base_currency_id: null` clears the base currency."""

    model_config = ConfigDict(extra="forbid")

    code: str | None = Field(default=None, pattern=_CURRENCY_CODE_PATTERN)
    exchange_rate: Decimal | None = Field(default=None, gt=0, lt=_MAX_RATE)
    base_currency_id: int | None = None

    @model_validator(mode="after")
    def reject_null_for_required_fields(self) -> Self:
        for name in ("code", "exchange_rate"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class CurrencyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    exchange_rate: DecimalNumber
    base_currency_id: int | None = None
