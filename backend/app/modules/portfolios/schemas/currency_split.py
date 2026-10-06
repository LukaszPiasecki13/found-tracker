"""Pydantic schemas for the currency split of the current holdings (pie chart)."""

from pydantic import BaseModel, ConfigDict, Field


class CurrencySplitQuery(BaseModel):
    """Query parameters of `GET /portfolios/currency-split`. Without `portfolioName`
    the split covers all the user's portfolios, in the user's base currency."""

    model_config = ConfigDict(extra="forbid")

    portfolio_name: str | None = Field(default=None, alias="portfolioName")


class CurrencySplitItem(BaseModel):
    currency: str
    value: float


class CurrencySplitResponse(BaseModel):
    """The held value by currency, largest first. `currency` is the one the values
    are in (the portfolio's base currency, or the account's). `unpriced` counts the
    positions left out for lack of a rate."""

    currency: str
    items: list[CurrencySplitItem]
    unpriced: int = 0
