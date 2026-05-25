from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class CurrencySeed:
    code: str
    exchange_rate: Decimal
    base_currency_code: str | None = None


@dataclass(frozen=True, slots=True)
class AssetClassSeed:
    name: str


@dataclass(frozen=True, slots=True)
class AssetSeed:
    ticker: str
    name: str
    asset_class_name: str
    currency_code: str
    current_price: Decimal
    exchange: str = ""
    sector: str = ""


@dataclass(frozen=True, slots=True)
class PortfolioSeed:
    name: str
    base_currency_code: str
    cash_balance: Decimal
    total_deposited: Decimal
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class PositionSeed:
    portfolio_name: str
    ticker: str
    quantity: Decimal
    average_buy_price: Decimal
    average_fx_rate: Decimal
    total_fees: Decimal
    total_dividends: Decimal


@dataclass(frozen=True, slots=True)
class OperationSeed:
    portfolio_name: str
    operation_type: str
    ticker: str | None
    quantity: Decimal
    price: Decimal
    amount: Decimal | None
    fee: Decimal
    fx_rate: Decimal
    notes: str
    days_ago: int


SEED_USER_EMAIL = "admin@foundtracker.com"
SEED_USER_PASSWORD = "admin"

CURRENCIES: tuple[CurrencySeed, ...] = (
    CurrencySeed("USD", Decimal("1.0")),
    CurrencySeed("EUR", Decimal("1.08"), "USD"),
    CurrencySeed("PLN", Decimal("0.25"), "USD"),
    CurrencySeed("GBP", Decimal("1.27"), "USD"),
    CurrencySeed("JPY", Decimal("0.0067"), "USD"),
    CurrencySeed("CHF", Decimal("1.12"), "USD"),
)

ASSET_CLASSES: tuple[AssetClassSeed, ...] = (
    AssetClassSeed("Stock"),
    AssetClassSeed("ETF"),
    AssetClassSeed("Crypto"),
    AssetClassSeed("Bond"),
    AssetClassSeed("Commodity"),
    AssetClassSeed("Real Estate"),
)

ASSETS: tuple[AssetSeed, ...] = (
    AssetSeed(
        ticker="AAPL",
        name="Apple Inc.",
        asset_class_name="Stock",
        currency_code="USD",
        current_price=Decimal("225.50"),
        exchange="NASDAQ",
        sector="Technology",
    ),
    AssetSeed(
        ticker="MSFT",
        name="Microsoft Corporation",
        asset_class_name="Stock",
        currency_code="USD",
        current_price=Decimal("420.00"),
        exchange="NASDAQ",
        sector="Technology",
    ),
    AssetSeed(
        ticker="NVDA",
        name="NVIDIA Corporation",
        asset_class_name="Stock",
        currency_code="USD",
        current_price=Decimal("1120.00"),
        exchange="NASDAQ",
        sector="Semiconductors",
    ),
    AssetSeed(
        ticker="SPY",
        name="SPDR S&P 500 ETF",
        asset_class_name="ETF",
        currency_code="USD",
        current_price=Decimal("542.10"),
        exchange="NYSE",
        sector="Broad Market",
    ),
    AssetSeed(
        ticker="BTCUSD",
        name="Bitcoin (USD pair)",
        asset_class_name="Crypto",
        currency_code="USD",
        current_price=Decimal("65000.000000000"),
        exchange="Coinbase",
        sector="Crypto",
    ),
    AssetSeed(
        ticker="CDR",
        name="CD PROJEKT",
        asset_class_name="Stock",
        currency_code="PLN",
        current_price=Decimal("130.50"),
        exchange="GPW",
        sector="Gaming",
    ),
    AssetSeed(
        ticker="PKO",
        name="PKO Bank Polski",
        asset_class_name="Stock",
        currency_code="PLN",
        current_price=Decimal("58.20"),
        exchange="GPW",
        sector="Banking",
    ),
    AssetSeed(
        ticker="PKN",
        name="PKN Orlen",
        asset_class_name="Stock",
        currency_code="PLN",
        current_price=Decimal("52.80"),
        exchange="GPW",
        sector="Energy",
    ),
    AssetSeed(
        ticker="SAP.DE",
        name="SAP SE",
        asset_class_name="Stock",
        currency_code="EUR",
        current_price=Decimal("185.50"),
        exchange="XETRA",
        sector="Technology",
    ),
    AssetSeed(
        ticker="SIE.DE",
        name="Siemens AG",
        asset_class_name="Stock",
        currency_code="EUR",
        current_price=Decimal("172.30"),
        exchange="XETRA",
        sector="Industrials",
    ),
    AssetSeed(
        ticker="ETHUSD",
        name="Ethereum (USD pair)",
        asset_class_name="Crypto",
        currency_code="USD",
        current_price=Decimal("3500.000000"),
        exchange="Coinbase",
        sector="Crypto",
    ),
)

PORTFOLIOS: tuple[PortfolioSeed, ...] = (
    PortfolioSeed(
        name="US Stocks",
        base_currency_code="USD",
        cash_balance=Decimal("15000.000"),
        total_deposited=Decimal("25000.000"),
    ),
    PortfolioSeed(
        name="European Portfolio",
        base_currency_code="EUR",
        cash_balance=Decimal("8000.000"),
        total_deposited=Decimal("12000.000"),
    ),
    PortfolioSeed(
        name="Polish Stocks",
        base_currency_code="PLN",
        cash_balance=Decimal("25000.000"),
        total_deposited=Decimal("30000.000"),
    ),
    PortfolioSeed(
        name="Crypto Portfolio",
        base_currency_code="USD",
        cash_balance=Decimal("5000.000"),
        total_deposited=Decimal("8000.000"),
    ),
)

POSITIONS: tuple[PositionSeed, ...] = (
    PositionSeed(
        portfolio_name="US Stocks",
        ticker="AAPL",
        quantity=Decimal("15"),
        average_buy_price=Decimal("180.000000000"),
        average_fx_rate=Decimal("1.000000000"),
        total_fees=Decimal("7.00"),
        total_dividends=Decimal("18.50"),
    ),
    PositionSeed(
        portfolio_name="US Stocks",
        ticker="MSFT",
        quantity=Decimal("12"),
        average_buy_price=Decimal("300.000000000"),
        average_fx_rate=Decimal("1.000000000"),
        total_fees=Decimal("6.00"),
        total_dividends=Decimal("12.75"),
    ),
    PositionSeed(
        portfolio_name="US Stocks",
        ticker="NVDA",
        quantity=Decimal("5"),
        average_buy_price=Decimal("950.000000000"),
        average_fx_rate=Decimal("1.000000000"),
        total_fees=Decimal("5.00"),
        total_dividends=Decimal("0.00"),
    ),
    PositionSeed(
        portfolio_name="US Stocks",
        ticker="SPY",
        quantity=Decimal("10"),
        average_buy_price=Decimal("500.000000000"),
        average_fx_rate=Decimal("1.000000000"),
        total_fees=Decimal("5.00"),
        total_dividends=Decimal("22.50"),
    ),
    PositionSeed(
        portfolio_name="European Portfolio",
        ticker="SAP.DE",
        quantity=Decimal("12"),
        average_buy_price=Decimal("170.000000000"),
        average_fx_rate=Decimal("1.000000000"),
        total_fees=Decimal("7.00"),
        total_dividends=Decimal("6.75"),
    ),
    PositionSeed(
        portfolio_name="European Portfolio",
        ticker="SIE.DE",
        quantity=Decimal("15"),
        average_buy_price=Decimal("160.000000000"),
        average_fx_rate=Decimal("1.000000000"),
        total_fees=Decimal("8.00"),
        total_dividends=Decimal("10.20"),
    ),
    PositionSeed(
        portfolio_name="Polish Stocks",
        ticker="CDR",
        quantity=Decimal("50"),
        average_buy_price=Decimal("120.000000000"),
        average_fx_rate=Decimal("1.000000000"),
        total_fees=Decimal("12.00"),
        total_dividends=Decimal("0.00"),
    ),
    PositionSeed(
        portfolio_name="Polish Stocks",
        ticker="PKO",
        quantity=Decimal("150"),
        average_buy_price=Decimal("50.000000000"),
        average_fx_rate=Decimal("1.000000000"),
        total_fees=Decimal("8.00"),
        total_dividends=Decimal("22.50"),
    ),
    PositionSeed(
        portfolio_name="Polish Stocks",
        ticker="PKN",
        quantity=Decimal("80"),
        average_buy_price=Decimal("48.000000000"),
        average_fx_rate=Decimal("1.000000000"),
        total_fees=Decimal("6.00"),
        total_dividends=Decimal("12.80"),
    ),
    PositionSeed(
        portfolio_name="Crypto Portfolio",
        ticker="BTCUSD",
        quantity=Decimal("0.15"),
        average_buy_price=Decimal("54000.000000000"),
        average_fx_rate=Decimal("1.000000000"),
        total_fees=Decimal("20.00"),
        total_dividends=Decimal("0.00"),
    ),
    PositionSeed(
        portfolio_name="Crypto Portfolio",
        ticker="ETHUSD",
        quantity=Decimal("2.5"),
        average_buy_price=Decimal("3000.000000000"),
        average_fx_rate=Decimal("1.000000000"),
        total_fees=Decimal("12.00"),
        total_dividends=Decimal("0.00"),
    ),
)

OPERATIONS: tuple[OperationSeed, ...] = (
    OperationSeed(
        portfolio_name="US Stocks",
        operation_type="deposit",
        ticker=None,
        quantity=Decimal("0"),
        price=Decimal("0"),
        amount=Decimal("25000.00"),
        fee=Decimal("0.00"),
        fx_rate=Decimal("1.000000000"),
        notes="Initial deposit",
        days_ago=180,
    ),
    OperationSeed(
        portfolio_name="US Stocks",
        operation_type="buy",
        ticker="AAPL",
        quantity=Decimal("15"),
        price=Decimal("180.000000000"),
        amount=None,
        fee=Decimal("5.00"),
        fx_rate=Decimal("1.000000000"),
        notes="Buy AAPL",
        days_ago=170,
    ),
    OperationSeed(
        portfolio_name="US Stocks",
        operation_type="buy",
        ticker="MSFT",
        quantity=Decimal("12"),
        price=Decimal("300.000000000"),
        amount=None,
        fee=Decimal("6.00"),
        fx_rate=Decimal("1.000000000"),
        notes="Buy MSFT",
        days_ago=160,
    ),
    OperationSeed(
        portfolio_name="US Stocks",
        operation_type="dividend",
        ticker="AAPL",
        quantity=Decimal("0"),
        price=Decimal("0"),
        amount=Decimal("15.00"),
        fee=Decimal("0.00"),
        fx_rate=Decimal("1.000000000"),
        notes="AAPL dividend",
        days_ago=120,
    ),
    OperationSeed(
        portfolio_name="US Stocks",
        operation_type="buy",
        ticker="NVDA",
        quantity=Decimal("5"),
        price=Decimal("950.000000000"),
        amount=None,
        fee=Decimal("7.50"),
        fx_rate=Decimal("1.000000000"),
        notes="Buy NVDA",
        days_ago=90,
    ),
    OperationSeed(
        portfolio_name="US Stocks",
        operation_type="buy",
        ticker="SPY",
        quantity=Decimal("10"),
        price=Decimal("500.000000000"),
        amount=None,
        fee=Decimal("5.00"),
        fx_rate=Decimal("1.000000000"),
        notes="Buy SPY ETF",
        days_ago=80,
    ),
    OperationSeed(
        portfolio_name="US Stocks",
        operation_type="dividend",
        ticker="MSFT",
        quantity=Decimal("0"),
        price=Decimal("0"),
        amount=Decimal("7.50"),
        fee=Decimal("0.00"),
        fx_rate=Decimal("1.000000000"),
        notes="MSFT dividend",
        days_ago=60,
    ),
    OperationSeed(
        portfolio_name="US Stocks",
        operation_type="dividend",
        ticker="SPY",
        quantity=Decimal("0"),
        price=Decimal("0"),
        amount=Decimal("22.50"),
        fee=Decimal("0.00"),
        fx_rate=Decimal("1.000000000"),
        notes="SPY dividend",
        days_ago=30,
    ),
    OperationSeed(
        portfolio_name="European Portfolio",
        operation_type="deposit",
        ticker=None,
        quantity=Decimal("0"),
        price=Decimal("0"),
        amount=Decimal("12000.00"),
        fee=Decimal("0.00"),
        fx_rate=Decimal("1.000000000"),
        notes="Initial deposit EUR",
        days_ago=150,
    ),
    OperationSeed(
        portfolio_name="European Portfolio",
        operation_type="buy",
        ticker="SAP.DE",
        quantity=Decimal("12"),
        price=Decimal("170.000000000"),
        amount=None,
        fee=Decimal("7.00"),
        fx_rate=Decimal("1.000000000"),
        notes="Buy SAP",
        days_ago=140,
    ),
    OperationSeed(
        portfolio_name="European Portfolio",
        operation_type="buy",
        ticker="SIE.DE",
        quantity=Decimal("15"),
        price=Decimal("160.000000000"),
        amount=None,
        fee=Decimal("8.00"),
        fx_rate=Decimal("1.000000000"),
        notes="Buy Siemens",
        days_ago=130,
    ),
    OperationSeed(
        portfolio_name="European Portfolio",
        operation_type="dividend",
        ticker="SAP.DE",
        quantity=Decimal("0"),
        price=Decimal("0"),
        amount=Decimal("6.75"),
        fee=Decimal("0.00"),
        fx_rate=Decimal("1.000000000"),
        notes="SAP dividend",
        days_ago=90,
    ),
    OperationSeed(
        portfolio_name="European Portfolio",
        operation_type="dividend",
        ticker="SIE.DE",
        quantity=Decimal("0"),
        price=Decimal("0"),
        amount=Decimal("10.20"),
        fee=Decimal("0.00"),
        fx_rate=Decimal("1.000000000"),
        notes="Siemens dividend",
        days_ago=60,
    ),
    OperationSeed(
        portfolio_name="Polish Stocks",
        operation_type="deposit",
        ticker=None,
        quantity=Decimal("0"),
        price=Decimal("0"),
        amount=Decimal("30000.00"),
        fee=Decimal("0.00"),
        fx_rate=Decimal("1.000000000"),
        notes="Initial deposit PLN",
        days_ago=120,
    ),
    OperationSeed(
        portfolio_name="Polish Stocks",
        operation_type="buy",
        ticker="CDR",
        quantity=Decimal("50"),
        price=Decimal("120.000000000"),
        amount=None,
        fee=Decimal("12.00"),
        fx_rate=Decimal("1.000000000"),
        notes="Buy CD Projekt",
        days_ago=110,
    ),
    OperationSeed(
        portfolio_name="Polish Stocks",
        operation_type="buy",
        ticker="PKO",
        quantity=Decimal("150"),
        price=Decimal("50.000000000"),
        amount=None,
        fee=Decimal("8.00"),
        fx_rate=Decimal("1.000000000"),
        notes="Buy PKO Bank",
        days_ago=100,
    ),
    OperationSeed(
        portfolio_name="Polish Stocks",
        operation_type="buy",
        ticker="PKN",
        quantity=Decimal("80"),
        price=Decimal("48.000000000"),
        amount=None,
        fee=Decimal("6.00"),
        fx_rate=Decimal("1.000000000"),
        notes="Buy PKN Orlen",
        days_ago=90,
    ),
    OperationSeed(
        portfolio_name="Polish Stocks",
        operation_type="dividend",
        ticker="PKO",
        quantity=Decimal("0"),
        price=Decimal("0"),
        amount=Decimal("22.50"),
        fee=Decimal("0.00"),
        fx_rate=Decimal("1.000000000"),
        notes="PKO dividend",
        days_ago=60,
    ),
    OperationSeed(
        portfolio_name="Polish Stocks",
        operation_type="dividend",
        ticker="PKN",
        quantity=Decimal("0"),
        price=Decimal("0"),
        amount=Decimal("12.80"),
        fee=Decimal("0.00"),
        fx_rate=Decimal("1.000000000"),
        notes="PKN dividend",
        days_ago=45,
    ),
    OperationSeed(
        portfolio_name="Crypto Portfolio",
        operation_type="deposit",
        ticker=None,
        quantity=Decimal("0"),
        price=Decimal("0"),
        amount=Decimal("8000.00"),
        fee=Decimal("0.00"),
        fx_rate=Decimal("1.000000000"),
        notes="Initial crypto deposit",
        days_ago=100,
    ),
    OperationSeed(
        portfolio_name="Crypto Portfolio",
        operation_type="buy",
        ticker="BTCUSD",
        quantity=Decimal("0.15"),
        price=Decimal("54000.000000000"),
        amount=None,
        fee=Decimal("20.00"),
        fx_rate=Decimal("1.000000000"),
        notes="Buy Bitcoin",
        days_ago=90,
    ),
    OperationSeed(
        portfolio_name="Crypto Portfolio",
        operation_type="buy",
        ticker="ETHUSD",
        quantity=Decimal("2.5"),
        price=Decimal("3000.000000000"),
        amount=None,
        fee=Decimal("12.00"),
        fx_rate=Decimal("1.000000000"),
        notes="Buy Ethereum",
        days_ago=80,
    ),
)
