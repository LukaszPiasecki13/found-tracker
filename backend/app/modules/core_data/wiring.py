"""Composition root for core_data (ADR-0002): the only place that assembles
its services. No FastAPI, no `dependencies.py`, no commit."""

from sqlalchemy.orm import Session

from app.modules.core_data.repositories.users import UserRepository
from app.modules.core_data.services.users import UserService


def build_user_service(session: Session) -> UserService:
    return UserService(UserRepository(session))
