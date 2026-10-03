from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.sql.base import Base

if TYPE_CHECKING:
    from app.modules.assets.models.assets import Asset
    from app.modules.assets.models.currencies import Currency


class AssetPrice(Base):
    """One unadjusted daily close of an asset from one source.

    Sources coexist on a day; `manual` wins, then providers (see
    `domain.pricing`). Forward-fill is computed on read, never stored.
    """

    __tablename__ = "assets_price"
    __table_args__ = (
        UniqueConstraint(
            "asset_id", "price_date", "source", name="uq_assets_price_asset_date_source"
        ),
        CheckConstraint("close > 0", name="ck_assets_price_close_positive"),
        Index("ix_assets_price_asset_id_price_date", "asset_id", "price_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    asset_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("assets_asset.id"), nullable=False
    )
    price_date: Mapped[date] = mapped_column(Date, nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 9), nullable=False)
    currency_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("assets_currency.id"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    asset: Mapped[Asset] = relationship()
    currency: Mapped[Currency] = relationship()
