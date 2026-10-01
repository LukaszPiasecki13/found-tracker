"""Portfolio management: CRUD scoped to the owner, and the valued read models
(summary list, detail with positions)."""

from typing import Any

from sqlalchemy.exc import IntegrityError

from app.core.entities import apply_changes
from app.modules.assets.services.currencies import CurrencyService
from app.modules.portfolios.domain import (
    PortfolioValuation,
    PortfolioValuator,
    PositionValuation,
)
from app.modules.portfolios.exceptions import (
    PortfolioAlreadyExistsError,
    PortfolioCurrencyLockedError,
    UnknownCurrencyError,
)
from app.modules.portfolios.models import Portfolio, Position
from app.modules.portfolios.repositories.portfolios import PortfolioRepository
from app.modules.portfolios.schemas.portfolios import (
    PortfolioCreateRequest,
    PortfolioDetailResponse,
    PortfolioResponse,
    PortfolioSummaryResponse,
    PortfolioUpdateRequest,
)
from app.modules.portfolios.schemas.positions import PositionFields, PositionResponse


def position_response(
    position: Position, valuation: PositionValuation
) -> PositionResponse:
    """A stored position plus its valuation as the response DTO; the schema
    rounds the computed figures."""
    return PositionResponse(
        **dict(PositionFields.model_validate(position)),
        cost_basis=valuation.cost_basis,
        cost_basis_in_portfolio_currency=valuation.cost_basis_in_portfolio_currency,
        market_value=valuation.market_value,
        unrealized_pnl=valuation.unrealized_pnl,
        return_pct=valuation.return_pct,
        portfolio_weight_pct=valuation.portfolio_weight_pct,
    )


def _summary_fields(
    portfolio: Portfolio, valuation: PortfolioValuation
) -> dict[str, Any]:
    return {
        **dict(PortfolioResponse.model_validate(portfolio)),
        "positions_value": valuation.positions_value,
        "total_value": valuation.total_value,
        "total_profit_loss": valuation.total_profit_loss,
        "total_return_pct": valuation.total_return_pct,
        "total_fees": valuation.total_fees,
    }


class PortfolioService:
    """Portfolios of one owner; another owner's portfolio is reported as not
    found (404), never as forbidden. Names are unique per owner.

    The read models value positions at the asset prices and currency rates
    stored in `assets` (refreshing them is `PositionService`'s job).
    """

    def __init__(
        self,
        portfolio_repo: PortfolioRepository,
        currency_service: CurrencyService,
        valuator: PortfolioValuator,
    ) -> None:
        self._repo = portfolio_repo
        self._currencies = currency_service
        self._valuator = valuator

    # --- Reads ---

    def get_owned(self, portfolio_id: int, owner_id: int) -> Portfolio:
        """Raises PortfolioNotFoundError."""
        return self._repo.get_owned(portfolio_id, owner_id)

    def get_owned_by_name(self, owner_id: int, name: str) -> Portfolio:
        """Raises PortfolioNotFoundError."""
        return self._repo.get_by_owner_and_name(owner_id, name)

    def list_summaries(
        self, owner_id: int, name: str | None = None
    ) -> list[PortfolioSummaryResponse]:
        """The owner's valued portfolios, newest first; `name` filters."""
        summaries = []
        for portfolio in self._repo.list_by_owner(owner_id, name=name):
            valuation = self._valuator.value(portfolio, portfolio.positions)
            summaries.append(
                PortfolioSummaryResponse(**_summary_fields(portfolio, valuation))
            )
        return summaries

    def get_detail(self, portfolio_id: int, owner_id: int) -> PortfolioDetailResponse:
        """One valued portfolio with its valued positions (weights relative to
        the total value, cash included). Raises PortfolioNotFoundError."""
        portfolio = self._repo.get_owned(portfolio_id, owner_id)
        positions = list(portfolio.positions)
        valuation = self._valuator.value(portfolio, positions)
        return PortfolioDetailResponse(
            **_summary_fields(portfolio, valuation),
            positions=[
                position_response(position, position_valuation)
                for position, position_valuation in zip(
                    positions, valuation.positions, strict=True
                )
            ],
            updated_at=portfolio.updated_at,
        )

    # --- Writes (own transaction) ---

    def create(self, data: PortfolioCreateRequest, owner_id: int) -> Portfolio:
        """An empty portfolio. Raises PortfolioAlreadyExistsError,
        UnknownCurrencyError."""
        try:
            with self._repo.transaction():
                if self._repo.find_by_owner_and_name(owner_id, data.name):
                    raise PortfolioAlreadyExistsError
                self._require_currency(data.base_currency_id)
                return self._repo.create(
                    owner_id=owner_id,
                    name=data.name,
                    base_currency_id=data.base_currency_id,
                )
        except IntegrityError as err:
            self._raise_if_name_taken(owner_id, data.name, err)
            raise

    def update(
        self, portfolio_id: int, data: PortfolioUpdateRequest, owner_id: int
    ) -> Portfolio:
        """Set the given, non-null fields. Raises PortfolioNotFoundError,
        PortfolioAlreadyExistsError, UnknownCurrencyError,
        PortfolioCurrencyLockedError."""
        values = data.model_dump(exclude_unset=True, exclude_none=True)
        try:
            with self._repo.transaction():
                portfolio = self._repo.get_owned(portfolio_id, owner_id)
                if "name" in values:
                    duplicate = self._repo.find_by_owner_and_name(
                        owner_id, values["name"]
                    )
                    if duplicate is not None and duplicate.id != portfolio.id:
                        raise PortfolioAlreadyExistsError
                if "base_currency_id" in values:
                    self._change_base_currency(portfolio, values["base_currency_id"])
                apply_changes(portfolio, values)
                return self._repo.update(portfolio)
        except IntegrityError as err:
            if "name" in values:
                self._raise_if_name_taken(
                    owner_id, values["name"], err, other_than=portfolio_id
                )
            raise

    def delete(self, portfolio_id: int, owner_id: int) -> None:
        """Delete a portfolio with its positions and operations. Raises
        PortfolioNotFoundError."""
        with self._repo.transaction():
            self._repo.delete(self._repo.get_owned(portfolio_id, owner_id))

    # --- Helpers ---

    def _change_base_currency(self, portfolio: Portfolio, currency_id: int) -> None:
        """The stored amounts are in the base currency and are not converted, so
        it may only change while the portfolio has no operations."""
        self._require_currency(currency_id)
        if currency_id != portfolio.base_currency_id and self._repo.has_operations(
            portfolio.id
        ):
            raise PortfolioCurrencyLockedError

    def _require_currency(self, currency_id: int) -> None:
        if self._currencies.find_by_id(currency_id) is None:
            raise UnknownCurrencyError

    def _raise_if_name_taken(
        self,
        owner_id: int,
        name: str,
        err: IntegrityError,
        *,
        other_than: int | None = None,
    ) -> None:
        """After a failed commit: a concurrent writer took the name first."""
        existing = self._repo.find_by_owner_and_name(owner_id, name)
        if existing is not None and existing.id != other_than:
            raise PortfolioAlreadyExistsError from err
