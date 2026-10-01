import base64
import hashlib

import pytest

from app.core.errors import ValidationException
from app.modules.security.services.password import (
    burn_password_verification,
    hash_password,
    validate_password_length,
    verify_password,
)


def _pbkdf2(plain: str, salt: str, iterations: int) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt.encode(), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${base64.b64encode(digest).decode()}"


def test_hash_password_creates_verifiable_bcrypt_hash() -> None:
    hashed = hash_password("StrongPass123")

    assert hashed != "StrongPass123"
    assert verify_password("StrongPass123", hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_verify_password_supports_legacy_pbkdf2_hashes() -> None:
    encoded = _pbkdf2("StrongPass123", "testsalt", 1200)

    assert verify_password("StrongPass123", encoded) is True
    assert verify_password("wrong-password", encoded) is False


@pytest.mark.parametrize(
    "hashed",
    [None, "", "not-a-hash", "$2b$12$tooshort", "pbkdf2_sha256$x$y", "pbkdf2_sha256$"],
)
def test_verify_password_rejects_missing_or_malformed_hash(hashed: str | None) -> None:
    assert verify_password("StrongPass123", hashed) is False


def test_verify_password_rejects_input_bcrypt_cannot_hash() -> None:
    hashed = hash_password("StrongPass123")

    assert verify_password("x" * 100, hashed) is False


def test_validate_password_length_counts_bytes_not_characters() -> None:
    validate_password_length("a" * 72)
    with pytest.raises(ValidationException) as exc_info:
        validate_password_length("ą" * 37)  # 37 chars, 74 bytes

    assert exc_info.value.code == "PASSWORD_TOO_LONG"


def test_burn_password_verification_checks_against_a_bcrypt_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str | None]] = []

    def spy(plain: str, hashed: str | None) -> bool:
        calls.append((plain, hashed))
        return False

    monkeypatch.setattr("app.modules.security.services.password.verify_password", spy)

    burn_password_verification("anything")

    assert len(calls) == 1
    plain, hashed = calls[0]
    assert plain == "anything"
    assert hashed is not None
    assert hashed.startswith("$2")
