from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import relationship

from app.infrastructure.sql.base import Base


class Currency(Base):
    __tablename__ = "assets_currency"

    id = Column(BigInteger, primary_key=True, index=True)
    code = Column(String(3), unique=True, nullable=False, index=True)
    exchange_rate = Column(Numeric(18, 9), nullable=False, default=1.0)
    base_currency_id = Column(
        BigInteger, ForeignKey("assets_currency.id"), nullable=True
    )

    base_currency = relationship("Currency", remote_side="Currency.id")
    assets = relationship("Asset", back_populates="currency")

    def __repr__(self):
        return self.code


class AssetClass(Base):
    __tablename__ = "assets_assetclass"

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String(20), unique=True, nullable=False)

    assets = relationship("Asset", back_populates="asset_class")

    def __repr__(self):
        return self.name


class Asset(Base):
    __tablename__ = "assets_asset"

    id = Column(BigInteger, primary_key=True, index=True)
    ticker = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    asset_class_id = Column(
        BigInteger, ForeignKey("assets_assetclass.id"), nullable=False
    )
    currency_id = Column(BigInteger, ForeignKey("assets_currency.id"), nullable=False)
    current_price = Column(Numeric(18, 9), nullable=False, default=0)
    exchange = Column(String(50), nullable=False, default="")
    sector = Column(String(100), nullable=False, default="")
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    asset_class = relationship("AssetClass", back_populates="assets")
    currency = relationship("Currency", back_populates="assets")
