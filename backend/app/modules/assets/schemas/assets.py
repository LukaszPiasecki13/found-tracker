"""Pydantic schemas for assets, provider search and create-from-provider."""

from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.market_data import Quote
from app.core.schemas import DecimalNumber
from app.modules.assets.constants import ASSET_TYPES, DEFAULT_ASSET_TYPE
from app.modules.assets.domain import normalize_country, normalize_isin, normalize_mic
from app.modules.assets.schemas.asset_classes import AssetClassResponse
from app.modules.assets.schemas.currencies import CurrencyResponse

# At least one non-blank character; the service strips and uppercases.
_TICKER_PATTERN = r"\S"
# `Numeric(18, 9)` holds at most 9 integer digits.
_MAX_PRICE = Decimal("1e9")


# --- Requests ---


def _normalized(
    raw: str | None, normalize: Callable[[str], str | None], label: str
) -> str | None:
    """Run an identifier normalizer; a blank value clears, a bad one is a 422."""
    if raw is None or not raw.strip():
        return None
    value = normalize(raw)
    if value is None:
        raise ValueError(f"invalid {label}")
    return value


class _IdentifierFields(BaseModel):
    """ISIN, MIC and country: validated and normalized (upper case) on input."""

    isin: str | None = Field(default=None, max_length=20)
    mic: str | None = Field(default=None, max_length=10)
    country: str | None = Field(default=None, max_length=10)

    @field_validator("isin")
    @classmethod
    def _check_isin(cls, value: str | None) -> str | None:
        return _normalized(value, normalize_isin, "ISIN")

    @field_validator("mic")
    @classmethod
    def _check_mic(cls, value: str | None) -> str | None:
        return _normalized(value, normalize_mic, "MIC")

    @field_validator("country")
    @classmethod
    def _check_country(cls, value: str | None) -> str | None:
        return _normalized(value, normalize_country, "country code")


def _check_asset_type(value: str | None) -> str | None:
    if value is not None and value not in ASSET_TYPES:
        raise ValueError(f"asset_type must be one of: {', '.join(ASSET_TYPES)}")
    return value


class AssetListQuery(BaseModel):
    """Query parameters of `GET /assets/`."""

    search: str | None = None
    asset_type: str | None = None
    asset_class_id: int | None = Field(default=None, gt=0)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    include_archived: bool = False

    @field_validator("asset_type")
    @classmethod
    def _check_type(cls, value: str | None) -> str | None:
        return _check_asset_type(value)

    @field_validator("country")
    @classmethod
    def _check_country(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class AssetSearchQuery(BaseModel):
    """Query parameters of `GET /assets/search-yahoo`."""

    q: str = Field(min_length=2)


class AssetCreateRequest(_IdentifierFields):
    model_config = ConfigDict(extra="forbid")

    ticker: str = Field(min_length=1, max_length=20, pattern=_TICKER_PATTERN)
    name: str = Field(min_length=1, max_length=100)
    asset_class_id: int
    currency_id: int
    current_price: Decimal = Field(
        default=Decimal("0"), ge=0, lt=_MAX_PRICE, decimal_places=9
    )
    exchange: str = Field(default="", max_length=50)
    sector: str = Field(default="", max_length=100)
    asset_type: str = DEFAULT_ASSET_TYPE

    @field_validator("asset_type")
    @classmethod
    def _check_type(cls, value: str) -> str:
        return _check_asset_type(value) or DEFAULT_ASSET_TYPE


# Columns that are NOT NULL: an explicit `null` for one of them is a 422 (the
# identifiers `isin`, `mic` and `country` are nullable: `null` clears them).
_REQUIRED_UPDATE_FIELDS = frozenset(
    {
        "ticker",
        "name",
        "asset_class_id",
        "currency_id",
        "current_price",
        "exchange",
        "sector",
        "asset_type",
    }
)


class AssetUpdateRequest(_IdentifierFields):
    """Partial update (a `current_price` must be positive); NOT NULL columns
    reject an explicit `null` with a 422,
    `isin`, `mic` and `country` accept it to clear the value."""

    model_config = ConfigDict(extra="forbid")

    ticker: str | None = Field(
        default=None, min_length=1, max_length=20, pattern=_TICKER_PATTERN
    )
    name: str | None = Field(default=None, min_length=1, max_length=100)
    asset_class_id: int | None = None
    currency_id: int | None = None
    current_price: Decimal | None = Field(
        default=None, gt=0, lt=_MAX_PRICE, decimal_places=9
    )
    exchange: str | None = Field(default=None, max_length=50)
    sector: str | None = Field(default=None, max_length=100)
    asset_type: str | None = None

    @field_validator("asset_type")
    @classmethod
    def _check_type(cls, value: str | None) -> str | None:
        return _check_asset_type(value)

    @model_validator(mode="after")
    def reject_null_for_required_fields(self) -> Self:
        for name in self.model_fields_set & _REQUIRED_UPDATE_FIELDS:
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


class AssetBase(BaseModel):
    """What every asset response carries. The `price_*`/`stale` fields describe
    the latest effective close from the history: `stale` is true when there is
    none or it is older than `STALE_AFTER_DAYS`."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    name: str
    current_price: DecimalNumber
    exchange: str
    sector: str
    isin: str | None = None
    mic: str | None = None
    country: str | None = None
    asset_type: str = DEFAULT_ASSET_TYPE
    archived_at: datetime | None = None
    updated_at: datetime | None = None
    price_date: date | None = None
    price_source: str | None = None
    stale: bool = True


class AssetResponse(AssetBase):
    asset_class_id: int
    currency_id: int


class AssetDetailResponse(AssetBase):
    asset_class: AssetClassResponse
    currency: CurrencyResponse


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
