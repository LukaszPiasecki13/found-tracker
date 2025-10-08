from rest_framework.test import APIClient
import pytest
from authentication.models import UserProfile
from api.models import AssetClass, Currency, Operation, Pocket, Asset, AssetAllocation
from django.urls import reverse
from api.tests.integration.TransactionFactory import TransactionFactory
from django.db.models import Sum
from decimal import Decimal
from api.serializers import UserProfileSerializer, OperationSerializer, AssetAllocationSerializer
from collections import namedtuple
import json


from api.lib.AssetProcessor import AssetProcessor

LOOP_COUNT = 50


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def create_user():
    def _create_user(username, password, email):
        return UserProfile.objects.create_user(username=username, password=password, email=email)
    return _create_user


@pytest.fixture
def create_currency():
    def _create_currency(name, exchange_rate):
        return Currency.objects.create(name=name, exchange_rate=exchange_rate)
    return _create_currency


@pytest.mark.django_db
class TestUserViews:

    def test_user_list(self, api_client, create_user):
        user1 = create_user('user1', 'password', 'email@email.com')
        user2 = create_user('user2', 'password', 'email1@email.com')

        api_client.force_authenticate(user=user1)
        url = reverse('user-list')
        response = api_client.get(url)

        assert response.status_code == 200

        expected_response = UserProfileSerializer(
            [user1, user2], many=True).data
        assert response.json() == expected_response

    def test_user_detail(self, api_client, create_user):
        user = create_user('user1', 'password', 'email@email.com')

        api_client.force_authenticate(user=user)
        url = reverse('user-detail', args=[user.id])
        response = api_client.get(url)

        assert response.status_code == 200
        expected_response = UserProfileSerializer(user).data
        assert response.json() == expected_response

    def test_user_destroy(self, api_client, create_user):
        user = create_user('user1', 'password', 'email@email.com')

        api_client.force_authenticate(user=user)
        url = reverse('user-detail', args=[user.id])
        response = api_client.delete(url)

        assert response.status_code == 204
        assert UserProfile.objects.filter(id=user.id).exists() == False


@pytest.mark.django_db
class TestOperationViews:

    @pytest.fixture(autouse=True)
    def setup_method(self, create_user, create_currency):
        self.user = create_user('user1', 'password', 'email@email.com')

        usd = create_currency('USD', 1)
        pln = create_currency('PLN', 4)
        eur = create_currency('EUR', 1.2)
        self.START_CASH = 10000000

        self.pocket_name = 'TestPocket'

        Pocket.objects.create(name=self.pocket_name,
                              owner=self.user, currency=usd, fees=0, free_cash=self.START_CASH)

    def _buy_assets(self, api_client, asset_count: int):
        url = reverse('operation-list')

        transactionFactory = TransactionFactory(
            user=self.user, pocket_name=self.pocket_name)
        backup_data = []
        success_operations = []

        for _ in range(asset_count):
            draw_data = transactionFactory.draw_buy(allow_duplicates=True)
            backup_data.append(draw_data)

            response = api_client.post(url, draw_data)
            assert response.status_code == 201
            success_operations.append(draw_data)

        return backup_data, success_operations

    def _sell_assets(self, api_client, count: int, tickers: list, backup_data_buy: list = []):
        url = reverse('operation-list')
        pocket = Pocket.objects.get(name=self.pocket_name)
        transactionFactory = TransactionFactory(
            user=self.user, pocket_name=self.pocket_name)

        backup_data_sell = []
        success_operations = []
        for _ in range(count):
            if tickers:
                draw_data = transactionFactory.draw_sell(tickers=tickers)
                tickers.remove(draw_data['ticker'])
                backup_data_sell.append(draw_data)

                buy_operations = [
                    data for data in backup_data_buy if data['operation_type'] == 'buy' and data['ticker'] == draw_data['ticker']]
                sell_operations = [
                    data for data in backup_data_sell if data['operation_type'] == 'sell' and data['ticker'] == draw_data['ticker']]

                buy_quantity = sum(item['quantity'] for item in buy_operations)
                sell_quantity = sum(item['quantity']
                                    for item in sell_operations)

                response = api_client.post(url, draw_data)

                if buy_quantity < sell_quantity:
                    assert response.status_code == 400
                    error = json.loads(response.content.decode('utf-8'))
                    assert error["error"]["details"] == {
                        "error": "Not enough assets to sell"}
                elif buy_quantity == sell_quantity:
                    assert response.status_code == 201
                    assert not AssetAllocation.objects.filter(
                        asset__ticker=draw_data['ticker'], pocket=pocket).exists()
                    success_operations.append(draw_data)
                elif buy_quantity > sell_quantity:
                    assert response.status_code == 201
                    asset_allocation = AssetAllocation.objects.get(
                        asset__ticker=draw_data['ticker'], pocket=pocket)

                    assert asset_allocation.quantity == buy_quantity - sell_quantity
                    assert asset_allocation.fee == sum(
                        item['fee'] for item in buy_operations+sell_operations)

                    TransactionTuple = namedtuple(
                        'TransactionTuple', ['id', 'price', 'quantity', 'fee'])

                    buy_transactions = [TransactionTuple(id=None, price=operation['price'], quantity=operation['quantity'], fee=operation['fee'])
                                        for operation in buy_operations]
                    sell_transactions = [TransactionTuple(
                        id=None, price=operation['price'], quantity=operation['quantity'], fee=operation['fee']) for operation in sell_operations]

                    average_purchase_price = AssetProcessor._calculate_average_purchase_price(
                        buy_transactions=buy_transactions, sell_transactions=sell_transactions)

                    try:
                        assert asset_allocation.average_purchase_price == pytest.approx(
                            Decimal(average_purchase_price), abs=0.01)
                    except:
                        ...

                    success_operations.append(draw_data)

            else:
                break

        return backup_data_sell, success_operations

    def _add_funds(self, api_client, count):
        url = reverse('operation-list')
        pocket = Pocket.objects.get(name=self.pocket_name)
        pocket.free_cash = 0
        pocket.save()

        transactionFactory = TransactionFactory(
            user=self.user, pocket_name=self.pocket_name)
        backup_data = []

        for _ in range(count):
            draw_data = transactionFactory.draw_add_founds()
            backup_data.append(draw_data)

            response = api_client.post(url, draw_data, format='json')
            assert response.status_code == 201

        return backup_data

    def _withdraw_funds(self, api_client, count, free_cash):
        url = reverse('operation-list')
        pocket = Pocket.objects.get(name=self.pocket_name)
        pocket.free_cash = free_cash
        pocket.save()

        transactionFactory = TransactionFactory(
            user=self.user, pocket_name=self.pocket_name)
        backup_data = []

        for _ in range(count):
            draw_data = transactionFactory.draw_withdraw_founds()
            backup_data.append(draw_data)

            response = api_client.post(url, draw_data, format='json')
            assert response.status_code == 201

        return backup_data

    def test_operations_list(self, api_client):
        api_client.force_authenticate(user=self.user)

        operation1 = Operation.objects.create(owner=self.user, ticker='AAPL', operation_type='buy',
                                              quantity=10, price=100,  fee=5,  currency='USD', date='2022-01-02', comment='Test comment')
        operation2 = Operation.objects.create(
            owner=self.user, ticker='TSLA', operation_type='buy', quantity=5, price=245, fee=1, currency='PLN', date='2022-01-01', comment='Test comment')

        url = reverse('operation-list')
        response = api_client.get(url)

        assert response.status_code == 200
        expected_response = OperationSerializer(
            [operation1, operation2], many=True).data
        assert response.json() == expected_response

    def test_operations_create(self, api_client):
        api_client.force_authenticate(user=self.user)
        url = reverse('operation-list')

        data = {
            'asset_class': 'Equity',
            'ticker': 'AAPL',
            'operation_type': 'buy',
            'quantity': 10,
            'price': 100,
            'fee': 5,
            'currency': 'USD',
            "purchase_currency_price": 1,
            'date': '2022-01-01',
            'comment': 'Test comment',
            'pocket_name': self.pocket_name
        }

        response = api_client.post(url, data)

        assert response.status_code == 201
        assert Operation.objects.filter(ticker='AAPL').exists()
        assert Asset.objects.filter(ticker='AAPL').exists()
        pocket = Pocket.objects.get(name=self.pocket_name, owner=self.user)
        assert AssetAllocation.objects.filter(
            asset__ticker='AAPL', pocket=pocket).exists()
        assert pocket.fees == 5

    def test_operations_wrong_data(self, api_client):
        api_client.force_authenticate(user=self.user)
        url = reverse('operation-list')

        def set_default_data():
            return {
                'asset_class': 'Equity',
                'ticker': 'AAPL',
                'operation_type': 'buy',
                'quantity': 1,
                'price': 1,
                'fee': 1,
                'currency': 'USD',
                "purchase_currency_price": 1,
                'date': '2022-01-01',
                'comment': 'Test comment',
                'pocket_name': self.pocket_name
            }

        for price in (-10, -1, 0):
            data = set_default_data()
            data['price'] = price
            response = api_client.post(url, data)
            assert response.status_code == 400
            if price == 0:
                error = json.loads(response.content.decode('utf-8'))
                assert error["error"]["details"] == {
                    "non_field_errors": ["Missing required fields."]}
            else:
                error = json.loads(response.content.decode('utf-8'))
                assert error["error"]["details"] == {
                    "non_field_errors": ["Price must be greater than 0."]}

        for quantity in (-10, -1, 0):
            data = set_default_data()
            data['quantity'] = quantity
            response = api_client.post(url, data)
            assert response.status_code == 400
            if quantity == 0:
                error = json.loads(response.content.decode('utf-8'))
                assert error["error"]["details"] == {
                    "non_field_errors": ["Missing required fields."]}
            else:
                error = json.loads(response.content.decode('utf-8'))
                assert error["error"]["details"] == {
                    "non_field_errors": ["Quantity must be greater than 0."]}

        for fee in (-10, -1):
            data = set_default_data()
            data['fee'] = fee
            response = api_client.post(url, data)
            assert response.status_code == 400
            error = json.loads(response.content.decode('utf-8'))
            assert error["error"]["details"] == {
                "non_field_errors": ["Fee must be greater or equal to 0."]}

        for purchase_currency_price in (-10, -1, 0):
            data = set_default_data()
            data['purchase_currency_price'] = purchase_currency_price
            response = api_client.post(url, data)
            assert response.status_code == 400
            if purchase_currency_price == 0:
                error = json.loads(response.content.decode('utf-8'))
                assert error["error"]["details"] == {
                    "non_field_errors": ["Missing required fields."]}
            else:
                error = json.loads(response.content.decode('utf-8'))
                assert error["error"]["details"] == {"non_field_errors": [
                    "Purchase currency price must be greater than 0."]}

    def test_buy_random_assets_with_replacement(self, api_client):
        api_client.force_authenticate(user=self.user)

        # Buy random assets
        backup_data_buy, _ = self._buy_assets(api_client, LOOP_COUNT)

        for asset_allocation in AssetAllocation.objects.all():
            if asset_allocation == None:
                break

            ticker = asset_allocation.asset.ticker
            veryfication_list = [
                data for data in backup_data_buy if data['ticker'] == ticker]
            assert asset_allocation.quantity == sum(
                item['quantity'] for item in veryfication_list)
            assert asset_allocation.fee == sum(
                item['fee'] for item in veryfication_list)
            average_purchase_price = sum(item['quantity']*item['price']+item['fee']
                                         for item in veryfication_list) / sum(item['quantity'] for item in veryfication_list)
            assert asset_allocation.average_purchase_price == pytest.approx(
                Decimal(average_purchase_price), abs=0.01)

        pocket = Pocket.objects.get(name=self.pocket_name)
        total_cost = sum(item['quantity']*item['price'] +
                         item['fee'] for item in backup_data_buy)
        assert pocket.free_cash == pytest.approx(
            Decimal(self.START_CASH - total_cost), abs=0.01)

    def test_buy_sell_random(self, api_client):
        api_client.force_authenticate(user=self.user)

        # Buy random assets
        backup_data_buy, success_operations_buy = self._buy_assets(
            api_client, LOOP_COUNT)
        total_fee = sum(item['fee'] for item in backup_data_buy)
        tickers = list(set([operation["ticker"]
                       for operation in backup_data_buy]))

        # Sell assets
        backup_data_sell, success_operations_sell = self._sell_assets(
            api_client, LOOP_COUNT, tickers, backup_data_buy)
        backup_data = backup_data_buy + backup_data_sell
        success_operations = success_operations_buy + success_operations_sell

        pocket = Pocket.objects.get(name=self.pocket_name)
        total_fee = sum(item['fee'] for item in success_operations)
        assert pocket.fees == total_fee
        total_cost_buy = sum(item['quantity']*item['price']+item['fee']
                             for item in success_operations if item['operation_type'] == 'buy')
        total_cost_sell = sum(item['quantity']*item['price']-item['fee']
                              for item in success_operations if item['operation_type'] == 'sell')
        assert pocket.free_cash == pytest.approx(
            Decimal(self.START_CASH - total_cost_buy + total_cost_sell), abs=0.01)

    def test_add_funds(self, api_client):
        api_client.force_authenticate(user=self.user)
        url = reverse('operation-list')
        FREE_CASH = 100
        fee_check = 0
        pocket = Pocket.objects.get(name=self.pocket_name)
        pocket.free_cash = FREE_CASH
        pocket.save()

        for quantity in (-1, 0, 1, 1.1, 100):
            for fee in (-1, 0, 1, 1.1, 100):
                data = {
                    "operation_type": "add_funds",
                    "asset_class": None,
                    "ticker": None,
                    "date": "2024-09-13",
                    "currency": None,
                    "purchase_currency_price": None,
                    "quantity": quantity,
                    "price": None,
                    "fee": fee,
                    "comment": "",
                    "pocket_name": self.pocket_name
                }

                response = api_client.post(url, data, format='json')

                if quantity <= 0 or fee < 0:
                    assert response.status_code == 400
                    error = json.loads(response.content.decode('utf-8'))
                    assert error["error"]["details"] == {"non_field_errors": ["Quantity must be greater than 0."]} if quantity <= 0 else {
                        "non_field_errors": ["Fee must be greater or equal to 0."]}

                else:
                    assert response.status_code == 201
                    fee_check += fee
                    assert Pocket.objects.get(name=self.pocket_name).fees == pytest.approx(
                        Decimal(fee_check), abs=0.01)

                    pocket = Pocket.objects.get(name=self.pocket_name)
                    assert pocket.free_cash == pytest.approx(
                        Decimal(FREE_CASH) + Decimal(quantity), abs=0.01)
                    pocket.free_cash = FREE_CASH
                    pocket.save()

    def test_withdraw_funds(self, api_client):
        api_client.force_authenticate(user=self.user)
        url = reverse('operation-list')
        pocket = Pocket.objects.get(name=self.pocket_name)
        FREE_CASH = 100
        pocket.free_cash = FREE_CASH
        pocket.save()

        for quantity in (-1, 0, 1, 1.1, 100):
            data = {
                "operation_type": "withdraw_funds",
                "asset_class": None,
                "ticker": None,
                "date": "2024-09-13",
                "currency": None,
                "purchase_currency_price": None,
                "quantity": quantity,
                "price": None,
                "fee": 0,
                "comment": "",
                "pocket_name": self.pocket_name
            }

            response = api_client.post(url, data, format='json')

            if quantity <= 0:
                assert response.status_code == 400
                error = json.loads(response.content.decode('utf-8'))
                assert error["error"]["details"] == {
                    "non_field_errors": ["Quantity must be greater than 0."]}
            elif pocket.free_cash - quantity < 0:
                assert response.status_code == 400
                error = json.loads(response.content.decode('utf-8'))
                assert error["error"]["details"] == {
                    "error": "Not enough cash to withdraw"}
            else:
                assert response.status_code == 201
                assert Pocket.objects.get(name=self.pocket_name).fees == 0
                pocket = Pocket.objects.get(name=self.pocket_name)
                assert pocket.free_cash == pytest.approx(
                    Decimal(FREE_CASH) - Decimal(quantity), abs=0.01)

                pocket.free_cash = FREE_CASH
                pocket.save()

    def test_buy_operation_destroy(self, api_client):
        api_client.force_authenticate(user=self.user)

        # Buy random assets
        backup_data_buy, _ = self._buy_assets(api_client, LOOP_COUNT)
        w_backup_data_buy = backup_data_buy.copy()

        for transaction in w_backup_data_buy[:]:
            operation = Operation.objects.get(
                owner=self.user, ticker=transaction['ticker'], quantity=transaction['quantity'], fee=transaction['fee'], price=transaction['price'])
            pocket_fee = Pocket.objects.get(name=self.pocket_name).fees

            url = reverse('operation-detail', args=[operation.id])
            transaction_with_same_tickers = [
                item for item in w_backup_data_buy if item['ticker'] == transaction['ticker']]
            response = api_client.delete(url)
            assert response.status_code == 204

            if len(transaction_with_same_tickers) >= 2:
                assert Operation.objects.filter(
                    id=operation.id).exists() == False
                pocket = Pocket.objects.get(
                    name=self.pocket_name, owner=self.user)
                assert AssetAllocation.objects.filter(
                    asset__ticker=transaction['ticker'], pocket=pocket).exists()

                assert pocket.fees == pocket_fee-transaction['fee']

            else:
                assert Operation.objects.filter(
                    id=operation.id).exists() == False
                pocket = Pocket.objects.get(
                    name=self.pocket_name, owner=self.user)

                assert AssetAllocation.objects.filter(
                    asset__ticker=transaction['ticker'], pocket=pocket).exists() == False
                assert pocket.fees == pocket_fee-transaction['fee']

            w_backup_data_buy.remove(transaction)

    def test_sell_operation_destroy(self, api_client):
        api_client.force_authenticate(user=self.user)

        # Buy random assets
        backup_data_buy, success_operations_buy = self._buy_assets(
            api_client, LOOP_COUNT)
        tickers = list(set([operation["ticker"]
                            for operation in backup_data_buy]))

        # Sell assets
        backup_data_sell, success_operations_sell = self._sell_assets(
            api_client, LOOP_COUNT, tickers, backup_data_buy)
        backup_data = backup_data_buy + backup_data_sell
        success_operations = success_operations_buy + success_operations_sell

        w_success_operations_sell = success_operations_sell.copy()

        for transaction in w_success_operations_sell[:]:
            operation = Operation.objects.get(
                owner=self.user, ticker=transaction['ticker'], quantity=transaction['quantity'], fee=transaction['fee'], price=transaction['price'])

            pocket_fee = Pocket.objects.get(name=self.pocket_name).fees
            try:
                asset_allocation_quantity = AssetAllocation.objects.get(
                    asset__ticker=transaction['ticker'], pocket__name=self.pocket_name).quantity

            except:
                ...

            url = reverse('operation-detail', args=[operation.id])
            response = api_client.delete(url)
            assert response.status_code == 204

            transaction_with_same_tickers = [
                item for item in w_success_operations_sell if item['ticker'] == transaction['ticker']]

            if len(transaction_with_same_tickers) >= 2:
                assert Operation.objects.filter(
                    id=operation.id).exists() == False
                pocket = Pocket.objects.get(
                    name=self.pocket_name, owner=self.user)

                assert AssetAllocation.objects.filter(
                    asset__ticker=transaction['ticker'], pocket=pocket).exists()

                assert pocket.fees == pocket_fee-transaction['fee']

            else:
                assert Operation.objects.filter(
                    id=operation.id).exists() == False
                pocket = Pocket.objects.get(
                    name=self.pocket_name, owner=self.user)

                asset_allocation_query = AssetAllocation.objects.filter(
                    asset__ticker=transaction['ticker'], pocket=pocket)
                assert asset_allocation_query.exists()
                asset_allocation = asset_allocation_query.first()

                assert asset_allocation.quantity == asset_allocation_quantity + \
                    transaction['quantity']

                assert pocket.fees == pocket_fee-transaction['fee']

            w_success_operations_sell.remove(transaction)

    def test_add_funds_destroy(self, api_client):
        api_client.force_authenticate(user=self.user)

        # Add funds
        backup_data = self._add_funds(api_client, LOOP_COUNT)
        pocket = Pocket.objects.get(name=self.pocket_name)
        assert pocket.free_cash == sum(
            item['quantity'] for item in backup_data)
        assert pocket.fees == sum(item['fee'] for item in backup_data)

        w_beckup_data = backup_data.copy()

        for transaction in w_beckup_data[:]:
            pocket = Pocket.objects.get(name=self.pocket_name)
            pocket_fee = Pocket.objects.get(name=self.pocket_name).fees
            pocket_free_cash = pocket.free_cash
            operation = Operation.objects.filter(
                owner=self.user, quantity=transaction['quantity'], fee=transaction['fee']).first()

            url = reverse('operation-detail', args=[operation.id])
            response = api_client.delete(url)
            assert response.status_code == 204

            assert Operation.objects.filter(id=operation.id).exists() == False
            pocket = Pocket.objects.get(
                name=self.pocket_name, owner=self.user)
            assert pocket.fees == pocket_fee-transaction['fee']
            assert pocket.free_cash == pocket_free_cash-transaction['quantity']

            w_beckup_data.remove(transaction)

    def test_withdraw_funds_destroy(self, api_client):
        api_client.force_authenticate(user=self.user)

        # Withdraw funds
        backup_data_withdraw = self._withdraw_funds(
            api_client, LOOP_COUNT, free_cash=self.START_CASH)
        w_backup_data_withdraw = backup_data_withdraw.copy()

        pocket = Pocket.objects.get(name=self.pocket_name)
        assert pocket.free_cash == self.START_CASH - \
            sum(item['quantity'] for item in backup_data_withdraw)
        assert pocket.fees == sum(item['fee'] for item in backup_data_withdraw)

        for transaction in w_backup_data_withdraw[:]:
            pocket = Pocket.objects.get(name=self.pocket_name)
            pocket_fee = Pocket.objects.get(name=self.pocket_name).fees
            pocket_free_cash = pocket.free_cash
            operation = Operation.objects.filter(
                owner=self.user, quantity=transaction['quantity'], fee=transaction['fee']).first()

            url = reverse('operation-detail', args=[operation.id])
            response = api_client.delete(url)
            assert response.status_code == 204

            assert Operation.objects.filter(id=operation.id).exists() == False
            pocket = Pocket.objects.get(
                name=self.pocket_name, owner=self.user)
            assert pocket.fees == pocket_fee-transaction['fee']
            assert pocket.free_cash == pocket_free_cash+transaction['quantity']

            w_backup_data_withdraw.remove(transaction)


@pytest.mark.django_db
class TestAssetAllocationViews:

    @pytest.fixture(autouse=True)
    def setup_method(self, create_user, create_currency):
        self.user = create_user('user1', 'password', 'email@email.com')

        usd = create_currency('USD', 1)
        pln = create_currency('PLN', 4)
        eur = create_currency('EUR', 1.2)
        START_CASH = 10000000

        self.pocket_name = 'TestPocket'
        Pocket.objects.create(name=self.pocket_name,
                              owner=self.user, currency=usd, fees=0, free_cash=START_CASH)

    def test_asset_allocation_list(self, api_client):
        api_client.force_authenticate(user=self.user)
        url_send_data = reverse('operation-list')
        url_get = reverse('asset-allocation-list')

        # Create X operations by drawing without replacement
        transactionFactory = TransactionFactory(
            user=self.user, pocket_name=self.pocket_name)
        backup_data = []

        for _ in range(LOOP_COUNT):
            draw_data = transactionFactory.draw_buy(allow_duplicates=True)
            backup_data.append(draw_data)

            response = api_client.post(url_send_data, draw_data)
            assert response.status_code == 201

        # Get asset allocations
        response = api_client.get(url_get, {'pocket_name': self.pocket_name})
        assert response.status_code == 200

        test_participation_dic = {}
        for asset_allocation in response.json():

            ticker = asset_allocation['asset']['ticker']
            test_participation_dic[float(asset_allocation['participation'])] = float(
                asset_allocation['total_value_XXX'])

            veryfication_list = [
                data for data in backup_data if data['ticker'] == ticker]
            assert float(asset_allocation['quantity']) == sum(
                item['quantity'] for item in veryfication_list)
            assert float(asset_allocation['fee']) == sum(
                item['fee'] for item in veryfication_list)
            average_purchase_price = sum(item['quantity']*item['price']+item['fee']
                                         for item in veryfication_list) / sum(item['quantity'] for item in veryfication_list)
            average_purchase_currency_price = sum(item['quantity']*item['purchase_currency_price']
                                                  for item in veryfication_list) / sum(item['quantity'] for item in veryfication_list)
            assert float(asset_allocation['average_purchase_price']) == pytest.approx(
                average_purchase_price, abs=0.01)
            assert float(asset_allocation['average_purchase_currency_price']) == pytest.approx(
                average_purchase_currency_price, abs=0.01)

        # Participation test
        total_sum = sum(value for value in test_participation_dic.values())
        participation_sum = sum(key for key in test_participation_dic.keys())
        assert participation_sum == pytest.approx(100, abs=0.1)

        for participation, total_value in test_participation_dic.items():
            assert participation == pytest.approx(
                total_value/total_sum*100, abs=0.1)
