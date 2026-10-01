from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.sql.base import Base

if TYPE_CHECKING:
    from app.modules.assets.models.assets import Asset


class Currency(Base):
    __tablename__ = "assets_currency"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(
        String(3), unique=True, nullable=False, index=True
    )
    exchange_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 9), nullable=False, default=Decimal("1")
    )
    base_currency_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("assets_currency.id"), nullable=True
    )

    base_currency: Mapped[Currency | None] = relationship(remote_side="Currency.id")
    assets: Mapped[list[Asset]] = relationship(back_populates="currency")

    def __repr__(self) -> str:
        return self.code
