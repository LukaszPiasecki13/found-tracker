from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.sql.base import Base

if TYPE_CHECKING:
    from app.modules.assets.models.assets import Asset
    from app.modules.portfolios.models.portfolio import Portfolio


class Position(Base):
    """Holding of one asset in one portfolio - derived from the operations."""

    __tablename__ = "portfolios_position"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    portfolio_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("portfolios_portfolio.id"), nullable=False
    )
    asset_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("assets_asset.id"), nullable=False
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 9), nullable=False, default=Decimal("0")
    )
    average_buy_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 9), nullable=False, default=Decimal("0")
    )
    average_fx_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 9), nullable=False, default=Decimal("1")
    )
    total_fees: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0")
    )
    total_dividends: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0")
    )

    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    portfolio: Mapped[Portfolio] = relationship(back_populates="positions")
    asset: Mapped[Asset] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "portfolio_id", "asset_id", name="unique_position_per_portfolio"
        ),
        Index("ix_position_portfolio_asset", "portfolio_id", "asset_id"),
    )
