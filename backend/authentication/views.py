from authentication.models import UserProfile
from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from .serializers import UserSerializer, UserProfileSerializer


class CreateUserView(generics.CreateAPIView):
    """Register a new user"""
    queryset = UserProfile.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]


class UsersView(generics.ListCreateAPIView):
    """List all users or create a new one"""
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]


class UserRetrieveDestroyView(generics.RetrieveDestroyAPIView):
    """Retrieve or delete a specific user"""
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]


class CurrentUserView(APIView):
    """Get current logged-in user profile"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)
