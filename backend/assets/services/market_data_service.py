"""
Market Data Service for fetching and updating asset prices and currency exchange rates.
Encapsulates all external data provider interactions (yfinance).
"""
import yfinance as yf
from decimal import Decimal
from typing import Optional, Dict, Any
from ..models import Asset, Currency


class MarketDataService:
    """
    Service for managing market data updates.
    Handles price fetching from Yahoo Finance and currency exchange rate updates.
    """
    
    @staticmethod
    def update_asset_price(asset: Asset) -> Decimal:
        """
        Fetch and update the current price for a given asset.
        
        Args:
            asset: Asset instance to update
            
        Returns:
            Updated current price
            
        Raises:
            Exception if price fetch fails
        """
        try:
            ticker = yf.Ticker(asset.ticker)
            info = ticker.info
            
            # Try to get current price from various fields
            current_price = (
                info.get('currentPrice') or 
                info.get('regularMarketPrice') or 
                info.get('previousClose', 0)
            )
            
            if current_price:
                asset.current_price = Decimal(str(current_price))
                asset.save()
                return asset.current_price
            else:
                raise ValueError(f"Could not retrieve price for {asset.ticker}")
                
        except Exception as e:
            raise Exception(f"Failed to update price for {asset.ticker}: {str(e)}")
    
    @staticmethod
    def get_asset_info(ticker: str) -> Dict[str, Any]:
        """
        Fetch detailed information about an asset from Yahoo Finance.
        
        Args:
            ticker: Asset ticker symbol
            
        Returns:
            Dictionary with asset information
        """
        try:
            ticker_obj = yf.Ticker(ticker)
            return ticker_obj.info
        except Exception as e:
            raise Exception(f"Failed to fetch info for {ticker}: {str(e)}")
    
    @staticmethod
    def get_asset_name(ticker: str) -> str:
        """
        Get the full name of an asset by ticker.
        
        Args:
            ticker: Asset ticker symbol
            
        Returns:
            Full asset name
        """
        try:
            asset_info = yf.Ticker(ticker).info
            return asset_info.get('longName', ticker)
        except Exception:
            return ticker
    
    @staticmethod
    def update_currency_rates(base_currency_code: str = 'USD'):
        """
        Update exchange rates for all currencies relative to a base currency.
        
        Args:
            base_currency_code: The base currency code (e.g., 'USD', 'EUR', 'PLN')
        """
        currencies = Currency.objects.all()
        
        for currency in currencies:
            if currency.code != base_currency_code:
                try:
                    # Fetch exchange rate from Yahoo Finance
                    # Format: USDPLN=X for USD to PLN conversion
                    pair_symbol = f'{currency.code}{base_currency_code}=X'
                    ticker = yf.Ticker(pair_symbol)
                    info = ticker.info
                    
                    # Get the bid price or last price
                    rate = info.get('bid') or info.get('regularMarketPrice') or info.get('previousClose')
                    
                    if rate:
                        currency.exchange_rate = Decimal(str(rate))
                        currency.save()
                    else:
                        print(f"Warning: Could not update rate for {currency.code}")
                        
                except Exception as e:
                    print(f"Error updating {currency.code}: {str(e)}")
            else:
                # Base currency always has rate of 1.0
                currency.exchange_rate = Decimal('1.0')
                currency.save()
    
    @staticmethod
    def update_multiple_assets(asset_ids: list) -> Dict[int, bool]:
        """
        Update prices for multiple assets at once.
        
        Args:
            asset_ids: List of asset IDs to update
            
        Returns:
            Dictionary mapping asset_id to success status
        """
        results = {}
        assets = Asset.objects.filter(id__in=asset_ids)
        
        for asset in assets:
            try:
                MarketDataService.update_asset_price(asset)
                results[asset.id] = True
            except Exception:
                results[asset.id] = False
                
        return results
