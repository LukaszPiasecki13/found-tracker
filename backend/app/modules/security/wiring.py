"""Composition root for security (ADR-0002): the only place that assembles
its services. No FastAPI, no `dependencies.py`, no commit.

`core_data`'s wiring is imported as a module, as every module's wiring reaches
another's (see `01_backend-architecture.md` §2.4).
"""

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.core_data import wiring as core_data_wiring
from app.modules.security.services.auth import AuthService
from app.modules.security.services.token import TokenService


def build_token_service() -> TokenService:
    settings = get_settings()
    return TokenService(
        secret_key=settings.secret_key,
        algorithm=settings.algorithm,
        access_token_expire_minutes=settings.access_token_expire_minutes,
        refresh_token_expire_days=settings.refresh_token_expire_days,
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
    )


def build_auth_service(session: Session) -> AuthService:
    return AuthService(
        core_data_wiring.build_user_service(session), build_token_service()
    )
