from rest_framework import serializers
from assets.serializers import AssetDetailSerializer
from assets.models import Currency, Asset, AssetClass
from assets.serializers import CurrencySerializer
from . import models


class PositionSerializer(serializers.ModelSerializer):
    """
    Serializator dla Pozycji w portfelu.
    Głównie do odczytu, ponieważ pozycje są modyfikowane przez Operacje.
    """

    asset = AssetDetailSerializer(read_only=True)

    # Pola obliczeniowe oparte na @property z modelu
    cost_basis = serializers.DecimalField(max_digits=18, decimal_places=3, read_only=True)
    cost_basis_in_pocket_currency = serializers.DecimalField(max_digits=18, decimal_places=3, read_only=True)
    market_value = serializers.DecimalField(max_digits=18, decimal_places=3, read_only=True)
    unrealized_pnl = serializers.DecimalField(max_digits=18, decimal_places=3, read_only=True)
    return_pct = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)
    pocket_weight_pct = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)
    
    class Meta:
        model = models.Position
        fields = "__all__"
        # read_only_fields = fields






class PocketSerializer(serializers.ModelSerializer):
    owner = serializers.HiddenField(default=serializers.CurrentUserDefault())
    owner_username = serializers.CharField(source='owner.username', read_only=True)
    base_currency = CurrencySerializer(read_only=True)
    base_currency_code = serializers.SlugRelatedField(
        source='base_currency',
        slug_field='code',
        queryset=Currency.objects.all(),
        write_only=True
    )


    class Meta:
        model = models.Pocket
        fields = ['id', 'owner', 'owner_username', 'name', 'base_currency', 'base_currency_code', 'cash_balance', 'total_deposited', 'is_active', 'created_at']
        read_only_fields = ['owner_username', 'created_at', 'base_currency']

    def validate_name(self, name):
        if models.Pocket.objects.filter(name=name, owner=self.context['request'].user).exists():
            raise serializers.ValidationError(
                "Pocket with this name already exists.")
        return name


class PocketDetailSerializer(PocketSerializer):
    """
    Rozszerzony serializator dla Portfela (do widoku szczegółowego).
    Zawiera zagnieżdżone pozycje i obliczone wartości.
    """

    positions = PositionSerializer(many=True, read_only=True)
    total_fees = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    
    # # Implementacja logiki dla pól, które były zakomentowane w modelu
    # positions_value = serializers.SerializerMethodField()
    # total_value = serializers.SerializerMethodField()
    # total_profit_loss = serializers.SerializerMethodField()
    # total_return_pct = serializers.SerializerMethodField()

    class Meta(PocketSerializer.Meta):
        # Rozszerzamy listę pól o te z serializatora szczegółowego
        fields = PocketSerializer.Meta.fields + [
            'positions', 'total_fees', 'positions_value', 'total_value',
            'total_profit_loss', 'total_return_pct', 'updated_at'
        ]
        read_only_fields = PocketSerializer.Meta.read_only_fields + ['updated_at']

    




class OperationSerializer(serializers.ModelSerializer):
    pocket = serializers.PrimaryKeyRelatedField(queryset=models.Pocket.objects.all())
    asset = serializers.PrimaryKeyRelatedField(
        queryset=Asset.objects.all(),
        required=False,  # Nie jest wymagane dla depozytów/wypłat
        allow_null=True
    )
    ticker = serializers.CharField(write_only=True, required=False, allow_blank=True)
    asset_class = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = models.Operation
        fields = "__all__"
        read_only_fields = ['created_at', 'updated_at']


    def validate(self, data):
            operation_type = data.get('operation_type')
            asset = data.get('asset')

            asset_operations = ['buy', 'sell', 'dividend']
            cash_operations = ['deposit', 'withdrawal']

            ticker = data.pop("ticker", "").strip()
            asset_class_name = data.pop("asset_class", None)

            if not asset and ticker:
                # Try to get existing asset first
                try:
                    asset = Asset.objects.get(ticker=ticker.upper())
                except Asset.DoesNotExist:
                    # If asset_class is provided, create the asset
                    if asset_class_name:
                        asset_class, _ = AssetClass.objects.get_or_create(name=asset_class_name)
                        # Get currency from pocket if available
                        pocket = data.get('pocket')
                        currency = pocket.base_currency if pocket else Currency.objects.first()
                        
                        asset = Asset.objects.create(
                            ticker=ticker.upper(),
                            name=ticker.upper(),
                            asset_class=asset_class,
                            currency=currency
                        )
                    else:
                        raise serializers.ValidationError("Asset does not exist. Please provide asset_class to create it.")

                data["asset"] = asset

            if operation_type in asset_operations and not asset:
                raise serializers.ValidationError(f"Operation type '{operation_type}' requires an associated asset or ticker.")
            
            if operation_type in cash_operations and asset:
                raise serializers.ValidationError(f"Operation type '{operation_type}' should not have an asset associated.")

            if operation_type in ['buy', 'sell']:
                if 'price' not in data or 'fx_rate' not in data or 'quantity' not in data:
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
                elif data['fx_rate'] <= 0:
                    raise serializers.ValidationError(
                        "Foreign exchange rate must be greater than 0.")
                
            elif operation_type in ['deposit', 'withdrawal']:
                if 'amount' not in data:
                    raise serializers.ValidationError("Missing required fields.")
                if data['amount'] <= 0:
                    raise serializers.ValidationError(
                        "Amount must be greater than 0.")
                elif data['fee'] < 0:
                    raise serializers.ValidationError(
                        "Fee must be greater or equal to 0.")


            return data