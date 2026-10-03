"""Asset management: CRUD, creation from the market-data provider, combined
local + provider search, and the get-or-create core used by `portfolios`."""

from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from app.core.entities import apply_changes
from app.core.market_data import MarketDataUnavailableError
from app.modules.assets.constants import (
    DEFAULT_ASSET_CLASS_NAME,
    LOCAL_SEARCH_LIMIT,
    QUOTE_TYPE_ASSET_CLASSES,
)
from app.modules.assets.exceptions import (
    AssetAlreadyExistsError,
    AssetInUseError,
    AssetNotFoundOnProviderError,
    UnknownAssetClassError,
    UnknownCurrencyError,
)
from app.modules.assets.models.assets import Asset
from app.modules.assets.repositories.assets import AssetRepository
from app.modules.assets.schemas.assets import (
    AssetCreateRequest,
    AssetDetailResponse,
    AssetFromProviderRequest,
    AssetSearchResponse,
    AssetUpdateRequest,
    ProviderQuoteResponse,
)
from app.modules.assets.services.asset_classes import AssetClassService
from app.modules.assets.services.currencies import CurrencyService
from app.modules.assets.services.market_data import MarketDataService

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
    ) -> None:
        self._repo = repository
        self._asset_classes = asset_classes
        self._currencies = currencies
        self._market_data = market_data

    @staticmethod
    def _normalize_ticker(ticker: str) -> str:
        return ticker.strip().upper()

    # --- Reads ---

    def list_assets(self, search: str | None = None) -> list[Asset]:
        return self._repo.list_all(search=search)

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
        quotes = [
            q
            for q in self._market_data.search(query)
            if self._repo.find_by_ticker(self._normalize_ticker(q.symbol)) is None
        ]
        return AssetSearchResponse(
            local=[AssetDetailResponse.model_validate(asset) for asset in local],
            yahoo=[ProviderQuoteResponse.from_quote(quote) for quote in quotes],
        )

    # --- Writes (own transaction) ---

    def create(self, data: AssetCreateRequest) -> Asset:
        ticker = self._normalize_ticker(data.ticker)
        try:
            with self._repo.transaction():
                if self._repo.find_by_ticker(ticker):
                    raise AssetAlreadyExistsError
                self._require_asset_class(data.asset_class_id)
                self._require_currency(data.currency_id)
                return self._repo.create(
                    ticker=ticker,
                    name=data.name,
                    asset_class_id=data.asset_class_id,
                    currency_id=data.currency_id,
                    current_price=data.current_price,
                    exchange=data.exchange,
                    sector=data.sector,
                )
        except IntegrityError as err:
            self._raise_if_ticker_taken(ticker, err)
            raise

    def update(self, asset_id: int, data: AssetUpdateRequest) -> Asset:
        values = data.model_dump(exclude_unset=True)
        if "ticker" in values:
            values["ticker"] = self._normalize_ticker(values["ticker"])
        try:
            with self._repo.transaction():
                asset = self._repo.get_by_id(asset_id)
                if "ticker" in values:
                    duplicate = self._repo.find_by_ticker(values["ticker"])
                    if duplicate and duplicate.id != asset.id:
                        raise AssetAlreadyExistsError
                if "asset_class_id" in values:
                    self._require_asset_class(values["asset_class_id"])
                if "currency_id" in values:
                    self._require_currency(values["currency_id"])
                apply_changes(asset, values)
                return self._repo.update(asset)
        except IntegrityError as err:
            if "ticker" in values:
                self._raise_if_ticker_taken(values["ticker"], err, other_than=asset_id)
            raise

    def delete(self, asset_id: int) -> None:
        """Delete an asset no position or operation references."""
        try:
            with self._repo.transaction():
                self._repo.delete(self._repo.get_by_id(asset_id))
        except IntegrityError as err:
            raise AssetInUseError from err

    def create_from_provider(self, data: AssetFromProviderRequest) -> Asset:
        """Create an asset from the provider's quote for `data.ticker`.

        Without an explicit class/currency, the class follows the quote type
        (ETF, Crypto, Mutual Fund, otherwise Stock) and the currency the quote's
        currency; both are created when missing. Raises AssetAlreadyExistsError,
        AssetNotFoundOnProviderError, MarketDataUnavailableError.
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
                return self._repo.create(
                    ticker=ticker,
                    # Provider text is unbounded; clamp it to the column sizes.
                    name=(quote.name or ticker)[:_MAX_NAME],
                    asset_class_id=asset_class_id,
                    currency_id=currency_id,
                    current_price=quote.price or Decimal("0"),
                    exchange=quote.exchange[:_MAX_EXCHANGE],
                    sector=quote.sector[:_MAX_SECTOR],
                )
        except IntegrityError as err:
            self._raise_if_ticker_taken(ticker, err)
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
        currency_id = self._quote_currency_id(ticker)
        if currency_id is None:
            self._require_currency(fallback_currency_id)
            currency_id = fallback_currency_id
        asset_class = self._asset_classes.get_or_create_by_name(asset_class_name)
        return self._repo.create(
            ticker=ticker,
            name=ticker,
            asset_class_id=asset_class.id,
            currency_id=currency_id,
        )

    # --- Helpers ---

    def _quote_currency_id(self, ticker: str) -> int | None:
        """The id of the currency the provider quotes `ticker` in, `None` when
        the provider does not know the ticker or is unavailable."""
        try:
            quote = self._market_data.get_quote(ticker)
        except AssetNotFoundOnProviderError, MarketDataUnavailableError:
            return None
        return self._currencies.get_or_create_by_code(quote.currency).id

    def _require_asset_class(self, asset_class_id: int) -> None:
        if self._asset_classes.find_by_id(asset_class_id) is None:
            raise UnknownAssetClassError

    def _require_currency(self, currency_id: int) -> None:
        if self._currencies.find_by_id(currency_id) is None:
            raise UnknownCurrencyError

    def _raise_if_ticker_taken(
        self, ticker: str, err: IntegrityError, *, other_than: int | None = None
    ) -> None:
        """After a failed commit: a concurrent writer took the ticker first."""
        existing = self._repo.find_by_ticker(ticker)
        if existing is not None and existing.id != other_than:
            raise AssetAlreadyExistsError from err
