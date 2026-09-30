"""Core data API endpoints."""

from app.modules.core_data.api.users import router as users_router

__all__ = ["users_router"]
