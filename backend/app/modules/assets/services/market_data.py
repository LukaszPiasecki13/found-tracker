"""Market data: provider search and quotes, price and FX-rate refresh.

The provider (`MarketDataProvider` port) is an external dependency: a failure to
fetch one instrument is a normal event. Refreshes are best-effort per item - a
failing ticker or currency is logged and skipped, never aborts the rest.
"""

import logging
from collections.abc import Iterable
from dataclasses import replace
from datetime import date
from decimal import Decimal

from app.core.market_data import MarketDataProvider, MarketDataUnavailableError, Quote
from app.modules.assets.constants import DEFAULT_CURRENCY_CODE, DEFAULT_QUOTE_TYPE
from app.modules.assets.exceptions import AssetNotFoundOnProviderError
from app.modules.assets.models.assets import Asset
from app.modules.assets.models.currencies import Currency
from app.modules.assets.repositories.assets import AssetRepository
from app.modules.assets.repositories.currencies import CurrencyRepository

logger = logging.getLogger(__name__)

_BASE_CURRENCY_RATE = Decimal("1")


class MarketDataService:
    """Reads market data through the injected provider and writes refreshed
    prices and rates."""

    def __init__(
        self,
        asset_repo: AssetRepository,
        currency_repo: CurrencyRepository,
        provider: MarketDataProvider,
    ) -> None:
        self._asset_repo = asset_repo
        self._currency_repo = currency_repo
        self._provider = provider

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
        """Set `current_price` from the provider; returns how many were updated.

        Best-effort per asset: no price or a provider failure skips that asset.
        Prices are fetched before the transaction opens.
        """
        prices: list[tuple[Asset, Decimal]] = []
        seen: set[int] = set()
        for asset in assets:
            if asset.id in seen:
                continue
            seen.add(asset.id)
            price = self._fetch_price(asset.ticker)
            if price is not None:
                prices.append((asset, price))

        with self._asset_repo.transaction():
            for asset, price in prices:
                asset.current_price = price
            self._asset_repo.flush()
        return len(prices)

    def refresh_currency_rates(self, base_code: str = DEFAULT_CURRENCY_CODE) -> int:
        """Set every currency's `exchange_rate` to units of `base_code` per one
        unit of it (the base itself gets 1); returns how many were updated.

        Best-effort per currency: no rate or a provider failure skips it.
        """
        base_code = base_code.strip().upper()
        rates: list[tuple[Currency, Decimal]] = []
        for currency in self._currency_repo.list_all():
            if currency.code == base_code:
                rates.append((currency, _BASE_CURRENCY_RATE))
                continue
            rate = self._fetch_rate(currency.code, base_code)
            if rate is not None:
                rates.append((currency, rate))

        with self._currency_repo.transaction():
            for currency, rate in rates:
                currency.exchange_rate = rate
            self._currency_repo.flush()
        return len(rates)

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
