from datetime import UTC, datetime
from hashlib import sha256

from fastapi import HTTPException, status

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

from .models import User
from .repository import UserRepository
from .schemas import LoginRequest, Token, UserCreate


class AuthService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    @staticmethod
    def _normalize_email(email: str) -> str:
        return email.strip().lower()

    @staticmethod
    def _build_username(email: str) -> str:
        digest = sha256(email.encode("utf-8")).hexdigest()[:16]
        return f"user_{digest}"

    def _issue_tokens(self, user: User) -> Token:
        access = create_access_token({"sub": str(user.id)})
        refresh = create_refresh_token({"sub": str(user.id)})
        return Token(access=access, refresh=refresh)

    def register(self, data: UserCreate) -> User:
        email = self._normalize_email(data.email)
        if self.repo.get_by_email(email):
            raise HTTPException(status_code=400, detail="Email already registered")

        user = User(
            username=self._build_username(email),
            email=email,
            password_hash=hash_password(data.password),
            first_name=data.first_name.strip(),
            last_name=data.last_name.strip(),
            date_joined=datetime.now(UTC),
        )
        return self.repo.create(user)

    def login(self, data: LoginRequest) -> Token:
        user = self.repo.get_by_email(self._normalize_email(data.email))
        if (
            not user
            or not user.is_active
            or not verify_password(
                data.password,
                user.password_hash,
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )
        return self._issue_tokens(user)

    def refresh(self, refresh_token: str) -> Token:
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        user_id = payload.get("sub")
        user = self.repo.get_by_id(int(user_id))
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found")
        return self._issue_tokens(user)
