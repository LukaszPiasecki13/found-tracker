import base64
import hashlib
import hmac

import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_bcrypt(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _verify_pbkdf2_sha256(plain: str, encoded: str) -> bool:
    """Verify pbkdf2_sha256$<iterations>$<salt>$<hash> format."""
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
        return _verify_pbkdf2_sha256(plain, hashed)
    return _verify_bcrypt(plain, hashed)
