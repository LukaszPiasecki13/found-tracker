"""Currency repository for data access."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.sql.repository import SQLRepository
from app.modules.assets.exceptions import CurrencyNotFoundError
from app.modules.assets.models.currencies import Currency


class CurrencyRepository(SQLRepository):
    """Repository for Currency model database operations."""

    def __init__(self, session: Session):
        super().__init__(session)

    def list_all(self) -> list[Currency]:
        """All currencies ordered by code."""
        stmt = select(Currency).order_by(Currency.code)
        return list(self.session.execute(stmt).scalars())

    def find_by_id(self, currency_id: int) -> Currency | None:
        """Find currency by ID. Returns None if not found."""
        stmt = select(Currency).where(Currency.id == currency_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_by_id(self, currency_id: int) -> Currency:
        """Get currency by ID or raise CurrencyNotFoundError."""
        currency = self.find_by_id(currency_id)
        if currency is None:
            raise CurrencyNotFoundError
        return currency

    def find_by_code(self, code: str) -> Currency | None:
        """Find currency by (already normalized) code."""
        stmt = select(Currency).where(Currency.code == code)
        return self.session.execute(stmt).scalar_one_or_none()

    def create(
        self,
        code: str,
        exchange_rate: Decimal = Decimal("1"),
        base_currency_id: int | None = None,
    ) -> Currency:
        """Create new currency."""
        currency = Currency(
            code=code, exchange_rate=exchange_rate, base_currency_id=base_currency_id
        )
        self.session.add(currency)
        self.flush()
        return currency

    def update(self, currency: Currency) -> Currency:
        """Write pending changes of a currency."""
        self.flush()
        return currency

    def delete(self, currency: Currency) -> None:
        """Delete currency; a still-referenced currency fails here (IntegrityError)."""
        self.session.delete(currency)
        self.flush()
