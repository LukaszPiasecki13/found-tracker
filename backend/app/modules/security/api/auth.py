"""Authentication API endpoints."""

from fastapi import APIRouter, Depends

from app.modules.security.dependencies import get_auth_service
from app.modules.security.schemas.auth import (
    LoginRequest,
    TokenRefreshRequest,
    TokenResponse,
)
from app.modules.security.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
@router.post("/token", response_model=TokenResponse)
def login(data: LoginRequest, svc: AuthService = Depends(get_auth_service)):
    return svc.login(data)


@router.post("/token/refresh", response_model=TokenResponse)
@router.post("/token/refresh/", response_model=TokenResponse)
def refresh_token(
    body: TokenRefreshRequest, svc: AuthService = Depends(get_auth_service)
):
    return svc.refresh(body.refresh)
