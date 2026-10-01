"""Authentication API endpoints."""

from fastapi import APIRouter, Depends, Request

from app.core.rate_limit import limiter
from app.modules.security.constants import LOGIN_RATE_LIMIT, REFRESH_RATE_LIMIT
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
@limiter.limit(LOGIN_RATE_LIMIT)
def login(
    request: Request, data: LoginRequest, svc: AuthService = Depends(get_auth_service)
):
    return svc.login(data)


@router.post("/token/refresh", response_model=TokenResponse)
@router.post("/token/refresh/", response_model=TokenResponse)
@limiter.limit(REFRESH_RATE_LIMIT)
def refresh_token(
    request: Request,
    body: TokenRefreshRequest,
    svc: AuthService = Depends(get_auth_service),
):
    return svc.refresh(body.refresh)
