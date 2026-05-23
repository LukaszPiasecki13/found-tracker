from datetime import datetime

from pydantic import BaseModel

# --- Currency ---


class CurrencyCreate(BaseModel):
    code: str
    exchange_rate: float = 1.0
    base_currency_id: int | None = None


class CurrencyRead(BaseModel):
    id: int
    code: str
    exchange_rate: float
    base_currency_id: int | None = None

    model_config = {"from_attributes": True}


# --- AssetClass ---


class AssetClassCreate(BaseModel):
    name: str


class AssetClassRead(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


# --- Asset ---


class AssetCreate(BaseModel):
    ticker: str
    name: str
    asset_class_id: int
    currency_id: int
    current_price: float = 0
    exchange: str = ""
    sector: str = ""


class AssetRead(BaseModel):
    id: int
    ticker: str
    name: str
    asset_class_id: int
    currency_id: int
    current_price: float
    exchange: str
    sector: str
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class AssetDetailRead(BaseModel):
    id: int
    ticker: str
    name: str
    asset_class: AssetClassRead
    currency: CurrencyRead
    current_price: float
    exchange: str
    sector: str
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class YahooSearchResult(BaseModel):
    symbol: str
    name: str
    exchange: str
    type: str
    currency: str
    sector: str


class CreateFromYahoo(BaseModel):
    ticker: str
    asset_class_id: int | None = None
    currency_id: int | None = None
