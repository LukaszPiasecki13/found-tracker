from sqlalchemy.orm import Session

from .models import Operation, Portfolio, Position


class PortfolioRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_owner(self, owner_id: int, name: str | None = None) -> list[Portfolio]:
        q = self.db.query(Portfolio).filter(Portfolio.owner_id == owner_id)
        if name:
            q = q.filter(Portfolio.name == name)
        return q.order_by(Portfolio.created_at.desc()).all()

    def get_by_id(self, portfolio_id: int) -> Portfolio | None:
        return self.db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()

    def get_by_owner_and_name(self, owner_id: int, name: str) -> Portfolio | None:
        return (
            self.db.query(Portfolio)
            .filter(Portfolio.owner_id == owner_id, Portfolio.name == name)
            .first()
        )

    def create(self, portfolio: Portfolio) -> Portfolio:
        self.db.add(portfolio)
        self.db.commit()
        self.db.refresh(portfolio)
        return portfolio

    def update(self, portfolio: Portfolio) -> Portfolio:
        self.db.commit()
        self.db.refresh(portfolio)
        return portfolio

    def delete(self, portfolio: Portfolio) -> None:
        self.db.delete(portfolio)
        self.db.commit()

    def save(self) -> None:
        self.db.commit()


class PositionRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_portfolio(self, portfolio_id: int) -> list[Position]:
        return (
            self.db.query(Position)
            .filter(Position.portfolio_id == portfolio_id)
            .order_by(Position.updated_at.desc())
            .all()
        )

    def get_by_portfolio_and_asset(
        self, portfolio_id: int, asset_id: int
    ) -> Position | None:
        return (
            self.db.query(Position)
            .filter(
                Position.portfolio_id == portfolio_id, Position.asset_id == asset_id
            )
            .first()
        )

    def create(self, position: Position) -> Position:
        self.db.add(position)
        self.db.commit()
        self.db.refresh(position)
        return position

    def update(self, position: Position) -> Position:
        self.db.commit()
        self.db.refresh(position)
        return position

    def delete(self, position: Position) -> None:
        self.db.delete(position)
        self.db.commit()


class OperationRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_owner(
        self, owner_id: int, portfolio_name: str | None = None
    ) -> list[Operation]:
        q = (
            self.db.query(Operation)
            .join(Portfolio)
            .filter(Portfolio.owner_id == owner_id)
        )
        if portfolio_name:
            q = q.filter(Portfolio.name == portfolio_name)
        return q.order_by(
            Operation.operation_date.desc(), Operation.created_at.desc()
        ).all()

    def get_by_id(self, operation_id: int) -> Operation | None:
        return self.db.query(Operation).filter(Operation.id == operation_id).first()

    def create(self, operation: Operation) -> Operation:
        self.db.add(operation)
        self.db.commit()
        self.db.refresh(operation)
        return operation

    def delete(self, operation: Operation) -> None:
        self.db.delete(operation)
        self.db.commit()
