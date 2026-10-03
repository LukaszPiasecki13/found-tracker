"""Portfolio repository for data access. Every read is scoped to an owner."""

from sqlalchemy import Select, exists, select
from sqlalchemy.orm import joinedload, selectinload

from app.infrastructure.sql.repository import SQLRepository
from app.modules.assets.models import Asset
from app.modules.portfolios.exceptions import PortfolioNotFoundError
from app.modules.portfolios.models import Operation, Portfolio, Position


def _owned_with_holdings() -> Select[tuple[Portfolio]]:
    """Portfolios with what valuing them needs: base currency and positions with
    their asset (class and currency) - one query per level, no N+1.

    `populate_existing` refreshes rows already in the session, so a portfolio
    read after its positions changed in the same session is never stale.
    """
    return (
        select(Portfolio)
        .options(
            joinedload(Portfolio.base_currency),
            selectinload(Portfolio.positions)
            .selectinload(Position.asset)
            .options(joinedload(Asset.currency), joinedload(Asset.asset_class)),
        )
        .execution_options(populate_existing=True)
    )


class PortfolioRepository(SQLRepository):
    """Repository for Portfolio model database operations."""

    def list_by_owner(self, owner_id: int, name: str | None = None) -> list[Portfolio]:
        """The owner's portfolios, newest first; `name` filters by exact name."""
        stmt = (
            _owned_with_holdings()
            .where(Portfolio.owner_id == owner_id)
            .order_by(Portfolio.created_at.desc())
        )
        if name:
            stmt = stmt.where(Portfolio.name == name)
        return list(self.session.execute(stmt).unique().scalars())

    def find_owned(self, portfolio_id: int, owner_id: int) -> Portfolio | None:
        """The owner's portfolio with this id; `None` also for another owner's."""
        stmt = _owned_with_holdings().where(
            Portfolio.id == portfolio_id, Portfolio.owner_id == owner_id
        )
        return self.session.execute(stmt).unique().scalar_one_or_none()

    def get_owned(self, portfolio_id: int, owner_id: int) -> Portfolio:
        """The owner's portfolio or PortfolioNotFoundError (also for another
        owner's - existence is not disclosed)."""
        portfolio = self.find_owned(portfolio_id, owner_id)
        if portfolio is None:
            raise PortfolioNotFoundError
        return portfolio

    def lock_owned(self, portfolio_id: int, owner_id: int) -> None:
        """Take a row lock on the owner's portfolio until the transaction ends,
        so concurrent writers of its cash and positions run one after another.
        Raises PortfolioNotFoundError (also for another owner's)."""
        stmt = (
            select(Portfolio.id)
            .where(Portfolio.id == portfolio_id, Portfolio.owner_id == owner_id)
            .with_for_update()
        )
        if self.session.execute(stmt).first() is None:
            raise PortfolioNotFoundError

    def has_operations(self, portfolio_id: int) -> bool:
        """Whether any operation was recorded in the portfolio."""
        stmt = select(exists().where(Operation.portfolio_id == portfolio_id))
        return bool(self.session.execute(stmt).scalar())

    def find_by_owner_and_name(self, owner_id: int, name: str) -> Portfolio | None:
        stmt = _owned_with_holdings().where(
            Portfolio.owner_id == owner_id, Portfolio.name == name
        )
        return self.session.execute(stmt).unique().scalar_one_or_none()

    def get_by_owner_and_name(self, owner_id: int, name: str) -> Portfolio:
        """Raises PortfolioNotFoundError."""
        portfolio = self.find_by_owner_and_name(owner_id, name)
        if portfolio is None:
            raise PortfolioNotFoundError
        return portfolio

    def create(self, *, owner_id: int, name: str, base_currency_id: int) -> Portfolio:
        """Create an empty, active portfolio; refreshed so the server-side
        timestamps are loaded."""
        portfolio = Portfolio(
            owner_id=owner_id,
            name=name,
            base_currency_id=base_currency_id,
            cash_balance=0,
            total_deposited=0,
            is_active=True,
        )
        return self.save_new(portfolio)

    def update(self, portfolio: Portfolio) -> Portfolio:
        """Write pending changes; refreshed so stored (rounded) values and the
        new `updated_at` are loaded."""
        return self.persist(portfolio)

    def delete(self, portfolio: Portfolio) -> None:
        """Delete a portfolio together with its positions and operations."""
        self.session.delete(portfolio)
        self.flush()
