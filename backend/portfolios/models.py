from django.db import models
from authentication.models import UserProfile
from assets.models import Currency, AssetClass, Asset


class Pocket(models.Model):
    owner = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    base_currency = models.ForeignKey(
        Currency, on_delete=models.PROTECT, related_name='pockets')

    cash_balance = models.DecimalField(
        max_digits=18, decimal_places=3, default=0, help_text="Available cash")
    total_deposited = models.DecimalField(
        max_digits=18, decimal_places=3, default=0, help_text="Total deposits - withdrawals")

    assets = models.ManyToManyField('assets.Asset', through='Position', blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['owner', 'name'],
                name='unique_pocket_per_user'
            )
        ]

    def __str__(self):
        return f"{self.owner.username} - {self.name}"
    
    @property
    def total_fees(self):
        """Suma opłat ze wszystkich operacji"""
        from django.db.models import Sum
        return self.oerations.aggregate(
            total=Sum('fee')
        )['total'] or 0

    @property
    def positions_value(self):
        """Wartość wszystkich pozycji w walucie portfela"""
        from decimal import Decimal
        total = Decimal('0')
        for position in self.positions.all():
            total += position.market_value
        return total

    @property
    def total_value(self):
        """Całkowita wartość portfela (gotówka + pozycje)"""
        return self.cash_balance + self.positions_value

    @property
    def total_profit_loss(self):
        """Całkowity zysk/strata"""
        return self.total_value - self.total_deposited
    
    @property
    def total_return_pct(self):
        """Stopa zwrotu w %"""
        if self.total_deposited == 0:
            return 0
        return (self.total_profit_loss / self.total_deposited) * 100


class Position(models.Model):
    pocket = models.ForeignKey(
        Pocket, on_delete=models.CASCADE,  related_name='positions')
    asset = models.ForeignKey(
        Asset, on_delete=models.CASCADE, related_name='positions')

    quantity = models.DecimalField(
        max_digits=18, decimal_places=9, default=0)
    average_buy_price = models.DecimalField(
        max_digits=18, decimal_places=9, default=0,  help_text="Weighted average purchase price in asset currency")
    average_fx_rate = models.DecimalField(
        max_digits=18, decimal_places=9, default=1,  help_text="Weighted average FX rate at purchase time"
    )

    total_fees = models.DecimalField(
        max_digits=18, decimal_places=2, default=0)
    total_dividends = models.DecimalField(
        max_digits=18, decimal_places=2, default=0)

    opened_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        constraints = [
            models.UniqueConstraint(
                fields=['pocket', 'asset'],
                name='unique_position_per_pocket'
            )
        ]
        indexes = [
            models.Index(fields=['pocket', 'asset']),
        ]

    def __str__(self):
        return self.pocket.name + "_" + self.asset.ticker

    @property
    def cost_basis(self):
        """Koszt nabycia w walucie assetu"""
        return self.quantity * self.average_buy_price

    @property
    def cost_basis_in_pocket_currency(self):
        """Koszt nabycia w walucie portfela"""
        return self.cost_basis * self.average_fx_rate

    @property
    def current_price(self):
        """Aktualna cena z modelu Asset"""
        return self.asset.current_price

    @property
    def market_value_in_asset_currency(self):
        """Wartość rynkowa w walucie assetu"""
        return self.quantity * self.asset.current_price

    @property
    def market_value(self):
        """Wartość rynkowa w walucie portfela"""
        if self.asset.currency == self.pocket.base_currency:
            return self.market_value_in_asset_currency

        return self.market_value_in_asset_currency * self.asset.currency.exchange_rate

    @property
    def unrealized_pnl(self):
        """Niezrealizowany P&L"""
        return self.market_value - self.cost_basis_in_pocket_currency

    @property
    def profit(self):
        """Zysk/strata w walucie portfela"""
        return self.market_value - self.cost_basis_in_pocket_currency

    @property
    def return_pct(self):
        """Stopa zwrotu w %"""
        if self.cost_basis_in_pocket_currency == 0:
            return 0
        return (self.profit / self.cost_basis_in_pocket_currency) * 100

    @property
    def pocket_weight_pct(self):
        """Udział w portfelu"""
        pocket_value = self.pocket.total_value
        if pocket_value == 0:
            return 0
        return (self.market_value / pocket_value) * 100

    # daily_change_percent = models.DecimalField(
    #     max_digits=18, decimal_places=9, default=0)
    # daily_change_XXX = models.DecimalField(
    #     max_digits=18, decimal_places=9, default=0)


class Operation(models.Model):
    pocket = models.ForeignKey(
        Pocket, on_delete=models.CASCADE, related_name='oerations')
    asset = models.ForeignKey(
        Asset, on_delete=models.PROTECT, null=True, blank=True)

    OPERATION_TYPES = [
        ('buy', 'Buy'),
        ('sell', 'Sell'),
        ('deposit', 'Deposit Cash'),
        ('withdrawal', 'Withdraw Cash'),
        ('dividend', 'Dividend')
    ]

    operation_type = models.CharField(max_length=20, choices=OPERATION_TYPES)
    quantity = models.DecimalField(max_digits=18, decimal_places=9, default=0)
    price = models.DecimalField(max_digits=18, decimal_places=9, default=0)
    amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    fee = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    fx_rate = models.DecimalField(max_digits=18, decimal_places=9, default=1)

    notes = models.TextField(null=True, blank=True)
    operation_date = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-operation_date']
        indexes = [
            models.Index(fields=['pocket', '-operation_date']),
        ]
    def __str__(self):
        asset_name = self.asset.ticker if self.asset else 'Cash'
        return f"{self.operation_type}: {asset_name}"
