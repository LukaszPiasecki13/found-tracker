import yfinance as yf
from decimal import Decimal



class AssetCalculator:
    def __init__(self, asset_allocation):
        self.asset = asset_allocation.asset
        self.quantity = asset_allocation.quantity
        self.average_purchase_currency_price = asset_allocation.average_purchase_currency_price
        self.average_purchase_price = asset_allocation.average_purchase_price

        self.yf_info = yf.Ticker(self.asset.ticker).info

        self.current_price = self.update_price()

    def update_price(self):
        return Decimal(self.yf_info['currentPrice'])

    def get_total_value(self):
        return Decimal(self.quantity * self.current_price)

    def get_total_value_in_base_currency(self):
        return Decimal(self.get_total_value()*self.asset.currency.exchange_rate)

    def get_daily_change_percent(self):
        return Decimal(self._calculate_percentage_change(value=self.yf_info['currentPrice'], base=self.yf_info['previousClose']))

    def get_daily_change_in_base_currency(self):
        return Decimal((self.yf_info['currentPrice'] - self.yf_info['previousClose']) * float(self.quantity) * float(self.asset.currency.exchange_rate))

    def get_rate_of_return(self):
        return Decimal(self._calculate_percentage_change(value=self.current_price, base=self.average_purchase_price))

    def get_rate_of_return_in_base_currency(self):
        result = (self.current_price*self.asset.currency.exchange_rate - self.average_purchase_price *
                                                   self.average_purchase_currency_price) / (self.average_purchase_price*self.average_purchase_currency_price) * 100
        return Decimal(result)
    
    def get_profit_in_base_currency(self):
        return Decimal((self.get_rate_of_return_in_base_currency() / 100) * self._get_total_buy_cost_in_base_currency())

    def _get_total_buy_cost_in_base_currency(self):
        return Decimal(self.quantity * self.average_purchase_price * self.average_purchase_currency_price)

    def _calculate_percentage_change(self, value, base):
        if value != base:
            return(value - base) / base * 100
        else:
            return 0


        

