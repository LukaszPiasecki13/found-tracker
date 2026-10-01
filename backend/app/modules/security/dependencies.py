"""FastAPI adapter for security: exposes `wiring.py` builders as request-session
dependencies (ADR-0002) plus the HTTP-only `get_current_user`."""

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.core.dependencies import provide
from app.modules.core_data.dependencies import get_user_service
from app.modules.core_data.models.user import User
from app.modules.core_data.services.users import UserService
from app.modules.security.constants import TOKEN_TYPE_ACCESS
from app.modules.security.errors import (
    AdminRequiredError,
    InactiveUserError,
    InvalidAccessTokenError,
    MissingCredentialsError,
)
from app.modules.security.services.token import TokenService, parse_user_id
from app.modules.security.wiring import build_auth_service, build_token_service

# `auto_error=False`: a missing header is reported by `get_current_user` with our
# own error contract (`code`), not by FastAPI's bare 403/401.
bearer_scheme = HTTPBearer(auto_error=False)


def get_token_service() -> TokenService:
    """No session - kept as a plain function (not `provide`) because
    `build_token_service` needs none."""
    return build_token_service()


get_auth_service = provide(build_auth_service)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    users: UserService = Depends(get_user_service),
    token_service: TokenService = Depends(get_token_service),
) -> User:
    """Resolve the authenticated, active user from the `Authorization` header."""
    if credentials is None:
        raise MissingCredentialsError

    payload = token_service.decode_token(credentials.credentials)
    if not payload or payload.get("type") != TOKEN_TYPE_ACCESS:
        raise InvalidAccessTokenError

    user_id = parse_user_id(payload)
    if user_id is None:
        raise InvalidAccessTokenError

    user = users.find_by_id(user_id)
    if user is None or not user.is_active:
        raise InactiveUserError
    return user


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    """The authenticated user, who must be listed in `ADMIN_EMAILS`."""
    admins = {email.strip().lower() for email in get_settings().admin_emails}
    if user.email.strip().lower() not in admins:
        raise AdminRequiredError
    return user
