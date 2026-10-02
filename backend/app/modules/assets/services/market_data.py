"""Market data: provider search and quotes, price and FX-rate refresh.

The provider (`MarketDataProvider` port) is an external dependency: a failure to
fetch one instrument is a normal event. Refreshes are best-effort per item - a
failing ticker or currency is logged and skipped, never aborts the rest.

Refreshes write the history (`assets_price`, `assets_fx_rate`) under the day they
run, once per day and source, so repeating one is harmless; the cached
`current_price` / `exchange_rate` follow in the same transaction (ADR-0015). A
quote is taken mid-session as often as at the close, so it is stored as
synthetic; `manual` observations of the same day still outrank it.
"""

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal

from app.core.market_data import MarketDataProvider, MarketDataUnavailableError, Quote
from app.modules.assets.constants import (
    DEFAULT_CURRENCY_CODE,
    DEFAULT_QUOTE_TYPE,
    SOURCE_YAHOO,
)
from app.modules.assets.exceptions import AssetNotFoundOnProviderError
from app.modules.assets.models.assets import Asset
from app.modules.assets.models.currencies import Currency
from app.modules.assets.repositories.assets import AssetRepository
from app.modules.assets.repositories.currencies import CurrencyRepository
from app.modules.assets.services.fx_rates import FxRateService
from app.modules.assets.services.prices import PriceService

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AssetDataStatus:
    asset_id: int
    ticker: str
    price_date: date | None
    source: str | None
    stale: bool
    last_success_at: datetime | None


@dataclass(frozen=True, slots=True)
class DataStatus:
    fx_last_success_at: datetime | None
    assets: list[AssetDataStatus]


_BASE_CURRENCY_RATE = Decimal("1")


class MarketDataService:
    """Reads market data through the injected provider and writes refreshed
    prices and rates."""

    def __init__(
        self,
        asset_repo: AssetRepository,
        currency_repo: CurrencyRepository,
        provider: MarketDataProvider,
        prices: PriceService,
        fx_rates: FxRateService,
        today: Callable[[], date] = date.today,
    ) -> None:
        self._asset_repo = asset_repo
        self._currency_repo = currency_repo
        self._provider = provider
        self._prices = prices
        self._fx_rates = fx_rates
        self._today = today

    @staticmethod
    def _with_defaults(quote: Quote) -> Quote:
        return replace(
            quote,
            currency=quote.currency or DEFAULT_CURRENCY_CODE,
            quote_type=quote.quote_type or DEFAULT_QUOTE_TYPE,
        )

    def search(self, query: str) -> list[Quote]:
        """Provider instruments matching `query` (an exact ticker lookup).

        Accepts "TICKER - Name" (as typed into a picker); a hit counts only when
        it has a market price or a previous close. A provider failure is logged
        and yields no hits - search degrades, it does not fail.
        """
        ticker = query.strip().split(" - ")[0].strip().upper()
        if not ticker:
            return []
        try:
            quote = self._provider.fetch_quote(ticker)
        except MarketDataUnavailableError:
            logger.warning("Market data search failed for %s", ticker, exc_info=True)
            return []
        if quote is None or not quote.symbol:
            return []
        if not (quote.regular_market_price or quote.previous_close):
            return []
        return [self._with_defaults(quote)]

    def get_quote(self, ticker: str) -> Quote:
        """Raises AssetNotFoundOnProviderError, MarketDataUnavailableError."""
        quote = self._provider.fetch_quote(ticker)
        if quote is None:
            raise AssetNotFoundOnProviderError
        return self._with_defaults(quote)

    def current_price(self, ticker: str) -> Decimal | None:
        """Provider's current price, `None` when it has none or knows no such
        ticker. Raises MarketDataUnavailableError."""
        quote = self._provider.fetch_quote(ticker)
        return quote.price if quote is not None else None

    def close_history(self, ticker: str, start: date, end: date) -> dict[date, Decimal]:
        """Daily closes for `start <= day < end`. Raises MarketDataUnavailableError."""
        return self._provider.fetch_close_history(ticker, start, end)

    def refresh_asset_prices(self, assets: Iterable[Asset]) -> int:
        """Store today's provider price of each asset in the history (which also
        refreshes `current_price`); returns how many were stored.

        Best-effort per asset: no price or a provider failure skips that asset;
        archived assets are not refreshed. Prices are fetched before the
        transaction opens.
        """
        found: list[tuple[Asset, Decimal]] = []
        seen: set[int] = set()
        for asset in assets:
            if asset.id in seen or asset.archived_at is not None:
                continue
            seen.add(asset.id)
            price = self._fetch_price(asset.ticker)
            if price is not None and price > 0:
                found.append((asset, price))

        today = self._today()
        stored = 0
        with self._asset_repo.transaction():
            for asset, price in found:
                stored += self._prices.record_closes(
                    asset, {today: price}, source=SOURCE_YAHOO, is_synthetic=True
                )
            self._asset_repo.flush()
        return stored

    def refresh_currency_rates(self, base_code: str = DEFAULT_CURRENCY_CODE) -> int:
        """Store today's rate of every currency to `base_code` in the history and
        set its cached `exchange_rate` (units of `base_code` per one unit; the base
        itself gets 1); returns how many currencies were updated.

        Best-effort per currency: no rate or a provider failure skips it.
        """
        base_code = base_code.strip().upper()
        currencies = self._currency_repo.list_all()
        base = next((c for c in currencies if c.code == base_code), None)
        rates: list[tuple[Currency, Decimal]] = []
        for currency in currencies:
            if currency.code == base_code:
                rates.append((currency, _BASE_CURRENCY_RATE))
                continue
            rate = self._fetch_rate(currency.code, base_code)
            if rate is not None:
                rates.append((currency, rate))

        today = self._today()
        with self._currency_repo.transaction():
            for currency, rate in rates:
                if currency is base:
                    currency.exchange_rate = rate
                    continue
                if base is not None:
                    self._fx_rates.record_rate(
                        currency,
                        base,
                        rate,
                        rate_date=today,
                        source=SOURCE_YAHOO,
                        is_synthetic=True,
                    )
                # The cache is derived from the history only for the system
                # currency; any other base keeps the direct assignment.
                if base is None or base_code != DEFAULT_CURRENCY_CODE:
                    currency.exchange_rate = rate
            self._currency_repo.flush()
        return len(rates)

    def data_status(self, *, only_problems: bool = False) -> DataStatus:
        """Freshness of the data: when the provider last wrote a rate, and per
        active asset its price day, source and last provider write. An asset is a
        problem when its price is missing or stale."""
        assets = self._asset_repo.list_all()
        quotes = self._prices.latest_quotes(assets)
        fetched = self._prices.last_provider_fetch(assets)
        rows = []
        for asset in assets:
            quote = quotes.get(asset.id)
            stale = quote is None or quote.stale
            if only_problems and not stale:
                continue
            rows.append(
                AssetDataStatus(
                    asset_id=asset.id,
                    ticker=asset.ticker,
                    price_date=quote.price_date if quote else None,
                    source=quote.source if quote else None,
                    stale=stale,
                    last_success_at=fetched.get(asset.id),
                )
            )
        return DataStatus(
            fx_last_success_at=self._fx_rates.last_provider_fetch(), assets=rows
        )

    def _fetch_price(self, ticker: str) -> Decimal | None:
        try:
            quote = self._provider.fetch_quote(ticker)
        except MarketDataUnavailableError:
            logger.warning("Price refresh failed for %s", ticker, exc_info=True)
            return None
        price = quote.price if quote is not None else None
        if price is None:
            logger.warning("No price available for %s", ticker)
        return price

    def _fetch_rate(self, code: str, base_code: str) -> Decimal | None:
        try:
            rate = self._provider.fetch_fx_rate(code, base_code)
        except MarketDataUnavailableError:
            logger.warning(
                "Rate refresh failed for %s/%s", code, base_code, exc_info=True
            )
            return None
        if rate is None:
            logger.warning("No rate available for %s/%s", code, base_code)
        return rate
