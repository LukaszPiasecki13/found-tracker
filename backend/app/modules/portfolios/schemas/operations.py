"""Pydantic schemas for operations.

Requests check shape only: types, lengths and what the `Numeric` columns can
hold. Signs and relationships between fields (quantity > 0, an asset for a buy,
none for a deposit, ...) are the ledger's rules - one place, `domain/`.
"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.core.schemas import DecimalNumber
from app.modules.assets.schemas.assets import AssetDetailResponse
from app.modules.portfolios.domain import OperationType

# Column capacity: `Numeric(18, 9)` holds 9 integer digits, `Numeric(18, 2)` 16.
_Numeric18x9 = Annotated[
    Decimal, Field(gt=-Decimal("1e9"), lt=Decimal("1e9"), allow_inf_nan=False)
]
_Numeric18x2 = Annotated[
    Decimal, Field(gt=-Decimal("1e16"), lt=Decimal("1e16"), allow_inf_nan=False)
]
# At least one non-blank character; `assets` strips and uppercases the ticker.
_TICKER_PATTERN = r"\S"


# --- Requests ---


class OperationListQuery(BaseModel):
    """Query parameters of `GET /portfolios/operations`."""

    portfolio_name: str | None = None


class OperationCreateRequest(BaseModel):
    """The asset is `asset_id`, or `ticker` (created in class `asset_class`
    when unknown); none for deposits and withdrawals. `amount` is read only by
    deposits, withdrawals and dividends."""

    model_config = ConfigDict(extra="forbid")

    portfolio_id: int
    asset_id: int | None = None
    operation_type: OperationType
    quantity: _Numeric18x9 = Decimal("0")
    price: _Numeric18x9 = Decimal("0")
    amount: _Numeric18x2 | None = None
    fee: _Numeric18x2 = Decimal("0")
    fx_rate: _Numeric18x9 = Decimal("1")
    notes: str | None = None
    operation_date: datetime
    ticker: str | None = Field(
        default=None, min_length=1, max_length=20, pattern=_TICKER_PATTERN
    )
    asset_class: str | None = Field(default=None, min_length=1, max_length=20)


class OperationUpdateRequest(BaseModel):
    """Same body for PUT and PATCH; the type and the asset cannot change. Only
    `notes` is nullable - an explicit `null` elsewhere means "leave as is"."""

    model_config = ConfigDict(extra="forbid")

    quantity: _Numeric18x9 | None = None
    price: _Numeric18x9 | None = None
    amount: _Numeric18x2 | None = None
    fee: _Numeric18x2 | None = None
    fx_rate: _Numeric18x9 | None = None
    notes: str | None = None
    operation_date: datetime | None = None


# --- Responses ---


class OperationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    portfolio_id: int
    asset_id: int | None = None
    asset: AssetDetailResponse | None = None
    operation_type: str
    quantity: DecimalNumber
    price: DecimalNumber
    amount: DecimalNumber | None = None
    fee: DecimalNumber
    fx_rate: DecimalNumber
    notes: str | None = None
    operation_date: datetime
    created_at: datetime | None = None
