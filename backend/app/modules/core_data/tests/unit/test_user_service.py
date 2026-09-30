from functools import partial
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.errors import ConflictError
from app.infrastructure.sql.repository import SQLRepository
from app.modules.core_data.schemas.users import UserCreateRequest
from app.modules.core_data.services.users import UserService


@pytest.fixture
def session() -> MagicMock:
    return MagicMock()


@pytest.fixture
def repo(session: MagicMock) -> MagicMock:
    repo = MagicMock()
    repo.commit = session.commit
    repo.rollback = session.rollback
    repo.transaction = partial(SQLRepository.transaction, repo)
    return repo


@pytest.fixture
def service(repo: MagicMock) -> UserService:
    return UserService(repo)


def test_register_normalizes_email_and_hashes_password(
    service: UserService,
    repo: MagicMock,
    session: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo.find_by_email.return_value = None
    repo.create.side_effect = lambda email, password_hash: SimpleNamespace(
        email=email, password_hash=password_hash
    )
    monkeypatch.setattr(
        "app.modules.core_data.services.users.hash_password",
        lambda password: f"hashed:{password}",
    )

    user = service.register(
        UserCreateRequest(email="User@Example.com", password="StrongPass123")
    )

    assert user.email == "user@example.com"
    assert user.password_hash == "hashed:StrongPass123"
    repo.find_by_email.assert_called_once_with("user@example.com")
    session.commit.assert_called_once()


def test_register_rejects_duplicate_email(
    service: UserService,
    repo: MagicMock,
    session: MagicMock,
) -> None:
    repo.find_by_email.return_value = SimpleNamespace(id=1)

    with pytest.raises(ConflictError) as exc_info:
        service.register(
            UserCreateRequest(email="user@example.com", password="StrongPass123")
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "EMAIL_ALREADY_REGISTERED"
    repo.create.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_called_once()


def test_find_by_email_normalizes_the_lookup_key(
    service: UserService, repo: MagicMock
) -> None:
    found = SimpleNamespace(id=1)
    repo.find_by_email.return_value = found

    assert service.find_by_email("  User@Example.com ") is found
    repo.find_by_email.assert_called_once_with("user@example.com")


def test_find_by_id_returns_none_when_missing(
    service: UserService, repo: MagicMock
) -> None:
    repo.find_by_id.return_value = None

    assert service.find_by_id(7) is None
    repo.find_by_id.assert_called_once_with(7)


def test_request_schema_forbids_unknown_fields() -> None:
    with pytest.raises(ValueError):
        UserCreateRequest.model_validate(
            {"email": "user@example.com", "password": "StrongPass123", "role": "x"}
        )
