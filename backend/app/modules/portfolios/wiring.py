"""Composition root for portfolios (ADR-0002): the only place that assembles its
services - and the domain components they talk to (ADR-0005, DOM-10). No
FastAPI, no `dependencies.py`, no commit.

Services of `assets` come from its own builders, called through the module
import (`assets_wiring.build_x`) so a cycle between `wiring.py` files stays
harmless.
"""

from sqlalchemy.orm import Session

from app.core.import_parser import ImportParser
from app.infrastructure.import_parsers import XtbParser
from app.modules.assets import wiring as assets_wiring
from app.modules.portfolios.domain import PortfolioLedger, PortfolioValuator
from app.modules.portfolios.repositories.imports import ImportRepository
from app.modules.portfolios.repositories.operations import OperationRepository
from app.modules.portfolios.repositories.portfolios import PortfolioRepository
from app.modules.portfolios.repositories.positions import PositionRepository
from app.modules.portfolios.services.fx import FxMapBuilder, FxRateService
from app.modules.portfolios.services.imports import ImportService
from app.modules.portfolios.services.metrics import MetricsService
from app.modules.portfolios.services.operations import OperationService
from app.modules.portfolios.services.portfolios import PortfolioService
from app.modules.portfolios.services.positions import PositionService


def build_portfolio_valuator() -> PortfolioValuator:
    return PortfolioValuator()


def build_portfolio_ledger() -> PortfolioLedger:
    return PortfolioLedger()


def build_fx_map_builder(session: Session) -> FxMapBuilder:
    return FxMapBuilder(assets_wiring.build_currency_service(session))


def build_fx_rate_service(session: Session) -> FxRateService:
    return FxRateService(
        assets_wiring.build_currency_service(session), build_fx_map_builder(session)
    )


def build_portfolio_service(session: Session) -> PortfolioService:
    return PortfolioService(
        PortfolioRepository(session),
        assets_wiring.build_currency_service(session),
        build_portfolio_valuator(),
        build_fx_map_builder(session),
    )


def build_position_service(session: Session) -> PositionService:
    return PositionService(
        build_portfolio_service(session),
        PositionRepository(session),
        assets_wiring.build_market_data_service(session),
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
    return (XtbParser(),)


def build_import_service(session: Session) -> ImportService:
    return ImportService(
        ImportRepository(session),
        build_operation_service(session),
        assets_wiring.build_asset_service(session),
        build_portfolio_service(session),
        build_import_parsers(),
    )


def build_metrics_service(session: Session) -> MetricsService:
    """Price history through `MarketDataService` (it satisfies the
    `PriceHistoryProvider` port structurally)."""
    return MetricsService(
        OperationRepository(session),
        assets_wiring.build_market_data_service(session),
    )
