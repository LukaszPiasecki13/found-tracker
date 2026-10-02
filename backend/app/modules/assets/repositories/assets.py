"""Asset repository for data access."""

from decimal import Decimal

from sqlalchemy import or_, select

from app.infrastructure.sql.repository import SQLRepository
from app.modules.assets.exceptions import AssetNotFoundError
from app.modules.assets.models.assets import Asset


class AssetRepository(SQLRepository):
    """Repository for Asset model database operations."""

    def list_all(
        self,
        search: str | None = None,
        limit: int | None = None,
        *,
        asset_type: str | None = None,
        asset_class_id: int | None = None,
        country: str | None = None,
        include_archived: bool = False,
    ) -> list[Asset]:
        """Assets ordered by ticker; `search` matches ticker, name or ISIN
        (case-insensitive substring). Archived assets are left out unless
        `include_archived`."""
        stmt = select(Asset).order_by(Asset.ticker)
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    Asset.ticker.ilike(pattern),
                    Asset.name.ilike(pattern),
                    Asset.isin.ilike(pattern),
                )
            )
        if asset_type is not None:
            stmt = stmt.where(Asset.asset_type == asset_type)
        if asset_class_id is not None:
            stmt = stmt.where(Asset.asset_class_id == asset_class_id)
        if country is not None:
            stmt = stmt.where(Asset.country == country)
        if not include_archived:
            stmt = stmt.where(Asset.archived_at.is_(None))
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.session.execute(stmt).scalars())

    def list_by_ids(self, asset_ids: list[int]) -> list[Asset]:
        """The assets with these ids, ordered by ticker; unknown ids are absent."""
        if not asset_ids:
            return []
        stmt = select(Asset).where(Asset.id.in_(asset_ids)).order_by(Asset.ticker)
        return list(self.session.execute(stmt).scalars())

    def find_by_isin(self, isin: str) -> Asset | None:
        """Find asset by (already normalized) ISIN."""
        stmt = select(Asset).where(Asset.isin == isin)
        return self.session.execute(stmt).scalar_one_or_none()

    def find_by_id(self, asset_id: int) -> Asset | None:
        """Find asset by ID. Returns None if not found."""
        stmt = select(Asset).where(Asset.id == asset_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_by_id(self, asset_id: int) -> Asset:
        """Get asset by ID or raise AssetNotFoundError."""
        asset = self.find_by_id(asset_id)
        if asset is None:
            raise AssetNotFoundError
        return asset

    def find_by_ticker(self, ticker: str) -> Asset | None:
        """Find asset by (already normalized) ticker."""
        stmt = select(Asset).where(Asset.ticker == ticker)
        return self.session.execute(stmt).scalar_one_or_none()

    def create(
        self,
        *,
        ticker: str,
        name: str,
        asset_class_id: int,
        currency_id: int,
        current_price: Decimal = Decimal("0"),
        exchange: str = "",
        sector: str = "",
        isin: str | None = None,
        mic: str | None = None,
        country: str | None = None,
        asset_type: str = "user_asset",
    ) -> Asset:
        """Create new asset; refreshed so the server-side `updated_at` is loaded."""
        asset = Asset(
            ticker=ticker,
            name=name,
            asset_class_id=asset_class_id,
            currency_id=currency_id,
            current_price=current_price,
            exchange=exchange,
            sector=sector,
            isin=isin,
            mic=mic,
            country=country,
            asset_type=asset_type,
        )
        return self.save_new(asset)

    def update(self, asset: Asset) -> Asset:
        """Write pending changes; refreshed so the new `updated_at` is loaded."""
        return self.persist(asset)

    def delete(self, asset: Asset) -> None:
        """Delete asset; a still-referenced asset fails here (IntegrityError)."""
        self.session.delete(asset)
        self.flush()
