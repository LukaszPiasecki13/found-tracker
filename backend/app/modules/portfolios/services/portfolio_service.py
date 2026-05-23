from decimal import Decimal

from ..models import Operation, Pocket
from ..repository import OperationRepository, PocketRepository


class PortfolioService:
    def __init__(
        self, pocket_repo: PocketRepository, operation_repo: OperationRepository
    ):
        self.pocket_repo = pocket_repo
        self.operation_repo = operation_repo

    def deposit_cash(self, data: dict) -> bool:
        pocket: Pocket = data["pocket"]
        amount = Decimal(str(data["amount"]))
        fee = Decimal(str(data.get("fee", 0)))

        if amount <= 0:
            raise ValueError("Deposit amount must be positive")

        pocket.cash_balance += amount
        pocket.total_deposited += amount
        if fee > 0:
            pocket.cash_balance -= fee
        self.pocket_repo.update(pocket)
        return True

    def withdraw_cash(self, data: dict) -> bool:
        pocket: Pocket = data["pocket"]
        amount = Decimal(str(data["amount"]))
        fee = Decimal(str(data.get("fee", 0)))

        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive")

        total_withdrawal = amount + fee
        if pocket.cash_balance < total_withdrawal:
            raise ValueError(
                "Insufficient cash balance. Available: "
                f"{pocket.cash_balance}, Required: {total_withdrawal}"
            )

        pocket.cash_balance -= total_withdrawal
        pocket.total_deposited -= amount
        self.pocket_repo.update(pocket)
        return True

    def delete_operation(self, operation: Operation) -> bool:
        pocket = operation.pocket

        if operation.operation_type == "deposit":
            net_deposit = operation.amount - operation.fee
            if pocket.cash_balance < net_deposit:
                raise ValueError(
                    "Cannot delete deposit: would result in negative cash balance"
                )
            pocket.cash_balance -= net_deposit
            pocket.total_deposited -= operation.amount
            self.pocket_repo.update(pocket)

        elif operation.operation_type == "withdrawal":
            net_withdrawal = operation.amount + operation.fee
            pocket.cash_balance += net_withdrawal
            pocket.total_deposited += operation.amount
            self.pocket_repo.update(pocket)

        elif operation.operation_type in ("buy", "sell"):
            raise NotImplementedError(
                "Deleting buy/sell operations requires position "
                "recalculation. Not yet implemented."
            )

        self.operation_repo.delete(operation)
        return True
