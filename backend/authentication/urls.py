from django.urls import path, include
from . import views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    # Authentication
    path('register/', views.CreateUserView.as_view(), name='register'),
    path('token/', TokenObtainPairView.as_view(), name='get_token'),
    path('token/refresh/', TokenRefreshView.as_view(), name='refresh_token'),
    path('api-auth/', include('rest_framework.urls')),
    
    # User Management
    path('users/', views.UsersView.as_view(), name='user-list'),
    path('users/<int:pk>/', views.UserRetrieveDestroyView.as_view(), name='user-detail'),
    path('users/me/', views.CurrentUserView.as_view(), name='current-user'),
]
