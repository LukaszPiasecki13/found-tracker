from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db

from .repository import AssetClassRepository, AssetRepository, CurrencyRepository
from .service import MarketDataService


def get_currency_repo(db: Session = Depends(get_db)) -> CurrencyRepository:
    return CurrencyRepository(db)


def get_asset_class_repo(db: Session = Depends(get_db)) -> AssetClassRepository:
    return AssetClassRepository(db)


def get_asset_repo(db: Session = Depends(get_db)) -> AssetRepository:
    return AssetRepository(db)


def get_market_data_service(
    asset_repo: AssetRepository = Depends(get_asset_repo),
    currency_repo: CurrencyRepository = Depends(get_currency_repo),
    asset_class_repo: AssetClassRepository = Depends(get_asset_class_repo),
) -> MarketDataService:
    return MarketDataService(asset_repo, currency_repo, asset_class_repo)
