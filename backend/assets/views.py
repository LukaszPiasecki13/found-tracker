from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q

from .models import Currency, AssetClass, Asset
from .serializers import CurrencySerializer, AssetClassSerializer, AssetSerializer, AssetDetailSerializer
from .services.market_data_service import MarketDataService


class CurrencyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing currencies.
    Provides CRUD operations for Currency model.
    """
    serializer_class = CurrencySerializer
    permission_classes = [IsAuthenticated]
    queryset = Currency.objects.all()


class AssetClassViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing asset classes.
    Provides CRUD operations for AssetClass model.
    """
    serializer_class = AssetClassSerializer
    permission_classes = [IsAuthenticated]
    queryset = AssetClass.objects.all()


class AssetViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing assets.
    Provides CRUD operations and search functionality.
    """
    serializer_class = AssetSerializer
    permission_classes = [IsAuthenticated]
    queryset = Asset.objects.all()
    
    def get_serializer_class(self):
        """Use detailed serializer for retrieve action."""
        if self.action == 'retrieve':
            return AssetDetailSerializer
        return AssetSerializer
    
    def get_queryset(self):
        """
        Filter assets based on search query parameter.
        Searches in ticker and name fields.
        """
        queryset = Asset.objects.all().select_related('asset_class', 'currency')
        search_query = self.request.query_params.get('search', None)
        
        if search_query:
            queryset = queryset.filter(
                Q(ticker__icontains=search_query) | 
                Q(name__icontains=search_query)
            )
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def search_yahoo(self, request):
        """
        Search for assets on Yahoo Finance.
        Query parameter: q (search query)
        
        Returns both local database results and Yahoo Finance results.
        """
        query = request.query_params.get('q', '').strip()
        
        if not query or len(query) < 2:
            return Response(
                {'error': 'Query must be at least 2 characters'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Search in local database first
        local_results = Asset.objects.filter(
            Q(ticker__icontains=query) | Q(name__icontains=query)
        ).select_related('asset_class', 'currency')[:10]
        
        local_data = AssetDetailSerializer(local_results, many=True).data
        
        # Search Yahoo Finance
        yahoo_results = MarketDataService.search_yahoo_finance(query)
        
        # Filter out Yahoo results that are already in database
        existing_tickers = {asset.ticker for asset in local_results}
        yahoo_filtered = [
            result for result in yahoo_results 
            if result['symbol'] not in existing_tickers
        ]
        
        return Response({
            'local': local_data,
            'yahoo': yahoo_filtered,
        })
    
    @action(detail=False, methods=['post'])
    def create_from_yahoo(self, request):
        """
        Create a new asset from Yahoo Finance data.
        Expects: ticker, asset_class_id, currency_id
        """
        ticker = request.data.get('ticker', '').strip().upper()
        asset_class_id = request.data.get('asset_class_id')
        currency_id = request.data.get('currency_id')
        
        if not ticker:
            return Response(
                {'error': 'Ticker is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if asset already exists
        if Asset.objects.filter(ticker=ticker).exists():
            return Response(
                {'error': 'Asset with this ticker already exists'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Fetch info from Yahoo Finance
            info = MarketDataService.get_asset_info(ticker)
            
            if not info or not info.get('symbol'):
                return Response(
                    {'error': 'Could not find asset on Yahoo Finance'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Determine asset class if not provided
            if not asset_class_id:
                quote_type = info.get('quoteType', 'EQUITY')
                asset_class_name = 'Stock'  # default
                
                if quote_type == 'ETF':
                    asset_class_name = 'ETF'
                elif quote_type in ['CRYPTOCURRENCY', 'CRYPTO']:
                    asset_class_name = 'Crypto'
                elif quote_type == 'MUTUALFUND':
                    asset_class_name = 'Mutual Fund'
                
                asset_class, _ = AssetClass.objects.get_or_create(name=asset_class_name)
                asset_class_id = asset_class.id
            
            # Determine currency if not provided
            if not currency_id:
                currency_code = info.get('currency', 'USD').upper()
                currency, _ = Currency.objects.get_or_create(code=currency_code)
                currency_id = currency.id
            
            # Get current price
            current_price = (
                info.get('currentPrice') or 
                info.get('regularMarketPrice') or 
                info.get('previousClose', 0)
            )
            
            # Create asset
            asset = Asset.objects.create(
                ticker=ticker,
                name=info.get('longName') or info.get('shortName', ticker),
                asset_class_id=asset_class_id,
                currency_id=currency_id,
                current_price=current_price,
                exchange=info.get('exchange', ''),
                sector=info.get('sector', ''),
            )
            
            return Response(
                AssetDetailSerializer(asset).data,
                status=status.HTTP_201_CREATED
            )
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
