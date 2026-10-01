"""Pydantic schemas for portfolios."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.schemas import DecimalNumber
from app.modules.assets.schemas.currencies import CurrencyResponse
from app.modules.portfolios.schemas.positions import (
    PositionResponse,
    RoundedFees,
    RoundedPercent,
    RoundedValue,
)

# --- Requests ---


class PortfolioListQuery(BaseModel):
    """Query parameters of `GET /portfolios/`."""

    name: str | None = None


class PortfolioCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    base_currency_id: int = Field(gt=0)


class PortfolioUpdateRequest(BaseModel):
    """Same body for PUT and PATCH. Both columns are NOT NULL: an explicit
    `null` means "leave as is"."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    base_currency_id: int | None = Field(default=None, gt=0)


# --- Responses ---


class PortfolioResponse(BaseModel):
    """A stored portfolio (create/update)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    name: str
    base_currency: CurrencyResponse
    cash_balance: DecimalNumber
    total_deposited: DecimalNumber
    is_active: bool
    created_at: datetime | None = None


class PortfolioSummaryResponse(PortfolioResponse):
    """A portfolio valued at current prices (read model, ADR-0003)."""

    positions_value: RoundedValue
    total_value: RoundedValue
    total_profit_loss: RoundedValue
    total_return_pct: RoundedPercent
    total_fees: RoundedFees


class PortfolioDetailResponse(PortfolioSummaryResponse):
    """A valued portfolio with its valued positions."""

    positions: list[PositionResponse]
    updated_at: datetime | None = None
