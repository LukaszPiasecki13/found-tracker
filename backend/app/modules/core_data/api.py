from fastapi import APIRouter, Depends

from .dependencies import get_current_user, get_user_service
from .models import User
from .schemas import UserCreate, UserRead
from .service import UserService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=201)
def register(data: UserCreate, svc: UserService = Depends(get_user_service)):
    return svc.register(data)


@router.get("/me", response_model=UserRead)
def current_user(user: User = Depends(get_current_user)):
    return user
