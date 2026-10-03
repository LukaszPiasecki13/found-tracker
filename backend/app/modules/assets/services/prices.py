"""Price history: effective close of a day, series, manual prices, and the write
core the refresh uses. `Asset.current_price` is a cache of the latest effective
close, kept in step in the same transaction as every history write (ADR-0015)."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal

from app.modules.assets.constants import (
    KNOWN_PROVIDER_SOURCES,
    SOURCE_MANUAL,
    STALE_AFTER_DAYS,
)
from app.modules.assets.domain import best_per_day, is_stale, pick_effective, storable
from app.modules.assets.exceptions import (
    AssetArchivedError,
    FutureDateError,
    InvalidDateRangeError,
    PriceCurrencyMismatchError,
    PriceNotFoundError,
)
from app.modules.assets.models.assets import Asset
from app.modules.assets.models.prices import AssetPrice
from app.modules.assets.repositories.assets import AssetRepository
from app.modules.assets.repositories.prices import PriceRepository

# A forward-filled series is built day by day; keep one request bounded.
MAX_SERIES_DAYS = 3660


@dataclass(frozen=True, slots=True)
class PriceQuote:
    """The effective close an asset has on a day, with where it came from."""

    asset_id: int
    price_date: date
    close: Decimal
    currency_id: int
    source: str
    is_synthetic: bool
    stale: bool


@dataclass(frozen=True, slots=True)
class PriceSeriesItem:
    """One day of a series. `price_date` is the day the close was observed; it is
    earlier than `day` when the close was carried forward."""

    day: date
    price_date: date
    close: Decimal
    source: str
    is_synthetic: bool
    stale: bool


@dataclass(frozen=True, slots=True)
class PriceSeries:
    asset_id: int
    currency_id: int
    items: list[PriceSeriesItem]


def _day(row: AssetPrice) -> date:
    return row.price_date


def _source(row: AssetPrice) -> str:
    return row.source


class PriceService:
    """Reads and writes an asset's close history."""

    def __init__(
        self,
        price_repository: PriceRepository,
        asset_repository: AssetRepository,
        today: Callable[[], date] = date.today,
    ) -> None:
        self._prices = price_repository
        self._assets = asset_repository
        self._today = today

    # --- Reads ---

    def find_close(self, asset_id: int, as_of: date | None = None) -> PriceQuote | None:
        """The close that prices the asset on `as_of` (default today): the latest
        day not after it, `manual` first, then providers. `None` when the asset
        has none. Raises AssetNotFoundError."""
        asset = self._assets.get_by_id(asset_id)
        reference = as_of or self._today()
        rows = self._prices.latest_day_rows(asset.id, reference)
        return self._quote(asset, rows, reference)

    def latest_quotes(self, assets: list[Asset]) -> dict[int, PriceQuote]:
        """Each asset's latest effective close, in one query; assets without a
        price are absent."""
        rows = self._prices.latest_day_rows_for([asset.id for asset in assets])
        by_asset: dict[int, list[AssetPrice]] = {}
        for row in rows:
            by_asset.setdefault(row.asset_id, []).append(row)
        today = self._today()
        quotes: dict[int, PriceQuote] = {}
        for asset in assets:
            quote = self._quote(asset, by_asset.get(asset.id, []), today)
            if quote is not None:
                quotes[asset.id] = quote
        return quotes

    def last_provider_fetch(self, assets: list[Asset]) -> dict[int, datetime]:
        """When each asset last received a provider observation."""
        return self._prices.last_fetched_at([asset.id for asset in assets])

    def series(
        self,
        asset_id: int,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        source: str | None = None,
        fill: Literal["none", "forward"] = "none",
    ) -> PriceSeries:
        """Closes of an asset between `from_date` and `to_date` (inclusive), one
        per day that has one - the winning source of the day, or only `source`
        when given. `fill="forward"` returns every calendar day from `from_date`
        on, carrying the last close over days without one (never stored).

        Raises AssetNotFoundError, InvalidDateRangeError.
        """
        asset = self._assets.get_by_id(asset_id)
        if from_date is not None and to_date is not None and from_date > to_date:
            raise InvalidDateRangeError
        if fill == "none":
            rows = self._prices.list_for_asset(
                asset.id, up_to=to_date, from_date=from_date, source=source
            )
            winners = best_per_day(
                rows,
                day_of=_day,
                source_of=_source,
                known_providers=KNOWN_PROVIDER_SOURCES,
            )
            items = [
                self._item(day, winner, day) for day, winner in sorted(winners.items())
            ]
            return PriceSeries(asset.id, asset.currency_id, items)

        if from_date is None:
            raise InvalidDateRangeError("Forward fill needs a `from` date")
        end = to_date or self._today()
        if (end - from_date).days >= MAX_SERIES_DAYS:
            raise InvalidDateRangeError(
                f"Forward fill covers at most {MAX_SERIES_DAYS} days"
            )
        rows = self._prices.list_for_asset(asset.id, up_to=end, source=source)
        winners = best_per_day(
            rows, day_of=_day, source_of=_source, known_providers=KNOWN_PROVIDER_SOURCES
        )
        carried_days = sorted(day for day in winners if day <= from_date)
        carried = winners[carried_days[-1]] if carried_days else None
        items = []
        day = from_date
        while day <= end:
            carried = winners.get(day, carried)
            if carried is not None:
                items.append(self._item(day, carried, day))
            day += timedelta(days=1)
        return PriceSeries(asset.id, asset.currency_id, items)

    # --- Writes (own transaction) ---

    def set_manual_price(
        self,
        asset_id: int,
        price_date: date,
        close: Decimal,
        currency_id: int | None = None,
    ) -> AssetPrice:
        """Record (or replace) the manual close of `price_date`. Manual always
        wins over a provider on the same day. Raises AssetNotFoundError,
        AssetArchivedError, FutureDateError, PriceCurrencyMismatchError."""
        with self._prices.transaction():
            asset = self._assets.get_by_id(asset_id)
            if asset.archived_at is not None:
                raise AssetArchivedError
            if price_date > self._today():
                raise FutureDateError
            if currency_id is not None and currency_id != asset.currency_id:
                raise PriceCurrencyMismatchError
            row = self._prices.upsert(
                asset_id=asset.id,
                price_date=price_date,
                close=close,
                currency_id=asset.currency_id,
                source=SOURCE_MANUAL,
                is_synthetic=False,
            )
            self.sync_current_price(asset)
            return row

    def delete_manual_price(self, asset_id: int, price_date: date) -> None:
        """Remove the manual close of `price_date`. Raises AssetNotFoundError,
        AssetArchivedError, PriceNotFoundError."""
        with self._prices.transaction():
            asset = self._assets.get_by_id(asset_id)
            if asset.archived_at is not None:
                raise AssetArchivedError
            row = self._prices.find(asset.id, price_date, SOURCE_MANUAL)
            if row is None:
                raise PriceNotFoundError
            self._prices.delete(row)
            self.sync_current_price(asset)

    # --- Cores for the refresh and for AssetService (caller owns the transaction) ---

    def record_closes(
        self,
        asset: Asset,
        closes: Mapping[date, Decimal],
        *,
        source: str,
        is_synthetic: bool,
    ) -> int:
        """Store provider closes (ones that do not fit the column are dropped) and
        refresh the asset's cached price; returns how many were stored.
        Idempotent: the same day and source overwrites.

        No-commit core - transaction belongs to caller.
        """
        stored = 0
        for day, raw in closes.items():
            close = storable(raw)
            if close is None:
                continue
            self._prices.upsert(
                asset_id=asset.id,
                price_date=day,
                close=close,
                currency_id=asset.currency_id,
                source=source,
                is_synthetic=is_synthetic,
            )
            stored += 1
        if stored:
            self.sync_current_price(asset)
        return stored

    def record_manual_price_today(self, asset: Asset, close: Decimal) -> None:
        """A hand-entered price (create or edit of an asset) as today's manual
        close; a zero price records nothing.

        No-commit core - transaction belongs to caller.
        """
        if close <= 0:
            return
        self._prices.upsert(
            asset_id=asset.id,
            price_date=self._today(),
            close=close,
            currency_id=asset.currency_id,
            source=SOURCE_MANUAL,
            is_synthetic=False,
        )
        self.sync_current_price(asset)

    def sync_current_price(self, asset: Asset) -> None:
        """Set `asset.current_price` to the latest effective close; keep it when
        the history is empty. No-commit core."""
        rows = self._prices.latest_day_rows(asset.id)
        winner = pick_effective(
            rows,
            day_of=_day,
            source_of=_source,
            known_providers=KNOWN_PROVIDER_SOURCES,
            as_of=date.max,
        )
        if winner is not None:
            asset.current_price = winner.close

    # --- Helpers ---

    @staticmethod
    def _item(day: date, row: AssetPrice, reference: date) -> PriceSeriesItem:
        return PriceSeriesItem(
            day=day,
            price_date=row.price_date,
            close=row.close,
            source=row.source,
            is_synthetic=row.is_synthetic,
            stale=is_stale(
                row.price_date, today=reference, max_age_days=STALE_AFTER_DAYS
            ),
        )

    def _quote(
        self, asset: Asset, rows: list[AssetPrice], reference: date
    ) -> PriceQuote | None:
        winner = pick_effective(
            rows,
            day_of=_day,
            source_of=_source,
            known_providers=KNOWN_PROVIDER_SOURCES,
            as_of=date.max,
        )
        if winner is None:
            return None
        return PriceQuote(
            asset_id=asset.id,
            price_date=winner.price_date,
            close=winner.close,
            currency_id=winner.currency_id,
            source=winner.source,
            is_synthetic=winner.is_synthetic,
            stale=is_stale(
                winner.price_date, today=reference, max_age_days=STALE_AFTER_DAYS
            ),
        )
