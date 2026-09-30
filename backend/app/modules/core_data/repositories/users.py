"""User repository for data access."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.infrastructure.sql.repository import SQLRepository
from app.modules.core_data.models.user import User


class UserRepository(SQLRepository):
    """Repository for User model database operations."""

    def __init__(self, session: Session):
        super().__init__(session)

    def find_by_id(self, user_id: int) -> User | None:
        """Find user by ID. Returns None if not found."""
        stmt = select(User).where(User.id == user_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_by_id(self, user_id: int) -> User:
        """Get user by ID or raise NotFoundError."""
        user = self.find_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found", code="USER_NOT_FOUND")
        return user

    def find_by_email(self, email: str) -> User | None:
        """Find user by (already normalized) email."""
        stmt = select(User).where(User.email == email)
        return self.session.execute(stmt).scalar_one_or_none()

    def create(self, email: str, password_hash: str, is_active: bool = True) -> User:
        """Create new user."""
        user = User(email=email, password_hash=password_hash, is_active=is_active)
        self.session.add(user)
        self.flush()
        return user
