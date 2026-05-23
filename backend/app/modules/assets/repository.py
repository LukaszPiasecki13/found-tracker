from sqlalchemy import or_
from sqlalchemy.orm import Session

from .models import Asset, AssetClass, Currency


class CurrencyRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_all(self) -> list[Currency]:
        return self.db.query(Currency).order_by(Currency.code).all()

    def get_by_id(self, currency_id: int) -> Currency | None:
        return self.db.query(Currency).filter(Currency.id == currency_id).first()

    def get_by_code(self, code: str) -> Currency | None:
        return self.db.query(Currency).filter(Currency.code == code.upper()).first()

    def get_or_create(self, code: str) -> Currency:
        currency = self.get_by_code(code)
        if not currency:
            currency = Currency(code=code.upper())
            self.db.add(currency)
            self.db.commit()
            self.db.refresh(currency)
        return currency

    def create(self, currency: Currency) -> Currency:
        currency.code = currency.code.upper()
        self.db.add(currency)
        self.db.commit()
        self.db.refresh(currency)
        return currency

    def update(self, currency: Currency) -> Currency:
        self.db.commit()
        self.db.refresh(currency)
        return currency

    def delete(self, currency: Currency) -> None:
        self.db.delete(currency)
        self.db.commit()


class AssetClassRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_all(self) -> list[AssetClass]:
        return self.db.query(AssetClass).order_by(AssetClass.name).all()

    def get_by_id(self, ac_id: int) -> AssetClass | None:
        return self.db.query(AssetClass).filter(AssetClass.id == ac_id).first()

    def get_or_create(self, name: str) -> AssetClass:
        ac = self.db.query(AssetClass).filter(AssetClass.name == name).first()
        if not ac:
            ac = AssetClass(name=name)
            self.db.add(ac)
            self.db.commit()
            self.db.refresh(ac)
        return ac

    def create(self, asset_class: AssetClass) -> AssetClass:
        self.db.add(asset_class)
        self.db.commit()
        self.db.refresh(asset_class)
        return asset_class

    def update(self, asset_class: AssetClass) -> AssetClass:
        self.db.commit()
        self.db.refresh(asset_class)
        return asset_class

    def delete(self, asset_class: AssetClass) -> None:
        self.db.delete(asset_class)
        self.db.commit()


class AssetRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_all(self, search: str | None = None) -> list[Asset]:
        q = self.db.query(Asset)
        if search:
            q = q.filter(
                or_(
                    Asset.ticker.ilike(f"%{search}%"),
                    Asset.name.ilike(f"%{search}%"),
                )
            )
        return q.all()

    def get_by_id(self, asset_id: int) -> Asset | None:
        return self.db.query(Asset).filter(Asset.id == asset_id).first()

    def get_by_ticker(self, ticker: str) -> Asset | None:
        return self.db.query(Asset).filter(Asset.ticker == ticker.upper()).first()

    def create(self, asset: Asset) -> Asset:
        asset.ticker = asset.ticker.upper().strip()
        self.db.add(asset)
        self.db.commit()
        self.db.refresh(asset)
        return asset

    def update(self, asset: Asset) -> Asset:
        self.db.commit()
        self.db.refresh(asset)
        return asset

    def delete(self, asset: Asset) -> None:
        self.db.delete(asset)
        self.db.commit()
