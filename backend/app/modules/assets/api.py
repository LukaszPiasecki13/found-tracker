from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User

from .dependencies import get_asset_class_repo, get_asset_repo, get_currency_repo
from .models import Asset, AssetClass, Currency
from .repository import AssetClassRepository, AssetRepository, CurrencyRepository
from .schemas import (
    AssetClassCreate,
    AssetClassRead,
    AssetCreate,
    AssetDetailRead,
    AssetRead,
    CreateFromYahoo,
    CurrencyCreate,
    CurrencyRead,
)
from .service import MarketDataService

router = APIRouter(prefix="/assets", tags=["assets"])


# --- Currencies ---


@router.get("/currencies", response_model=list[CurrencyRead])
def list_currencies(
    repo: CurrencyRepository = Depends(get_currency_repo),
    _: User = Depends(get_current_user),
):
    return repo.list_all()


@router.post("/currencies", response_model=CurrencyRead, status_code=201)
def create_currency(
    data: CurrencyCreate,
    repo: CurrencyRepository = Depends(get_currency_repo),
    _: User = Depends(get_current_user),
):
    currency = Currency(
        code=data.code.upper(),
        exchange_rate=data.exchange_rate,
        base_currency_id=data.base_currency_id,
    )
    return repo.create(currency)


@router.get("/currencies/{currency_id}", response_model=CurrencyRead)
def get_currency(
    currency_id: int,
    repo: CurrencyRepository = Depends(get_currency_repo),
    _: User = Depends(get_current_user),
):
    currency = repo.get_by_id(currency_id)
    if not currency:
        raise HTTPException(status_code=404, detail="Currency not found")
    return currency


@router.delete("/currencies/{currency_id}", status_code=204)
def delete_currency(
    currency_id: int,
    repo: CurrencyRepository = Depends(get_currency_repo),
    _: User = Depends(get_current_user),
):
    currency = repo.get_by_id(currency_id)
    if not currency:
        raise HTTPException(status_code=404, detail="Currency not found")
    repo.delete(currency)


# --- Asset Classes ---


@router.get("/asset-classes", response_model=list[AssetClassRead])
def list_asset_classes(
    repo: AssetClassRepository = Depends(get_asset_class_repo),
    _: User = Depends(get_current_user),
):
    return repo.list_all()


@router.post("/asset-classes", response_model=AssetClassRead, status_code=201)
def create_asset_class(
    data: AssetClassCreate,
    repo: AssetClassRepository = Depends(get_asset_class_repo),
    _: User = Depends(get_current_user),
):
    ac = AssetClass(name=data.name)
    return repo.create(ac)


@router.delete("/asset-classes/{ac_id}", status_code=204)
def delete_asset_class(
    ac_id: int,
    repo: AssetClassRepository = Depends(get_asset_class_repo),
    _: User = Depends(get_current_user),
):
    ac = repo.get_by_id(ac_id)
    if not ac:
        raise HTTPException(status_code=404, detail="Asset class not found")
    repo.delete(ac)


# --- Assets ---


@router.get("/", response_model=list[AssetRead])
def list_assets(
    search: str | None = None,
    repo: AssetRepository = Depends(get_asset_repo),
    _: User = Depends(get_current_user),
):
    return repo.list_all(search=search)


@router.post("/", response_model=AssetRead, status_code=201)
def create_asset(
    data: AssetCreate,
    repo: AssetRepository = Depends(get_asset_repo),
    _: User = Depends(get_current_user),
):
    asset = Asset(
        ticker=data.ticker.upper().strip(),
        name=data.name,
        asset_class_id=data.asset_class_id,
        currency_id=data.currency_id,
        current_price=data.current_price,
        exchange=data.exchange,
        sector=data.sector,
    )
    return repo.create(asset)


@router.get("/search-yahoo", response_model=dict)
def search_yahoo(
    q: str = Query(min_length=2),
    repo: AssetRepository = Depends(get_asset_repo),
    _: User = Depends(get_current_user),
):
    local_results = repo.list_all(search=q)[:10]
    local_data = [AssetDetailRead.model_validate(a) for a in local_results]
    yahoo_results = MarketDataService.search_yahoo_finance(q)
    existing_tickers = {a.ticker for a in local_results}
    yahoo_filtered = [r for r in yahoo_results if r["symbol"] not in existing_tickers]
    return {"local": [d.model_dump() for d in local_data], "yahoo": yahoo_filtered}


@router.post("/create-from-yahoo", response_model=AssetDetailRead, status_code=201)
def create_from_yahoo(
    data: CreateFromYahoo,
    repo: AssetRepository = Depends(get_asset_repo),
    asset_class_repo: AssetClassRepository = Depends(get_asset_class_repo),
    currency_repo: CurrencyRepository = Depends(get_currency_repo),
    _: User = Depends(get_current_user),
):
    ticker = data.ticker.strip().upper()
    if repo.get_by_ticker(ticker):
        raise HTTPException(
            status_code=400, detail="Asset with this ticker already exists"
        )

    info = MarketDataService.get_asset_info(ticker)
    if not info or not info.get("symbol"):
        raise HTTPException(
            status_code=404, detail="Could not find asset on Yahoo Finance"
        )

    asset_class_id = data.asset_class_id
    if not asset_class_id:
        quote_type = info.get("quoteType", "EQUITY")
        name_map = {
            "ETF": "ETF",
            "CRYPTOCURRENCY": "Crypto",
            "CRYPTO": "Crypto",
            "MUTUALFUND": "Mutual Fund",
        }
        ac_name = name_map.get(quote_type, "Stock")
        ac = asset_class_repo.get_or_create(ac_name)
        asset_class_id = ac.id

    currency_id = data.currency_id
    if not currency_id:
        code = info.get("currency", "USD").upper()
        cur = currency_repo.get_or_create(code)
        currency_id = cur.id

    current_price = (
        info.get("currentPrice")
        or info.get("regularMarketPrice")
        or info.get("previousClose", 0)
    )
    asset = Asset(
        ticker=ticker,
        name=info.get("longName") or info.get("shortName", ticker),
        asset_class_id=asset_class_id,
        currency_id=currency_id,
        current_price=Decimal(str(current_price)),
        exchange=info.get("exchange", ""),
        sector=info.get("sector", ""),
    )
    return repo.create(asset)


@router.get("/{asset_id}", response_model=AssetDetailRead)
def get_asset(
    asset_id: int,
    repo: AssetRepository = Depends(get_asset_repo),
    _: User = Depends(get_current_user),
):
    asset = repo.get_by_id(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.delete("/{asset_id}", status_code=204)
def delete_asset(
    asset_id: int,
    repo: AssetRepository = Depends(get_asset_repo),
    _: User = Depends(get_current_user),
):
    asset = repo.get_by_id(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    repo.delete(asset)
