import pytest
from authentication.models import UserProfile
from assets.models import AssetClass, Currency, Asset
from portfolios.models import Operation, Pocket, Position

@pytest.mark.django_db
class TestOperationModel:
    def setup_method(self):
        self.user = UserProfile.objects.create_user(username='testuser', password='password')
        currency = Currency.objects.create(code='USD', exchange_rate=1)
        self.pocket = Pocket.objects.create(owner=self.user, name='Test Pocket', base_currency=currency)
        asset_class = AssetClass.objects.create(name='Stock')
        self.asset = Asset.objects.create(
            ticker='AAPL',
            name='Apple Inc.',
            asset_class=asset_class,
            currency=currency,
            current_price=150
        )

    def test_create_model(self):
        from datetime import datetime
        operation = Operation.objects.create(
            pocket=self.pocket,
            asset=self.asset,
            operation_type='buy',
            quantity=10,
            price=100,
            fee=5,
            fx_rate=1,
            notes='Test operation',
            operation_date=datetime(2021, 1, 1)
        )

        assert isinstance(operation, Operation)
        assert operation.pocket == self.pocket
        assert operation.asset == self.asset

@pytest.mark.django_db
class TestAssetClassModel:
    def setup_method(self):
        self.asset_class = AssetClass.objects.create(name='shares')
    
    def test_create_model(self):
        assert isinstance(self.asset_class, AssetClass)
        assert str(self.asset_class) == 'shares'
    
@pytest.mark.django_db
class TestAssetModel:
    def setup_method(self):
        currency = Currency.objects.create(code='USD', exchange_rate=1)
        asset_class = AssetClass.objects.create(name='shares')
        self.asset = Asset.objects.create(
            ticker='AAPL',
            name='Apple',
            asset_class=asset_class,
            currency=currency
        )

    def test_create_model(self):
        assert isinstance(self.asset, Asset)
        assert 'Apple' in str(self.asset)

    
@pytest.mark.django_db
class TestPocketModel:
    def setup_method(self):
        self.user = UserProfile.objects.create_user(username='testuser', password='password')
        self.currency = Currency.objects.create(code='USD', exchange_rate=1)
        self.pocket = Pocket.objects.create(owner=self.user, name='Pocket', base_currency=self.currency)

    def test_create_model(self):
        assert isinstance(self.pocket, Pocket)
        assert 'Pocket' in str(self.pocket)
        assert self.pocket.owner == self.user


@pytest.mark.django_db
class TestAssetAllocationModel:
    def setup_method(self):
        self.user = UserProfile.objects.create_user(username='testuser', password='password')
        self.currency = Currency.objects.create(code='USD', exchange_rate=1)
        self.pocket = Pocket.objects.create(owner=self.user, name='Pocket', base_currency=self.currency)
        asset_class = AssetClass.objects.create(name='shares')
        self.asset = Asset.objects.create(
            ticker='AAPL',
            name='Apple',
            asset_class=asset_class,
            currency=self.currency
        )
        self.asset_allocation = Position.objects.create(
            pocket=self.pocket,
            asset=self.asset,
            quantity=10,
            average_buy_price=100
        )

    def test_create_model(self):
        assert isinstance(self.asset_allocation, Position)
        assert self.asset_allocation.pocket == self.pocket
        assert self.asset_allocation.asset == self.asset
        assert self.asset_allocation.quantity == 10
        assert self.asset_allocation.average_buy_price == 100



    def teardown_method(self):
        self.asset_allocation.delete()
        self.asset.delete()
        self.pocket.delete()
        self.user.delete()

    



        
