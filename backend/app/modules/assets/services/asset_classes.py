"""Asset class management."""

from sqlalchemy.exc import IntegrityError

from app.modules.assets.exceptions import (
    AssetClassAlreadyExistsError,
    AssetClassInUseError,
)
from app.modules.assets.models.asset_classes import AssetClass
from app.modules.assets.repositories.asset_classes import AssetClassRepository
from app.modules.assets.schemas.asset_classes import (
    AssetClassCreateRequest,
    AssetClassUpdateRequest,
)


class AssetClassService:
    """Asset class CRUD; names are unique (exact match)."""

    def __init__(self, repository: AssetClassRepository) -> None:
        self._repo = repository

    def list_asset_classes(self) -> list[AssetClass]:
        return self._repo.list_all()

    def get_by_id(self, asset_class_id: int) -> AssetClass:
        """Raises AssetClassNotFoundError."""
        return self._repo.get_by_id(asset_class_id)

    def find_by_id(self, asset_class_id: int) -> AssetClass | None:
        return self._repo.find_by_id(asset_class_id)

    def create(self, data: AssetClassCreateRequest) -> AssetClass:
        try:
            with self._repo.transaction():
                if self._repo.find_by_name(data.name):
                    raise AssetClassAlreadyExistsError
                return self._repo.create(data.name)
        except IntegrityError as err:
            self._raise_if_name_taken(data.name, err)
            raise

    def update(self, asset_class_id: int, data: AssetClassUpdateRequest) -> AssetClass:
        try:
            with self._repo.transaction():
                asset_class = self._repo.get_by_id(asset_class_id)
                duplicate = self._repo.find_by_name(data.name)
                if duplicate and duplicate.id != asset_class.id:
                    raise AssetClassAlreadyExistsError
                asset_class.name = data.name
                return self._repo.update(asset_class)
        except IntegrityError as err:
            self._raise_if_name_taken(data.name, err, other_than=asset_class_id)
            raise

    def delete(self, asset_class_id: int) -> None:
        """Delete a class no asset belongs to."""
        try:
            with self._repo.transaction():
                self._repo.delete(self._repo.get_by_id(asset_class_id))
        except IntegrityError as err:
            raise AssetClassInUseError from err

    def get_or_create_by_name(self, name: str) -> AssetClass:
        """Existing class with this exact name, or a new one (flushed, has an id).

        No-commit core — transaction belongs to caller.
        """
        asset_class = self._repo.find_by_name(name)
        if asset_class is None:
            asset_class = self._repo.create(name)
        return asset_class

    def _raise_if_name_taken(
        self, name: str, err: IntegrityError, *, other_than: int | None = None
    ) -> None:
        """After a failed commit: a concurrent writer took the name first."""
        existing = self._repo.find_by_name(name)
        if existing is not None and existing.id != other_than:
            raise AssetClassAlreadyExistsError from err
