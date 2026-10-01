from fastapi import APIRouter, Depends

from app.modules.core_data.dependencies import get_user_service
from app.modules.core_data.models.user import User
from app.modules.core_data.schemas.users import UserCreateRequest, UserResponse
from app.modules.core_data.services.users import UserService
from app.modules.security.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
@router.post("/register/", response_model=UserResponse, status_code=201)
def register(
    data: UserCreateRequest,
    service: UserService = Depends(get_user_service),
):
    return service.register(data)


@router.get("/me", response_model=UserResponse)
@router.get("/users/me/", response_model=UserResponse)
def current_user(user: User = Depends(get_current_user)):
    return user
