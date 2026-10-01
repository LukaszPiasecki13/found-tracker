"""Asset repository for data access."""

from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.infrastructure.sql.repository import SQLRepository
from app.modules.assets.exceptions import AssetNotFoundError
from app.modules.assets.models.assets import Asset


class AssetRepository(SQLRepository):
    """Repository for Asset model database operations."""

    def __init__(self, session: Session):
        super().__init__(session)

    def list_all(
        self, search: str | None = None, limit: int | None = None
    ) -> list[Asset]:
        """Assets ordered by ticker; `search` matches ticker or name
        (case-insensitive substring)."""
        stmt = select(Asset).order_by(Asset.ticker)
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(Asset.ticker.ilike(pattern), Asset.name.ilike(pattern))
            )
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.session.execute(stmt).scalars())

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
        )
        self.session.add(asset)
        self.flush()
        self.refresh(asset)
        return asset

    def update(self, asset: Asset) -> Asset:
        """Write pending changes; refreshed so the new `updated_at` is loaded."""
        self.flush()
        self.refresh(asset)
        return asset

    def delete(self, asset: Asset) -> None:
        """Delete asset; a still-referenced asset fails here (IntegrityError)."""
        self.session.delete(asset)
        self.flush()
