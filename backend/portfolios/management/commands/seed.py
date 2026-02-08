# portfolios/management/commands/seed.py
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.apps import apps
from django.db import transaction
from django.utils import timezone


class Command(BaseCommand):
    help = "Seeds the database with comprehensive demo data for all models."

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
            # === USERS ===
            self.stdout.write("Seeding: users...")
            
            # Create admin user
            admin, created = UserProfile.objects.update_or_create(
                username='admin',
                defaults={
                    'email': 'admin@foundtracker.com',
                    'status': 'admin',
                    'main_currency': 'USD',
                    'is_staff': True,
                    'is_superuser': True,
                    'first_name': 'Admin',
                    'last_name': 'User',
                }
            )
            if created:
                admin.set_password('admin')
                admin.save()
            self.stdout.write(f" - {'created' if created else 'updated'} admin user")
            
            # Use admin as owner for all seeded data
            owner = admin
            
            # Clear existing data for admin user
            self.stdout.write("Clearing existing data for admin...")
            admin_pockets = Pocket.objects.filter(owner=admin)
            operations_count = Operation.objects.filter(pocket__in=admin_pockets).count()
            positions_count = Position.objects.filter(pocket__in=admin_pockets).count()
            pockets_count = admin_pockets.count()
            
            Operation.objects.filter(pocket__in=admin_pockets).delete()
            Position.objects.filter(pocket__in=admin_pockets).delete()
            admin_pockets.delete()
            
            self.stdout.write(f" - deleted {operations_count} operations, {positions_count} positions, {pockets_count} pockets")
            
            # === CURRENCIES ===
            # === CURRENCIES ===
            self.stdout.write("Seeding: currencies...")
            currencies_data = [
                ("USD", D("1.0"), None),
                ("EUR", D("1.08"), "USD"),
                ("PLN", D("0.25"), "USD"),
                ("GBP", D("1.27"), "USD"),
                ("JPY", D("0.0067"), "USD"),
                ("CHF", D("1.12"), "USD"),
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
            for name in ["Stock", "ETF", "Crypto", "Bond", "Commodity", "Real Estate"]:
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
                {
                    "ticker": "PKO",
                    "name": "PKO Bank Polski",
                    "asset_class": "Stock",
                    "currency": "PLN",
                    "current_price": D("58.20"),
                    "exchange": "GPW",
                    "sector": "Banking",
                },
                {
                    "ticker": "PKN",
                    "name": "PKN Orlen",
                    "asset_class": "Stock",
                    "currency": "PLN",
                    "current_price": D("52.80"),
                    "exchange": "GPW",
                    "sector": "Energy",
                },
                {
                    "ticker": "SAP.DE",
                    "name": "SAP SE",
                    "asset_class": "Stock",
                    "currency": "EUR",
                    "current_price": D("185.50"),
                    "exchange": "XETRA",
                    "sector": "Technology",
                },
                {
                    "ticker": "SIE.DE",
                    "name": "Siemens AG",
                    "asset_class": "Stock",
                    "currency": "EUR",
                    "current_price": D("172.30"),
                    "exchange": "XETRA",
                    "sector": "Industrials",
                },
                {
                    "ticker": "ETHUSD",
                    "name": "Ethereum (USD pair)",
                    "asset_class": "Crypto",
                    "currency": "USD",
                    "current_price": D("3500.000000"),
                    "exchange": "Coinbase",
                    "sector": "Crypto",
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

            # === POCKETS ===
            self.stdout.write("Seeding: pockets...")
            # US Stocks pocket
            p_us, created = Pocket.objects.update_or_create(
                owner=owner,
                name="US Stocks",
                defaults={
                    "base_currency": code_to_currency["USD"],
                    "cash_balance": D("15000.000"),
                    "total_deposited": D("25000.000"),
                    "is_active": True,
                },
            )
            self.stdout.write(f" - {'created' if created else 'updated'} Pocket {p_us.name}")

            # European Portfolio
            p_eur, created = Pocket.objects.update_or_create(
                owner=owner,
                name="European Portfolio",
                defaults={
                    "base_currency": code_to_currency["EUR"],
                    "cash_balance": D("8000.000"),
                    "total_deposited": D("12000.000"),
                    "is_active": True,
                },
            )
            self.stdout.write(f" - {'created' if created else 'updated'} Pocket {p_eur.name}")

            # Polish Stocks
            p_pln, created = Pocket.objects.update_or_create(
                owner=owner,
                name="Polish Stocks",
                defaults={
                    "base_currency": code_to_currency["PLN"],
                    "cash_balance": D("25000.000"),
                    "total_deposited": D("30000.000"),
                    "is_active": True,
                },
            )
            self.stdout.write(f" - {'created' if created else 'updated'} Pocket {p_pln.name}")

            # Crypto Portfolio
            p_crypto, created = Pocket.objects.update_or_create(
                owner=owner,
                name="Crypto Portfolio",
                defaults={
                    "base_currency": code_to_currency["USD"],
                    "cash_balance": D("5000.000"),
                    "total_deposited": D("8000.000"),
                    "is_active": True,
                },
            )
            self.stdout.write(f" - {'created' if created else 'updated'} Pocket {p_crypto.name}")

            # === POSITIONS ===
            self.stdout.write("Seeding: positions...")
            positions_data = [
                # US Stocks pocket positions
                {
                    "pocket": p_us,
                    "ticker": "AAPL",
                    "quantity": D("15"),
                    "avg_price": D("180.000000000"),
                    "avg_fx": D("1.000000000"),
                    "fees": D("7.00"),
                    "divs": D("18.50"),
                },
                {
                    "pocket": p_us,
                    "ticker": "MSFT",
                    "quantity": D("12"),
                    "avg_price": D("300.000000000"),
                    "avg_fx": D("1.000000000"),
                    "fees": D("6.00"),
                    "divs": D("12.75"),
                },
                {
                    "pocket": p_us,
                    "ticker": "NVDA",
                    "quantity": D("5"),
                    "avg_price": D("950.000000000"),
                    "avg_fx": D("1.000000000"),
                    "fees": D("5.00"),
                    "divs": D("0.00"),
                },
                {
                    "pocket": p_us,
                    "ticker": "SPY",
                    "quantity": D("10"),
                    "avg_price": D("500.000000000"),
                    "avg_fx": D("1.000000000"),
                    "fees": D("5.00"),
                    "divs": D("22.50"),
                },
                # European Portfolio positions
                {
                    "pocket": p_eur,
                    "ticker": "SAP.DE",
                    "quantity": D("12"),
                    "avg_price": D("170.000000000"),
                    "avg_fx": D("1.000000000"),
                    "fees": D("7.00"),
                    "divs": D("6.75"),
                },
                {
                    "pocket": p_eur,
                    "ticker": "SIE.DE",
                    "quantity": D("15"),
                    "avg_price": D("160.000000000"),
                    "avg_fx": D("1.000000000"),
                    "fees": D("8.00"),
                    "divs": D("10.20"),
                },
                # Polish Stocks positions
                {
                    "pocket": p_pln,
                    "ticker": "CDR",
                    "quantity": D("50"),
                    "avg_price": D("120.000000000"),
                    "avg_fx": D("1.000000000"),
                    "fees": D("12.00"),
                    "divs": D("0.00"),
                },
                {
                    "pocket": p_pln,
                    "ticker": "PKO",
                    "quantity": D("150"),
                    "avg_price": D("50.000000000"),
                    "avg_fx": D("1.000000000"),
                    "fees": D("8.00"),
                    "divs": D("22.50"),
                },
                {
                    "pocket": p_pln,
                    "ticker": "PKN",
                    "quantity": D("80"),
                    "avg_price": D("48.000000000"),
                    "avg_fx": D("1.000000000"),
                    "fees": D("6.00"),
                    "divs": D("12.80"),
                },
                # Crypto Portfolio positions
                {
                    "pocket": p_crypto,
                    "ticker": "BTCUSD",
                    "quantity": D("0.15"),
                    "avg_price": D("54000.000000000"),
                    "avg_fx": D("1.000000000"),
                    "fees": D("20.00"),
                    "divs": D("0.00"),
                },
                {
                    "pocket": p_crypto,
                    "ticker": "ETHUSD",
                    "quantity": D("2.5"),
                    "avg_price": D("3000.000000000"),
                    "avg_fx": D("1.000000000"),
                    "fees": D("12.00"),
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
                # US Stocks operations
                {
                    "pocket": p_us,
                    "type": "deposit",
                    "asset": None,
                    "quantity": D("0"),
                    "price": D("0"),
                    "amount": D("25000.00"),
                    "fee": D("0.00"),
                    "fx": D("1.000000000"),
                    "notes": "Initial deposit",
                    "date": now - timezone.timedelta(days=180),
                },
                {
                    "pocket": p_us,
                    "type": "buy",
                    "asset": ticker_to_asset["AAPL"],
                    "quantity": D("15"),
                    "price": D("180.000000000"),
                    "amount": None,
                    "fee": D("5.00"),
                    "fx": D("1.000000000"),
                    "notes": "Buy AAPL",
                    "date": now - timezone.timedelta(days=170),
                },
                {
                    "pocket": p_us,
                    "type": "buy",
                    "asset": ticker_to_asset["MSFT"],
                    "quantity": D("12"),
                    "price": D("300.000000000"),
                    "amount": None,
                    "fee": D("6.00"),
                    "fx": D("1.000000000"),
                    "notes": "Buy MSFT",
                    "date": now - timezone.timedelta(days=160),
                },
                {
                    "pocket": p_us,
                    "type": "dividend",
                    "asset": ticker_to_asset["AAPL"],
                    "quantity": D("0"),
                    "price": D("0"),
                    "amount": D("15.00"),
                    "fee": D("0.00"),
                    "fx": D("1.000000000"),
                    "notes": "AAPL dividend",
                    "date": now - timezone.timedelta(days=120),
                },
                {
                    "pocket": p_us,
                    "type": "buy",
                    "asset": ticker_to_asset["NVDA"],
                    "quantity": D("5"),
                    "price": D("950.000000000"),
                    "amount": None,
                    "fee": D("7.50"),
                    "fx": D("1.000000000"),
                    "notes": "Buy NVDA",
                    "date": now - timezone.timedelta(days=90),
                },
                {
                    "pocket": p_us,
                    "type": "buy",
                    "asset": ticker_to_asset["SPY"],
                    "quantity": D("10"),
                    "price": D("500.000000000"),
                    "amount": None,
                    "fee": D("5.00"),
                    "fx": D("1.000000000"),
                    "notes": "Buy SPY ETF",
                    "date": now - timezone.timedelta(days=80),
                },
                {
                    "pocket": p_us,
                    "type": "dividend",
                    "asset": ticker_to_asset["MSFT"],
                    "quantity": D("0"),
                    "price": D("0"),
                    "amount": D("7.50"),
                    "fee": D("0.00"),
                    "fx": D("1.000000000"),
                    "notes": "MSFT dividend",
                    "date": now - timezone.timedelta(days=60),
                },
                {
                    "pocket": p_us,
                    "type": "dividend",
                    "asset": ticker_to_asset["SPY"],
                    "quantity": D("0"),
                    "price": D("0"),
                    "amount": D("22.50"),
                    "fee": D("0.00"),
                    "fx": D("1.000000000"),
                    "notes": "SPY dividend",
                    "date": now - timezone.timedelta(days=30),
                },
                # European Portfolio operations
                {
                    "pocket": p_eur,
                    "type": "deposit",
                    "asset": None,
                    "quantity": D("0"),
                    "price": D("0"),
                    "amount": D("12000.00"),
                    "fee": D("0.00"),
                    "fx": D("1.000000000"),
                    "notes": "Initial deposit EUR",
                    "date": now - timezone.timedelta(days=150),
                },
                {
                    "pocket": p_eur,
                    "type": "buy",
                    "asset": ticker_to_asset["SAP.DE"],
                    "quantity": D("12"),
                    "price": D("170.000000000"),
                    "amount": None,
                    "fee": D("7.00"),
                    "fx": D("1.000000000"),
                    "notes": "Buy SAP",
                    "date": now - timezone.timedelta(days=140),
                },
                {
                    "pocket": p_eur,
                    "type": "buy",
                    "asset": ticker_to_asset["SIE.DE"],
                    "quantity": D("15"),
                    "price": D("160.000000000"),
                    "amount": None,
                    "fee": D("8.00"),
                    "fx": D("1.000000000"),
                    "notes": "Buy Siemens",
                    "date": now - timezone.timedelta(days=130),
                },
                {
                    "pocket": p_eur,
                    "type": "dividend",
                    "asset": ticker_to_asset["SAP.DE"],
                    "quantity": D("0"),
                    "price": D("0"),
                    "amount": D("6.75"),
                    "fee": D("0.00"),
                    "fx": D("1.000000000"),
                    "notes": "SAP dividend",
                    "date": now - timezone.timedelta(days=90),
                },
                {
                    "pocket": p_eur,
                    "type": "dividend",
                    "asset": ticker_to_asset["SIE.DE"],
                    "quantity": D("0"),
                    "price": D("0"),
                    "amount": D("10.20"),
                    "fee": D("0.00"),
                    "fx": D("1.000000000"),
                    "notes": "Siemens dividend",
                    "date": now - timezone.timedelta(days=60),
                },
                # Polish Stocks operations
                {
                    "pocket": p_pln,
                    "type": "deposit",
                    "asset": None,
                    "quantity": D("0"),
                    "price": D("0"),
                    "amount": D("30000.00"),
                    "fee": D("0.00"),
                    "fx": D("1.000000000"),
                    "notes": "Initial deposit PLN",
                    "date": now - timezone.timedelta(days=120),
                },
                {
                    "pocket": p_pln,
                    "type": "buy",
                    "asset": ticker_to_asset["CDR"],
                    "quantity": D("50"),
                    "price": D("120.000000000"),
                    "amount": None,
                    "fee": D("12.00"),
                    "fx": D("1.000000000"),
                    "notes": "Buy CD Projekt",
                    "date": now - timezone.timedelta(days=110),
                },
                {
                    "pocket": p_pln,
                    "type": "buy",
                    "asset": ticker_to_asset["PKO"],
                    "quantity": D("150"),
                    "price": D("50.000000000"),
                    "amount": None,
                    "fee": D("8.00"),
                    "fx": D("1.000000000"),
                    "notes": "Buy PKO Bank",
                    "date": now - timezone.timedelta(days=100),
                },
                {
                    "pocket": p_pln,
                    "type": "buy",
                    "asset": ticker_to_asset["PKN"],
                    "quantity": D("80"),
                    "price": D("48.000000000"),
                    "amount": None,
                    "fee": D("6.00"),
                    "fx": D("1.000000000"),
                    "notes": "Buy PKN Orlen",
                    "date": now - timezone.timedelta(days=90),
                },
                {
                    "pocket": p_pln,
                    "type": "dividend",
                    "asset": ticker_to_asset["PKO"],
                    "quantity": D("0"),
                    "price": D("0"),
                    "amount": D("22.50"),
                    "fee": D("0.00"),
                    "fx": D("1.000000000"),
                    "notes": "PKO dividend",
                    "date": now - timezone.timedelta(days=60),
                },
                {
                    "pocket": p_pln,
                    "type": "dividend",
                    "asset": ticker_to_asset["PKN"],
                    "quantity": D("0"),
                    "price": D("0"),
                    "amount": D("12.80"),
                    "fee": D("0.00"),
                    "fx": D("1.000000000"),
                    "notes": "PKN dividend",
                    "date": now - timezone.timedelta(days=45),
                },
                # Crypto Portfolio operations
                {
                    "pocket": p_crypto,
                    "type": "deposit",
                    "asset": None,
                    "quantity": D("0"),
                    "price": D("0"),
                    "amount": D("8000.00"),
                    "fee": D("0.00"),
                    "fx": D("1.000000000"),
                    "notes": "Initial crypto deposit",
                    "date": now - timezone.timedelta(days=100),
                },
                {
                    "pocket": p_crypto,
                    "type": "buy",
                    "asset": ticker_to_asset["BTCUSD"],
                    "quantity": D("0.15"),
                    "price": D("54000.000000000"),
                    "amount": None,
                    "fee": D("20.00"),
                    "fx": D("1.000000000"),
                    "notes": "Buy Bitcoin",
                    "date": now - timezone.timedelta(days=90),
                },
                {
                    "pocket": p_crypto,
                    "type": "buy",
                    "asset": ticker_to_asset["ETHUSD"],
                    "quantity": D("2.5"),
                    "price": D("3000.000000000"),
                    "amount": None,
                    "fee": D("12.00"),
                    "fx": D("1.000000000"),
                    "notes": "Buy Ethereum",
                    "date": now - timezone.timedelta(days=80),
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

            self.stdout.write(self.style.SUCCESS("\n✅ Seed completed successfully!"))
            self.stdout.write(self.style.SUCCESS(f"Created: 1 admin user, 6 currencies, 6 asset classes, 11+ assets"))
            self.stdout.write(self.style.SUCCESS(f"Created: 4 pockets (for admin), positions, and operations"))