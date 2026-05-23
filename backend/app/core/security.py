import base64
import hashlib
import hmac
from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt

from .config import get_settings

settings = get_settings()


# --- Password hashing (bcrypt for new users) ---


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_bcrypt(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _verify_django_pbkdf2(plain: str, encoded: str) -> bool:
    """Verify Django's pbkdf2_sha256$<iterations>$<salt>$<hash> format."""
    try:
        _, iterations_str, salt, hash_b64 = encoded.split("$", 3)
        iterations = int(iterations_str)
        dk = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt.encode(), iterations)
        expected = base64.b64encode(dk).decode()
        return hmac.compare_digest(expected, hash_b64)
    except Exception:
        return False


def verify_password(plain: str, hashed: str) -> bool:
    if hashed.startswith("pbkdf2_sha256$"):
        return _verify_django_pbkdf2(plain, hashed)
    return _verify_bcrypt(plain, hashed)


# --- JWT tokens ---


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(days=1)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None
