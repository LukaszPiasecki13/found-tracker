from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.core_data.api import router
from app.modules.core_data.dependencies import get_current_user, get_user_service


def build_client(
    user_service: MagicMock,
    current_user: object | None = None,
) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_user_service] = lambda: user_service
    if current_user is not None:
        app.dependency_overrides[get_current_user] = lambda: current_user
    return TestClient(app)


def test_register_endpoint_uses_email_password_payload() -> None:
    user_service = MagicMock()
    user_service.register.return_value = SimpleNamespace(
        id=1,
        email="user@example.com",
        is_active=True,
    )
    client = build_client(user_service)

    response = client.post(
        "/auth/register",
        json={
            "email": "user@example.com",
            "password": "StrongPass123",
        },
    )

    assert response.status_code == 201
    assert response.json()["email"] == "user@example.com"
    user_service.register.assert_called_once()


def test_me_endpoint_returns_current_user() -> None:
    user_service = MagicMock()
    current_user = SimpleNamespace(
        id=1,
        email="user@example.com",
        is_active=True,
    )
    client = build_client(user_service, current_user=current_user)

    response = client.get("/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"
