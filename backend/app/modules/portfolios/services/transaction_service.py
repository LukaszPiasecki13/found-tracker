from decimal import Decimal

from ..models import Pocket, Position
from ..repository import PocketRepository, PositionRepository


class TransactionService:
    def __init__(
        self, pocket_repo: PocketRepository, position_repo: PositionRepository
    ):
        self.pocket_repo = pocket_repo
        self.position_repo = position_repo

    def execute_buy(self, data: dict) -> bool:
        pocket: Pocket = data["pocket"]
        asset = data["asset"]
        quantity = Decimal(str(data["quantity"]))
        price = Decimal(str(data["price"]))
        fee = Decimal(str(data.get("fee", 0)))
        fx_rate = Decimal(str(data.get("fx_rate", 1)))

        total_cost = (quantity * price + fee) * fx_rate

        if pocket.cash_balance < total_cost:
            raise ValueError("Insufficient cash balance to execute buy operation")

        pocket.cash_balance -= total_cost
        self.pocket_repo.update(pocket)

        position = self.position_repo.get_by_pocket_and_asset(pocket.id, asset.id)
        if position:
            old_qty = position.quantity
            new_qty = old_qty + quantity
            position.average_buy_price = (
                old_qty * position.average_buy_price + quantity * price + fee
            ) / new_qty
            position.average_fx_rate = (
                old_qty * position.average_fx_rate + quantity * fx_rate
            ) / new_qty
            position.quantity = new_qty
            position.total_fees += fee
            self.position_repo.update(position)
        else:
            position = Position(
                pocket_id=pocket.id,
                asset_id=asset.id,
                quantity=quantity,
                average_buy_price=(quantity * price + fee) / quantity,
                average_fx_rate=fx_rate,
                total_fees=fee,
            )
            self.position_repo.create(position)

        return True

    def execute_sell(self, data: dict) -> bool:
        pocket: Pocket = data["pocket"]
        asset = data["asset"]
        quantity = Decimal(str(data["quantity"]))
        price = Decimal(str(data["price"]))
        fee = Decimal(str(data.get("fee", 0)))
        fx_rate = Decimal(str(data.get("fx_rate", 1)))

        position = self.position_repo.get_by_pocket_and_asset(pocket.id, asset.id)
        if not position:
            raise ValueError(
                "Position does not exist - cannot sell asset you do not own"
            )
        if position.quantity < quantity:
            raise ValueError(
                "Insufficient shares. Have "
                f"{position.quantity}, trying to sell {quantity}"
            )

        proceeds = (quantity * price - fee) * fx_rate
        pocket.cash_balance += proceeds
        self.pocket_repo.update(pocket)

        position.quantity -= quantity
        position.total_fees += fee
        if position.quantity == 0:
            self.position_repo.delete(position)
        else:
            self.position_repo.update(position)

        return True
