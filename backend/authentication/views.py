from django.shortcuts import render
from django.views import View
import json
from django.http import JsonResponse
from authentication.models import UserProfile
from validate_email import validate_email
from django.contrib import messages
from django.contrib import auth
from django.shortcuts import redirect
from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from .serializers import UserSerializer


class CreateUserView(generics.CreateAPIView):
    queryset = UserProfile.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]
