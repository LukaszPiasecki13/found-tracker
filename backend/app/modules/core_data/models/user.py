from sqlalchemy import BigInteger, Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.sql.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # The currency of the account's charts (DEC-08). NULL until set: the service
    # falls back to PLN (ACCOUNT_FALLBACK_CURRENCY).
    base_currency_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("assets_currency.id"), nullable=True
    )
