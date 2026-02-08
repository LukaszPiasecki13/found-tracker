# Backend Structure - Django Portfolio Tracker

## Overview
This Django backend has been structured following domain-driven design principles with clear separation of concerns.

## Applications

### 1. **assets** - Market Data & Reference Data
Manages financial instruments and market data.

**Models:**
- `Currency` - Currency codes and exchange rates
- `AssetClass` - Asset categorization (Stock, ETF, Crypto, etc.)
- `Asset` - Financial instruments (stocks, bonds, cryptocurrencies)

**Services:**
- `MarketDataService` - Fetches prices and exchange rates from Yahoo Finance

**API Endpoints:**
- `GET/POST /api/currencies/`
- `GET/POST /api/asset-classes/`

---

### 2. **portfolios** - Portfolio Management
Core business logic for portfolio operations.

**Models:**
- `Pocket` - User portfolio with cash balance
- `Position` - Holdings of specific assets in a portfolio
- `Operation` - Transaction history (buy/sell/deposit/withdrawal)

**Services:**
- `TransactionService` - Handles buy/sell operations with FIFO cost basis
- `PortfolioService` - Manages cash deposits/withdrawals

**Analytics:**
- `PocketMetrics` - Time-series portfolio performance analysis
- `AssetCalculator` - Position-level calculations

**API Endpoints:**
- `GET/POST /api/pockets/`
- `GET /api/positions/?pocket_name=<name>`
- `GET/POST /api/operations/`
- `GET /api/pocket-vectors/` - Historical performance data

---

### 3. **authentication** - User Management
Handles user authentication and authorization.

**Models:**
- `UserProfile` - Extended Django user model

**API Endpoints:**
- `POST /auth/register/`
- `POST /auth/token/` - JWT token
- `POST /auth/token/refresh/`

---

## Project Structure

```
backend/
├── manage.py
├── requirements.txt
├── assets/                     # Market data app
│   ├── models.py              # Currency, AssetClass, Asset
│   ├── serializers.py
│   ├── views.py
│   ├── urls.py
│   ├── admin.py
│   └── services/
│       └── market_data_service.py
│
├── portfolios/                 # Portfolio management app
│   ├── models.py              # Pocket, Position, Operation
│   ├── serializers.py
│   ├── views.py
│   ├── urls.py
│   ├── admin.py
│   ├── services/
│   │   ├── transaction_service.py
│   │   └── portfolio_service.py
│   ├── analytics/
│   │   ├── pocket_metrics.py
│   │   └── asset_calculator.py
│   ├── management/
│   │   └── commands/
│   │       └── seed.py
│   └── tests/
│       ├── unit/
│       └── integration/
│
├── authentication/             # User auth app
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   └── urls.py
│
└── core/                       # Django settings
    ├── settings.py
    ├── urls.py
    └── wsgi.py
```

## Development Commands

### Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Seed database (optional)
python manage.py seed
```

### Running
```bash
# Development server
python manage.py runserver

# The API will be available at http://localhost:8000/api/
# Admin panel at http://localhost:8000/admin/
# API docs at http://localhost:8000/docs/
```

### Testing
```bash
# Run all tests
pytest

# Run specific app tests
pytest assets/
pytest portfolios/

# With coverage
pytest --cov=.
```

### Migrations
```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Show migration status
python manage.py showmigrations
```

## Service Layer Usage Examples

### TransactionService
```python
from portfolios.services import TransactionService

service = TransactionService(owner=request.user)

# Execute buy operation
data = {
    'pocket': pocket_instance,
    'asset': asset_instance,
    'quantity': 10,
    'price': 150.50,
    'fee': 1.00,
    'fx_rate': 1.0
}
service.execute_buy(data)

# Execute sell operation
service.execute_sell(data)
```

### PortfolioService
```python
from portfolios.services import PortfolioService

service = PortfolioService(owner=request.user)

# Deposit cash
service.deposit_cash({'pocket': pocket, 'amount': 1000})

# Withdraw cash
service.withdraw_cash({'pocket': pocket, 'amount': 500})

# Calculate portfolio value
total_value = service.calculate_portfolio_value(pocket)
```

### MarketDataService
```python
from assets.services import MarketDataService

# Update asset price
MarketDataService.update_asset_price(asset)

# Update all currency rates
MarketDataService.update_currency_rates(base_currency_code='USD')

# Get asset info
info = MarketDataService.get_asset_info('AAPL')
```

## API Documentation

Full API documentation is available via Swagger UI at `/docs/` when running the development server.

## Database Schema

### Assets App Tables
- `assets_currency`
- `assets_assetclass`
- `assets_asset`

### Portfolios App Tables
- `portfolios_pocket`
- `portfolios_position`
- `portfolios_operation`

### Relationships
- `Pocket` → `Currency` (base currency)
- `Pocket` → `UserProfile` (owner)
- `Position` → `Pocket` + `Asset` (many-to-many through table)
- `Operation` → `Pocket` + `Asset` (transaction log)

## Configuration

Key settings in `core/settings.py`:

```python
INSTALLED_APPS = [
    # ...
    'assets.apps.AssetsConfig',
    'portfolios.apps.PortfoliosConfig',
    'authentication',
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    # ...
}
```

## Environment Variables

Required environment variables:
- `DEBUG` - Debug mode (True/False)
- `SECRET_KEY` - Django secret key
- `DATABASE_URL` - PostgreSQL connection string
- `ALLOWED_HOSTS` - Comma-separated list of allowed hosts

## Notes

- All API endpoints require authentication (JWT tokens)
- Market data is fetched from Yahoo Finance via `yfinance`
- Portfolio calculations use FIFO method for cost basis
- Time-series analytics use pandas and numpy
- Admin interface available for all models

## Support

For issues or questions, refer to the main project README or open an issue on GitHub.
