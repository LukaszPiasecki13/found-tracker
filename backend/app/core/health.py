"""Health check endpoint used by deployment platforms."""

import logging

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import get_settings
from app.core.dependencies import get_sql_engine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", summary="Health check")
def health() -> JSONResponse:
    """Return OK only when the process is running and the database answers."""
    settings = get_settings()
    try:
        with get_sql_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health check failed")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unavailable", "database": "down"},
        )
    return JSONResponse(
        content={
            "status": "ok",
            "app": settings.app_name,
            "environment": settings.environment,
            "database": "up",
        }
    )
