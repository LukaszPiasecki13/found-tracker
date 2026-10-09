"""Bond series terms model: parameters needed to calculate interest accrual."""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.sql.base import Base

if TYPE_CHECKING:
    from app.modules.assets.models.assets import Asset


class BondTerms(Base):
    """Bond series parameters (1:1 with Asset). Used to calculate accrual.

    One bond asset has at most one BondTerms record. The relationship is optional
    (asset_id can be null initially, then filled via upsert).
    """

    __tablename__ = "assets_bond_terms"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets_asset.id"), nullable=False, unique=True, index=True
    )
    bond_symbol: Mapped[str] = mapped_column(
        String(10), nullable=False, index=True
    )  # OTS, ROR, DOR, TOS, COI, EDO, ROS, ROD
    series_code: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # e.g., EDO1036
    nominal_value: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("100.00")
    )
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    maturity_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Capitalization strategy: "none" (interest paid out), "monthly" (rare),
    # "annual" (most bonds).
    capitalization: Mapped[str] = mapped_column(String(10), nullable=False)
    # Fixed rate for first period (percent per year): used by all types.
    first_period_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(9, 4), nullable=True
    )
    # For types with reference rates: "fixed" (TOS), "nbp_reference" (ROR, DOR),
    # "cpi" (COI, EDO, ROS, ROD).
    reference_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Margin over reference rate/CPI (percent per year), nullable.
    margin: Mapped[Decimal | None] = mapped_column(Numeric(9, 4), nullable=True)
    # Early redemption fee in PLN per bond unit (e.g., 1.00, 2.00, 3.00).
    redemption_fee: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    # Source of data: "bonds" (from provider), "manual" (user override).
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="bonds", server_default=text("'bonds'")
    )
    # Timestamp when data was fetched from provider (null if manual).
    fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    asset: Mapped[Asset] = relationship(back_populates="bond_terms")
