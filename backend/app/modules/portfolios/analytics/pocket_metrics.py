from datetime import datetime
from itertools import groupby

import numpy as np
import pandas as pd
import yfinance as yf


class PocketMetrics:
    def __init__(
        self, operations: list, interval: str, start_time: datetime, end_time: datetime
    ):
        if start_time > end_time:
            raise ValueError("Start date cannot be after end date.")

        if interval != "1d":
            raise ValueError("Only daily interval is supported now.")

        self.interval = interval
        self.start_time = start_time
        self.end_time = end_time
        self.operations = operations

        self.interval_seconds = 24 * 60 * 60
        total_seconds = (end_time - start_time).total_seconds()
        self.time_diff = int(total_seconds // self.interval_seconds) + 1

        self._saved_data = {
            "sum_value_vector": None,
            "transaction_cost_vector": None,
            "net_deposits_vector": None,
            "free_cash_vector": None,
        }

    def get_date_vector(self) -> np.ndarray:
        return np.array(
            [
                self.start_time + pd.Timedelta(seconds=i * self.interval_seconds)
                for i in range(self.time_diff)
            ]
        )

    def get_assets_vectors(self) -> dict:
        assets = {}
        transactions = [
            op for op in self.operations if op.operation_type in ("buy", "sell")
        ]
        transactions.sort(key=lambda x: x.asset.ticker)
        grouped = {
            ticker: list(ops)
            for ticker, ops in groupby(transactions, key=lambda x: x.asset.ticker)
        }

        for ticker, ops in grouped.items():
            quantity_vector = self._quantity_vector(ops)
            value_vector = self._value_vector(
                ticker=ticker, quantity_vector=quantity_vector
            )
            assets[ticker] = value_vector

        self._saved_data["sum_value_vector"] = self._get_asset_value_sum(assets)
        return assets

    def _get_asset_value_sum(self, assets: dict) -> np.ndarray:
        total = np.zeros(self.time_diff, dtype=float)
        for v in assets.values():
            total += v
        return total

    def get_asset_classes_vectors(self) -> dict:
        asset_classes = {}
        transactions = [
            op for op in self.operations if op.operation_type in ("buy", "sell")
        ]
        transactions.sort(
            key=lambda x: x.asset.asset_class.name if x.asset.asset_class else ""
        )
        grouped = {
            ac: list(ops)
            for ac, ops in groupby(
                transactions,
                key=lambda x: x.asset.asset_class.name if x.asset.asset_class else "",
            )
        }

        for ac_name, ops in grouped.items():
            sum_vector = np.zeros(self.time_diff, dtype=float)
            ops.sort(key=lambda x: x.asset.ticker)
            grouped_ticker = {
                t: list(o) for t, o in groupby(ops, key=lambda x: x.asset.ticker)
            }
            for ticker, ticker_ops in grouped_ticker.items():
                qv = self._quantity_vector(ticker_ops)
                vv = self._value_vector(ticker=ticker, quantity_vector=qv)
                sum_vector += vv
            asset_classes[ac_name] = sum_vector

        return asset_classes

    def get_net_deposits_vector(self) -> np.ndarray:
        fund_ops = [
            op
            for op in self.operations
            if op.operation_type in ("deposit", "withdrawal")
        ]
        fund_ops.sort(key=lambda x: x.operation_date)
        vector = np.zeros(self.time_diff, dtype=float)
        saldo = 0.0

        for op in fund_ops:
            index = max(
                0,
                int(
                    (op.operation_date - self.start_time).total_seconds()
                    / self.interval_seconds
                ),
            )
            if op.operation_type == "deposit":
                saldo += float(op.amount or 0)
            elif op.operation_type == "withdrawal":
                saldo -= float(op.amount or 0)
            if index < self.time_diff:
                vector[index:] = saldo

        self._saved_data["net_deposits_vector"] = vector
        return vector

    def get_transaction_cost_vector(self) -> np.ndarray:
        ops = sorted(self.operations, key=lambda x: x.operation_date)
        vector = np.zeros(self.time_diff, dtype=float)
        cost = 0.0

        for op in ops:
            index = max(
                0,
                int(
                    (op.operation_date - self.start_time).total_seconds()
                    / self.interval_seconds
                ),
            )
            if op.operation_type == "buy":
                cost += float(op.quantity) * float(op.price) + float(op.fee)
            elif op.operation_type == "sell":
                cost -= float(op.quantity) * float(op.price) - float(op.fee)
            else:
                cost += float(op.fee)
            if index < self.time_diff:
                vector[index:] = cost

        self._saved_data["transaction_cost_vector"] = vector
        return vector

    def get_profit_vector(self) -> np.ndarray:
        svv = self._saved_data.get("sum_value_vector")
        tcv = self._saved_data.get("transaction_cost_vector")
        if svv is not None and tcv is not None:
            return svv - tcv
        assets = self.get_assets_vectors()
        svv = self._get_asset_value_sum(assets)
        tcv = self.get_transaction_cost_vector()
        return svv - tcv

    def get_free_cash_vector(self) -> np.ndarray:
        ndv = self._saved_data.get("net_deposits_vector")
        tcv = self._saved_data.get("transaction_cost_vector")
        if ndv is not None and tcv is not None:
            fcv = ndv - tcv
            self._saved_data["free_cash_vector"] = fcv
            return fcv
        ndv = self.get_net_deposits_vector()
        tcv = self.get_transaction_cost_vector()
        fcv = ndv - tcv
        self._saved_data["free_cash_vector"] = fcv
        return fcv

    def get_pocket_value_vector(self) -> np.ndarray:
        fcv = self._saved_data.get("free_cash_vector")
        svv = self._saved_data.get("sum_value_vector")
        if fcv is not None and svv is not None:
            return fcv + svv
        fcv = self.get_free_cash_vector()
        assets = self.get_assets_vectors()
        svv = self._get_asset_value_sum(assets)
        return fcv + svv

    def _quantity_vector(self, operations: list) -> np.ndarray:
        ops = sorted(operations, key=lambda x: x.operation_date)
        vector = np.zeros(self.time_diff, dtype=float)
        qty = 0.0
        for op in ops:
            index = max(
                0,
                int(
                    (op.operation_date - self.start_time).total_seconds()
                    / self.interval_seconds
                ),
            )
            if op.operation_type == "buy":
                qty += float(op.quantity)
            elif op.operation_type == "sell":
                qty -= float(op.quantity)
            if index < self.time_diff:
                vector[index:] = qty
        return vector

    def _value_vector(self, ticker: str, quantity_vector: np.ndarray) -> np.ndarray:
        hist = self._asset_historical_values(ticker=ticker)
        return quantity_vector * hist

    def _asset_historical_values(self, ticker: str) -> np.ndarray:
        start_str = self.start_time.strftime("%Y-%m-%d")
        end_str = self.end_time.strftime("%Y-%m-%d")
        ticker_df = yf.Ticker(ticker).history(
            start=self.start_time, end=self.end_time, interval=self.interval
        )[["Close"]]
        ticker_df.index = ticker_df.index.tz_localize(None).date

        full_range = pd.date_range(start=start_str, end=end_str)
        ticker_df = ticker_df.reindex(full_range)

        if self.end_time.weekday() < 5 and pd.isna(ticker_df["Close"].iloc[-1]):
            ticker_df.loc[ticker_df.index[-1], "Close"] = yf.Ticker(ticker).info.get(
                "currentPrice", 0
            )

        ticker_df["Close"] = ticker_df["Close"].ffill().bfill()
        return ticker_df["Close"].values
