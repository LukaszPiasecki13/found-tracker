from fastapi import APIRouter, Depends

from .dependencies import get_auth_service, get_current_user
from .models import User
from .schemas import (
    LoginRequest,
    Token,
    TokenRefresh,
    UserCreate,
    UserRead,
)
from .service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=201)
def register(data: UserCreate, svc: AuthService = Depends(get_auth_service)):
    return svc.register(data)


@router.post("/login", response_model=Token)
def login(data: LoginRequest, svc: AuthService = Depends(get_auth_service)):
    return svc.login(data)


@router.post("/token/refresh", response_model=Token)
def refresh_token(body: TokenRefresh, svc: AuthService = Depends(get_auth_service)):
    return svc.refresh(body.refresh)


@router.get("/me", response_model=UserRead)
def current_user(user: User = Depends(get_current_user)):
    return user
