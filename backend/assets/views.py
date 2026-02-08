from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Currency, AssetClass
from .serializers import CurrencySerializer, AssetClassSerializer


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
