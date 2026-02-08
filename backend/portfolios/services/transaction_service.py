"""
Transaction Service for handling buy/sell operations on assets.
Manages position updates with weighted averages and FIFO calculations.
"""
from decimal import Decimal
from typing import Dict, Tuple, List
from collections import namedtuple

from django.db.models import Q
from authentication.models import UserProfile
from assets.models import Asset, Currency, AssetClass
from assets.services import MarketDataService
from ..models import Pocket, Position, Operation


TransactionTuple = namedtuple('TransactionTuple', ['id', 'price', 'quantity', 'fee'])


class TransactionService:
    """
    Service for managing asset transactions (buy/sell).
    Handles position creation/updates with proper cost basis calculations.
    """
    
    def __init__(self, owner: UserProfile):
        self.owner = owner
    
    def execute_buy(self, data: Dict) -> bool:
        """
        Execute a buy operation: purchase asset shares.
        
        Args:
            data: Dictionary with transaction details (pocket, asset, quantity, price, fee, fx_rate)
            
        Returns:
            True if successful
            
        Raises:
            ValueError if insufficient cash or invalid data
        """
        pocket = data.get('pocket')
        asset = data.get('asset')
        quantity = Decimal(str(data.get('quantity')))
        price = Decimal(str(data.get('price')))
        fee = Decimal(str(data.get('fee', 0)))
        fx_rate = Decimal(str(data.get('fx_rate', 1)))
        
        # Calculate total cost in pocket currency
        total_cost_in_asset_currency = quantity * price + fee
        total_cost_in_pocket_currency = total_cost_in_asset_currency * fx_rate
        
        # Check if pocket has enough cash
        if pocket.cash_balance < total_cost_in_pocket_currency:
            raise ValueError('Insufficient cash balance to execute buy operation')
        
        # Deduct cash from pocket
        pocket.cash_balance -= total_cost_in_pocket_currency
        pocket.save()
        
        # Get or create position
        position, created = Position.objects.get_or_create(
            pocket=pocket,
            asset=asset,
            defaults={
                'quantity': quantity,
                'average_buy_price': price,
                'average_fx_rate': fx_rate,
                'total_fees': fee
            }
        )
        
        if not created:
            # Update existing position with weighted averages
            old_quantity = position.quantity
            new_quantity = old_quantity + quantity
            
            # Weighted average buy price
            position.average_buy_price = (
                (old_quantity * position.average_buy_price + quantity * price) / new_quantity
            )
            
            # Weighted average FX rate
            position.average_fx_rate = (
                (old_quantity * position.average_fx_rate + quantity * fx_rate) / new_quantity
            )
            
            position.quantity = new_quantity
            position.total_fees += fee
            position.save()
        
        return True
    
    def execute_sell(self, data: Dict) -> bool:
        """
        Execute a sell operation: sell asset shares.
        
        Args:
            data: Dictionary with transaction details
            
        Returns:
            True if successful
            
        Raises:
            ValueError if insufficient shares or position doesn't exist
        """
        pocket = data.get('pocket')
        asset = data.get('asset')
        quantity = Decimal(str(data.get('quantity')))
        price = Decimal(str(data.get('price')))
        fee = Decimal(str(data.get('fee', 0)))
        fx_rate = Decimal(str(data.get('fx_rate', 1)))
        
        # Get position
        try:
            position = Position.objects.get(pocket=pocket, asset=asset)
        except Position.DoesNotExist:
            raise ValueError('Position does not exist - cannot sell asset you do not own')
        
        # Check if enough shares
        if position.quantity < quantity:
            raise ValueError(f'Insufficient shares. Have {position.quantity}, trying to sell {quantity}')
        
        # Calculate proceeds in pocket currency
        proceeds_in_asset_currency = quantity * price - fee
        proceeds_in_pocket_currency = proceeds_in_asset_currency * fx_rate
        
        # Add cash to pocket
        pocket.cash_balance += proceeds_in_pocket_currency
        pocket.save()
        
        # Update position
        position.quantity -= quantity
        position.total_fees += fee
        
        if position.quantity == 0:
            # Close position if all shares sold
            position.delete()
        else:
            position.save()
        
        return True
    
    @staticmethod
    def calculate_average_purchase_price(buy_transactions: List, sell_transactions: List) -> Decimal:
        """
        Calculate weighted average purchase price using FIFO method.
        
        Args:
            buy_transactions: List of TransactionTuple for buys
            sell_transactions: List of TransactionTuple for sells
            
        Returns:
            Weighted average price
        """
        if not buy_transactions:
            return Decimal('0')
        
        # Sort by ID (chronological order)
        buys = sorted([t for t in buy_transactions if t.id is not None], key=lambda x: x.id)
        sells = sorted([t for t in sell_transactions if t.id is not None], key=lambda x: x.id)
        
        # Apply FIFO to determine remaining shares
        remaining_buys = []
        sell_quantity_remaining = sum(s.quantity for s in sells)
        
        for buy in buys:
            if sell_quantity_remaining >= buy.quantity:
                # This buy was completely sold
                sell_quantity_remaining -= buy.quantity
            elif sell_quantity_remaining > 0:
                # This buy was partially sold
                remaining_qty = buy.quantity - sell_quantity_remaining
                remaining_buys.append(TransactionTuple(
                    id=buy.id,
                    price=buy.price,
                    quantity=remaining_qty,
                    fee=buy.fee * (remaining_qty / buy.quantity)
                ))
                sell_quantity_remaining = 0
            else:
                # This buy was not sold at all
                remaining_buys.append(buy)
        
        if not remaining_buys:
            return Decimal('0')
        
        # Calculate weighted average
        total_cost = sum(b.price * b.quantity + b.fee for b in remaining_buys)
        total_quantity = sum(b.quantity for b in remaining_buys)
        
        if total_quantity == 0:
            return Decimal('0')
        
        return total_cost / total_quantity
    
    @staticmethod
    def get_asset_operations(pocket: Pocket, asset: Asset) -> Tuple[List, List]:
        """
        Retrieve all buy and sell operations for an asset in a pocket.
        
        Returns:
            Tuple of (buy_transactions, sell_transactions)
        """
        operations = Operation.objects.filter(
            pocket=pocket,
            asset=asset,
            operation_type__in=['buy', 'sell']
        ).order_by('operation_date', 'id')
        
        buy_transactions = []
        sell_transactions = []
        
        for op in operations:
            t = TransactionTuple(
                id=op.id,
                price=op.price,
                quantity=op.quantity,
                fee=op.fee
            )
            
            if op.operation_type == 'buy':
                buy_transactions.append(t)
            elif op.operation_type == 'sell':
                sell_transactions.append(t)
        
        return buy_transactions, sell_transactions
