from datetime import datetime

from pydantic import BaseModel

from app.modules.assets.schemas import AssetDetailRead, CurrencyRead

# --- Position ---


class PositionRead(BaseModel):
    id: int
    pocket_id: int
    asset_id: int
    asset: AssetDetailRead
    quantity: float
    average_buy_price: float
    average_fx_rate: float
    total_fees: float
    total_dividends: float
    opened_at: datetime | None = None
    updated_at: datetime | None = None

    # Computed fields
    cost_basis: float = 0
    cost_basis_in_pocket_currency: float = 0
    market_value: float = 0
    unrealized_pnl: float = 0
    return_pct: float = 0
    pocket_weight_pct: float = 0

    model_config = {"from_attributes": True}


# --- Pocket ---


class PocketCreate(BaseModel):
    name: str
    base_currency_id: int


class PocketRead(BaseModel):
    id: int
    owner_id: int
    name: str
    base_currency: CurrencyRead
    cash_balance: float
    total_deposited: float
    is_active: bool
    created_at: datetime | None = None

    # Computed
    positions_value: float = 0
    total_value: float = 0
    total_profit_loss: float = 0
    total_return_pct: float = 0

    model_config = {"from_attributes": True}


class PocketDetailRead(PocketRead):
    positions: list[PositionRead] = []
    total_fees: float = 0
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


# --- Operation ---


class OperationCreate(BaseModel):
    pocket_id: int
    asset_id: int | None = None
    operation_type: str  # buy, sell, deposit, withdrawal, dividend
    quantity: float = 0
    price: float = 0
    amount: float | None = None
    fee: float = 0
    fx_rate: float = 1
    notes: str | None = None
    operation_date: datetime
    ticker: str | None = None
    asset_class: str | None = None


class OperationRead(BaseModel):
    id: int
    pocket_id: int
    asset_id: int | None = None
    operation_type: str
    quantity: float
    price: float
    amount: float | None = None
    fee: float
    fx_rate: float
    notes: str | None = None
    operation_date: datetime
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
