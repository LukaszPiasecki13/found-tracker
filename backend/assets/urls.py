from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CurrencyViewSet, AssetClassViewSet

router = DefaultRouter()
router.register(r'currencies', CurrencyViewSet, basename='currency')
router.register(r'asset-classes', AssetClassViewSet, basename='assetclass')

urlpatterns = [
    path('', include(router.urls)),
]
