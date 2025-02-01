from rest_framework import serializers
from authentication.models import UserProfile
from . import models


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = "__all__"


class OperationSerializer(serializers.ModelSerializer):
    owner = serializers.PrimaryKeyRelatedField(
        read_only=True, default=serializers.CurrentUserDefault())

    class Meta:
        model = models.Operation
        fields = "__all__"

    ticker = serializers.CharField(required=False, allow_null=True)
    asset_class = serializers.CharField(required=False, allow_null=True)
    currency = serializers.CharField(required=False, allow_null=True)
    price = serializers.FloatField(required=False, allow_null=True)
    purchase_currency_price = serializers.FloatField(
        required=False, allow_null=True)

    def validate(self, data):
        operation_type = data.get('operation_type')

        if operation_type in ['buy', 'sell']:
            if not data.get('ticker') or not data.get('asset_class') or not data.get('currency') or not data.get('price') or not data.get('purchase_currency_price') or not data.get('quantity'):
                raise serializers.ValidationError("Missing required fields.")
            elif data['quantity'] <= 0:
                raise serializers.ValidationError(
                    "Quantity must be greater than 0.")
            elif data['price'] <= 0:
                raise serializers.ValidationError(
                    "Price must be greater than 0.")
            elif data['fee'] < 0:
                raise serializers.ValidationError(
                    "Fee must be greater or equal to 0.")
            elif data['purchase_currency_price'] <= 0:
                raise serializers.ValidationError(
                    "Purchase currency price must be greater than 0.")

        elif operation_type == 'add_funds' or operation_type == 'withdraw_funds':
            if data['quantity'] <= 0:
                raise serializers.ValidationError(
                    "Quantity must be greater than 0.")
            elif data['fee'] < 0:
                raise serializers.ValidationError(
                    "Fee must be greater or equal to 0.")

        return data


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Currency
        fields = "__all__"


class PocketSerializer(serializers.ModelSerializer):
    currency = serializers.PrimaryKeyRelatedField(queryset=models.Currency.objects.all())
    owner = serializers.PrimaryKeyRelatedField(
        read_only=True, default=serializers.CurrentUserDefault())

    class Meta:
        model = models.Pocket
        fields = "__all__"

    def validate_name(self, name):
        if models.Pocket.objects.filter(name=name, owner=self.context['request'].user).exists():
            raise serializers.ValidationError(
                "Pocket with this name already exists.")
        return name


class CurencySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Currency
        fields = "__all__"


class AssetClassSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.AssetClass
        fields = "__all__"

class AssetSerializer(serializers.ModelSerializer):
    currency = CurrencySerializer()

    class Meta:
        model = models.Asset
        fields = "__all__"


class AssetAllocationSerializer(serializers.ModelSerializer):
    pocket = PocketSerializer()
    asset = AssetSerializer()

    class Meta:
        model = models.AssetAllocation
        fields = "__all__"
