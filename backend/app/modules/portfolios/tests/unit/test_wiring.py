from unittest.mock import MagicMock

from app.modules.assets.services import (
    AssetService,
    CurrencyService,
    FxRateService,
    MarketDataService,
    PriceService,
)
from app.modules.portfolios import wiring
from app.modules.portfolios.domain import (
    DailySnapshotBuilder,
    PortfolioLedger,
    PortfolioValuator,
)
from app.modules.portfolios.services import (
    FxMapBuilder,
    MetricsService,
    OperationService,
    PortfolioService,
    PositionService,
)
from app.modules.portfolios.services.imports import ImportService
from app.modules.portfolios.services.snapshots import SnapshotService


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
    assert operations._portfolio_repo.session is session
    assert operations._position_repo.session is session
    assert operations._operation_repo.session is session
    assert isinstance(operations._assets, AssetService)
    assert operations._assets._repo.session is session
    assert metrics._operation_repo.session is session
    assert isinstance(metrics._market_data, MarketDataService)
    assert isinstance(metrics._prices, PriceService)
    assert isinstance(metrics._fx_rates, FxRateService)


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
    assert [parser.parser_id for parser in imports._parsers] == ["xtb", "bos"]
    assert [p.parser_id for p in wiring.build_import_parsers()] == ["xtb", "bos"]


def test_the_return_is_computed_by_a_snapshot_service_on_the_request_session() -> None:
    session = MagicMock()

    snapshots = wiring.build_portfolio_service(session)._snapshots

    assert isinstance(snapshots, SnapshotService)
    assert snapshots._portfolios.session is session
    assert snapshots._daily.session is session
    assert snapshots._operations.session is session
    assert isinstance(snapshots._prices, PriceService)
    assert isinstance(snapshots._market_data, MarketDataService)
    assert isinstance(snapshots._builder, DailySnapshotBuilder)
    assert isinstance(snapshots._builder._ledger, PortfolioLedger)
