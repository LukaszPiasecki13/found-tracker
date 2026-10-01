"""Operation repository for data access. Owner-scoped reads join the
portfolio."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Select, select
from sqlalchemy.orm import joinedload, selectinload

from app.infrastructure.sql.repository import SQLRepository
from app.modules.assets.models import Asset
from app.modules.portfolios.exceptions import OperationNotFoundError
from app.modules.portfolios.models import Operation, Portfolio


def _with_asset() -> Select[tuple[Operation]]:
    """Operations with their asset (class and currency) - what the response
    and the vector metrics read."""
    return select(Operation).options(
        selectinload(Operation.asset).options(
            joinedload(Asset.currency), joinedload(Asset.asset_class)
        )
    )


class OperationRepository(SQLRepository):
    """Repository for Operation model database operations."""

    def list_by_owner(
        self, owner_id: int, portfolio_name: str | None = None
    ) -> list[Operation]:
        """The owner's operations, newest first (`operation_date`, then
        `created_at`); `portfolio_name` narrows to one portfolio."""
        stmt = (
            _with_asset()
            .join(Portfolio, Operation.portfolio_id == Portfolio.id)
            .where(Portfolio.owner_id == owner_id)
            .order_by(Operation.operation_date.desc(), Operation.created_at.desc())
        )
        if portfolio_name:
            stmt = stmt.where(Portfolio.name == portfolio_name)
        return list(self.session.execute(stmt).scalars())

    def list_by_portfolio(self, portfolio_id: int) -> list[Operation]:
        """The portfolio's history in the order the ledger replays it:
        `operation_date`, `created_at`, `id`; fresh from the database."""
        stmt = (
            select(Operation)
            .where(Operation.portfolio_id == portfolio_id)
            .order_by(
                Operation.operation_date.asc(),
                Operation.created_at.asc(),
                Operation.id.asc(),
            )
            .execution_options(populate_existing=True)
        )
        return list(self.session.execute(stmt).scalars())

    def find_owned(self, operation_id: int, owner_id: int) -> Operation | None:
        """The operation if it belongs to one of the owner's portfolios."""
        stmt = (
            _with_asset()
            .join(Portfolio, Operation.portfolio_id == Portfolio.id)
            .where(Operation.id == operation_id, Portfolio.owner_id == owner_id)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def get_owned(self, operation_id: int, owner_id: int) -> Operation:
        """Raises OperationNotFoundError (also for another owner's operation)."""
        operation = self.find_owned(operation_id, owner_id)
        if operation is None:
            raise OperationNotFoundError
        return operation

    def create(
        self,
        *,
        portfolio_id: int,
        asset_id: int | None,
        operation_type: str,
        quantity: Decimal,
        price: Decimal,
        amount: Decimal | None,
        fee: Decimal,
        fx_rate: Decimal,
        notes: str | None,
        operation_date: datetime,
    ) -> Operation:
        """Create an operation; refreshed so stored (rounded) values and
        `created_at` are loaded."""
        operation = Operation(
            portfolio_id=portfolio_id,
            asset_id=asset_id,
            operation_type=operation_type,
            quantity=quantity,
            price=price,
            amount=amount,
            fee=fee,
            fx_rate=fx_rate,
            notes=notes,
            operation_date=operation_date,
        )
        return self.save_new(operation)

    def update(self, operation: Operation) -> Operation:
        """Write pending changes; refreshed so stored (rounded) values are
        loaded."""
        return self.persist(operation)

    def delete(self, operation: Operation) -> None:
        self.session.delete(operation)
        self.flush()
