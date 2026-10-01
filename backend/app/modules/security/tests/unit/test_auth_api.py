from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import register_error_handlers
from app.modules.security.api.auth import router
from app.modules.security.dependencies import get_auth_service
from app.modules.security.errors import InvalidCredentialsError
from app.modules.security.schemas import TokenResponse


@pytest.fixture
def auth_service() -> MagicMock:
    return MagicMock()


@pytest.fixture
def client(auth_service: MagicMock) -> TestClient:
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    return TestClient(app)


@pytest.mark.parametrize("path", ["/auth/login", "/auth/token"])
def test_login_endpoint_uses_email_password_payload(
    client: TestClient, auth_service: MagicMock, path: str
) -> None:
    auth_service.login.return_value = TokenResponse(
        access="access-token", refresh="refresh-token"
    )

    response = client.post(
        path, json={"email": "user@example.com", "password": "StrongPass123"}
    )

    assert response.status_code == 200
    assert response.json() == {"access": "access-token", "refresh": "refresh-token"}
    auth_service.login.assert_called_once()
    assert auth_service.login.call_args.args[0].email == "user@example.com"


def test_login_failure_uses_error_contract(
    client: TestClient, auth_service: MagicMock
) -> None:
    auth_service.login.side_effect = InvalidCredentialsError

    response = client.post(
        "/auth/login", json={"email": "user@example.com", "password": "bad"}
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Invalid credentials",
        "code": "INVALID_CREDENTIALS",
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "user@example.com", "password": "x" * 73},
        {"email": "user@example.com", "password": "ą" * 37},
        {"email": "user@example.com", "password": ""},
        {"email": "not-an-email", "password": "StrongPass123"},
        {"email": "user@example.com", "password": "StrongPass123", "admin": True},
    ],
    ids=["too-long", "too-many-bytes", "empty", "bad-email", "extra-field"],
)
def test_login_rejects_invalid_payload_before_the_service(
    client: TestClient, auth_service: MagicMock, payload: dict[str, object]
) -> None:
    response = client.post("/auth/login", json=payload)

    assert response.status_code == 422
    auth_service.login.assert_not_called()


@pytest.mark.parametrize("path", ["/auth/token/refresh", "/auth/token/refresh/"])
def test_refresh_endpoint_passes_the_refresh_token(
    client: TestClient, auth_service: MagicMock, path: str
) -> None:
    auth_service.refresh.return_value = TokenResponse(access="a", refresh="r")

    response = client.post(path, json={"refresh": "old-refresh"})

    assert response.status_code == 200
    auth_service.refresh.assert_called_once_with("old-refresh")


def test_refresh_rejects_empty_token(
    client: TestClient, auth_service: MagicMock
) -> None:
    response = client.post("/auth/token/refresh", json={"refresh": ""})

    assert response.status_code == 422
    auth_service.refresh.assert_not_called()
