from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db

from .repository import OperationRepository, PocketRepository, PositionRepository
from .services import PortfolioService, TransactionService


def get_pocket_repo(db: Session = Depends(get_db)) -> PocketRepository:
    return PocketRepository(db)


def get_position_repo(db: Session = Depends(get_db)) -> PositionRepository:
    return PositionRepository(db)


def get_operation_repo(db: Session = Depends(get_db)) -> OperationRepository:
    return OperationRepository(db)


def get_transaction_service(
    pocket_repo: PocketRepository = Depends(get_pocket_repo),
    position_repo: PositionRepository = Depends(get_position_repo),
) -> TransactionService:
    return TransactionService(pocket_repo, position_repo)


def get_portfolio_service(
    pocket_repo: PocketRepository = Depends(get_pocket_repo),
    operation_repo: OperationRepository = Depends(get_operation_repo),
) -> PortfolioService:
    return PortfolioService(pocket_repo, operation_repo)
