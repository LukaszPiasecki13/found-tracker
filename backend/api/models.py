from django.db import models
from authentication.models import UserProfile

# Create your models here.


class Operation(models.Model):
    operation_type = models.CharField(max_length=20) # buy, sell
    asset_class = models.CharField(null=True, blank=True,)
    ticker = models.CharField(max_length=20, null=True, blank=True,)
    date = models.DateField()
    currency = models.CharField(max_length=3, null=True, blank=True,)
    purchase_currency_price = models.FloatField(null=True, blank=True, default=1.0)
    quantity = models.FloatField()
    price = models.FloatField(null=True, blank=True)
    fee = models.FloatField()
    comment = models.TextField(blank=True)
    owner = models.ForeignKey(to=UserProfile, on_delete=models.CASCADE)
    pocket_name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    

    def __str__(self):
        return ("{}_{}_{}_{}".format(self.id, self.operation_type, self.ticker, self.pocket_name))


class AssetClass(models.Model):
    name = models.CharField(max_length=20)

    class Meta:
        verbose_name_plural = "Asset classes"

    def __str__(self):
        return self.name


class Currency(models.Model):
    name = models.CharField(max_length=3)
    reference_currency_name = models.CharField(max_length=3)
    exchange_rate = models.DecimalField(max_digits=8, decimal_places=3, default=1.0) # exchange rate to base currency

    class Meta:
        verbose_name_plural = "Currencies"

    def __str__(self):
        return self.name


class Asset(models.Model):
    ticker = models.CharField(max_length=10)
    name = models.CharField(max_length=100)
    asset_class = models.CharField()
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE)
    current_price = models.DecimalField(max_digits=8, decimal_places=3, default=0.0)

    def __str__(self):
        return self.name


class Pocket(models.Model):
    owner = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    assets = models.ManyToManyField('Asset', through='AssetAllocation', blank=True)
    fees = models.DecimalField(max_digits=8, decimal_places=3, default=0.0, )
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE)
    net_deposit_value= models.DecimalField(max_digits=12, decimal_places=3, default=0.0)
    free_cash = models.DecimalField(max_digits=12, decimal_places=3, default=0.0)

    def __str__(self):
        return self.name


class AssetAllocation(models.Model):
    pocket = models.ForeignKey(Pocket, on_delete=models.CASCADE)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0.0)
    average_purchase_price = models.DecimalField(max_digits=12, decimal_places=3, default=0.0)
    average_purchase_currency_price = models.DecimalField(max_digits=8, decimal_places=3, default=0.0)
    total_value_XXX = models.DecimalField(max_digits=12, decimal_places=3, default=0.0)
    daily_change_percent = models.DecimalField(max_digits=8, decimal_places=3, default=0.0)
    daily_change_XXX = models.DecimalField(max_digits=12, decimal_places=3, default=0.0)
    participation = models.DecimalField(max_digits=8, decimal_places=3, default=0.0)    # Participation in % in the pocket
    rate_of_return = models.DecimalField(max_digits=12, decimal_places=3, default=0.0)   # Rate of return in % in asset currency
    rate_of_return_XXX = models.DecimalField(max_digits=12, decimal_places=3, default=0.0) # Rate of return in % in base currency
    profit_XXX = models.DecimalField(max_digits=12, decimal_places=3, default=0.0)
    dividends = models.DecimalField(max_digits=12, decimal_places=3, default=0.0)
    fee = models.DecimalField(max_digits=12, decimal_places=3, default=0.0)
    
    def __str__(self):
        return self.pocket.name + "_" + self.asset.name
