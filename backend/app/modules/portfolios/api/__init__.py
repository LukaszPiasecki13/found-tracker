"""Portfolios API endpoints.

`router` bundles the module's routers for `main.py`; the static-path routers go
first, although `{portfolio_id:int}` would not capture them anyway.
"""

from fastapi import APIRouter

from app.modules.portfolios.api.metrics import router as metrics_router
from app.modules.portfolios.api.operations import router as operations_router
from app.modules.portfolios.api.portfolios import router as portfolios_router
from app.modules.portfolios.api.positions import router as positions_router

router = APIRouter()
router.include_router(positions_router)
router.include_router(operations_router)
router.include_router(metrics_router)
router.include_router(portfolios_router)

__all__ = [
    "metrics_router",
    "operations_router",
    "portfolios_router",
    "positions_router",
    "router",
]
