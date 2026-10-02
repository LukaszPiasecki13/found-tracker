"""FX-rate history repository for data access."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select

from app.infrastructure.sql.repository import SQLRepository
from app.modules.assets.constants import SOURCE_MANUAL
from app.modules.assets.models.fx_rates import FxRate


class FxRateRepository(SQLRepository):
    """Repository for `FxRate` database operations."""

    def find(
        self, from_id: int, to_id: int, rate_date: date, source: str
    ) -> FxRate | None:
        stmt = select(FxRate).where(
            FxRate.from_currency_id == from_id,
            FxRate.to_currency_id == to_id,
            FxRate.rate_date == rate_date,
            FxRate.source == source,
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def upsert(
        self,
        *,
        from_id: int,
        to_id: int,
        rate_date: date,
        rate: Decimal,
        source: str,
        table_no: str | None = None,
        is_synthetic: bool = False,
    ) -> FxRate:
        """Insert the observation, or overwrite the one with the same pair, day
        and source (idempotent)."""
        row = self.find(from_id, to_id, rate_date, source)
        if row is None:
            row = FxRate(
                from_currency_id=from_id,
                to_currency_id=to_id,
                rate_date=rate_date,
                rate=rate,
                source=source,
                table_no=table_no,
                is_synthetic=is_synthetic,
            )
            self.session.add(row)
        else:
            row.rate = rate
            row.table_no = table_no
            row.is_synthetic = is_synthetic
            row.fetched_at = datetime.now().astimezone()
        self.flush()
        return row

    def list_pair(
        self,
        from_id: int,
        to_id: int,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        source: str | None = None,
    ) -> list[FxRate]:
        """Observations of one directed pair, oldest first (inclusive bounds)."""
        stmt = select(FxRate).where(
            FxRate.from_currency_id == from_id, FxRate.to_currency_id == to_id
        )
        if from_date is not None:
            stmt = stmt.where(FxRate.rate_date >= from_date)
        if to_date is not None:
            stmt = stmt.where(FxRate.rate_date <= to_date)
        if source is not None:
            stmt = stmt.where(FxRate.source == source)
        stmt = stmt.order_by(FxRate.rate_date, FxRate.source)
        return list(self.session.execute(stmt).scalars())

    def latest_day_rows(
        self, from_id: int, to_id: int, as_of: date | None = None
    ) -> list[FxRate]:
        """Every source's row on the pair's most recent day (not after `as_of`);
        empty when it has no rate that old."""
        latest = select(func.max(FxRate.rate_date)).where(
            FxRate.from_currency_id == from_id, FxRate.to_currency_id == to_id
        )
        if as_of is not None:
            latest = latest.where(FxRate.rate_date <= as_of)
        stmt = select(FxRate).where(
            FxRate.from_currency_id == from_id,
            FxRate.to_currency_id == to_id,
            FxRate.rate_date == latest.scalar_subquery(),
        )
        return list(self.session.execute(stmt).scalars())

    def last_fetched_at(self) -> datetime | None:
        """When any provider last wrote a rate."""
        stmt = select(func.max(FxRate.fetched_at)).where(FxRate.source != SOURCE_MANUAL)
        return self.session.execute(stmt).scalar_one_or_none()

    def currency_ids_with_rates(self) -> set[int]:
        """Currencies that appear on either side of a stored rate."""
        from_ids = select(FxRate.from_currency_id).distinct()
        to_ids = select(FxRate.to_currency_id).distinct()
        return set(self.session.execute(from_ids).scalars()) | set(
            self.session.execute(to_ids).scalars()
        )
