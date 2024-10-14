from datetime import datetime
from itertools import groupby
import numpy as np
import pandas as pd
import yfinance as yf


class PocketMetrics:
    def __init__(self, operations: list, interval: str, start_time: datetime, end_time: datetime):
        '''

        Valid intervals: now only [1d]
        '''

        if start_time > end_time:
            raise ValueError("Start date cannot be after end date.")

        self.interval = interval
        self.start_time = start_time
        self.end_time = end_time
        self.operations = operations

        interval_mapping = {
            "1m": 60,
            "2m": 2 * 60,
            "5m": 5 * 60,
            "15m": 15 * 60,
            "30m": 30 * 60,
            "60m": 60 * 60,
            "90m": 90 * 60,
            "1h": 60 * 60,
            "1d": 24 * 60 * 60,
            "5d": 5 * 24 * 60 * 60,
            "1wk": 7 * 24 * 60 * 60,
            "1mo": 30 * 24 * 60 * 60,
            "3mo": 90 * 24 * 60 * 60
        }
        if interval != '1d':
            raise ValueError("Only daily interval is supported now.")

        if interval not in interval_mapping:
            raise ValueError(
                f"Invalid input - interval={interval} is not supported. Valid intervals: [1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo]")

        self.interval_seconds = interval_mapping[interval]
        total_seconds = (end_time - start_time).total_seconds()
        self.time_diff = int(total_seconds // self.interval_seconds)+1

        self._saved_data = {"sum_value_vector": None,
                            "transaction_cost_vector": None,
                            "net_deposits_vector": None,
                            "free_cash_vector": None,
                            }

    def get_date_vector(self) -> np.array:
        date_vector = np.array(
            [self.start_time + pd.Timedelta(seconds=i*self.interval_seconds) for i in range(self.time_diff)])
        return date_vector

    def get_assets_vectors(self) -> dict:
        assets = {}
        transactions = [
            operation for operation in self.operations if operation.operation_type in ['buy', 'sell']]
        transactions.sort(key=lambda x: x.ticker)
        grouped_transactions = {ticker: list(ops) for ticker, ops in groupby(
            transactions, key=lambda x: x.ticker)}

        for ticker, ops in grouped_transactions.items():
            quantity_vector = self._qunatity_vector(ops)
            value_vector = self._value_vector(
                ticker=ticker, quantity_vector=quantity_vector)

            assets[ticker] = value_vector

        sum_value_vector = np.zeros(self.time_diff, dtype=float)
        for asset in assets.values():
            sum_value_vector += asset

        # assets["sum_value_vector"] = sum_value_vector
        self._saved_data["sum_value_vector"] = sum_value_vector

        return assets

    def get_asset_classes_vectors(self) -> dict:
        asset_classes = {}

        transactions = [
            operation for operation in self.operations if operation.operation_type in ['buy', 'sell']]
        transactions.sort(key=lambda x: x.asset_class)
        grouped_transactions = {asset_class: list(ops) for asset_class, ops in groupby(
            transactions, key=lambda x: x.asset_class)}

        for asset_class, ops in grouped_transactions.items():
            sum_vector = np.zeros(self.time_diff, dtype=float)

            ops.sort(key=lambda x: x.ticker)
            grouped_transactions_ticker = {ticker: list(transactions) for ticker, transactions in groupby(
                ops, key=lambda x: x.ticker)}

            for ticker, transactions in grouped_transactions_ticker.items():
                quantity_vector = self._qunatity_vector(transactions)
                value_vector = self._value_vector(
                    ticker=ticker, quantity_vector=quantity_vector)
                sum_vector += value_vector

            if np.any(value_vector < 0):
                raise ValueError("Negative value of assets in time.")

            asset_classes[asset_class] = sum_vector

        return asset_classes

    def get_net_deposits_vector(self) -> np.array:

        fund_operations = [operation for operation in self.operations if operation.operation_type in [
            'add_funds', 'withdraw_funds']]
        fund_operations.sort(key=lambda x: x.date)
        net_deposits_vector = np.zeros(self.time_diff, dtype=float)
        current_saldo = 0

        for operation in fund_operations:
            index = int(((self.start_time.date() - operation.date).total_seconds()) / self.interval_seconds)
            if operation.operation_type == 'add_funds':
                current_saldo += operation.quantity
            elif operation.operation_type == 'withdraw_funds':
                current_saldo -= operation.quantity

            net_deposits_vector[index:] = current_saldo

        if np.any(net_deposits_vector < 0):
            raise ValueError("Negative net deposits in time.")
        else:
            self._saved_data["net_deposits_vector"] = net_deposits_vector
            return net_deposits_vector

    def get_transaction_cost_vector(self) -> np.array:
        operations = self.operations.copy()
        operations.sort(key=lambda x: x.date)

        transaction_cost_vector = np.zeros(self.time_diff, dtype=float)
        current_cost = 0

        # Iteration over operations
        for op in operations:
            index = int(((self.start_time.date() - op.date).total_seconds()) / self.interval_seconds)
        
            if op.operation_type == 'buy':
                current_cost += op.quantity * op.price + op.fee
            elif op.operation_type == 'sell':
                current_cost -= (op.quantity * op.price - op.fee)
            else:
                current_cost += op.fee

            # Update the quantity vector from this date
            transaction_cost_vector[index:] = current_cost

        if np.any(transaction_cost_vector < 0):
            raise ValueError("Negative cost of assets in time.")
        else:
            self._saved_data["transaction_cost_vector"] = transaction_cost_vector
            return transaction_cost_vector

    def get_profit_vector(self) -> np.array:
        if np.any(self._saved_data["sum_value_vector"]) and np.any(self._saved_data["transaction_cost_vector"]):
            return self._saved_data["sum_value_vector"] - self._saved_data["transaction_cost_vector"]
        else:
            sum_value_vector = self.get_assets_vectors()["sum_value_vector"]
            transaction_cost_vector = self.get_transaction_cost_vector()
            return sum_value_vector - transaction_cost_vector

    def get_free_cash_vector(self) -> np.array:
        if np.any(self._saved_data["net_deposits_vector"]) and np.any(self._saved_data["transaction_cost_vector"]):
            free_cash_vector = self._saved_data["net_deposits_vector"] - \
                self._saved_data["transaction_cost_vector"]
            self._saved_data["free_cash_vector"] = free_cash_vector
            return free_cash_vector
        else:
            net_deposits_vector = self.get_net_deposits_vector()
            transaction_cost_vector = self.get_transaction_cost_vector()
            free_cash_vector = net_deposits_vector - transaction_cost_vector
            self._saved_data["free_cash_vector"] = free_cash_vector
            return free_cash_vector

    def get_pocket_value_vector(self) -> np.array:
        if np.any(self._saved_data["free_cash_vector"]) and np.any(self._saved_data["sum_value_vector"]):
            return self._saved_data["free_cash_vector"] + self._saved_data["sum_value_vector"]
        else:
            free_cash_vector = self.get_free_cash_vector()
            sum_value_vector = self.get_assets_vectors()["sum_value_vector"]
            return free_cash_vector + sum_value_vector

    def _qunatity_vector(self, operations: list) -> np.array:
        operations.sort(key=lambda x: x.date)

        quantity_vector = np.zeros(self.time_diff, dtype=float)
        current_quantity = 0

        # Iteration over operations
        for op in operations:
            index = int(
                ((self.start_time.date() - op.date).total_seconds()) / self.interval_seconds)
            if op.operation_type == 'buy':
                current_quantity += op.quantity
            elif op.operation_type == 'sell':
                current_quantity -= op.quantity

            # Update the quantity vector from this date
            quantity_vector[index:] = current_quantity

        if np.any(quantity_vector < 0):
            raise ValueError("Negative quantity of assets in time.")
        else:
            return quantity_vector

    def _value_vector(self, ticker: str, quantity_vector: np.array) -> np.array:

        asset_historical_values = self._asset_historical_values(ticker=ticker)
        value_vector = (quantity_vector*asset_historical_values)
        return value_vector

    def _asset_historical_values(self, ticker: str) -> np.array:
        '''
        Get historical values of the asset in the given time range. 
        If the last date is a work day, we fill the last cell with the current price.
        '''

        start_date_str = self.start_time.date().strftime('%Y-%m-%d')
        end_date_str = self.end_time.date().strftime('%Y-%m-%d')
        ticker_df = yf.Ticker(ticker).history(
            start=self.start_time, end=self.end_time, interval=self.interval)[['Close']]

        ticker_df.index = ticker_df.index.tz_localize(
            None).date  # Delete timezone info and hours

        # We need to fill the data with missing dates, because there are no weekend days
        full_data_range = pd.date_range(
            start=start_date_str, end=end_date_str)
        ticker_df = ticker_df.reindex(full_data_range)

        # If is work day
        if self.end_time.weekday() < 5:
            # If last cell is NaN
            if pd.isna(ticker_df['Close'].iloc[-1]):
                ticker_df.loc[ticker_df.index[-1],
                              'Close'] = yf.Ticker(ticker).info['currentPrice']

        ticker_df['Close'] = ticker_df['Close'].ffill()
        if ticker_df['Close'].isna().any():
            ticker_df['Close'] = ticker_df['Close'].bfill()

        return ticker_df['Close'].values
