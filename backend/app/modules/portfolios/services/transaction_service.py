from decimal import Decimal

from ..models import Portfolio, Position
from ..repository import PortfolioRepository, PositionRepository


class TransactionService:
    def __init__(
        self, portfolio_repo: PortfolioRepository, position_repo: PositionRepository
    ):
        self.portfolio_repo = portfolio_repo
        self.position_repo = position_repo

    def execute_buy(self, data: dict) -> bool:
        portfolio: Portfolio = data["portfolio"]
        asset = data["asset"]
        quantity = Decimal(str(data["quantity"]))
        price = Decimal(str(data["price"]))
        fee = Decimal(str(data.get("fee", 0)))
        fx_rate = Decimal(str(data.get("fx_rate", 1)))

        total_cost = (quantity * price + fee) * fx_rate

        if portfolio.cash_balance < total_cost:
            raise ValueError("Insufficient cash balance to execute buy operation")

        portfolio.cash_balance -= total_cost
        self.portfolio_repo.update(portfolio)

        position = self.position_repo.get_by_portfolio_and_asset(portfolio.id, asset.id)
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
                portfolio_id=portfolio.id,
                asset_id=asset.id,
                quantity=quantity,
                average_buy_price=(quantity * price + fee) / quantity,
                average_fx_rate=fx_rate,
                total_fees=fee,
            )
            self.position_repo.create(position)

        return True

    def execute_sell(self, data: dict) -> bool:
        portfolio: Portfolio = data["portfolio"]
        asset = data["asset"]
        quantity = Decimal(str(data["quantity"]))
        price = Decimal(str(data["price"]))
        fee = Decimal(str(data.get("fee", 0)))
        fx_rate = Decimal(str(data.get("fx_rate", 1)))

        position = self.position_repo.get_by_portfolio_and_asset(portfolio.id, asset.id)
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
        portfolio.cash_balance += proceeds
        self.portfolio_repo.update(portfolio)

        position.quantity -= quantity
        position.total_fees += fee
        if position.quantity == 0:
            self.position_repo.delete(position)
        else:
            self.position_repo.update(position)

        return True
