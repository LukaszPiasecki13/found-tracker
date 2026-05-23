import logging
from decimal import Decimal
from typing import Any

import yfinance as yf

from .models import Asset
from .repository import AssetClassRepository, AssetRepository, CurrencyRepository

logger = logging.getLogger(__name__)


class MarketDataService:
    def __init__(
        self,
        asset_repo: AssetRepository,
        currency_repo: CurrencyRepository,
        asset_class_repo: AssetClassRepository,
    ):
        self.asset_repo = asset_repo
        self.currency_repo = currency_repo
        self.asset_class_repo = asset_class_repo

    def update_asset_price(self, asset: Asset) -> Decimal:
        try:
            ticker = yf.Ticker(asset.ticker)
            info = ticker.info
            current_price = (
                info.get("currentPrice")
                or info.get("regularMarketPrice")
                or info.get("previousClose", 0)
            )
            if current_price:
                asset.current_price = Decimal(str(current_price))
                self.asset_repo.update(asset)
                return asset.current_price
            raise ValueError(f"Could not retrieve price for {asset.ticker}")
        except Exception as e:
            raise Exception(f"Failed to update price for {asset.ticker}: {e}") from e

    @staticmethod
    def get_asset_info(ticker: str) -> dict[str, Any]:
        try:
            return yf.Ticker(ticker).info
        except Exception as e:
            raise Exception(f"Failed to fetch info for {ticker}: {e}") from e

    def update_currency_rates(self, base_currency_code: str = "USD") -> None:
        currencies = self.currency_repo.list_all()
        for currency in currencies:
            if currency.code != base_currency_code:
                try:
                    pair_symbol = f"{currency.code}{base_currency_code}=X"
                    info = yf.Ticker(pair_symbol).info
                    rate = (
                        info.get("bid")
                        or info.get("regularMarketPrice")
                        or info.get("previousClose")
                    )
                    if rate:
                        currency.exchange_rate = Decimal(str(rate))
                        self.currency_repo.update(currency)
                except Exception:
                    logger.exception("Error updating %s", currency.code)
            else:
                currency.exchange_rate = Decimal("1.0")
                self.currency_repo.update(currency)

    @staticmethod
    def search_yahoo_finance(query: str) -> list[dict[str, Any]]:
        if not query or len(query) < 1:
            return []
        clean_query = query.strip()
        if " - " in clean_query:
            clean_query = clean_query.split(" - ")[0].strip()
        results = []
        try:
            ticker_obj = yf.Ticker(clean_query.upper())
            info = ticker_obj.info
            if (
                info
                and info.get("symbol")
                and (info.get("regularMarketPrice") or info.get("previousClose"))
            ):
                results.append(
                    {
                        "symbol": info.get("symbol", clean_query.upper()),
                        "name": info.get("longName") or info.get("shortName", ""),
                        "exchange": info.get("exchange", ""),
                        "type": info.get("quoteType", "EQUITY"),
                        "currency": info.get("currency", "USD"),
                        "sector": info.get("sector", ""),
                    }
                )
                return results
        except Exception:
            logger.exception("Failed to fetch Yahoo data for %s", clean_query)
        return results
