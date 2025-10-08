from django.urls import path, include
from . import views
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'operations', views.OperationsViewSet, basename='operation')
router.register(r'pockets', views.PocketsViewSet, basename='pocket')
router.register(r'asset-allocations',
                views.AssetAllocationViewSet, basename='asset-allocation')
router.register(r'currencies', views.CurencyViewSet, basename='currency')
router.register(r'asset-classes', views.AssetClassViewSet,
                basename='asset-class')


urlpatterns = [
    path('users/', views.UsersView.as_view(), name='user-list'),
    path('users/<int:pk>/', views.UserRetrieveDestroyView.as_view(),
         name='user-detail'),
    path('users/me/', views.CurrentUserView.as_view(), name='current-user'),
    path('', include(router.urls)),
    path('pocket-vectors/', views.PocketVectorsView.as_view(), name='pocket-vectors')
]
