"""Composition root for assets (ADR-0002): the only place that assembles its
services. No FastAPI, no `dependencies.py`, no commit.

Also the one place that picks the market-data adapter: services depend on the
`MarketDataProvider` port from `app.core.market_data`, never on `yfinance`.
Tests replace `build_market_data_provider` to stay off the network.
"""

from sqlalchemy.orm import Session

from app.core.market_data import MarketDataProvider
from app.infrastructure.market_data import YahooFinanceProvider
from app.modules.assets.repositories.asset_classes import AssetClassRepository
from app.modules.assets.repositories.assets import AssetRepository
from app.modules.assets.repositories.currencies import CurrencyRepository
from app.modules.assets.repositories.fx_rates import FxRateRepository
from app.modules.assets.repositories.prices import PriceRepository
from app.modules.assets.services.asset_classes import AssetClassService
from app.modules.assets.services.assets import AssetService
from app.modules.assets.services.currencies import CurrencyService
from app.modules.assets.services.fx_rates import FxRateService
from app.modules.assets.services.history import HistoryBackfillService
from app.modules.assets.services.market_data import MarketDataService
from app.modules.assets.services.prices import PriceService


def build_market_data_provider() -> MarketDataProvider:
    return YahooFinanceProvider()


def build_asset_class_service(session: Session) -> AssetClassService:
    return AssetClassService(AssetClassRepository(session))


def build_fx_rate_service(session: Session) -> FxRateService:
    return FxRateService(FxRateRepository(session), CurrencyRepository(session))


def build_price_service(session: Session) -> PriceService:
    return PriceService(PriceRepository(session), AssetRepository(session))


def build_currency_service(session: Session) -> CurrencyService:
    return CurrencyService(CurrencyRepository(session), build_fx_rate_service(session))


def build_market_data_service(session: Session) -> MarketDataService:
    return MarketDataService(
        AssetRepository(session),
        CurrencyRepository(session),
        build_market_data_provider(),
        build_price_service(session),
        build_fx_rate_service(session),
    )


def build_asset_service(session: Session) -> AssetService:
    return AssetService(
        AssetRepository(session),
        build_asset_class_service(session),
        build_currency_service(session),
        build_market_data_service(session),
        build_price_service(session),
    )


def build_history_backfill_service(session: Session) -> HistoryBackfillService:
    return HistoryBackfillService(
        AssetRepository(session),
        CurrencyRepository(session),
        PriceRepository(session),
        FxRateRepository(session),
    )
