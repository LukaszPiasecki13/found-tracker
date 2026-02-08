from django.contrib import admin
from .models import Currency, AssetClass, Asset


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ['code', 'exchange_rate', 'base_currency']
    search_fields = ['code']


@admin.register(AssetClass)
class AssetClassAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ['ticker', 'name', 'asset_class', 'currency', 'current_price', 'updated_at']
    list_filter = ['asset_class', 'currency']
    search_fields = ['ticker', 'name']
    readonly_fields = ['updated_at']
