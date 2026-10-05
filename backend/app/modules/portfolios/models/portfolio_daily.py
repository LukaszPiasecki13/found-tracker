from datetime import date
from decimal import Decimal

from sqlalchemy import BigInteger, Date, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.sql.base import Base


class PortfolioDaily(Base):
    """One day of a portfolio, derived from its operations and the closes
    (ADR-0016): value at the close, cash, the netted external flow, the day's
    return and the cumulative time-weighted index. Rows from
    `Portfolio.dirty_from` on are out of date and rebuilt on the next read."""

    __tablename__ = "portfolios_daily"

    portfolio_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("portfolios_portfolio.id", ondelete="CASCADE"),
        primary_key=True,
    )
    day: Mapped[date] = mapped_column(Date, primary_key=True)

    value: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    cash: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    inflow: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    outflow: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    r_day: Mapped[Decimal] = mapped_column(Numeric(24, 12), nullable=False)
    twr_index: Mapped[Decimal] = mapped_column(Numeric(24, 12), nullable=False)
