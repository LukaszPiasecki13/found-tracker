from fastapi import Depends

from app.core.config import get_settings
from app.modules.core_data.dependencies import get_user_repo
from app.modules.core_data.repository import UserRepository

from .services.auth import AuthService
from .services.token import TokenService


def get_token_service() -> TokenService:
    settings = get_settings()
    return TokenService(
        secret_key=settings.secret_key,
        algorithm=settings.algorithm,
        access_token_expire_minutes=settings.access_token_expire_minutes,
    )


def get_auth_service(
    repo: UserRepository = Depends(get_user_repo),
    token_service: TokenService = Depends(get_token_service),
) -> AuthService:
    return AuthService(repo, token_service)
