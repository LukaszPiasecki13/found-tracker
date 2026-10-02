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
    from app.modules.assets.models.currencies import Currency


class FxRate(Base):
    """One daily exchange rate from one source: `rate` units of `to_currency`
    per one unit of `from_currency` (the pair as the source quotes it).

    Rates are data about a currency, not a reason to keep it: deleting a currency
    (allowed only when no asset or portfolio uses it) removes its rates."""

    __tablename__ = "assets_fx_rate"
    __table_args__ = (
        UniqueConstraint(
            "from_currency_id",
            "to_currency_id",
            "rate_date",
            "source",
            name="uq_assets_fx_rate_pair_date_source",
        ),
        CheckConstraint("rate > 0", name="ck_assets_fx_rate_rate_positive"),
        CheckConstraint(
            "from_currency_id <> to_currency_id", name="ck_assets_fx_rate_distinct"
        ),
        Index(
            "ix_assets_fx_rate_pair_rate_date",
            "from_currency_id",
            "to_currency_id",
            "rate_date",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    from_currency_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("assets_currency.id", ondelete="CASCADE"),
        nullable=False,
    )
    to_currency_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("assets_currency.id", ondelete="CASCADE"),
        nullable=False,
    )
    rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 9), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    # Publisher's table number as evidence (e.g. NBP "187/A/NBP/2026").
    table_no: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    from_currency: Mapped[Currency] = relationship(foreign_keys=[from_currency_id])
    to_currency: Mapped[Currency] = relationship(foreign_keys=[to_currency_id])
