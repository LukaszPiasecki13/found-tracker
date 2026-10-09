"""FastAPI adapter for assets: exposes `wiring.py` builders as request-session
dependencies (ADR-0002)."""

from app.core.dependencies import provide
from app.core.market_data import BondDataProvider
from app.modules.assets import wiring as assets_wiring
from app.modules.assets.wiring import (
    build_asset_class_service,
    build_asset_service,
    build_bond_data_service,
    build_bond_pricing_service,
    build_currency_service,
    build_daily_refresh_service,
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
get_daily_refresh_service = provide(build_daily_refresh_service)
get_bond_data_service = provide(build_bond_data_service)
get_bond_pricing_service = provide(build_bond_pricing_service)


def get_bond_data_provider() -> BondDataProvider:
    """No session needed: the provider only talks to the external feed.

    Calls through the `wiring` module reference (not a bare name import), so
    tests can `monkeypatch.setattr(assets_wiring, "build_bond_data_provider",
    ...)` the same way they replace the market-data provider."""
    return assets_wiring.build_bond_data_provider()
