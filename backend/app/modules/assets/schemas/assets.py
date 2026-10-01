"""Pydantic schemas for assets, provider search and create-from-provider."""

from datetime import datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.market_data import Quote
from app.core.schemas import DecimalNumber
from app.modules.assets.schemas.asset_classes import AssetClassResponse
from app.modules.assets.schemas.currencies import CurrencyResponse

# At least one non-blank character; the service strips and uppercases.
_TICKER_PATTERN = r"\S"
# `Numeric(18, 9)` holds at most 9 integer digits.
_MAX_PRICE = Decimal("1e9")


# --- Requests ---


class AssetListQuery(BaseModel):
    """Query parameters of `GET /assets/`."""

    search: str | None = None


class AssetSearchQuery(BaseModel):
    """Query parameters of `GET /assets/search-yahoo`."""

    q: str = Field(min_length=2)


class AssetCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str = Field(min_length=1, max_length=20, pattern=_TICKER_PATTERN)
    name: str = Field(min_length=1, max_length=100)
    asset_class_id: int
    currency_id: int
    current_price: Decimal = Field(default=Decimal("0"), ge=0, lt=_MAX_PRICE)
    exchange: str = Field(default="", max_length=50)
    sector: str = Field(default="", max_length=100)


class AssetUpdateRequest(BaseModel):
    """Partial update; every column is NOT NULL, so an explicit `null` is a 422."""

    model_config = ConfigDict(extra="forbid")

    ticker: str | None = Field(
        default=None, min_length=1, max_length=20, pattern=_TICKER_PATTERN
    )
    name: str | None = Field(default=None, min_length=1, max_length=100)
    asset_class_id: int | None = None
    currency_id: int | None = None
    current_price: Decimal | None = Field(default=None, ge=0, lt=_MAX_PRICE)
    exchange: str | None = Field(default=None, max_length=50)
    sector: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def reject_null_for_required_fields(self) -> Self:
        for name in self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class AssetFromProviderRequest(BaseModel):
    """Create an asset from market-data provider data; class and currency are
    derived from the quote unless given."""

    model_config = ConfigDict(extra="forbid")

    ticker: str = Field(min_length=1, max_length=20, pattern=_TICKER_PATTERN)
    asset_class_id: int | None = Field(default=None, gt=0)
    currency_id: int | None = Field(default=None, gt=0)


# --- Responses ---


class AssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    name: str
    asset_class_id: int
    currency_id: int
    current_price: DecimalNumber
    exchange: str
    sector: str
    updated_at: datetime | None = None


class AssetDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    name: str
    asset_class: AssetClassResponse
    currency: CurrencyResponse
    current_price: DecimalNumber
    exchange: str
    sector: str
    updated_at: datetime | None = None


class ProviderQuoteResponse(BaseModel):
    """One market-data provider hit; `type` is the provider's quote type
    (`EQUITY`, `ETF`, ...) - the key the frontend reads."""

    symbol: str
    name: str
    exchange: str
    type: str
    currency: str
    sector: str

    @classmethod
    def from_quote(cls, quote: Quote) -> Self:
        return cls(
            symbol=quote.symbol,
            name=quote.name,
            exchange=quote.exchange,
            type=quote.quote_type,
            currency=quote.currency,
            sector=quote.sector,
        )


class AssetSearchResponse(BaseModel):
    """Combined search read model: known local assets plus provider hits that are
    not local yet. The provider list keeps its historical key, `yahoo`."""

    local: list[AssetDetailResponse]
    yahoo: list[ProviderQuoteResponse]
