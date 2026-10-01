from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.sql.base import Base

if TYPE_CHECKING:
    from app.modules.assets.models.assets import Asset
    from app.modules.portfolios.models.portfolio import Portfolio


class Operation(Base):
    """A recorded event - the source of truth a portfolio's state derives from.

    `operation_type` holds an `OperationType` value (buy, sell, deposit,
    withdrawal, dividend).
    """

    __tablename__ = "portfolios_operation"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    portfolio_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("portfolios_portfolio.id"), nullable=False
    )
    asset_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("assets_asset.id"), nullable=True
    )

    operation_type: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 9), nullable=False, default=Decimal("0")
    )
    price: Mapped[Decimal] = mapped_column(
        Numeric(18, 9), nullable=False, default=Decimal("0")
    )
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    fee: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0")
    )
    fx_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 9), nullable=False, default=Decimal("1")
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    operation_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    portfolio: Mapped[Portfolio] = relationship(back_populates="operations")
    asset: Mapped[Asset | None] = relationship()

    __table_args__ = (
        Index("ix_operation_portfolio_date", "portfolio_id", "operation_date"),
    )
