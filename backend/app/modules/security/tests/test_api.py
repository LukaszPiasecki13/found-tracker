from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.security.api import router
from app.modules.security.dependencies import get_auth_service


def build_client(
    auth_service: MagicMock,
) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_auth_service] = lambda: auth_service
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
