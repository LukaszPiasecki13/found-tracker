"""Constants of the `security` module."""

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"

# bcrypt ignores (and bcrypt>=5 rejects) anything past 72 bytes of input.
MAX_PASSWORD_BYTES = 72
