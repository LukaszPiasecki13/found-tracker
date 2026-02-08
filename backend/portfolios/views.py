from rest_framework import generics, viewsets
from rest_framework.views import APIView
from rest_framework import serializers
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework import status
from rest_framework.response import Response
from datetime import datetime
import plotly.graph_objects as go
import json
from django.core.exceptions import PermissionDenied

from .serializers import OperationSerializer, PositionSerializer, PocketSerializer
from .models import Operation, Position, Pocket
from .services import TransactionService, PortfolioService
from .analytics import PocketMetrics



class PocketsViewSet(viewsets.ModelViewSet):
    serializer_class = PocketSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Pocket.objects.filter(owner=self.request.user)

    def get_object(self):
        obj = super().get_object()
        if obj.owner != self.request.user:
            raise PermissionDenied("You do not have permission to access this pocket.")
        return obj



class PositionsViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PositionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):

        pocket_name = self.request.query_params.get('pocket_name', None)
        if not pocket_name:
            raise serializers.ValidationError("pocket_name query parameter is required.")

        pocket = Pocket.objects.get(name=pocket_name, owner=self.request.user)
        if not pocket:
            raise serializers.ValidationError("Pocket not found.")


        #TODO
        # processor = AssetProcessor(owner=self.request.user)
        # processor.update_assets(pocket_name=pocket_name)
        
        position_querry = Position.objects.filter(
            pocket=pocket)

        return position_querry.order_by('asset__ticker')


class OperationsViewSet(viewsets.ModelViewSet):
    serializer_class = OperationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        pocket_name = self.request.query_params.get('pocket_name', None)

        if pocket_name:
            queryset = Operation.objects.filter(pocket__owner=self.request.user,
                                                pocket__name=pocket_name)
        else:
            queryset = Operation.objects.filter(pocket__owner=self.request.user)
        return queryset.order_by('-operation_date', '-created_at')
    
    def get_object(self):
        obj = super().get_object()
        if obj.pocket.owner != self.request.user:
            raise PermissionDenied("You do not have permission to access this operation.")
        return obj

    def perform_create(self, serializer):
        """Execute operation using appropriate service."""
        operation_type = serializer.validated_data['operation_type']
        transaction_service = TransactionService(owner=self.request.user)
        portfolio_service = PortfolioService(owner=self.request.user)
        
        try:
            result = False
            
            if operation_type == 'buy':
                result = transaction_service.execute_buy(serializer.validated_data)
            elif operation_type == 'sell':
                result = transaction_service.execute_sell(serializer.validated_data)
            elif operation_type == 'deposit':
                result = portfolio_service.deposit_cash(serializer.validated_data)
            elif operation_type == 'withdrawal':
                result = portfolio_service.withdraw_cash(serializer.validated_data)
            
            if result:
                serializer.save()
            else:
                raise serializers.ValidationError({"error": "Operation processing failed"})
                
        except Exception as e:
            raise serializers.ValidationError({"error": str(e)})

    def perform_destroy(self, instance):
        """Delete operation and reverse its effects."""
        portfolio_service = PortfolioService(owner=self.request.user)
        try:
            portfolio_service.delete_operation(operation=instance)
        except Exception as e:
            raise serializers.ValidationError({"error": str(e)})


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
                pocket_vectors["net_deposits_vector"] = metrics.get_net_deposits_vector(
                )
                pocket_vectors["transaction_cost_vector"] = metrics.get_transaction_cost_vector(
                )
                pocket_vectors["profit_vector"] = metrics.get_profit_vector()
                pocket_vectors["free_cash_vector"] = metrics.get_free_cash_vector()
                pocket_vectors["pocket_value_vector"] = metrics.get_pocket_value_vector(
                )
            else:
                for vector in vectors:
                    if vector == "assets":
                        pocket_vectors["assets"] = metrics.get_assets_vectors()
                    if vector == "asset_classes":
                        pocket_vectors["asset_classes"] = metrics.get_asset_classes_vectors(
                        )
                    if vector == "net_deposits_vector":
                        pocket_vectors["net_deposits_vector"] = metrics.get_net_deposits_vector(
                        )
                    if vector == "transaction_cost_vector":
                        pocket_vectors["transaction_cost_vector"] = metrics.get_transaction_cost_vector(
                        )
                    if vector == "profit_vector":
                        pocket_vectors["profit_vector"] = metrics.get_profit_vector(
                        )
                    if vector == "free_cash_vector":
                        pocket_vectors["free_cash_vector"] = metrics.get_free_cash_vector(
                        )
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


