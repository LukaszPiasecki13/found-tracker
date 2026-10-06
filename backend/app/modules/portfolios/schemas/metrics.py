"""Pydantic schemas for portfolio vectors (chart data)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, RootModel

# Query parameter names are the frontend's (camelCase); `vectors` is a JSON list
# of vector names and the dates are `YYYY-MM-DD` - both parsed by the service,
# which reports bad values as 400 with a `code`.


class PortfolioVectorsQuery(BaseModel):
    """Query parameters of `GET /portfolios/portfolio-vectors`. Without
    `portfolioName` the vectors cover all the user's portfolios."""

    portfolio_name: str | None = Field(default=None, alias="portfolioName")
    start_date: str | None = Field(default=None, alias="startDate")
    end_date: str | None = Field(default=None, alias="endDate")
    interval: str = "1d"
    vectors: str = "[]"


# One entry: the `date` list, a single vector, or a vector per ticker/class name
# (`assets`, `asset_classes`). Floats only here (ADR-0010: chart data).
type VectorValue = list[datetime] | list[float | None] | dict[str, list[float | None]]


class PortfolioVectorsResponse(RootModel[dict[str, VectorValue]]):
    """`{"date": [...], "<vector>": [...] | {"<name>": [...]}}` - only the
    requested vectors (all when none are named); `{}` when the user has no
    operations. Vector names: `assets`, `asset_classes`, `net_deposits_vector`,
    `transaction_cost_vector`, `profit_vector`, `dividend_income_vector`,
    `free_cash_vector`, `portfolio_value_vector` and its alias `pocket_value_vector`."""


class AccountVectorsQuery(BaseModel):
    """Query parameters of `GET /portfolios/account-vectors`: the portfolio query
    without a portfolio name. The currency is the user's, not a parameter (DEC-08)."""

    model_config = ConfigDict(extra="forbid")

    start_date: str | None = Field(default=None, alias="startDate")
    end_date: str | None = Field(default=None, alias="endDate")
    interval: str = "1d"
    vectors: str = "[]"
