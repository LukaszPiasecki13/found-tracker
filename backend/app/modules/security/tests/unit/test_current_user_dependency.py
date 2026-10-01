from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.errors import register_error_handlers
from app.modules.core_data.dependencies import get_user_service
from app.modules.security.dependencies import get_current_user, get_token_service
from app.modules.security.services.token import TokenService

TOKENS = TokenService("test-secret")


@pytest.fixture
def users() -> MagicMock:
    service = MagicMock()
    service.find_by_id.return_value = SimpleNamespace(id=42, is_active=True)
    return service


@pytest.fixture
def client(users: MagicMock) -> TestClient:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/protected")
    def protected(user: SimpleNamespace = Depends(get_current_user)) -> dict[str, int]:
        return {"id": user.id}

    app.dependency_overrides[get_user_service] = lambda: users
    app.dependency_overrides[get_token_service] = lambda: TOKENS
    return TestClient(app)


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_valid_access_token_resolves_the_user(client: TestClient) -> None:
    response = client.get(
        "/protected", headers=_bearer(TOKENS.create_access_token({"sub": "42"}))
    )

    assert response.status_code == 200
    assert response.json() == {"id": 42}


def test_missing_header_returns_contract_error_with_bearer_challenge(
    client: TestClient,
) -> None:
    response = client.get("/protected")

    assert response.status_code == 401
    assert response.json()["code"] == "MISSING_CREDENTIALS"
    assert response.headers["www-authenticate"] == "Bearer"


def test_non_bearer_scheme_is_treated_as_missing_credentials(
    client: TestClient,
) -> None:
    response = client.get("/protected", headers={"Authorization": "Basic abc"})

    assert response.status_code == 401
    assert response.json()["code"] == "MISSING_CREDENTIALS"


@pytest.mark.parametrize(
    "token",
    [
        "garbage",
        TOKENS.create_refresh_token({"sub": "42"}),
        TOKENS.create_access_token({}),
        TOKENS.create_access_token({"sub": "abc"}),
        TokenService("other-secret").create_access_token({"sub": "42"}),
    ],
    ids=["garbage", "refresh-token", "no-sub", "non-numeric-sub", "wrong-signature"],
)
def test_invalid_access_token_is_rejected(client: TestClient, token: str) -> None:
    response = client.get("/protected", headers=_bearer(token))

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_ACCESS_TOKEN"
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("user", [None, SimpleNamespace(id=42, is_active=False)])
def test_missing_or_inactive_user_is_rejected(
    client: TestClient, users: MagicMock, user: SimpleNamespace | None
) -> None:
    users.find_by_id.return_value = user

    response = client.get(
        "/protected", headers=_bearer(TOKENS.create_access_token({"sub": "42"}))
    )

    assert response.status_code == 401
    assert response.json()["code"] == "INACTIVE_USER"
