from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.sql.base import Base

if TYPE_CHECKING:
    from app.modules.assets.models.asset_classes import AssetClass
    from app.modules.assets.models.bond_terms import BondTerms
    from app.modules.assets.models.currencies import Currency


class Asset(Base):
    __tablename__ = "assets_asset"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    ticker: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    asset_class_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("assets_assetclass.id"), nullable=False
    )
    currency_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("assets_currency.id"), nullable=False
    )
    current_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 9), nullable=False, default=Decimal("0")
    )
    exchange: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    sector: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    isin: Mapped[str | None] = mapped_column(
        String(12), unique=True, nullable=True, index=True
    )
    mic: Mapped[str | None] = mapped_column(String(4), nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    asset_type: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="stock",
        server_default=text("'stock'"),
    )
    # Set for an archived asset: hidden from search and new operations, kept in
    # history and valuation; ticker refreshes stop.
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    asset_class: Mapped[AssetClass] = relationship(back_populates="assets")
    currency: Mapped[Currency] = relationship(back_populates="assets")
    bond_terms: Mapped[BondTerms | None] = relationship(back_populates="asset")
