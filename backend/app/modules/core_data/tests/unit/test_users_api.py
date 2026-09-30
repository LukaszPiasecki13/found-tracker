from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import ConflictError, register_error_handlers
from app.modules.core_data.api.users import router
from app.modules.core_data.dependencies import get_current_user, get_user_service


def build_client(
    user_service: MagicMock,
    current_user: object | None = None,
) -> TestClient:
    app = FastAPI()
    register_error_handlers(app)
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
        json={"email": "user@example.com", "password": "StrongPass123"},
    )

    assert response.status_code == 201
    assert response.json() == {"id": 1, "email": "user@example.com", "is_active": True}
    user_service.register.assert_called_once()


def test_register_endpoint_never_exposes_password_hash() -> None:
    user_service = MagicMock()
    user_service.register.return_value = SimpleNamespace(
        id=1,
        email="user@example.com",
        is_active=True,
        password_hash="secret-hash",
    )
    client = build_client(user_service)

    response = client.post(
        "/auth/register",
        json={"email": "user@example.com", "password": "StrongPass123"},
    )

    assert "password_hash" not in response.json()


def test_register_endpoint_rejects_unknown_fields() -> None:
    client = build_client(MagicMock())

    response = client.post(
        "/auth/register",
        json={
            "email": "user@example.com",
            "password": "StrongPass123",
            "is_active": False,
        },
    )

    assert response.status_code == 422


def test_register_endpoint_maps_conflict_to_409_with_code() -> None:
    user_service = MagicMock()
    user_service.register.side_effect = ConflictError(
        "Email already registered", code="EMAIL_ALREADY_REGISTERED"
    )
    client = build_client(user_service)

    response = client.post(
        "/auth/register",
        json={"email": "user@example.com", "password": "StrongPass123"},
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Email already registered",
        "code": "EMAIL_ALREADY_REGISTERED",
    }


def test_me_endpoint_returns_current_user() -> None:
    current_user = SimpleNamespace(id=1, email="user@example.com", is_active=True)
    client = build_client(MagicMock(), current_user=current_user)

    response = client.get("/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"
