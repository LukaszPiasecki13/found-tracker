from fastapi import APIRouter, Depends

from .dependencies import get_auth_service
from .schemas import (
    LoginRequest,
    Token,
    TokenRefresh,
)
from .services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(data: LoginRequest, svc: AuthService = Depends(get_auth_service)):
    return svc.login(data)


@router.post("/token/refresh", response_model=Token)
def refresh_token(body: TokenRefresh, svc: AuthService = Depends(get_auth_service)):
    return svc.refresh(body.refresh)
