from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.modules.assets.exceptions import (
    AssetClassAlreadyExistsError,
    AssetClassInUseError,
    AssetClassNotFoundError,
)
from app.modules.assets.schemas.asset_classes import (
    AssetClassCreateRequest,
    AssetClassUpdateRequest,
)
from app.modules.assets.services.asset_classes import AssetClassService


def _integrity_error() -> IntegrityError:
    return IntegrityError("INSERT ...", {}, Exception("duplicate key"))


@pytest.fixture
def service(asset_class_repo: MagicMock) -> AssetClassService:
    return AssetClassService(asset_class_repo)


def test_create_writes_in_one_transaction(
    service: AssetClassService, asset_class_repo: MagicMock, session: MagicMock
) -> None:
    asset_class_repo.find_by_name.return_value = None
    created = SimpleNamespace(id=1, name="Stock")
    asset_class_repo.create.return_value = created

    assert service.create(AssetClassCreateRequest(name="Stock")) is created

    asset_class_repo.create.assert_called_once_with("Stock")
    session.commit.assert_called_once()


def test_create_rejects_duplicate_name(
    service: AssetClassService, asset_class_repo: MagicMock, session: MagicMock
) -> None:
    asset_class_repo.find_by_name.return_value = SimpleNamespace(id=1, name="ETF")

    with pytest.raises(AssetClassAlreadyExistsError) as exc_info:
        service.create(AssetClassCreateRequest(name="ETF"))

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "ASSET_CLASS_ALREADY_EXISTS"
    asset_class_repo.create.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_called_once()


def test_create_translates_a_lost_race_on_the_unique_name(
    service: AssetClassService, asset_class_repo: MagicMock, session: MagicMock
) -> None:
    # Free when checked, taken by a concurrent writer by the time we insert.
    asset_class_repo.find_by_name.side_effect = [None, SimpleNamespace(id=9)]
    asset_class_repo.create.side_effect = _integrity_error()

    with pytest.raises(AssetClassAlreadyExistsError) as exc_info:
        service.create(AssetClassCreateRequest(name="ETF"))

    assert isinstance(exc_info.value.__cause__, IntegrityError)
    session.rollback.assert_called_once()
    session.commit.assert_not_called()


def test_create_reraises_an_integrity_error_that_is_not_a_duplicate(
    service: AssetClassService, asset_class_repo: MagicMock
) -> None:
    asset_class_repo.find_by_name.return_value = None
    asset_class_repo.create.side_effect = _integrity_error()

    with pytest.raises(IntegrityError):
        service.create(AssetClassCreateRequest(name="ETF"))


def test_update_renames(
    service: AssetClassService, asset_class_repo: MagicMock, session: MagicMock
) -> None:
    asset_class = SimpleNamespace(id=1, name="Stock")
    asset_class_repo.get_by_id.return_value = asset_class
    asset_class_repo.find_by_name.return_value = None
    asset_class_repo.update.side_effect = lambda entity: entity

    updated = service.update(1, AssetClassUpdateRequest(name="Equity"))

    assert updated.name == "Equity"
    session.commit.assert_called_once()


def test_update_allows_keeping_its_own_name(
    service: AssetClassService, asset_class_repo: MagicMock
) -> None:
    asset_class = SimpleNamespace(id=1, name="Stock")
    asset_class_repo.get_by_id.return_value = asset_class
    asset_class_repo.find_by_name.return_value = asset_class
    asset_class_repo.update.side_effect = lambda entity: entity

    assert service.update(1, AssetClassUpdateRequest(name="Stock")).name == "Stock"


def test_update_rejects_name_of_another_class(
    service: AssetClassService, asset_class_repo: MagicMock, session: MagicMock
) -> None:
    asset_class_repo.get_by_id.return_value = SimpleNamespace(id=1, name="Stock")
    asset_class_repo.find_by_name.return_value = SimpleNamespace(id=2, name="ETF")

    with pytest.raises(AssetClassAlreadyExistsError):
        service.update(1, AssetClassUpdateRequest(name="ETF"))

    session.rollback.assert_called_once()
    session.commit.assert_not_called()


def test_update_of_missing_class_propagates_not_found(
    service: AssetClassService, asset_class_repo: MagicMock
) -> None:
    asset_class_repo.get_by_id.side_effect = AssetClassNotFoundError

    with pytest.raises(AssetClassNotFoundError) as exc_info:
        service.update(404, AssetClassUpdateRequest(name="ETF"))

    assert exc_info.value.code == "ASSET_CLASS_NOT_FOUND"


def test_delete_commits(
    service: AssetClassService, asset_class_repo: MagicMock, session: MagicMock
) -> None:
    asset_class = SimpleNamespace(id=1)
    asset_class_repo.get_by_id.return_value = asset_class

    service.delete(1)

    asset_class_repo.delete.assert_called_once_with(asset_class)
    session.commit.assert_called_once()


def test_delete_of_class_with_assets_is_in_use(
    service: AssetClassService, asset_class_repo: MagicMock, session: MagicMock
) -> None:
    asset_class_repo.get_by_id.return_value = SimpleNamespace(id=1)
    asset_class_repo.delete.side_effect = _integrity_error()

    with pytest.raises(AssetClassInUseError) as exc_info:
        service.delete(1)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "ASSET_CLASS_IN_USE"
    session.rollback.assert_called_once()


def test_get_or_create_by_name_returns_existing_without_committing(
    service: AssetClassService, asset_class_repo: MagicMock, session: MagicMock
) -> None:
    existing = SimpleNamespace(id=3, name="ETF")
    asset_class_repo.find_by_name.return_value = existing

    assert service.get_or_create_by_name("ETF") is existing

    asset_class_repo.create.assert_not_called()
    session.commit.assert_not_called()


def test_get_or_create_by_name_creates_without_committing(
    service: AssetClassService, asset_class_repo: MagicMock, session: MagicMock
) -> None:
    asset_class_repo.find_by_name.return_value = None
    created = SimpleNamespace(id=4, name="Crypto")
    asset_class_repo.create.return_value = created

    assert service.get_or_create_by_name("Crypto") is created

    asset_class_repo.create.assert_called_once_with("Crypto")
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


@pytest.mark.parametrize(
    "payload", [{"name": ""}, {"name": "x" * 21}, {"name": "ETF", "id": 1}]
)
def test_create_request_validates_shape(payload: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        AssetClassCreateRequest.model_validate(payload)
