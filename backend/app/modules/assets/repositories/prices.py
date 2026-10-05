"""Price history repository for data access."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.infrastructure.sql.repository import SQLRepository
from app.modules.assets.constants import SOURCE_MANUAL
from app.modules.assets.models.prices import AssetPrice


class PriceRepository(SQLRepository):
    """Repository for `AssetPrice` database operations."""

    def find(self, asset_id: int, price_date: date, source: str) -> AssetPrice | None:
        stmt = select(AssetPrice).where(
            AssetPrice.asset_id == asset_id,
            AssetPrice.price_date == price_date,
            AssetPrice.source == source,
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def upsert(
        self,
        *,
        asset_id: int,
        price_date: date,
        close: Decimal,
        currency_id: int,
        source: str,
        is_synthetic: bool,
    ) -> AssetPrice:
        """Insert the observation, or overwrite the one with the same asset, day
        and source - so a repeated fetch is a no-op in effect (idempotent)."""
        row = self.find(asset_id, price_date, source)
        if row is None:
            row = AssetPrice(
                asset_id=asset_id,
                price_date=price_date,
                close=close,
                currency_id=currency_id,
                source=source,
                is_synthetic=is_synthetic,
            )
            self.session.add(row)
        else:
            row.close = close
            row.currency_id = currency_id
            row.is_synthetic = is_synthetic
            row.fetched_at = datetime.now().astimezone()
        self.flush()
        return row

    def upsert_many(
        self,
        *,
        asset_id: int,
        currency_id: int,
        source: str,
        is_synthetic: bool,
        closes: dict[date, Decimal],
    ) -> int:
        """Insert or overwrite many days of one asset and source in one statement
        (the same rule as `upsert`, one round trip instead of one per day - a long
        history written row by row outlasts the database's statement timeout).
        Returns how many days were written."""
        if not closes:
            return 0
        statement = insert(AssetPrice).values(
            [
                {
                    "asset_id": asset_id,
                    "price_date": day,
                    "close": close,
                    "currency_id": currency_id,
                    "source": source,
                    "is_synthetic": is_synthetic,
                }
                for day, close in closes.items()
            ]
        )
        statement = statement.on_conflict_do_update(
            constraint="uq_assets_price_asset_date_source",
            set_={
                "close": statement.excluded.close,
                "currency_id": statement.excluded.currency_id,
                "is_synthetic": statement.excluded.is_synthetic,
                "fetched_at": func.now(),
            },
        )
        self.session.execute(statement)
        self.flush()
        return len(closes)

    def delete(self, row: AssetPrice) -> None:
        self.session.delete(row)
        self.flush()

    def list_for_asset(
        self,
        asset_id: int,
        *,
        up_to: date | None = None,
        from_date: date | None = None,
        source: str | None = None,
    ) -> list[AssetPrice]:
        """Observations of one asset, oldest first; `up_to` and `from_date` are
        inclusive bounds on `price_date`."""
        stmt = select(AssetPrice).where(AssetPrice.asset_id == asset_id)
        if up_to is not None:
            stmt = stmt.where(AssetPrice.price_date <= up_to)
        if from_date is not None:
            stmt = stmt.where(AssetPrice.price_date >= from_date)
        if source is not None:
            stmt = stmt.where(AssetPrice.source == source)
        stmt = stmt.order_by(AssetPrice.price_date, AssetPrice.source)
        return list(self.session.execute(stmt).scalars())

    def latest_day_rows(
        self, asset_id: int, as_of: date | None = None
    ) -> list[AssetPrice]:
        """Every source's row on the asset's most recent day (not after
        `as_of`); empty when it has no price that old."""
        latest = select(func.max(AssetPrice.price_date)).where(
            AssetPrice.asset_id == asset_id
        )
        if as_of is not None:
            latest = latest.where(AssetPrice.price_date <= as_of)
        stmt = select(AssetPrice).where(
            AssetPrice.asset_id == asset_id,
            AssetPrice.price_date == latest.scalar_subquery(),
        )
        return list(self.session.execute(stmt).scalars())

    def latest_day_rows_for(self, asset_ids: list[int]) -> list[AssetPrice]:
        """`latest_day_rows` for many assets in one query."""
        if not asset_ids:
            return []
        # One max-per-asset subquery, joined back to pick that day's rows.
        per_asset = (
            select(
                AssetPrice.asset_id.label("asset_id"),
                func.max(AssetPrice.price_date).label("day"),
            )
            .where(AssetPrice.asset_id.in_(asset_ids))
            .group_by(AssetPrice.asset_id)
            .subquery()
        )
        stmt = select(AssetPrice).join(
            per_asset,
            (AssetPrice.asset_id == per_asset.c.asset_id)
            & (AssetPrice.price_date == per_asset.c.day),
        )
        return list(self.session.execute(stmt).scalars())

    def last_fetched_at(self, asset_ids: list[int]) -> dict[int, datetime]:
        """When each asset last received a non-manual observation."""
        if not asset_ids:
            return {}
        stmt = (
            select(AssetPrice.asset_id, func.max(AssetPrice.fetched_at))
            .where(
                AssetPrice.asset_id.in_(asset_ids), AssetPrice.source != SOURCE_MANUAL
            )
            .group_by(AssetPrice.asset_id)
        )
        return {asset_id: at for asset_id, at in self.session.execute(stmt).all()}

    def exists_for_asset(self, asset_id: int) -> bool:
        stmt = select(AssetPrice.id).where(AssetPrice.asset_id == asset_id).limit(1)
        return self.session.execute(stmt).first() is not None
