"""FastAPI adapter for portfolios: exposes `wiring.py` builders as request-session
dependencies (ADR-0002)."""

from app.core.dependencies import provide
from app.modules.portfolios.wiring import (
    build_account_metrics_service,
    build_currency_split_service,
    build_fx_rate_service,
    build_import_service,
    build_metrics_service,
    build_operation_service,
    build_portfolio_service,
    build_position_service,
)

get_portfolio_service = provide(build_portfolio_service)
get_position_service = provide(build_position_service)
get_operation_service = provide(build_operation_service)
get_metrics_service = provide(build_metrics_service)
get_account_metrics_service = provide(build_account_metrics_service)
get_currency_split_service = provide(build_currency_split_service)
get_fx_rate_service = provide(build_fx_rate_service)
get_import_service = provide(build_import_service)
