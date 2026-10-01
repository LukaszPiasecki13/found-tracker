"""FastAPI adapter for portfolios: exposes `wiring.py` builders as request-session
dependencies (ADR-0002)."""

from app.core.dependencies import provide
from app.modules.portfolios.wiring import (
    build_metrics_service,
    build_operation_service,
    build_portfolio_service,
    build_position_service,
)

get_portfolio_service = provide(build_portfolio_service)
get_position_service = provide(build_position_service)
get_operation_service = provide(build_operation_service)
get_metrics_service = provide(build_metrics_service)
