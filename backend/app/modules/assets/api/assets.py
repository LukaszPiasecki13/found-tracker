"""Asset API endpoints: CRUD, archiving, provider (Yahoo Finance) search and import,
manual refresh and data status.

`{asset_id:int}` only matches digits, so `/assets/search-yahoo`,
`/assets/asset-classes` and `/assets/currencies` can never be captured by it,
whatever the router include order.
"""

from fastapi import APIRouter, BackgroundTasks, Depends

from app.core.errors import BondTermsNotFoundError
from app.core.market_data import BondDataProvider
from app.modules.assets import entrypoints
from app.modules.assets.dependencies import (
    get_asset_service,
    get_bond_data_provider,
    get_bond_data_service,
    get_market_data_service,
)
from app.modules.assets.exceptions import AssetNotABondError
from app.modules.assets.schemas.assets import (
    AssetCreateRequest,
    AssetDetailResponse,
    AssetFromProviderRequest,
    AssetListQuery,
    AssetResponse,
    AssetSearchQuery,
    AssetSearchResponse,
    AssetUpdateRequest,
)
from app.modules.assets.schemas.bonds import (
    BondSeriesSearchResponse,
    BondTermsCreateRequest,
    BondTermsResponse,
)
from app.modules.assets.schemas.prices import (
    DataStatusQuery,
    DataStatusResponse,
    FxDataStatus,
    RefreshPricesRequest,
    RefreshPricesResponse,
)
from app.modules.assets.services.assets import AssetService
from app.modules.assets.services.bond_data import BondDataService
from app.modules.assets.services.market_data import MarketDataService
from app.modules.security.dependencies import get_current_admin, get_current_user

router = APIRouter(
    prefix="/assets",
    tags=["assets"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/", response_model=list[AssetResponse])
def list_assets(
    query: AssetListQuery = Depends(),
    service: AssetService = Depends(get_asset_service),
):
    return service.list_responses(
        query.search,
        asset_type=query.asset_type,
        asset_class_id=query.asset_class_id,
        country=query.country,
        include_archived=query.include_archived,
    )


@router.post("/", response_model=AssetResponse, status_code=201)
def create_asset(
    data: AssetCreateRequest,
    service: AssetService = Depends(get_asset_service),
):
    return service.to_response(service.create(data))


@router.get("/search-yahoo", response_model=AssetSearchResponse)
def search_yahoo(
    query: AssetSearchQuery = Depends(),
    service: AssetService = Depends(get_asset_service),
):
    """Local assets plus provider hits not stored locally yet."""
    return service.search_local_and_provider(query.q)


@router.post("/create-from-yahoo", response_model=AssetDetailResponse, status_code=201)
def create_from_yahoo(
    data: AssetFromProviderRequest,
    service: AssetService = Depends(get_asset_service),
):
    return service.to_detail(service.create_from_provider(data))


@router.get("/bond-series/{series_code}", response_model=BondSeriesSearchResponse)
def search_bond_series(
    series_code: str,
    provider: BondDataProvider = Depends(get_bond_data_provider),
):
    """Look up a bond series' terms from the data provider, to prefill the
    registration form. 404 if the provider doesn't know this series; 502
    (`BOND_DATA_UNAVAILABLE`) if the provider itself can't be reached."""
    terms = provider.fetch_series(series_code)
    if terms is None:
        raise BondTermsNotFoundError(f"Bond series {series_code} not found")
    return BondSeriesSearchResponse.from_port(terms)


@router.post(
    "/{asset_id:int}/bond-terms", response_model=BondTermsResponse, status_code=201
)
def register_bond_terms(
    asset_id: int,
    data: BondTermsCreateRequest,
    assets: AssetService = Depends(get_asset_service),
    bonds: BondDataService = Depends(get_bond_data_service),
):
    """Register (or replace) the bond series terms backing `asset_id`. Always
    stored as `source="manual"`, so the daily sync job never overwrites it.
    404 if the asset doesn't exist; 400 (`ASSET_NOT_A_BOND`) if it isn't
    `asset_type="bond"`."""
    asset = assets.get_by_id(asset_id)
    if asset.asset_type != "bond":
        raise AssetNotABondError
    terms = bonds.register_series(
        asset_id=asset_id,
        bond_symbol=data.bond_symbol,
        series_code=data.series_code,
        nominal_value=data.nominal_value,
        issue_date=data.issue_date,
        maturity_date=data.maturity_date,
        capitalization=data.capitalization,
        first_period_rate=data.first_period_rate,
        reference_type=data.reference_type,
        margin=data.margin,
        redemption_fee=data.redemption_fee,
        source="manual",
    )
    return BondTermsResponse.model_validate(terms)


@router.get("/data-status", response_model=DataStatusResponse)
def data_status(
    query: DataStatusQuery = Depends(),
    service: MarketDataService = Depends(get_market_data_service),
):
    """Freshness of prices (per active asset) and of the exchange rates."""
    status = service.data_status(only_problems=query.only_problems)
    return DataStatusResponse(
        fx=FxDataStatus(last_success_at=status.fx_last_success_at),
        assets=status.assets,  # type: ignore[arg-type]
    )


@router.post("/refresh-prices", response_model=RefreshPricesResponse, status_code=202)
def refresh_prices(
    data: RefreshPricesRequest,
    background_tasks: BackgroundTasks,
    service: AssetService = Depends(get_asset_service),
):
    """Queue a provider refresh of the given assets and answer at once; the
    request itself never calls the provider. The result shows in `price_date` and
    `GET /assets/data-status`."""
    accepted = service.accept_for_refresh(data.asset_ids)
    background_tasks.add_task(entrypoints.refresh_prices, accepted)
    return RefreshPricesResponse(accepted=accepted)


@router.get("/{asset_id:int}", response_model=AssetDetailResponse)
def get_asset(
    asset_id: int,
    service: AssetService = Depends(get_asset_service),
):
    return service.get_detail(asset_id)


@router.put(
    "/{asset_id:int}",
    dependencies=[Depends(get_current_admin)],
    response_model=AssetResponse,
)
@router.patch(
    "/{asset_id:int}",
    dependencies=[Depends(get_current_admin)],
    response_model=AssetResponse,
)
def update_asset(
    asset_id: int,
    data: AssetUpdateRequest,
    service: AssetService = Depends(get_asset_service),
):
    return service.to_response(service.update(asset_id, data))


@router.delete(
    "/{asset_id:int}", dependencies=[Depends(get_current_admin)], status_code=204
)
def delete_asset(
    asset_id: int,
    service: AssetService = Depends(get_asset_service),
):
    service.delete(asset_id)


@router.post(
    "/{asset_id:int}/archive",
    dependencies=[Depends(get_current_admin)],
    response_model=AssetResponse,
)
def archive_asset(
    asset_id: int,
    service: AssetService = Depends(get_asset_service),
):
    """Hide the asset from search and new operations, keeping its history."""
    return service.to_response(service.archive(asset_id))


@router.post(
    "/{asset_id:int}/unarchive",
    dependencies=[Depends(get_current_admin)],
    response_model=AssetResponse,
)
def unarchive_asset(
    asset_id: int,
    service: AssetService = Depends(get_asset_service),
):
    return service.to_response(service.unarchive(asset_id))
