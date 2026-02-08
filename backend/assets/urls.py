from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CurrencyViewSet, AssetClassViewSet, AssetViewSet

router = DefaultRouter()
router.register(r'currencies', CurrencyViewSet, basename='currency')
router.register(r'asset-classes', AssetClassViewSet, basename='assetclass')
router.register(r'assets', AssetViewSet, basename='asset')

urlpatterns = [
    path('', include(router.urls)),
]
