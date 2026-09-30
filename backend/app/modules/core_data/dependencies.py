"""FastAPI adapter for core_data: exposes `wiring.py` builders as request-session
dependencies (ADR-0002) plus the HTTP-only `get_current_user`."""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.dependencies import provide
from app.modules.core_data.models.user import User
from app.modules.core_data.services.users import UserService
from app.modules.core_data.wiring import build_user_service

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

get_user_service = provide(build_user_service)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    service: UserService = Depends(get_user_service),
) -> User:
    # Import provider at runtime to avoid circular import during module import
    from app.modules.security.dependencies import get_token_service

    token_service = get_token_service()
    payload = token_service.decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )
    user = service.find_by_id(int(user_id))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    return user
