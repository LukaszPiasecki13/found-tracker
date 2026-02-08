from authentication.models import UserProfile
from rest_framework import serializers


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""
    class Meta:
        model = UserProfile
        fields = ["id", "username", "email", "password"]
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        user = UserProfile.objects.create_user(**validated_data)
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for full user profile"""
    class Meta:
        model = UserProfile
        fields = "__all__" 

    