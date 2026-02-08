import random
from authentication.models import UserProfile
from django.test import Client


class TransactionFactory():

    def __init__(self, user, pocket_name='NAME'):

        self.user = user
        self.pocket_name = pocket_name
        self.tickers = [
            'AAPL', 'MSFT', 'NVDA', 'GOOG', 'GOOGL', 'AMZN', 'META', 'AVGO', 'TSLA',
            'COST', 'ASML', 'NFLX', 'AZN', 'AMD', 'ADBE', 'PEP', 'TMUS', 'LIN', 'CSCO',
            'PDD', 'QCOM', 'INTU', 'TXN', 'AMGN', 'ISRG', 'AMAT', 'CMCSA', 'ARM',
            'HON', 'REGN', 'VRTX', 'BKNG', 'MU', 'PANW', 'LRCX', 'ADI', 'KLAC',
            'ADP', 'SBUX', 'MELI', 'MDLZ', 'GILD', 'INTC', 'SNPS', 'CTAS', 'CDNS',
            'ABNB', 'PYPL', 'ORLY', 'CSX', 'CRWD', 'NXPI', 'MAR', 'WDAY', 'MRVL',
            'CEG', 'ROP', 'FTNT', 'ADSK', 'DASH', 'AEP', 'TTD', 'PCAR', 'CPRT',
            'CHTR', 'ROST', 'KDP', 'MNST', 'PAYX', 'MCHP', 'KHC', 'ODFL', 'IDXX',
            'TEAM', 'EA', 'DDOG', 'GEHC', 'FAST', 'VRSK', 'EXC', 'CTSH', 'CCEP',
            'BKR', 'FANG', 'XEL', 'MRNA', 'LULU', 'ON', 'CSGP', 'BIIB', 'ZS',
            'CDW', 'DXCM', 'ANSS', 'TTWO', 'GFS', 'DLTR', 'ILMN', 'WBD', 'MDB',
            'WBA'
        ]
        self.operations = []

    def generate_ticker(self, allow_duplicates=False, tickers=[]):
        '''Generate a random ticker from the list of tickers and remove it from the list.'''
        if tickers:
            ticker = random.choice(tickers)
            return ticker
        else:
            if len(self.tickers) == 0:
                return []

            if allow_duplicates == False:
                ticker = random.choice(self.tickers)
                self.tickers.remove(ticker)
            else:
                ticker = random.choice(self.tickers)

            return ticker

    def generate_price(self):
        return random.randint(50, 500)

    def generate_quantity(self):
        return random.randint(1, 100)

    def generate_fee(self):
        return random.randint(0, 10)

    def generate_currency_price(self):
        return random.randint(5, 50)/10

    def draw_buy(self, allow_duplicates: bool = False) -> dict:
        '''Draw a random transaction data and the corresponding verification data.'''

        transaction_data = {
            'operation_type': "buy",
            'ticker': self.generate_ticker(allow_duplicates),
            'date': '2022-01-01',
            'currency': 'USD',
            'purchase_currency_price': self.generate_currency_price(),
            'quantity': self.generate_quantity(),
            'price': self.generate_price(),
            'fee': self.generate_fee(),
            'comment': 'Test comment',
            'asset_class': 'Equity',
            'pocket_name': self.pocket_name
        }

        return transaction_data

    def draw_sell(self, tickers: list, allow_duplicates: bool = False) -> dict:
        '''Draw a random transaction data and the corresponding verification data.'''

        transaction_data = {
            'operation_type': "sell",
            'ticker': self.generate_ticker(allow_duplicates=allow_duplicates, tickers=tickers),
            'date': '2022-01-01',
            'currency': 'USD',
            'purchase_currency_price': self.generate_currency_price(),
            'quantity': self.generate_quantity(),
            'price': self.generate_price(),
            'fee': self.generate_fee(),
            'comment': 'Test comment',
            'asset_class': 'Equity',
            'pocket_name': self.pocket_name
        }

        return transaction_data

    def draw_add_founds(self) -> dict:
        '''Draw a random transaction data and the corresponding verification data.'''

        transaction_data = {
            "operation_type": "add_funds",
            "asset_class": None,
            "ticker": None,
            "date": "2024-09-13",
            "currency": None,
            "purchase_currency_price": None,
            "quantity": self.generate_quantity(),
            "price": None,
            "fee": self.generate_fee(),
            "comment": "",
            "pocket_name": self.pocket_name
        }

        return transaction_data

    def draw_withdraw_founds(self) -> dict:
        '''Draw a random transaction data and the corresponding verification data.'''

        transaction_data = {
            "operation_type": "withdraw_funds",
            "asset_class": None,
            "ticker": None,
            "date": "2024-09-13",
            "currency": None,
            "purchase_currency_price": None,
            "quantity": self.generate_quantity(),
            "price": None,
            "fee": self.generate_fee(),
            "comment": "",
            "pocket_name": self.pocket_name
        }

        return transaction_data
