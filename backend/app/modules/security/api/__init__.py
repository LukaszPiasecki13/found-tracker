"""Security API endpoints."""

from app.modules.security.api.auth import router as auth_router

__all__ = ["auth_router"]
