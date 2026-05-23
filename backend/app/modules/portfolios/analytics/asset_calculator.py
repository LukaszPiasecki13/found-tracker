from decimal import Decimal

import yfinance as yf


class AssetCalculator:
    def __init__(self, position):
        self.asset = position.asset
        self.quantity = position.quantity
        self.average_buy_price = position.average_buy_price
        self.average_fx_rate = position.average_fx_rate

        self.yf_info = yf.Ticker(self.asset.ticker).info
        self.current_price = Decimal(
            str(
                self.yf_info.get("currentPrice")
                or self.yf_info.get("regularMarketPrice")
                or self.yf_info.get("previousClose", 0)
            )
        )

    def get_total_value(self) -> Decimal:
        return self.quantity * self.current_price

    def get_total_value_in_base_currency(self) -> Decimal:
        return self.get_total_value() * self.asset.currency.exchange_rate

    def get_daily_change_percent(self) -> Decimal:
        current = Decimal(str(self.yf_info.get("currentPrice", 0)))
        previous = Decimal(str(self.yf_info.get("previousClose", 0)))
        if previous == 0:
            return Decimal("0")
        return (current - previous) / previous * 100

    def get_daily_change_in_base_currency(self) -> Decimal:
        current = Decimal(str(self.yf_info.get("currentPrice", 0)))
        previous = Decimal(str(self.yf_info.get("previousClose", 0)))
        return (current - previous) * self.quantity * self.asset.currency.exchange_rate

    def get_rate_of_return(self) -> Decimal:
        if self.average_buy_price == 0:
            return Decimal("0")
        return (
            (self.current_price - self.average_buy_price) / self.average_buy_price * 100
        )

    def get_profit_in_base_currency(self) -> Decimal:
        cost = self.quantity * self.average_buy_price * self.average_fx_rate
        value = self.get_total_value_in_base_currency()
        return value - cost
