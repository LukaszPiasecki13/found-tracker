"""FastAPI adapter for assets: exposes `wiring.py` builders as request-session
dependencies (ADR-0002)."""

from app.core.dependencies import provide
from app.modules.assets.wiring import (
    build_asset_class_service,
    build_asset_service,
    build_currency_service,
    build_fx_rate_service,
    build_market_data_service,
    build_price_service,
)

get_asset_class_service = provide(build_asset_class_service)
get_currency_service = provide(build_currency_service)
get_asset_service = provide(build_asset_service)
get_market_data_service = provide(build_market_data_service)
get_price_service = provide(build_price_service)
get_fx_rate_service = provide(build_fx_rate_service)
