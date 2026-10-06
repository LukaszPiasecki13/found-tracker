"""Composition root for portfolios (ADR-0002): the only place that assembles its
services - and the domain components they talk to (ADR-0005, DOM-10). No
FastAPI, no `dependencies.py`, no commit.

Services of `assets` come from its own builders, called through the module
import (`assets_wiring.build_x`) so a cycle between `wiring.py` files stays
harmless.
"""

from sqlalchemy.orm import Session

from app.core.import_parser import ImportParser
from app.infrastructure.import_parsers import BosParser, XtbParser
from app.modules.assets import wiring as assets_wiring
from app.modules.portfolios.domain import (
    DailySnapshotBuilder,
    PortfolioLedger,
    PortfolioValuator,
)
from app.modules.portfolios.repositories.daily import DailyRepository
from app.modules.portfolios.repositories.imports import ImportRepository
from app.modules.portfolios.repositories.operations import OperationRepository
from app.modules.portfolios.repositories.portfolios import PortfolioRepository
from app.modules.portfolios.repositories.positions import PositionRepository
from app.modules.portfolios.services.account_metrics import AccountMetricsService
from app.modules.portfolios.services.fx import FxMapBuilder, FxRateService
from app.modules.portfolios.services.imports import ImportService
from app.modules.portfolios.services.metrics import MetricsService
from app.modules.portfolios.services.operations import OperationService
from app.modules.portfolios.services.portfolios import PortfolioService
from app.modules.portfolios.services.positions import PositionService
from app.modules.portfolios.services.snapshots import SnapshotService


def build_portfolio_valuator() -> PortfolioValuator:
    return PortfolioValuator()


def build_portfolio_ledger() -> PortfolioLedger:
    return PortfolioLedger()


def build_daily_snapshot_builder() -> DailySnapshotBuilder:
    return DailySnapshotBuilder(build_portfolio_ledger())


def build_fx_map_builder(session: Session) -> FxMapBuilder:
    return FxMapBuilder(assets_wiring.build_currency_service(session))


def build_fx_rate_service(session: Session) -> FxRateService:
    return FxRateService(
        assets_wiring.build_currency_service(session), build_fx_map_builder(session)
    )


def build_snapshot_service(session: Session) -> SnapshotService:
    return SnapshotService(
        PortfolioRepository(session),
        DailyRepository(session),
        OperationRepository(session),
        assets_wiring.build_price_service(session),
        assets_wiring.build_market_data_service(session),
        build_daily_snapshot_builder(),
    )


def build_portfolio_service(session: Session) -> PortfolioService:
    return PortfolioService(
        PortfolioRepository(session),
        assets_wiring.build_currency_service(session),
        build_portfolio_valuator(),
        build_fx_map_builder(session),
        build_snapshot_service(session),
    )


def build_position_service(session: Session) -> PositionService:
    return PositionService(
        build_portfolio_service(session),
        PositionRepository(session),
        build_portfolio_valuator(),
        build_fx_map_builder(session),
    )


def build_operation_service(session: Session) -> OperationService:
    return OperationService(
        PortfolioRepository(session),
        PositionRepository(session),
        OperationRepository(session),
        assets_wiring.build_asset_service(session),
        build_portfolio_ledger(),
    )


def build_import_parsers() -> tuple[ImportParser, ...]:
    """The registry of import sources: a new bank is a new adapter listed here
    (`ImportService` picks the first parser whose `sniff` accepts the file)."""
    return (XtbParser(), BosParser())


def build_import_service(session: Session) -> ImportService:
    return ImportService(
        ImportRepository(session),
        build_operation_service(session),
        assets_wiring.build_asset_service(session),
        build_portfolio_service(session),
        build_import_parsers(),
    )


def build_metrics_service(session: Session) -> MetricsService:
    """Stored prices and rates (DEC-01) through the `assets` services; the provider
    only through `MarketDataService`, for a backfill or a stale current value (DEC-03,
    DEC-14)."""
    return MetricsService(
        OperationRepository(session),
        assets_wiring.build_market_data_service(session),
        assets_wiring.build_price_service(session),
        assets_wiring.build_fx_rate_service(session),
    )


def build_account_metrics_service(session: Session) -> AccountMetricsService:
    """The account's vectors: the portfolios' own calculation, summed in the user's
    currency (DEC-01, DEC-05); the same stored prices and rates as `MetricsService`."""
    return AccountMetricsService(
        OperationRepository(session),
        assets_wiring.build_currency_service(session),
        assets_wiring.build_market_data_service(session),
        assets_wiring.build_price_service(session),
        assets_wiring.build_fx_rate_service(session),
    )
