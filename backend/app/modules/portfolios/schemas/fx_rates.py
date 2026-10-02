"""Pydantic schemas for `GET /portfolios/fx-rate` (a rate hint for the UI)."""

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field

from app.core.schemas import DecimalNumber
from app.modules.portfolios.schemas.positions import rounded_to

CURRENCY_CODE_PATTERN = "^[A-Za-z]{3}$"

# `fx_rate` of an operation holds 9 decimal places, so does the hint.
RoundedRate = Annotated[DecimalNumber, AfterValidator(rounded_to(9))]


class FxRateQuery(BaseModel):
    """Query parameters of `GET /portfolios/fx-rate`; codes are case-insensitive.

    No `extra="forbid"`: FastAPI ignores it for a query model used with `Depends()`.
    """

    from_currency: str = Field(pattern=CURRENCY_CODE_PATTERN)
    to_currency: str = Field(pattern=CURRENCY_CODE_PATTERN)


class FxRateResponse(BaseModel):
    """How much of `to_currency` one unit of `from_currency` buys. `via` says how
    it was composed from the stored "per USD" rates: `identity` (same currency),
    `direct` (into USD), `inverse` (out of USD) or `cross` (through USD)."""

    from_currency: str
    to_currency: str
    rate: RoundedRate
    via: Literal["identity", "direct", "inverse", "cross"]
