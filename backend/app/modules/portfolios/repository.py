from sqlalchemy.orm import Session

from .models import Operation, Pocket, Position


class PocketRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_owner(self, owner_id: int, name: str | None = None) -> list[Pocket]:
        q = self.db.query(Pocket).filter(Pocket.owner_id == owner_id)
        if name:
            q = q.filter(Pocket.name == name)
        return q.order_by(Pocket.created_at.desc()).all()

    def get_by_id(self, pocket_id: int) -> Pocket | None:
        return self.db.query(Pocket).filter(Pocket.id == pocket_id).first()

    def get_by_owner_and_name(self, owner_id: int, name: str) -> Pocket | None:
        return (
            self.db.query(Pocket)
            .filter(Pocket.owner_id == owner_id, Pocket.name == name)
            .first()
        )

    def create(self, pocket: Pocket) -> Pocket:
        self.db.add(pocket)
        self.db.commit()
        self.db.refresh(pocket)
        return pocket

    def update(self, pocket: Pocket) -> Pocket:
        self.db.commit()
        self.db.refresh(pocket)
        return pocket

    def delete(self, pocket: Pocket) -> None:
        self.db.delete(pocket)
        self.db.commit()

    def save(self) -> None:
        self.db.commit()


class PositionRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_pocket(self, pocket_id: int) -> list[Position]:
        return (
            self.db.query(Position)
            .filter(Position.pocket_id == pocket_id)
            .order_by(Position.updated_at.desc())
            .all()
        )

    def get_by_pocket_and_asset(self, pocket_id: int, asset_id: int) -> Position | None:
        return (
            self.db.query(Position)
            .filter(Position.pocket_id == pocket_id, Position.asset_id == asset_id)
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
        self, owner_id: int, pocket_name: str | None = None
    ) -> list[Operation]:
        q = self.db.query(Operation).join(Pocket).filter(Pocket.owner_id == owner_id)
        if pocket_name:
            q = q.filter(Pocket.name == pocket_name)
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
