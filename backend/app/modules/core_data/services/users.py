"""User management service."""

from app.core.errors import ConflictError
from app.modules.core_data.models.user import User
from app.modules.core_data.repositories.users import UserRepository
from app.modules.core_data.schemas.users import UserCreateRequest
from app.modules.security.services.password import hash_password


class UserService:
    """Service for user account operations."""

    def __init__(self, repository: UserRepository) -> None:
        self._repo = repository

    @staticmethod
    def _normalize_email(email: str) -> str:
        return email.strip().lower()

    def register(self, data: UserCreateRequest) -> User:
        """Create an account; the e-mail must be unique."""
        email = self._normalize_email(data.email)
        with self._repo.transaction():
            if self._repo.find_by_email(email):
                raise ConflictError(
                    "Email already registered", code="EMAIL_ALREADY_REGISTERED"
                )
            return self._repo.create(
                email=email, password_hash=hash_password(data.password)
            )

    def find_by_id(self, user_id: int) -> User | None:
        """Look up a user by ID, returning None instead of raising."""
        return self._repo.find_by_id(user_id)

    def find_by_email(self, email: str) -> User | None:
        """Look up a user by e-mail (normalized the same way as on register)."""
        return self._repo.find_by_email(self._normalize_email(email))
