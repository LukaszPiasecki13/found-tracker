from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt

from app.modules.security.services.token import TokenService, parse_user_id


def test_token_service_validates_claims_and_token_type() -> None:
    service = TokenService("test-secret", access_token_expire_minutes=5)

    access = service.create_access_token({"sub": "42"})
    refresh = service.create_refresh_token({"sub": "42"})

    access_payload = service.decode_token(access)
    refresh_payload = service.decode_token(refresh)

    assert access_payload is not None
    assert access_payload["type"] == "access"
    assert access_payload["iss"] == "found-tracker"
    assert access_payload["aud"] == "found-tracker-client"
    assert refresh_payload is not None
    assert refresh_payload["type"] == "refresh"


def test_token_service_rejects_wrong_audience() -> None:
    service = TokenService("test-secret", audience="expected-client")
    token = TokenService("test-secret", audience="other-client").create_access_token(
        {"sub": "42"}, expires_delta=timedelta(minutes=5)
    )

    assert service.decode_token(token) is None


def test_token_service_rejects_wrong_issuer() -> None:
    service = TokenService("test-secret", issuer="expected-issuer")
    token = TokenService("test-secret", issuer="other-issuer").create_access_token(
        {"sub": "42"}
    )

    assert service.decode_token(token) is None


def test_token_service_rejects_wrong_signature() -> None:
    token = TokenService("secret-a").create_access_token({"sub": "42"})

    assert TokenService("secret-b").decode_token(token) is None


def test_token_service_rejects_expired_token() -> None:
    service = TokenService("test-secret")
    token = service.create_access_token({"sub": "42"}, timedelta(seconds=-5))

    assert service.decode_token(token) is None


@pytest.mark.parametrize("missing", ["exp", "iss", "aud"])
def test_token_service_rejects_token_missing_a_required_claim(missing: str) -> None:
    claims: dict[str, object] = {
        "sub": "42",
        "type": "access",
        "exp": datetime.now(UTC) + timedelta(minutes=5),
        "iss": "found-tracker",
        "aud": "found-tracker-client",
    }
    del claims[missing]
    token = jwt.encode(claims, "test-secret", algorithm="HS256")

    assert TokenService("test-secret").decode_token(token) is None


@pytest.mark.parametrize("sub", ["42", "0", "007"])
def test_parse_user_id_accepts_plain_ascii_integers(sub: str) -> None:
    assert parse_user_id({"sub": sub}) == int(sub)


@pytest.mark.parametrize(
    "sub", [None, 42, "", " 1", "+1", "-1", "1.5", chr(0x661), "abc"]
)
def test_parse_user_id_rejects_everything_else(sub: object) -> None:
    assert parse_user_id({"sub": sub}) is None


def test_parse_user_id_rejects_missing_subject() -> None:
    assert parse_user_id({}) is None


def test_token_service_rejects_garbage() -> None:
    assert TokenService("test-secret").decode_token("not-a-jwt") is None


def test_refresh_token_lifetime_is_configurable() -> None:
    service = TokenService("test-secret", refresh_token_expire_days=7)

    payload = service.decode_token(service.create_refresh_token({"sub": "42"}))

    assert payload is not None
    remaining = payload["exp"] - datetime.now(UTC).timestamp()
    assert timedelta(days=7).total_seconds() - 60 < remaining
    assert remaining <= timedelta(days=7).total_seconds()
