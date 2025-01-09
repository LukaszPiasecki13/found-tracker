import pytest
from authentication.models import UserProfile
from api.models import AssetClass, Currency, Operation, Pocket, Asset, AssetAllocation

@pytest.mark.django_db
class TestOperationModel:
    def setup_method(self):
        self.user = UserProfile.objects.create_user(username='testuser', password = 'password')

    def test_create_model(self):
        operation = Operation.objects.create(
            operation_type = 'Buy',
            asset_class = 'Equity',
            ticker = 'AAPL',
            date = '2021-01-01',
            currency = 'USD',
            quantity = 10,
            price = 100,
            fee = 0,
            comment = 'Comment',
            owner = self.user
        )

        assert isinstance(operation, Operation)
        assert operation.owner == self.user

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
        self.asset = Asset.objects.create(ticker='AAPL', name='Apple', asset_class='shares', currency=Currency.objects.create(name='USD'))

    def test_create_model(self):
        assert isinstance(self.asset, Asset)
        assert str(self.asset) == 'Apple'

    
@pytest.mark.django_db
class TestPocketModel:
    def setup_method(self):
        self.user = UserProfile.objects.create_user(username='testuser', password = 'password')
        self.currency = Currency.objects.create(name='USD', reference_currency_name='USD', exchange_rate=1)
        self.pocket = Pocket.objects.create(owner=self.user, name='Pocket', fees=0, currency=self.currency)

    def test_create_model(self):
        assert isinstance(self.pocket, Pocket)
        assert str(self.pocket) == 'Pocket'
        assert self.pocket.owner == self.user


@pytest.mark.django_db
class TestAssetAllocationModel:
    def setup_method(self):
        self.user = UserProfile.objects.create_user(username='testuser', password = 'password')
        self.currency = Currency.objects.create(name='USD', reference_currency_name='USD', exchange_rate=1)
        self.pocket = Pocket.objects.create(owner=self.user, name='Pocket', fees=0, currency=self.currency)
        self.asset = Asset.objects.create(ticker='AAPL', name='Apple', asset_class='shares', currency=Currency.objects.create(name='USD') )
        self.asset_allocation = AssetAllocation.objects.create(pocket=self.pocket, asset=self.asset, quantity=10, average_purchase_price=100)

    def test_create_model(self):
        assert isinstance(self.asset_allocation, AssetAllocation)
        assert self.asset_allocation.pocket == self.pocket
        assert self.asset_allocation.asset == self.asset
        assert self.asset_allocation.quantity == 10
        assert self.asset_allocation.average_purchase_price == 100



    def teardown_method(self):
        self.asset_allocation.delete()
        self.asset.delete()
        self.pocket.delete()
        self.user.delete()

    



        
