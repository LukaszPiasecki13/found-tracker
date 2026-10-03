"""Position repository for data access."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from app.infrastructure.sql.repository import SQLRepository
from app.modules.assets.models import Asset
from app.modules.portfolios.models import Position


class PositionRepository(SQLRepository):
    """Repository for Position model database operations."""

    def list_by_portfolio(self, portfolio_id: int) -> list[Position]:
        """The portfolio's positions, most recently updated first, with their
        asset (class and currency) loaded; fresh from the database even when
        already in the session."""
        stmt = (
            select(Position)
            .where(Position.portfolio_id == portfolio_id)
            .options(
                selectinload(Position.asset).options(
                    joinedload(Asset.currency), joinedload(Asset.asset_class)
                )
            )
            .order_by(Position.updated_at.desc(), Position.id.desc())
            .execution_options(populate_existing=True)
        )
        return list(self.session.execute(stmt).scalars())

    def create(
        self,
        *,
        portfolio_id: int,
        asset_id: int,
        quantity: Decimal,
        average_buy_price: Decimal,
        average_fx_rate: Decimal,
        total_fees: Decimal,
        total_dividends: Decimal,
    ) -> Position:
        """Create a position; refreshed so stored (rounded) values and the
        server-side timestamps are loaded."""
        position = Position(
            portfolio_id=portfolio_id,
            asset_id=asset_id,
            quantity=quantity,
            average_buy_price=average_buy_price,
            average_fx_rate=average_fx_rate,
            total_fees=total_fees,
            total_dividends=total_dividends,
        )
        return self.save_new(position)

    def update(self, position: Position) -> Position:
        """Write pending changes; refreshed so stored (rounded) values are
        loaded."""
        return self.persist(position)

    def delete(self, position: Position) -> None:
        self.session.delete(position)
        self.flush()
