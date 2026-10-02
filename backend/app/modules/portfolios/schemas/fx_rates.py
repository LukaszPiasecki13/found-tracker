"""Pydantic schemas for `GET /portfolios/fx-rate` (a rate hint for the UI)."""

from typing import Literal

from pydantic import BaseModel, Field

from app.core.schemas import DecimalNumber

CURRENCY_CODE_PATTERN = "^[A-Za-z]{3}$"


class FxRateQuery(BaseModel):
    """Query parameters of `GET /portfolios/fx-rate`; codes are case-insensitive."""

    from_currency: str = Field(pattern=CURRENCY_CODE_PATTERN)
    to_currency: str = Field(pattern=CURRENCY_CODE_PATTERN)


class FxRateResponse(BaseModel):
    """How much of `to_currency` one unit of `from_currency` buys. `via` says how
    it was composed from the stored "per USD" rates: `identity` (same currency),
    `direct` (into USD), `inverse` (out of USD) or `cross` (through USD)."""

    from_currency: str
    to_currency: str
    rate: DecimalNumber
    via: Literal["identity", "direct", "inverse", "cross"]
