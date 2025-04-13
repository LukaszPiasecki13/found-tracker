from django.shortcuts import render
from rest_framework import generics, viewsets
from rest_framework.views import APIView
from rest_framework import serializers
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework import status
from rest_framework.response import Response
from datetime import datetime
import plotly.graph_objects as go
import json
from drf_yasg.utils import swagger_auto_schema

from authentication.models import UserProfile
from .serializers import UserProfileSerializer, OperationSerializer, AssetAllocationSerializer, PocketSerializer, CurrencySerializer, AssetClassSerializer
from .models import Operation, AssetAllocation, Pocket, Currency, AssetClass
from .lib.AssetProcessor import AssetProcessor
from .lib.PocketMetrics import PocketMetrics


class UsersView(generics.ListCreateAPIView):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]


class UserRetrieveDestroyView(generics.RetrieveDestroyAPIView):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)


class OperationsViewSet(viewsets.ModelViewSet):
    serializer_class = OperationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        pocket_name = self.request.query_params.get('pocket_name', None)

        if pocket_name:
            queryset = Operation.objects.filter(
                owner=self.request.user, pocket_name=pocket_name)
        else:
            queryset = Operation.objects.filter(owner=self.request.user)
        return queryset.order_by('-date', '-created_at')

    def perform_create(self, serializer):
        # TODO: Walidacja danych
        processor = AssetProcessor(
            data=serializer.validated_data, owner=self.request.user)
        try:
            if serializer.validated_data['operation_type'] == 'buy':
                result = processor.buy_operation()
            elif serializer.validated_data['operation_type'] == 'sell':
                result = processor.subtract_objects()
            elif serializer.validated_data['operation_type'] == 'add_funds':
                result = processor.add_funds()
            elif serializer.validated_data['operation_type'] == 'withdraw_funds':
                result = processor.withdraw_funds()

        except Exception as e:
            raise serializers.ValidationError({"error": str(e)})

        if result:
            serializer.save(owner=self.request.user)
        else:
            return Response({"error": "Error with operation processing"}, status=status.HTTP_400_BAD_REQUEST)

    def perform_destroy(self, instance):
        processor = AssetProcessor(owner=self.request.user)
        try:
            processor.destory_operation(operation=instance)
        except Exception as e:
            raise e


class PocketsViewSet(viewsets.ModelViewSet):
    serializer_class = PocketSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):

        queryset = Pocket.objects.filter(owner=self.request.user)
        name = self.request.query_params.get('name', None)

        if name is not None:
            # Filter by name
            queryset = queryset.filter(name=name)

        return queryset

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class AssetAllocationViewSet(viewsets.ModelViewSet):
    serializer_class = AssetAllocationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        pocket_name = self.request.query_params.get('pocket_name', None)
        processor = AssetProcessor(owner=self.request.user)
        processor.update_assets(pocket_name=pocket_name)
        pocket = Pocket.objects.get(name=pocket_name)
        asset_allocations_querry = AssetAllocation.objects.filter(
            pocket=pocket)

        return asset_allocations_querry.order_by('asset__ticker')


class CurencyViewSet(viewsets.ModelViewSet):
    serializer_class = CurrencySerializer
    permission_classes = [IsAuthenticated]
    queryset = Currency.objects.all()


class AssetClassViewSet(viewsets.ModelViewSet):
    serializer_class = AssetClassSerializer
    permission_classes = [IsAuthenticated]
    queryset = AssetClass.objects.all()


class PocketVectorsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        pocket_name = request.query_params.get('pocketName')
        start_time_str = request.query_params.get('startDate')
        end_time_str = request.query_params.get('endDate')
        interval = request.query_params.get('interval')
        vectors = json.loads(request.query_params.get('vectors', '[]'))

        if pocket_name:
            operations = Operation.objects.filter(
                owner=request.user, pocket_name=pocket_name)
        else:
            operations = Operation.objects.filter(owner=request.user)
        if operations:
            operations = [operation for operation in operations]  # make a list
            operations.sort(key=lambda x: x.date)

            # if operations[0].date > datetime.strptime(start_time_str, '%Y-%m-%d').date():
            #     start_time_str = operations[0].date.strftime('%Y-%m-%d')

            try:
                start_time = datetime.strptime(start_time_str, '%Y-%m-%d')
                end_time = datetime.strptime(end_time_str, '%Y-%m-%d')

            except ValueError:
                return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

            pocket_vectors = {}

            metrics = PocketMetrics(
                interval=interval, start_time=start_time, end_time=end_time, operations=operations)
            
            pocket_vectors["date"] = metrics.get_date_vector()

            if not vectors:                
                pocket_vectors["assets"] = metrics.get_assets_vectors()
                pocket_vectors["asset_classes"] = metrics.get_asset_classes_vectors()
                pocket_vectors["net_deposits_vector"] = metrics.get_net_deposits_vector()
                pocket_vectors["transaction_cost_vector"] = metrics.get_transaction_cost_vector(
                )
                pocket_vectors["profit_vector"] = metrics.get_profit_vector()
                pocket_vectors["free_cash_vector"] = metrics.get_free_cash_vector()
                pocket_vectors["pocket_value_vector"] = metrics.get_pocket_value_vector()
            else:
                for vector in vectors:
                    if vector == "assets":
                        pocket_vectors["assets"] = metrics.get_assets_vectors()
                    if vector == "asset_classes":
                        pocket_vectors["asset_classes"] = metrics.get_asset_classes_vectors()
                    if vector == "net_deposits_vector":
                        pocket_vectors["net_deposits_vector"] = metrics.get_net_deposits_vector()
                    if vector == "transaction_cost_vector":
                        pocket_vectors["transaction_cost_vector"] = metrics.get_transaction_cost_vector(
                        )
                    if vector == "profit_vector":
                        pocket_vectors["profit_vector"] = metrics.get_profit_vector()
                    if vector == "free_cash_vector":
                        pocket_vectors["free_cash_vector"] = metrics.get_free_cash_vector()
                    if vector == "pocket_value_vector":
                        pocket_vectors["pocket_value_vector"] = metrics.get_pocket_value_vector

            # self.chart_working_function(
            #     x=pocket_vectors["date"], y=pocket_vectors["net_deposits_vector"], title="net_deposits_vector")
            # self.chart_working_function(
            #     x=pocket_vectors["date"], y=pocket_vectors["transaction_cost_vector"], title="transaction_cost_vector")
            # self.chart_working_function(
            #     x=pocket_vectors["date"], y=pocket_vectors["profit_vector"], title="profit_vector")
            # self.chart_working_function(
            #     x=pocket_vectors["date"], y=pocket_vectors["free_cash_vector"], title="free_cash_vector")
            # self.chart_working_function(
            #     x=pocket_vectors["date"], y=pocket_vectors["pocket_value_vector"], title="pocket_value_vector")

        else:
            pocket_vectors = {}

        return Response(pocket_vectors, status=status.HTTP_200_OK)

    @staticmethod
    def chart_working_function(x, y, title):
        # Create traces
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=x,
            y=y,
            mode='lines+markers',
            name='lines+markers')
        )

        fig.update_layout(
            title=title
        )

        fig.show()
