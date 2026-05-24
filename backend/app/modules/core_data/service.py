from fastapi import HTTPException

from app.modules.security.services.password import hash_password

from .models import User
from .repository import UserRepository
from .schemas import UserCreate


class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    @staticmethod
    def _normalize_email(email: str) -> str:
        return email.strip().lower()

    def register(self, data: UserCreate) -> User:
        email = self._normalize_email(data.email)
        if self.repo.get_by_email(email):
            raise HTTPException(status_code=400, detail="Email already registered")

        user = User(
            email=email,
            password_hash=hash_password(data.password),
        )
        return self.repo.create(user)
