import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.dependencies import dispose_sql_engines
from app.core.errors import register_error_handlers
from app.core.health import router as health_router
from app.core.logging import configure_logging
from app.core.rate_limit import register_rate_limiting
from app.modules.assets.api import router as assets_router
from app.modules.core_data.api import users_router as core_data_router
from app.modules.portfolios.api import router as portfolios_router
from app.modules.security.api import auth_router

settings = get_settings()
configure_logging(level=settings.log_level, json_output=settings.log_json)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None]:
    # Tables are managed by Alembic migrations.
    try:
        yield
    finally:
        dispose_sql_engines()
        logger.info("Shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins or ["*"],
    allow_credentials=bool(settings.cors_origins),
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)
register_rate_limiting(app)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(core_data_router)
app.include_router(assets_router)
app.include_router(portfolios_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok"}
