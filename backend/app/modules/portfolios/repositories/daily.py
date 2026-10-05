"""Daily rows of a portfolio (`portfolios_daily`, ADR-0016); derived data."""

from collections.abc import Iterable
from datetime import date

from sqlalchemy import delete, select

from app.infrastructure.sql.repository import SQLRepository
from app.modules.portfolios.models import PortfolioDaily


class DailyRepository(SQLRepository):
    """Repository for PortfolioDaily; the portfolio's owner is checked by the
    caller (it reads the portfolio first)."""

    def last_row(
        self, portfolio_id: int, *, before: date | None = None
    ) -> PortfolioDaily | None:
        """The latest stored day, or the latest one strictly before `before`."""
        stmt = (
            select(PortfolioDaily)
            .where(PortfolioDaily.portfolio_id == portfolio_id)
            .order_by(PortfolioDaily.day.desc())
            .limit(1)
        )
        if before is not None:
            stmt = stmt.where(PortfolioDaily.day < before)
        return self.session.execute(stmt).scalar_one_or_none()

    def delete_from(self, portfolio_id: int, day: date) -> None:
        """Delete the rows from `day` on (inclusive)."""
        self.session.execute(
            delete(PortfolioDaily).where(
                PortfolioDaily.portfolio_id == portfolio_id,
                PortfolioDaily.day >= day,
            )
        )

    def add_many(self, rows: Iterable[PortfolioDaily]) -> None:
        self.session.add_all(rows)
        self.flush()
