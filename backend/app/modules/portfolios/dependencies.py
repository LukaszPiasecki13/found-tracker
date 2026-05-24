from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db

from .repository import OperationRepository, PortfolioRepository, PositionRepository
from .services import PortfolioService, TransactionService


def get_portfolio_repo(db: Session = Depends(get_db)) -> PortfolioRepository:
    return PortfolioRepository(db)


def get_position_repo(db: Session = Depends(get_db)) -> PositionRepository:
    return PositionRepository(db)


def get_operation_repo(db: Session = Depends(get_db)) -> OperationRepository:
    return OperationRepository(db)


def get_transaction_service(
    portfolio_repo: PortfolioRepository = Depends(get_portfolio_repo),
    position_repo: PositionRepository = Depends(get_position_repo),
) -> TransactionService:
    return TransactionService(portfolio_repo, position_repo)


def get_portfolio_service(
    portfolio_repo: PortfolioRepository = Depends(get_portfolio_repo),
    operation_repo: OperationRepository = Depends(get_operation_repo),
) -> PortfolioService:
    return PortfolioService(portfolio_repo, operation_repo)
