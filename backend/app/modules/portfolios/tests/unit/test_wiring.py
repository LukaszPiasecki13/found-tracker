from unittest.mock import MagicMock

from app.modules.assets.services import AssetService, CurrencyService, MarketDataService
from app.modules.portfolios import wiring
from app.modules.portfolios.domain import PortfolioLedger, PortfolioValuator
from app.modules.portfolios.services import (
    FxMapBuilder,
    MetricsService,
    OperationService,
    PortfolioService,
    PositionService,
)
from app.modules.portfolios.services.imports import ImportService


def test_builders_assemble_every_service_on_one_session() -> None:
    session = MagicMock()

    portfolios = wiring.build_portfolio_service(session)
    positions = wiring.build_position_service(session)
    operations = wiring.build_operation_service(session)
    metrics = wiring.build_metrics_service(session)

    assert isinstance(portfolios, PortfolioService)
    assert isinstance(positions, PositionService)
    assert isinstance(operations, OperationService)
    assert isinstance(metrics, MetricsService)
    # Every repository in the graph shares the request session (ADR-0001).
    assert portfolios._repo.session is session
    assert isinstance(portfolios._currencies, CurrencyService)
    assert isinstance(portfolios._fx, FxMapBuilder)
    assert isinstance(positions._fx, FxMapBuilder)
    assert positions._repo.session is session
    assert isinstance(positions._market_data, MarketDataService)
    assert operations._portfolio_repo.session is session
    assert operations._position_repo.session is session
    assert operations._operation_repo.session is session
    assert isinstance(operations._assets, AssetService)
    assert operations._assets._repo.session is session
    assert metrics._operation_repo.session is session
    assert isinstance(metrics._prices, MarketDataService)


def test_domain_components_are_built_and_injected() -> None:
    session = MagicMock()

    assert isinstance(wiring.build_portfolio_ledger(), PortfolioLedger)
    assert isinstance(wiring.build_portfolio_valuator(), PortfolioValuator)
    assert isinstance(wiring.build_operation_service(session)._ledger, PortfolioLedger)
    assert isinstance(
        wiring.build_portfolio_service(session)._valuator, PortfolioValuator
    )


def test_import_service_is_assembled_with_the_parser_registry() -> None:
    session = MagicMock()

    imports = wiring.build_import_service(session)

    assert isinstance(imports, ImportService)
    assert imports._imports.session is session
    assert isinstance(imports._operations, OperationService)
    assert isinstance(imports._assets, AssetService)
    assert isinstance(imports._portfolios, PortfolioService)
    assert [parser.parser_id for parser in imports._parsers] == ["xtb"]
    assert [p.parser_id for p in wiring.build_import_parsers()] == ["xtb"]
