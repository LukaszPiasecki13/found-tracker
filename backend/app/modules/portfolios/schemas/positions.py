"""Pydantic schemas for positions, and the rounding of valued figures.

Valuation is exact in the domain; the JSON contract carries the computed
figures rounded like before the migration: values to 3 decimals, percentages
to 4, fees to 2 (half-even, as Python's `round`). The rounding happens here,
once, at the response boundary.
"""

from collections.abc import Callable
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Context, Decimal
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict

from app.core.schemas import DecimalNumber
from app.modules.assets.schemas.assets import AssetDetailResponse

# Wide enough that quantizing a `Numeric(18, 9)` product never overflows.
_QUANTIZE_CONTEXT = Context(prec=60)


def rounded_to(places: int) -> Callable[[Decimal], Decimal]:
    exponent = Decimal(1).scaleb(-places)

    def round_value(value: Decimal) -> Decimal:
        return value.quantize(
            exponent, rounding=ROUND_HALF_EVEN, context=_QUANTIZE_CONTEXT
        )

    return round_value


# Computed read-model figures, serialized as JSON numbers.
RoundedValue = Annotated[DecimalNumber, AfterValidator(rounded_to(3))]
RoundedPercent = Annotated[DecimalNumber, AfterValidator(rounded_to(4))]
RoundedFees = Annotated[DecimalNumber, AfterValidator(rounded_to(2))]


class PositionListQuery(BaseModel):
    """Query parameters of `GET /portfolios/positions`."""

    portfolio_name: str


class PositionFields(BaseModel):
    """A stored position, as read from the ORM row."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    portfolio_id: int
    asset_id: int
    asset: AssetDetailResponse
    quantity: DecimalNumber
    average_buy_price: DecimalNumber
    average_fx_rate: DecimalNumber
    total_fees: DecimalNumber
    total_dividends: DecimalNumber
    opened_at: datetime | None = None
    updated_at: datetime | None = None


class PositionResponse(PositionFields):
    """A position valued at current prices (read model, ADR-0003).

    The cost needs no rate. Market value, profit, return and weight are `null`
    with `rate_missing` set when no rate turns the asset's currency into the
    portfolio's - never a silent rate of 1.
    """

    cost_basis: RoundedValue
    cost_basis_in_portfolio_currency: RoundedValue
    market_value: RoundedValue | None
    unrealized_pnl: RoundedValue | None
    return_pct: RoundedPercent | None
    portfolio_weight_pct: RoundedPercent | None
    rate_missing: bool = False
