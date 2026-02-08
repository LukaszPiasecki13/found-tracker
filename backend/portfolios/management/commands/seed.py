# your_app/management/commands/seed.py
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.apps import apps
from django.db import transaction
from django.utils import timezone



class Command(BaseCommand):
    help = "Seeds the database with sample data for currencies, assets, pockets, positions, and operations."

    def handle(self, *args, **options):
        # Import from assets app
        Currency = apps.get_model("assets", "Currency")
        AssetClass = apps.get_model("assets", "AssetClass")
        Asset = apps.get_model("assets", "Asset")
        
        # Import from portfolios app
        Pocket = apps.get_model("portfolios", "Pocket")
        Position = apps.get_model("portfolios", "Position")
        Operation = apps.get_model("portfolios", "Operation")
        
        # Import from authentication app
        UserProfile = apps.get_model("authentication", "UserProfile")

        def D(x) -> Decimal:
            return Decimal(str(x))

        with transaction.atomic():
            self.stdout.write("Seeding: currencies...")
            currencies_data = [
                # code, exchange_rate to base (USD), base_code
                ("USD", D("1.0"), None),
                ("EUR", D("1.08"), "USD"),
                ("PLN", D("0.25"), "USD"),
                ("GBP", D("1.27"), "USD"),
            ]

            # 1. Utwórz/aktualizuj waluty (bez ustawiania base_currency w pierwszym kroku)
            code_to_currency = {}
            for code, rate, _ in currencies_data:
                obj, created = Currency.objects.update_or_create(
                    code=code,
                    defaults={
                        "exchange_rate": rate,
                        "base_currency": None,
                    },
                )
                code_to_currency[code] = obj
                self.stdout.write(f" - {'created' if created else 'updated'} Currency {code}")

            # 2. Ustaw base_currency
            for code, rate, base_code in currencies_data:
                if base_code:
                    cur = code_to_currency[code]
                    cur.base_currency = code_to_currency[base_code]
                    cur.exchange_rate = rate
                    cur.save(update_fields=["base_currency", "exchange_rate"])
                    self.stdout.write(f"   set base_currency for {code} -> {base_code}")

            self.stdout.write("Seeding: asset classes...")
            asset_classes = {}
            for name in ["Stock", "ETF", "Crypto"]:
                ac, created = AssetClass.objects.update_or_create(name=name)
                asset_classes[name] = ac
                self.stdout.write(f" - {'created' if created else 'updated'} AssetClass {name}")

            self.stdout.write("Seeding: assets...")
            assets_data = [
                {
                    "ticker": "AAPL",
                    "name": "Apple Inc.",
                    "asset_class": "Stock",
                    "currency": "USD",
                    "current_price": D("225.50"),
                    "exchange": "NASDAQ",
                    "sector": "Technology",
                },
                {
                    "ticker": "MSFT",
                    "name": "Microsoft Corporation",
                    "asset_class": "Stock",
                    "currency": "USD",
                    "current_price": D("420.00"),
                    "exchange": "NASDAQ",
                    "sector": "Technology",
                },
                {
                    "ticker": "NVDA",
                    "name": "NVIDIA Corporation",
                    "asset_class": "Stock",
                    "currency": "USD",
                    "current_price": D("1120.00"),
                    "exchange": "NASDAQ",
                    "sector": "Semiconductors",
                },
                {
                    "ticker": "SPY",
                    "name": "SPDR S&P 500 ETF",
                    "asset_class": "ETF",
                    "currency": "USD",
                    "current_price": D("542.10"),
                    "exchange": "NYSE",
                    "sector": "Broad Market",
                },
                {
                    "ticker": "BTCUSD",
                    "name": "Bitcoin (USD pair)",
                    "asset_class": "Crypto",
                    "currency": "USD",
                    "current_price": D("65000.000000000"),
                    "exchange": "Coinbase",
                    "sector": "Crypto",
                },
                {
                    "ticker": "CDR",
                    "name": "CD PROJEKT",
                    "asset_class": "Stock",
                    "currency": "PLN",
                    "current_price": D("130.50"),
                    "exchange": "GPW",
                    "sector": "Gaming",
                },
            ]

            ticker_to_asset = {}
            for a in assets_data:
                asset, created = Asset.objects.update_or_create(
                    ticker=a["ticker"],
                    defaults={
                        "name": a["name"],
                        "asset_class": asset_classes[a["asset_class"]],
                        "currency": code_to_currency[a["currency"]],
                        "current_price": a["current_price"],
                        "exchange": a.get("exchange", ""),
                        "sector": a.get("sector", ""),
                    },
                )
                ticker_to_asset[a["ticker"]] = asset
                self.stdout.write(f" - {'created' if created else 'updated'} Asset {a['ticker']}")

            # Jeśli nie ma żadnego UserProfile, kończymy na słownikach (waluty/klasy/aktywa)
            owner = UserProfile.objects.order_by("id").first()
            if not owner:
                self.stdout.write(self.style.WARNING(
                    "Brak UserProfile w bazie – utworzyłem tylko waluty, klasy i aktywa. "
                    "Dodaj użytkownika (UserProfile), aby zasilić kieszenie/pozycje/operacje."
                ))
                return

            self.stdout.write("Seeding: pockets...")
            # Pocket w USD
            p_usd, created = Pocket.objects.update_or_create(
                owner=owner,
                name="Demo USD",
                defaults={
                    "base_currency": code_to_currency["USD"],
                    "cash_balance": D("10000.000"),
                    "total_deposited": D("15000.000"),
                    "is_active": True,
                },
            )
            self.stdout.write(f" - {'created' if created else 'updated'} Pocket {p_usd.name}")

            # Pocket w PLN
            p_pln, created = Pocket.objects.update_or_create(
                owner=owner,
                name="Demo PLN",
                defaults={
                    "base_currency": code_to_currency["PLN"],
                    "cash_balance": D("20000.000"),
                    "total_deposited": D("20000.000"),
                    "is_active": True,
                },
            )
            self.stdout.write(f" - {'created' if created else 'updated'} Pocket {p_pln.name}")

            self.stdout.write("Seeding: positions...")
            positions_data = [
                # USD pocket positions
                {
                    "pocket": p_usd,
                    "ticker": "AAPL",
                    "quantity": D("10"),
                    "avg_price": D("180.000000000"),
                    "avg_fx": D("1.000000000"),  # USD pocket vs USD asset
                    "fees": D("5.00"),
                    "divs": D("12.34"),
                },
                {
                    "pocket": p_usd,
                    "ticker": "MSFT",
                    "quantity": D("5"),
                    "avg_price": D("300.000000000"),
                    "avg_fx": D("1.000000000"),
                    "fees": D("3.50"),
                    "divs": D("0.00"),
                },
                {
                    "pocket": p_usd,
                    "ticker": "SPY",
                    "quantity": D("2"),
                    "avg_price": D("500.000000000"),
                    "avg_fx": D("1.000000000"),
                    "fees": D("1.25"),
                    "divs": D("0.00"),
                },
                # PLN pocket positions
                {
                    "pocket": p_pln,
                    "ticker": "CDR",
                    "quantity": D("30"),
                    "avg_price": D("120.000000000"),
                    # jeśli asset w PLN, a pocket w PLN, to 1
                    "avg_fx": D("1.000000000"),
                    "fees": D("7.00"),
                    "divs": D("0.00"),
                },
            ]

            for pd in positions_data:
                asset = ticker_to_asset[pd["ticker"]]
                pos, created = Position.objects.update_or_create(
                    pocket=pd["pocket"],
                    asset=asset,
                    defaults={
                        "quantity": pd["quantity"],
                        "average_buy_price": pd["avg_price"],
                        "average_fx_rate": pd["avg_fx"],
                        "total_fees": pd["fees"],
                        "total_dividends": pd["divs"],
                    },
                )
                self.stdout.write(
                    f" - {'created' if created else 'updated'} Position {pos}"
                )

            self.stdout.write("Seeding: operations...")
            now = timezone.now()
            ops_data = [
                # Depozyt do USD
                {
                    "pocket": p_usd,
                    "type": "deposit",
                    "asset": None,
                    "quantity": D("0"),
                    "price": D("0"),
                    "amount": D("15000.00"),
                    "fee": D("0.00"),
                    "fx": D("1.000000000"),
                    "notes": "Initial deposit",
                    "date": now - timezone.timedelta(days=90),
                },
                # Zakup AAPL
                {
                    "pocket": p_usd,
                    "type": "buy",
                    "asset": ticker_to_asset["AAPL"],
                    "quantity": D("10"),
                    "price": D("185.000000000"),
                    "amount": None,
                    "fee": D("5.00"),
                    "fx": D("1.000000000"),
                    "notes": "Buy AAPL",
                    "date": now - timezone.timedelta(days=85),
                },
                # Dywidenda AAPL
                {
                    "pocket": p_usd,
                    "type": "dividend",
                    "asset": ticker_to_asset["AAPL"],
                    "quantity": D("0"),
                    "price": D("0"),
                    "amount": D("12.34"),
                    "fee": D("0.00"),
                    "fx": D("1.000000000"),
                    "notes": "Dividend AAPL",
                    "date": now - timezone.timedelta(days=60),
                },
                # Zakup CDR do PLN
                {
                    "pocket": p_pln,
                    "type": "buy",
                    "asset": ticker_to_asset["CDR"],
                    "quantity": D("30"),
                    "price": D("120.000000000"),
                    "amount": None,
                    "fee": D("7.00"),
                    "fx": D("1.000000000"),
                    "notes": "Buy CDR",
                    "date": now - timezone.timedelta(days=40),
                },
            ]

            for od in ops_data:
                op = Operation.objects.create(
                    pocket=od["pocket"],
                    asset=od["asset"],
                    operation_type=od["type"],
                    quantity=od["quantity"],
                    price=od["price"],
                    amount=od["amount"],
                    fee=od["fee"],
                    fx_rate=od["fx"],
                    notes=od["notes"],
                    operation_date=od["date"],
                )
                self.stdout.write(f" - created Operation {op}")

            self.stdout.write(self.style.SUCCESS("Seed completed successfully."))