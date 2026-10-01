from unittest.mock import MagicMock

from app.infrastructure.market_data import YahooFinanceProvider
from app.modules.assets import wiring
from app.modules.assets.services import (
    AssetClassService,
    AssetService,
    CurrencyService,
    MarketDataService,
)


def test_builders_assemble_every_service_on_one_session() -> None:
    session = MagicMock()

    asset_service = wiring.build_asset_service(session)

    assert isinstance(asset_service, AssetService)
    assert isinstance(wiring.build_asset_class_service(session), AssetClassService)
    assert isinstance(wiring.build_currency_service(session), CurrencyService)
    assert isinstance(wiring.build_market_data_service(session), MarketDataService)
    # Every repository in the graph shares the request session (ADR-0001).
    assert asset_service._repo.session is session
    assert asset_service._asset_classes._repo.session is session
    assert asset_service._currencies._repo.session is session
    assert asset_service._market_data._asset_repo.session is session
    assert asset_service._market_data._currency_repo.session is session


def test_production_provider_is_yahoo_finance() -> None:
    assert isinstance(wiring.build_market_data_provider(), YahooFinanceProvider)
