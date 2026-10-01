from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.sql.base import Base

if TYPE_CHECKING:
    from app.modules.assets.models.assets import Asset


class AssetClass(Base):
    __tablename__ = "assets_assetclass"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    assets: Mapped[list[Asset]] = relationship(back_populates="asset_class")

    def __repr__(self) -> str:
        return self.name
