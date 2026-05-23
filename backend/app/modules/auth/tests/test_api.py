from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.auth.api import router
from app.modules.auth.dependencies import get_auth_service, get_current_user


def build_client(
    auth_service: MagicMock,
    current_user: object | None = None,
) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    if current_user is not None:
        app.dependency_overrides[get_current_user] = lambda: current_user
    return TestClient(app)


def test_login_endpoint_uses_email_password_payload() -> None:
    auth_service = MagicMock()
    auth_service.login.return_value = SimpleNamespace(
        access="access-token",
        refresh="refresh-token",
    )
    client = build_client(auth_service)

    response = client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "StrongPass123"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "access": "access-token",
        "refresh": "refresh-token",
    }
    auth_service.login.assert_called_once()
    assert auth_service.login.call_args.args[0].email == "user@example.com"


def test_me_endpoint_returns_current_user() -> None:
    auth_service = MagicMock()
    current_user = SimpleNamespace(
        id=1,
        email="user@example.com",
        first_name="Jan",
        last_name="Kowalski",
        is_active=True,
        date_joined=None,
    )
    client = build_client(auth_service, current_user=current_user)

    response = client.get("/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"
