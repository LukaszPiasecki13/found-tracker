from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import register_error_handlers
from app.core.rate_limit import register_rate_limiting
from app.modules.security.api.auth import router
from app.modules.security.constants import LOGIN_RATE_LIMIT
from app.modules.security.dependencies import get_auth_service
from app.modules.security.errors import InvalidCredentialsError


def _client() -> TestClient:
    app = FastAPI()
    register_error_handlers(app)
    register_rate_limiting(app)
    app.include_router(router)
    service = MagicMock()
    service.login.side_effect = InvalidCredentialsError
    app.dependency_overrides[get_auth_service] = lambda: service
    return TestClient(app)


def test_login_is_rate_limited_with_error_contract() -> None:
    client = _client()
    attempts = int(LOGIN_RATE_LIMIT.split("/")[0])
    body = {"email": "user@example.com", "password": "wrong-password"}

    for _ in range(attempts):
        assert client.post("/auth/login", json=body).status_code == 401

    response = client.post("/auth/login", json=body)

    assert response.status_code == 429
    assert response.json() == {
        "detail": "Too many requests",
        "code": "RATE_LIMIT_EXCEEDED",
    }
