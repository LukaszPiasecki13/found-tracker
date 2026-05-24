from fastapi import HTTPException, status

from app.modules.core_data.models import User
from app.modules.core_data.repository import UserRepository
from app.modules.security.schemas import LoginRequest, Token
from app.modules.security.services.password import verify_password

from .token import TokenService


class AuthService:
    def __init__(self, repo: UserRepository, token_service: TokenService):
        self.repo = repo
        self.token_service = token_service

    def _issue_tokens(self, user: User) -> Token:
        sub = {"sub": str(user.id)}
        access = self.token_service.create_access_token(sub)
        refresh = self.token_service.create_refresh_token(sub)
        return Token(access=access, refresh=refresh)

    def login(self, data: LoginRequest) -> Token:
        user = self.repo.get_by_email(data.email.strip().lower())
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
        payload = self.token_service.decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        user_id = payload.get("sub")
        if not isinstance(user_id, str):
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        user = self.repo.get_by_id(int(user_id))
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found")
        return self._issue_tokens(user)
