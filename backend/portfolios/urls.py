from django.urls import path, include
from . import views
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'pockets', views.PocketsViewSet, basename='pocket')
router.register(r'operations', views.OperationsViewSet, basename='operation')
router.register(r'positions', views.PositionsViewSet, basename='position')


urlpatterns = [
    path('', include(router.urls)),
    path('pocket-vectors/', views.PocketVectorsView.as_view(), name='pocket-vectors')
]
