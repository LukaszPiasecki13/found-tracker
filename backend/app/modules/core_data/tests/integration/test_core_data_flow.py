from fastapi.testclient import TestClient

from app.conftest import IntegrationData


def test_core_data_exposes_registered_user_through_authenticated_me_endpoint(
    integration_client: TestClient,
    integration_data: IntegrationData,
) -> None:
    email = f"{integration_data.value('core')}@example.com"
    registration = integration_client.post(
        "/auth/register",
        json={"email": email, "password": "StrongPass123"},
    )
    assert registration.status_code == 201
    user = registration.json()

    login = integration_client.post(
        "/auth/login",
        json={"email": email, "password": "StrongPass123"},
    )
    assert login.status_code == 200
    token = login.json()["access"]
    response = integration_client.get(
        "/auth/users/me/",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == user


def test_core_data_rejects_missing_authentication(
    integration_client: TestClient,
) -> None:
    response = integration_client.get("/auth/me")

    assert response.status_code == 401


def test_core_data_rejects_duplicate_registration_with_conflict_code(
    integration_client: TestClient,
    integration_data: IntegrationData,
) -> None:
    payload = {
        "email": f"{integration_data.value('dup')}@example.com",
        "password": "StrongPass123",
    }
    assert integration_client.post("/auth/register", json=payload).status_code == 201

    response = integration_client.post(
        "/auth/register",
        json={**payload, "email": payload["email"].upper()},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "EMAIL_ALREADY_REGISTERED"
