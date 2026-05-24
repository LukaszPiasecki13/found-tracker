from decimal import Decimal

from ..models import Operation, Portfolio
from ..repository import OperationRepository, PortfolioRepository


class PortfolioService:
    def __init__(
        self, portfolio_repo: PortfolioRepository, operation_repo: OperationRepository
    ):
        self.portfolio_repo = portfolio_repo
        self.operation_repo = operation_repo

    def deposit_cash(self, data: dict) -> bool:
        portfolio: Portfolio = data["portfolio"]
        amount = Decimal(str(data["amount"]))
        fee = Decimal(str(data.get("fee", 0)))

        if amount <= 0:
            raise ValueError("Deposit amount must be positive")

        portfolio.cash_balance += amount
        portfolio.total_deposited += amount
        if fee > 0:
            portfolio.cash_balance -= fee
        self.portfolio_repo.update(portfolio)
        return True

    def withdraw_cash(self, data: dict) -> bool:
        portfolio: Portfolio = data["portfolio"]
        amount = Decimal(str(data["amount"]))
        fee = Decimal(str(data.get("fee", 0)))

        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive")

        total_withdrawal = amount + fee
        if portfolio.cash_balance < total_withdrawal:
            raise ValueError(
                "Insufficient cash balance. Available: "
                f"{portfolio.cash_balance}, Required: {total_withdrawal}"
            )

        portfolio.cash_balance -= total_withdrawal
        portfolio.total_deposited -= amount
        self.portfolio_repo.update(portfolio)
        return True

    def delete_operation(self, operation: Operation) -> bool:
        portfolio = operation.portfolio

        if operation.operation_type == "deposit":
            net_deposit = operation.amount - operation.fee
            if portfolio.cash_balance < net_deposit:
                raise ValueError(
                    "Cannot delete deposit: would result in negative cash balance"
                )
            portfolio.cash_balance -= net_deposit
            portfolio.total_deposited -= operation.amount
            self.portfolio_repo.update(portfolio)

        elif operation.operation_type == "withdrawal":
            net_withdrawal = operation.amount + operation.fee
            portfolio.cash_balance += net_withdrawal
            portfolio.total_deposited += operation.amount
            self.portfolio_repo.update(portfolio)

        elif operation.operation_type in ("buy", "sell"):
            raise NotImplementedError(
                "Deleting buy/sell operations requires position "
                "recalculation. Not yet implemented."
            )

        self.operation_repo.delete(operation)
        return True
