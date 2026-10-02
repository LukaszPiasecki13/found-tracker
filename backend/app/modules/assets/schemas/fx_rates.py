"""Pydantic schemas for exchange-rate history."""

from datetime import date
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.schemas import DecimalNumber
from app.modules.assets.constants import MAX_PRICE_OR_RATE

_CURRENCY_CODE_PATTERN = r"^[A-Za-z]{3}$"


class FxRateLookupQuery(BaseModel):
    """Query parameters of `GET /assets/currencies/rate` (`date` defaults to
    today)."""

    model_config = ConfigDict(populate_by_name=True)

    from_currency: str = Field(pattern=_CURRENCY_CODE_PATTERN)
    to_currency: str = Field(pattern=_CURRENCY_CODE_PATTERN)
    as_of: date | None = Field(default=None, alias="date")


class FxRateHistoryQuery(BaseModel):
    """Query parameters of `GET /assets/fx-rates` (the directed pair; `from`/`to`
    are inclusive dates)."""

    model_config = ConfigDict(populate_by_name=True)

    from_currency: str = Field(pattern=_CURRENCY_CODE_PATTERN)
    to_currency: str = Field(pattern=_CURRENCY_CODE_PATTERN)
    from_date: date | None = Field(default=None, alias="from")
    to_date: date | None = Field(default=None, alias="to")
    source: str | None = Field(default=None, max_length=20)


class ManualFxRateRequest(BaseModel):
    """Body of `PUT /assets/fx-rates`: `rate` units of `to` per one unit of `from`."""

    model_config = ConfigDict(extra="forbid")

    from_currency_id: int = Field(gt=0)
    to_currency_id: int = Field(gt=0)
    rate_date: date
    rate: Decimal = Field(gt=0, lt=Decimal(MAX_PRICE_OR_RATE))

    @model_validator(mode="after")
    def currencies_differ(self) -> Self:
        if self.from_currency_id == self.to_currency_id:
            raise ValueError("from_currency_id and to_currency_id must differ")
        return self


class FxRateLookupResponse(BaseModel):
    """The rate on a day, direct or inverse (`via`); `identity` for one currency."""

    model_config = ConfigDict(from_attributes=True)

    from_currency: str
    to_currency: str
    rate: DecimalNumber
    rate_date: date
    source: str
    table_no: str | None = None
    is_synthetic: bool
    stale: bool
    via: Literal["identity", "direct", "inverse"]


class FxRateItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rate_date: date
    rate: DecimalNumber
    source: str
    table_no: str | None = None
    is_synthetic: bool


class FxRateHistoryResponse(BaseModel):
    items: list[FxRateItemResponse]


class FxRateResponse(BaseModel):
    """One stored observation, as returned by `PUT /assets/fx-rates`."""

    model_config = ConfigDict(from_attributes=True)

    from_currency_id: int
    to_currency_id: int
    rate_date: date
    rate: DecimalNumber
    source: str
    table_no: str | None = None
    is_synthetic: bool
