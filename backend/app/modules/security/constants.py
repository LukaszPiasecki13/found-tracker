"""Constants of the `security` module."""

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"

# Per client IP (see `core/rate_limit.py`).
LOGIN_RATE_LIMIT = "5/minute"
REFRESH_RATE_LIMIT = "10/minute"
