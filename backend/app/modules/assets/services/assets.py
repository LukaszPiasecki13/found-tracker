"""Asset management: CRUD, archiving, creation from the market-data provider,
combined local + provider search, and the get-or-create core used by `portfolios`.

Responses carry the price status (`price_date`, `price_source`, `stale`) read from
the history; `current_price` stays as the cache of the latest effective close.
"""

from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from app.core.entities import apply_changes
from app.core.market_data import MarketDataUnavailableError, Quote
from app.modules.assets.constants import (
    DEFAULT_ASSET_CLASS_NAME,
    DEFAULT_ASSET_TYPE,
    DEFAULT_PROVIDER_ASSET_TYPE,
    LOCAL_SEARCH_LIMIT,
    QUOTE_TYPE_ASSET_CLASSES,
    QUOTE_TYPE_ASSET_TYPES,
    SOURCE_YAHOO,
)
from app.modules.assets.exceptions import (
    AssetAlreadyExistsError,
    AssetArchivedError,
    AssetHasHistoryError,
    AssetNotFoundError,
    AssetNotFoundOnProviderError,
    UnknownAssetClassError,
    UnknownCurrencyError,
)
from app.modules.assets.models.assets import Asset
from app.modules.assets.repositories.assets import AssetRepository
from app.modules.assets.schemas.assets import (
    AssetBase,
    AssetCreateRequest,
    AssetDetailResponse,
    AssetFromProviderRequest,
    AssetResponse,
    AssetSearchResponse,
    AssetUpdateRequest,
    ProviderQuoteResponse,
)
from app.modules.assets.services.asset_classes import AssetClassService
from app.modules.assets.services.currencies import CurrencyService
from app.modules.assets.services.market_data import MarketDataService
from app.modules.assets.services.prices import PriceQuote, PriceService

# Column sizes of `assets_asset` (name, exchange, sector).
_MAX_NAME = 100
_MAX_EXCHANGE = 50
_MAX_SECTOR = 100


class AssetService:
    """Assets; tickers are unique and stored stripped and uppercase."""

    def __init__(
        self,
        repository: AssetRepository,
        asset_classes: AssetClassService,
        currencies: CurrencyService,
        market_data: MarketDataService,
        prices: PriceService,
        today: Callable[[], date] = date.today,
    ) -> None:
        self._repo = repository
        self._asset_classes = asset_classes
        self._currencies = currencies
        self._market_data = market_data
        self._prices = prices
        self._today = today

    @staticmethod
    def _normalize_ticker(ticker: str) -> str:
        return ticker.strip().upper()

    # --- Reads ---

    def list_assets(
        self,
        search: str | None = None,
        *,
        asset_type: str | None = None,
        asset_class_id: int | None = None,
        country: str | None = None,
        include_archived: bool = False,
    ) -> list[Asset]:
        """Assets by ticker; archived ones only with `include_archived`."""
        return self._repo.list_all(
            search=search,
            asset_type=asset_type,
            asset_class_id=asset_class_id,
            country=country,
            include_archived=include_archived,
        )

    def list_responses(
        self,
        search: str | None = None,
        *,
        asset_type: str | None = None,
        asset_class_id: int | None = None,
        country: str | None = None,
        include_archived: bool = False,
    ) -> list[AssetResponse]:
        """`list_assets` as read models with each asset's price status."""
        assets = self.list_assets(
            search,
            asset_type=asset_type,
            asset_class_id=asset_class_id,
            country=country,
            include_archived=include_archived,
        )
        quotes = self._prices.latest_quotes(assets)
        return [self._with_price(AssetResponse, asset, quotes) for asset in assets]

    def list_by_ids(self, asset_ids: list[int]) -> list[Asset]:
        """The assets with these ids, by ticker; unknown ids are absent."""
        return self._repo.list_by_ids(asset_ids)

    def accept_for_refresh(self, asset_ids: list[int]) -> list[int]:
        """The ids (deduplicated, in request order) a manual refresh will work on:
        every id must exist, archived assets are dropped. Raises
        AssetNotFoundError."""
        unique = list(dict.fromkeys(asset_ids))
        found = {asset.id: asset for asset in self._repo.list_by_ids(unique)}
        if len(found) != len(unique):
            raise AssetNotFoundError
        return [asset_id for asset_id in unique if found[asset_id].archived_at is None]

    def to_response(self, asset: Asset) -> AssetResponse:
        """One asset as a read model with its price status."""
        quotes = self._prices.latest_quotes([asset])
        return self._with_price(AssetResponse, asset, quotes)

    def get_detail(self, asset_id: int) -> AssetDetailResponse:
        """One asset with class, currency and price status. Raises
        AssetNotFoundError."""
        return self.to_detail(self._repo.get_by_id(asset_id))

    def to_detail(self, asset: Asset) -> AssetDetailResponse:
        quotes = self._prices.latest_quotes([asset])
        return self._with_price(AssetDetailResponse, asset, quotes)

    def get_by_id(self, asset_id: int) -> Asset:
        """Raises AssetNotFoundError."""
        return self._repo.get_by_id(asset_id)

    def find_by_id(self, asset_id: int) -> Asset | None:
        return self._repo.find_by_id(asset_id)

    def find_by_ticker(self, ticker: str) -> Asset | None:
        """Look up by ticker, normalized the same way as on create."""
        return self._repo.find_by_ticker(self._normalize_ticker(ticker))

    def search_local_and_provider(self, query: str) -> AssetSearchResponse:
        """Up to `LOCAL_SEARCH_LIMIT` local matches plus provider hits whose
        symbol is not a local ticker yet (read model, ADR-0003)."""
        # A picker sends "TICKER - Name"; look the ticker part up locally too.
        local_query = query.strip().split(" - ")[0].strip()
        local = self._repo.list_all(search=local_query, limit=LOCAL_SEARCH_LIMIT)
        quotes_by_asset = self._prices.latest_quotes(local)
        quotes = [
            q
            for q in self._market_data.search(query)
            if self._repo.find_by_ticker(self._normalize_ticker(q.symbol)) is None
        ]
        return AssetSearchResponse(
            local=[
                self._with_price(AssetDetailResponse, asset, quotes_by_asset)
                for asset in local
            ],
            yahoo=[ProviderQuoteResponse.from_quote(quote) for quote in quotes],
        )

    # --- Writes (own transaction) ---

    def create(self, data: AssetCreateRequest) -> Asset:
        ticker = self._normalize_ticker(data.ticker)
        try:
            with self._repo.transaction():
                if self._repo.find_by_ticker(ticker):
                    raise AssetAlreadyExistsError
                self._require_free_isin(data.isin)
                self._require_asset_class(data.asset_class_id)
                self._require_currency(data.currency_id)
                asset = self._repo.create(
                    ticker=ticker,
                    name=data.name,
                    asset_class_id=data.asset_class_id,
                    currency_id=data.currency_id,
                    current_price=data.current_price,
                    exchange=data.exchange,
                    sector=data.sector,
                    isin=data.isin,
                    mic=data.mic,
                    country=data.country,
                    asset_type=data.asset_type,
                )
                self._prices.record_manual_price_today(asset, data.current_price)
                return asset
        except IntegrityError as err:
            self._raise_if_taken(ticker, data.isin, err)
            raise

    def update(self, asset_id: int, data: AssetUpdateRequest) -> Asset:
        """Partial update. A `current_price` is recorded as today's manual close
        (it outranks a provider's of the same day); `isin`, `mic` and `country`
        accept `null` to clear. Raises AssetNotFoundError, AssetAlreadyExistsError,
        AssetArchivedError (a price on an archived asset), UnknownAssetClassError,
        UnknownCurrencyError."""
        values = data.model_dump(exclude_unset=True)
        if "ticker" in values:
            values["ticker"] = self._normalize_ticker(values["ticker"])
        price = values.pop("current_price", None)
        try:
            with self._repo.transaction():
                asset = self._repo.get_by_id(asset_id)
                if "ticker" in values:
                    duplicate = self._repo.find_by_ticker(values["ticker"])
                    if duplicate and duplicate.id != asset.id:
                        raise AssetAlreadyExistsError
                if values.get("isin") is not None:
                    self._require_free_isin(values["isin"], other_than=asset.id)
                if "asset_class_id" in values:
                    self._require_asset_class(values["asset_class_id"])
                if "currency_id" in values:
                    self._require_currency(values["currency_id"])
                if price is not None and asset.archived_at is not None:
                    raise AssetArchivedError
                apply_changes(asset, values)
                if price is not None:
                    # Through the history, which re-derives the cache.
                    self._prices.record_manual_price_today(asset, price)
                return self._repo.update(asset)
        except IntegrityError as err:
            self._raise_if_taken(
                values.get("ticker"), values.get("isin"), err, other_than=asset_id
            )
            raise

    def delete(self, asset_id: int) -> None:
        """Delete an asset with no history: no operations, positions or prices.
        Raises AssetNotFoundError, AssetHasHistoryError (archive it instead)."""
        try:
            with self._repo.transaction():
                self._repo.delete(self._repo.get_by_id(asset_id))
        except IntegrityError as err:
            raise AssetHasHistoryError from err

    def archive(self, asset_id: int) -> Asset:
        """Hide the asset from search and new operations; history, valuation and
        existing positions stay. Idempotent. Raises AssetNotFoundError."""
        with self._repo.transaction():
            asset = self._repo.get_by_id(asset_id)
            if asset.archived_at is None:
                asset.archived_at = datetime.now(UTC)
            return self._repo.update(asset)

    def unarchive(self, asset_id: int) -> Asset:
        """Undo `archive`. Idempotent. Raises AssetNotFoundError."""
        with self._repo.transaction():
            asset = self._repo.get_by_id(asset_id)
            asset.archived_at = None
            return self._repo.update(asset)

    def create_from_provider(self, data: AssetFromProviderRequest) -> Asset:
        """Create an asset from the provider's quote for `data.ticker`.

        Without an explicit class/currency, the class follows the quote type
        (ETF, Crypto, Mutual Fund, otherwise Stock) and the currency the quote's
        currency; both are created when missing. The asset type follows the quote
        type too, and the quote's price becomes today's (synthetic) provider
        price. Raises AssetAlreadyExistsError, AssetNotFoundOnProviderError,
        MarketDataUnavailableError.
        """
        ticker = self._normalize_ticker(data.ticker)
        if self._repo.find_by_ticker(ticker):
            raise AssetAlreadyExistsError
        quote = self._market_data.get_quote(ticker)
        try:
            with self._repo.transaction():
                if data.asset_class_id is not None:
                    self._require_asset_class(data.asset_class_id)
                    asset_class_id = data.asset_class_id
                else:
                    class_name = QUOTE_TYPE_ASSET_CLASSES.get(
                        quote.quote_type, DEFAULT_ASSET_CLASS_NAME
                    )
                    asset_class_id = self._asset_classes.get_or_create_by_name(
                        class_name
                    ).id
                if data.currency_id is not None:
                    self._require_currency(data.currency_id)
                    currency_id = data.currency_id
                else:
                    currency_id = self._currencies.get_or_create_by_code(
                        quote.currency
                    ).id
                price = quote.price or Decimal("0")
                asset = self._repo.create(
                    ticker=ticker,
                    # Provider text is unbounded; clamp it to the column sizes.
                    name=(quote.name or ticker)[:_MAX_NAME],
                    asset_class_id=asset_class_id,
                    currency_id=currency_id,
                    current_price=price,
                    exchange=quote.exchange[:_MAX_EXCHANGE],
                    sector=quote.sector[:_MAX_SECTOR],
                    asset_type=self._asset_type_of(quote),
                )
                if price > 0:
                    self._prices.record_closes(
                        asset,
                        {self._today(): price},
                        source=SOURCE_YAHOO,
                        is_synthetic=True,
                    )
                return asset
        except IntegrityError as err:
            self._raise_if_taken(ticker, None, err)
            raise

    # --- Cores for multi-module operations (caller owns the transaction) ---

    def get_or_create_by_ticker(
        self, ticker: str, *, asset_class_name: str, fallback_currency_id: int
    ) -> Asset:
        """Existing asset with this (normalized) ticker, or a new one named after
        the ticker, in class `asset_class_name` (created when missing), flushed so
        it has an id. Raises UnknownCurrencyError.

        The new asset is quoted in the provider's currency for the ticker (created
        when missing); only when the provider has no quote - or is down - does it
        fall back to `fallback_currency_id`, as the price is then unknown anyway.

        No-commit core — transaction belongs to caller.
        """
        ticker = self._normalize_ticker(ticker)
        asset = self._repo.find_by_ticker(ticker)
        if asset is not None:
            return asset
        quote = self._provider_quote(ticker)
        if quote is not None:
            currency_id = self._currencies.get_or_create_by_code(quote.currency).id
            asset_type = self._asset_type_of(quote)
        else:
            self._require_currency(fallback_currency_id)
            currency_id = fallback_currency_id
            asset_type = DEFAULT_ASSET_TYPE
        asset_class = self._asset_classes.get_or_create_by_name(asset_class_name)
        return self._repo.create(
            ticker=ticker,
            name=ticker,
            asset_class_id=asset_class.id,
            currency_id=currency_id,
            asset_type=asset_type,
        )

    # --- Helpers ---

    def _provider_quote(self, ticker: str) -> Quote | None:
        """The provider's quote for `ticker`, `None` when the provider does not
        know the ticker or is unavailable."""
        try:
            return self._market_data.get_quote(ticker)
        except AssetNotFoundOnProviderError, MarketDataUnavailableError:
            return None

    @staticmethod
    def _asset_type_of(quote: Quote) -> str:
        return QUOTE_TYPE_ASSET_TYPES.get(quote.quote_type, DEFAULT_PROVIDER_ASSET_TYPE)

    def _with_price[R: AssetBase](
        self, schema: type[R], asset: Asset, quotes: dict[int, PriceQuote]
    ) -> R:
        """`asset` as `schema` plus its price status (`stale` when it has no
        price at all)."""
        response = schema.model_validate(asset)
        quote = quotes.get(asset.id)
        if quote is None:
            return response
        return response.model_copy(
            update={
                "price_date": quote.price_date,
                "price_source": quote.source,
                "stale": quote.stale,
            }
        )

    def _require_free_isin(
        self, isin: str | None, *, other_than: int | None = None
    ) -> None:
        if isin is None:
            return
        existing = self._repo.find_by_isin(isin)
        if existing is not None and existing.id != other_than:
            raise AssetAlreadyExistsError("Asset with this ISIN already exists")

    def _require_asset_class(self, asset_class_id: int) -> None:
        if self._asset_classes.find_by_id(asset_class_id) is None:
            raise UnknownAssetClassError

    def _require_currency(self, currency_id: int) -> None:
        if self._currencies.find_by_id(currency_id) is None:
            raise UnknownCurrencyError

    def _raise_if_taken(
        self,
        ticker: str | None,
        isin: str | None,
        err: IntegrityError,
        *,
        other_than: int | None = None,
    ) -> None:
        """After a failed commit: a concurrent writer took the ticker or ISIN."""
        if ticker is not None:
            existing = self._repo.find_by_ticker(ticker)
            if existing is not None and existing.id != other_than:
                raise AssetAlreadyExistsError from err
        if isin is not None:
            existing = self._repo.find_by_isin(isin)
            if existing is not None and existing.id != other_than:
                raise AssetAlreadyExistsError(
                    "Asset with this ISIN already exists"
                ) from err
