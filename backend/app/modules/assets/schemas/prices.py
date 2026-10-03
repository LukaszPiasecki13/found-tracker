"""Pydantic schemas for the price history of an asset."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.schemas import DecimalNumber
from app.modules.assets.constants import MAX_PRICE_OR_RATE, MAX_REFRESH_ASSETS


class PriceSeriesQuery(BaseModel):
    """Query parameters of `GET /assets/{id}/prices`. `from`/`to` are inclusive;
    `fill=forward` needs `from` and carries the last close over days without one."""

    model_config = ConfigDict(populate_by_name=True)

    from_date: date | None = Field(default=None, alias="from")
    to_date: date | None = Field(default=None, alias="to")
    source: str | None = Field(default=None, max_length=20)
    fill: Literal["none", "forward"] = "none"


class ManualPriceRequest(BaseModel):
    """Body of `PUT /assets/{id}/prices/{price_date}`; the currency, when given,
    must be the asset's own."""

    model_config = ConfigDict(extra="forbid")

    close: Decimal = Field(gt=0, lt=Decimal(MAX_PRICE_OR_RATE), decimal_places=9)
    currency_id: int | None = Field(default=None, gt=0)


class PriceResponse(BaseModel):
    """One stored observation."""

    model_config = ConfigDict(from_attributes=True)

    asset_id: int
    price_date: date
    close: DecimalNumber
    currency_id: int
    source: str
    is_synthetic: bool


class PriceSeriesItemResponse(BaseModel):
    """One day of a series. `price_date` is when the close was observed; it is
    earlier than `day` for a carried-forward day. `stale`: older than the
    freshness threshold on that day."""

    model_config = ConfigDict(from_attributes=True)

    day: date
    price_date: date
    close: DecimalNumber
    source: str
    is_synthetic: bool
    stale: bool


class PriceSeriesResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    asset_id: int
    currency_id: int
    items: list[PriceSeriesItemResponse]


class RefreshPricesRequest(BaseModel):
    """Body of `POST /assets/refresh-prices`."""

    model_config = ConfigDict(extra="forbid")

    asset_ids: list[int] = Field(min_length=1, max_length=MAX_REFRESH_ASSETS)


class RefreshPricesResponse(BaseModel):
    accepted: list[int]


class DataStatusQuery(BaseModel):
    """Query parameters of `GET /assets/data-status`."""

    only_problems: bool = False


class AssetDataStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    asset_id: int
    ticker: str
    price_date: date | None = None
    stale: bool
    source: str | None = None
    last_success_at: datetime | None = None


class FxDataStatus(BaseModel):
    last_success_at: datetime | None = None


class DataStatusResponse(BaseModel):
    fx: FxDataStatus
    assets: list[AssetDataStatus]
