from rest_framework import serializers
from .models import Currency, AssetClass, Asset


class CurrencySerializer(serializers.ModelSerializer):
    """Serializer for Currency model."""
    
    class Meta:
        model = Currency
        fields = "__all__"


class AssetClassSerializer(serializers.ModelSerializer):
    """Serializer for AssetClass model."""
    
    class Meta:
        model = AssetClass
        fields = "__all__"


class AssetSerializer(serializers.ModelSerializer):
    """
    Basic serializer for Asset model.
    Uses PK references for related fields.
    """
    asset_class = serializers.PrimaryKeyRelatedField(queryset=AssetClass.objects.all())
    currency = serializers.PrimaryKeyRelatedField(queryset=Currency.objects.all())
    
    class Meta:
        model = Asset
        fields = "__all__"
        read_only_fields = ['updated_at']

    def create(self, validated_data):
        validated_data['ticker'] = validated_data['ticker'].upper().strip()
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        if 'ticker' in validated_data:
            validated_data['ticker'] = validated_data['ticker'].upper().strip()
        return super().update(instance, validated_data)


class AssetDetailSerializer(AssetSerializer):
    """
    Extended serializer for Asset detail view.
    Shows nested objects for relationships.
    """
    asset_class = AssetClassSerializer(read_only=True)
    currency = CurrencySerializer(read_only=True)
