"""
Portfolio Service for managing portfolio-level operations.
Handles cash management, portfolio snapshots, and portfolio-wide calculations.
"""
from decimal import Decimal
from typing import Any, Dict
from authentication.models import UserProfile
from ..models import Pocket, Operation


class PortfolioService:
    """
    Service for managing portfolio (Pocket) operations.
    Handles cash deposits/withdrawals and portfolio management.
    """
    
    def __init__(self, owner: UserProfile):
        self.owner = owner
    
    def deposit_cash(self, data: Dict[str, Any]) -> bool:
        """
        Deposit cash into a pocket.
        
        Args:
            data: Dictionary with 'pocket' and 'amount' keys
            
        Returns:
            True if successful
        """
        pocket = data.get('pocket')
        if pocket is None:
            raise ValueError('Pocket is required')
        amount = Decimal(str(data.get('amount')))
        fee = Decimal(str(data.get('fee', 0)))
        
        if amount <= 0:
            raise ValueError('Deposit amount must be positive')
        
        pocket.cash_balance += amount
        pocket.total_deposited += amount
        
        if fee > 0:
            pocket.cash_balance -= fee
        
        pocket.save()
        return True
    
    def withdraw_cash(self, data: Dict[str, Any]) -> bool:
        """
        Withdraw cash from a pocket.
        
        Args:
            data: Dictionary with 'pocket' and 'amount' keys
            
        Returns:
            True if successful
            
        Raises:
            ValueError if insufficient cash balance
        """
        pocket = data.get('pocket')
        if pocket is None:
            raise ValueError('Pocket is required')
        amount = Decimal(str(data.get('amount')))
        fee = Decimal(str(data.get('fee', 0)))
        
        if amount <= 0:
            raise ValueError('Withdrawal amount must be positive')
        
        total_withdrawal = amount + fee
        
        if pocket.cash_balance < total_withdrawal:
            raise ValueError(f'Insufficient cash balance. Available: {pocket.cash_balance}, Required: {total_withdrawal}')
        
        pocket.cash_balance -= total_withdrawal
        pocket.total_deposited -= amount
        
        pocket.save()
        return True
    
    def delete_operation(self, operation: Operation) -> bool:
        """
        Delete an operation and reverse its effects on the pocket/position.
        
        Args:
            operation: Operation instance to delete
            
        Returns:
            True if successful
            
        Raises:
            ValueError if operation cannot be safely deleted
        """
        pocket = operation.pocket
        
        if operation.operation_type == 'deposit':
            # Reverse deposit: originally cash_balance += amount - fee, so reverse: -= (amount - fee)
            net_deposit = operation.amount - operation.fee
            if pocket.cash_balance < net_deposit:
                raise ValueError('Cannot delete deposit: would result in negative cash balance')
            pocket.cash_balance -= net_deposit
            pocket.total_deposited -= operation.amount
            pocket.save()
            
        elif operation.operation_type == 'withdrawal':
            # Reverse withdrawal: originally cash_balance -= (amount + fee), so reverse: += (amount + fee)
            net_withdrawal = operation.amount + operation.fee
            pocket.cash_balance += net_withdrawal
            pocket.total_deposited += operation.amount
            pocket.save()
            
        elif operation.operation_type in ['buy', 'sell']:
            # For buy/sell operations, this requires more complex logic
            # involving position recalculation - for now, prevent deletion
            raise ValueError(
                'Deleting buy/sell operations requires position recalculation. '
                'This feature is not yet implemented. Please manually adjust positions.'
            )
        
        # Delete the operation record
        operation.delete()
        return True
    
    @staticmethod
    def calculate_portfolio_value(pocket: Pocket) -> Decimal:
        """
        Calculate total portfolio value (cash + positions).
        
        Args:
            pocket: Pocket instance
            
        Returns:
            Total value in pocket's base currency
        """
        positions_value = Decimal('0')
        
        for position in pocket.positions.all():
            # Use the property from Position model
            positions_value += position.market_value
        
        return pocket.cash_balance + positions_value
    
    @staticmethod
    def get_positions_summary(pocket: Pocket) -> Dict:
        """
        Get summary of all positions in a portfolio.
        
        Args:
            pocket: Pocket instance
            
        Returns:
            Dictionary with position summaries
        """
        positions = pocket.positions.all().select_related('asset', 'asset__currency', 'asset__asset_class')
        
        summary = {
            'total_positions': positions.count(),
            'total_market_value': Decimal('0'),
            'total_cost_basis': Decimal('0'),
            'total_unrealized_pnl': Decimal('0'),
            'positions': []
        }
        
        for position in positions:
            pos_data = {
                'asset': position.asset.ticker,
                'quantity': position.quantity,
                'market_value': position.market_value,
                'cost_basis': position.cost_basis_in_pocket_currency,
                'unrealized_pnl': position.unrealized_pnl,
                'return_pct': position.return_pct
            }
            summary['positions'].append(pos_data)
            summary['total_market_value'] += position.market_value
            summary['total_cost_basis'] += position.cost_basis_in_pocket_currency
            summary['total_unrealized_pnl'] += position.unrealized_pnl
        
        return summary

