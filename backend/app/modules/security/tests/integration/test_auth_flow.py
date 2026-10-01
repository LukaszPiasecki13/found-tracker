from fastapi.testclient import TestClient

from app.conftest import IntegrationData


def test_auth_tokens_and_current_user_round_trip(
    integration_client: TestClient,
    integration_data: IntegrationData,
) -> None:
    email = f"{integration_data.value('auth')}@example.com"
    password = "StrongPass123"

    registration = integration_client.post(
        "/auth/register",
        json={"email": email.upper(), "password": password},
    )
    assert registration.status_code == 201
    assert registration.json()["email"] == email.lower()

    login = integration_client.post(
        "/auth/token",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    tokens = login.json()
    assert tokens["access"]
    assert tokens["refresh"]

    current_user = integration_client.get(
        "/auth/me", headers={"Authorization": f"Bearer {tokens['access']}"}
    )
    assert current_user.status_code == 200
    assert current_user.json()["email"] == email.lower()

    refreshed = integration_client.post(
        "/auth/token/refresh",
        json={"refresh": tokens["refresh"]},
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["access"]


def test_auth_rejects_duplicate_email_case_insensitively(
    integration_client: TestClient,
    integration_data: IntegrationData,
) -> None:
    email = f"{integration_data.value('duplicate')}@example.com"
    payload = {"email": email, "password": "StrongPass123"}

    first = integration_client.post("/auth/register", json=payload)
    second = integration_client.post(
        "/auth/register",
        json={**payload, "email": email.upper()},
    )

    assert first.status_code == 201
    assert second.status_code == 409


def test_login_failure_returns_code_and_does_not_reveal_account_existence(
    integration_client: TestClient,
    integration_data: IntegrationData,
) -> None:
    email = f"{integration_data.value('wrongpw')}@example.com"
    integration_client.post(
        "/auth/register", json={"email": email, "password": "StrongPass123"}
    )

    wrong_password = integration_client.post(
        "/auth/login", json={"email": email, "password": "WrongPass123"}
    )
    unknown_user = integration_client.post(
        "/auth/login",
        json={"email": f"nobody_{email}", "password": "WrongPass123"},
    )

    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json()
    assert wrong_password.json()["code"] == "INVALID_CREDENTIALS"


def test_protected_endpoint_requires_a_valid_access_token(
    integration_client: TestClient,
    integration_data: IntegrationData,
) -> None:
    email = f"{integration_data.value('tokens')}@example.com"
    integration_client.post(
        "/auth/register", json={"email": email, "password": "StrongPass123"}
    )
    tokens = integration_client.post(
        "/auth/login", json={"email": email, "password": "StrongPass123"}
    ).json()

    missing = integration_client.get("/auth/me")
    refresh_as_access = integration_client.get(
        "/auth/me", headers={"Authorization": f"Bearer {tokens['refresh']}"}
    )
    access_as_refresh = integration_client.post(
        "/auth/token/refresh", json={"refresh": tokens["access"]}
    )

    assert missing.status_code == 401
    assert missing.json()["code"] == "MISSING_CREDENTIALS"
    assert missing.headers["www-authenticate"] == "Bearer"
    assert refresh_as_access.status_code == 401
    assert refresh_as_access.json()["code"] == "INVALID_ACCESS_TOKEN"
    assert access_as_refresh.status_code == 401
    assert access_as_refresh.json()["code"] == "INVALID_REFRESH_TOKEN"


def test_register_rejects_password_longer_than_bcrypt_limit(
    integration_client: TestClient,
    integration_data: IntegrationData,
) -> None:
    response = integration_client.post(
        "/auth/register",
        json={
            "email": f"{integration_data.value('longpw')}@example.com",
            "password": "a" * 73,
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "PASSWORD_TOO_LONG"
