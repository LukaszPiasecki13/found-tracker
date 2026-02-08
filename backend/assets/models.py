from django.db import models


class Currency(models.Model):
    """
    Currency model for asset pricing and portfolio base currency.
    Supports conversion rates relative to a base currency.
    """
    code = models.CharField(max_length=3, unique=True)
    exchange_rate = models.DecimalField(
        max_digits=18, decimal_places=9, default=1.0)  # exchange rate to base currency

    base_currency = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='derived_currencies'
    )

    class Meta:
        verbose_name_plural = "Currencies"
        ordering = ['code']

    def __str__(self):
        return self.code
    
    def save(self, *args, **kwargs):
        self.code = self.code.upper()
        super().save(*args, **kwargs)


class AssetClass(models.Model):
    """
    Asset class categorization (e.g., Stock, ETF, Crypto, Bond).
    """
    name = models.CharField(max_length=20, unique=True)

    class Meta:
        verbose_name_plural = "Asset classes"
        ordering = ['name']

    def __str__(self):
        return self.name


class Asset(models.Model):
    """
    Financial asset that can be traded (stocks, ETFs, cryptocurrencies, etc.).
    Linked to a specific asset class and currency.
    """
    ticker = models.CharField(max_length=20, unique=True, db_index=True)
    name = models.CharField(max_length=100)
    asset_class = models.ForeignKey(
        AssetClass, on_delete=models.PROTECT, related_name='assets')
    currency = models.ForeignKey(
        Currency, on_delete=models.PROTECT, related_name='assets')
    current_price = models.DecimalField(
        max_digits=18, decimal_places=9, default=0)
    exchange = models.CharField(
        max_length=50,
        blank=True,
        help_text="Stock exchange (e.g., NYSE, NASDAQ)"
    )
    sector = models.CharField(max_length=100, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.ticker} - {self.name}"

    def save(self, *args, **kwargs):
        self.ticker = self.ticker.upper().strip()
        super().save(*args, **kwargs)
