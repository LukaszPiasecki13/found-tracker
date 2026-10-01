"""Market-data adapters implementing `app.core.market_data.MarketDataProvider`."""

from app.infrastructure.market_data.yahoo import YahooFinanceProvider

__all__ = ["YahooFinanceProvider"]
