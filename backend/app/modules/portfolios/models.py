from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.infrastructure.sql.base import Base


class Pocket(Base):
    __tablename__ = "portfolios_pocket"

    id = Column(BigInteger, primary_key=True, index=True)
    owner_id = Column(
        BigInteger, ForeignKey("authentication_userprofile.id"), nullable=False
    )
    name = Column(String(100), nullable=False)
    base_currency_id = Column(
        BigInteger, ForeignKey("assets_currency.id"), nullable=False
    )

    cash_balance = Column(Numeric(18, 3), nullable=False, default=0)
    total_deposited = Column(Numeric(18, 3), nullable=False, default=0)

    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    owner = relationship("User")
    base_currency = relationship("Currency")
    positions = relationship(
        "Position", back_populates="pocket", cascade="all, delete-orphan"
    )
    operations = relationship(
        "Operation", back_populates="pocket", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="unique_pocket_per_user"),
    )


class Position(Base):
    __tablename__ = "portfolios_position"

    id = Column(BigInteger, primary_key=True, index=True)
    pocket_id = Column(BigInteger, ForeignKey("portfolios_pocket.id"), nullable=False)
    asset_id = Column(BigInteger, ForeignKey("assets_asset.id"), nullable=False)

    quantity = Column(Numeric(18, 9), nullable=False, default=0)
    average_buy_price = Column(Numeric(18, 9), nullable=False, default=0)
    average_fx_rate = Column(Numeric(18, 9), nullable=False, default=1)
    total_fees = Column(Numeric(18, 2), nullable=False, default=0)
    total_dividends = Column(Numeric(18, 2), nullable=False, default=0)

    opened_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    pocket = relationship("Pocket", back_populates="positions")
    asset = relationship("Asset")

    __table_args__ = (
        UniqueConstraint("pocket_id", "asset_id", name="unique_position_per_pocket"),
        Index("ix_position_pocket_asset", "pocket_id", "asset_id"),
    )


class Operation(Base):
    __tablename__ = "portfolios_operation"

    id = Column(BigInteger, primary_key=True, index=True)
    pocket_id = Column(BigInteger, ForeignKey("portfolios_pocket.id"), nullable=False)
    asset_id = Column(BigInteger, ForeignKey("assets_asset.id"), nullable=True)

    operation_type = Column(
        String(20), nullable=False
    )  # buy, sell, deposit, withdrawal, dividend
    quantity = Column(Numeric(18, 9), nullable=False, default=0)
    price = Column(Numeric(18, 9), nullable=False, default=0)
    amount = Column(Numeric(18, 2), nullable=True)
    fee = Column(Numeric(18, 2), nullable=False, default=0)
    fx_rate = Column(Numeric(18, 9), nullable=False, default=1)

    notes = Column(Text, nullable=True)
    operation_date = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    pocket = relationship("Pocket", back_populates="operations")
    asset = relationship("Asset")

    __table_args__ = (Index("ix_operation_pocket_date", "pocket_id", "operation_date"),)
