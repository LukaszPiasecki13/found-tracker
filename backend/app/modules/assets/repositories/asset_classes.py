"""Asset class repository for data access."""

from sqlalchemy import select

from app.infrastructure.sql.repository import SQLRepository
from app.modules.assets.exceptions import AssetClassNotFoundError
from app.modules.assets.models.asset_classes import AssetClass


class AssetClassRepository(SQLRepository):
    """Repository for AssetClass model database operations."""

    def list_all(self) -> list[AssetClass]:
        """All asset classes ordered by name."""
        stmt = select(AssetClass).order_by(AssetClass.name)
        return list(self.session.execute(stmt).scalars())

    def find_by_id(self, asset_class_id: int) -> AssetClass | None:
        """Find asset class by ID. Returns None if not found."""
        stmt = select(AssetClass).where(AssetClass.id == asset_class_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_by_id(self, asset_class_id: int) -> AssetClass:
        """Get asset class by ID or raise AssetClassNotFoundError."""
        asset_class = self.find_by_id(asset_class_id)
        if asset_class is None:
            raise AssetClassNotFoundError
        return asset_class

    def find_by_name(self, name: str) -> AssetClass | None:
        """Find asset class by exact name."""
        stmt = select(AssetClass).where(AssetClass.name == name)
        return self.session.execute(stmt).scalar_one_or_none()

    def create(self, name: str) -> AssetClass:
        """Create new asset class."""
        asset_class = AssetClass(name=name)
        self.session.add(asset_class)
        self.flush()
        return asset_class

    def update(self, asset_class: AssetClass) -> AssetClass:
        """Write pending changes of an asset class."""
        self.flush()
        return asset_class

    def delete(self, asset_class: AssetClass) -> None:
        """Delete asset class; a still-referenced class fails here (IntegrityError)."""
        self.session.delete(asset_class)
        self.flush()
