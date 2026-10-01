"""FastAPI adapter for core_data: exposes `wiring.py` builders as request-session
dependencies (ADR-0002)."""

from app.core.dependencies import provide
from app.modules.core_data.wiring import build_user_service

get_user_service = provide(build_user_service)
