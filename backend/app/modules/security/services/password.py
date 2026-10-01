import base64
import hashlib
import hmac
import secrets

import bcrypt

from app.core.errors import ValidationException
from app.modules.security.constants import MAX_PASSWORD_BYTES


def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_bcrypt(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:
        # Malformed hash or an input bcrypt refuses: never a match, never a 500.
        return False


def _verify_pbkdf2_sha256(plain: str, encoded: str) -> bool:
    """Verify pbkdf2_sha256$<iterations>$<salt>$<hash> format."""
    try:
        _, iterations_str, salt, hash_b64 = encoded.split("$", 3)
        iterations = int(iterations_str)
        dk = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt.encode(), iterations)
        expected = base64.b64encode(dk).decode()
        return hmac.compare_digest(expected, hash_b64)
    except ValueError:
        return False


def verify_password(plain: str, hashed: str | None) -> bool:
    """Verify password against hash (supports bcrypt and legacy pbkdf2)."""
    if not hashed:
        return False
    if hashed.startswith("pbkdf2_sha256$"):
        return _verify_pbkdf2_sha256(plain, hashed)
    return _verify_bcrypt(plain, hashed)


# Hash of a value no user can authenticate with, verified against when the
# account does not exist so that login costs the same either way.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(32))


def validate_password_length(password: str) -> None:
    """Raise ValidationException if password exceeds bcrypt's 72-byte limit."""
    if len(password.encode()) > MAX_PASSWORD_BYTES:
        raise ValidationException(
            f"Password exceeds {MAX_PASSWORD_BYTES} bytes when encoded as UTF-8",
            code="PASSWORD_TOO_LONG",
        )


def burn_password_verification(plain: str) -> None:
    """Spend the cost of a password check without having an account to check."""
    verify_password(plain, _DUMMY_HASH)
