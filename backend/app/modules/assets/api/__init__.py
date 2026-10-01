"""Assets API endpoints.

`router` bundles the module's three routers for `main.py`; the static-prefix
routers go first, although `{asset_id:int}` would not capture them anyway.
"""

from fastapi import APIRouter

from app.modules.assets.api.asset_classes import router as asset_classes_router
from app.modules.assets.api.assets import router as assets_router
from app.modules.assets.api.currencies import router as currencies_router

router = APIRouter()
router.include_router(asset_classes_router)
router.include_router(currencies_router)
router.include_router(assets_router)

__all__ = ["asset_classes_router", "assets_router", "currencies_router", "router"]
