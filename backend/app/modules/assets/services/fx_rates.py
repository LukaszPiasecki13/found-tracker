"""Exchange-rate history: direct and inverse lookups, manual rates, and the write
core the refresh uses. `Currency.exchange_rate` ("units of the system currency
per one unit") is a cache of the latest effective rate to the system currency,
kept in step in the same transaction as every history write (ADR-0015).

Cross rates (through a third currency) are not composed here: `portfolios` builds
them from the direct and inverse rates this service returns.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from app.modules.assets.constants import (
    DEFAULT_CURRENCY_CODE,
    KNOWN_PROVIDER_SOURCES,
    MAX_PRICE_OR_RATE,
    SOURCE_MANUAL,
    STALE_AFTER_DAYS,
)
from app.modules.assets.domain import invert_rate, is_stale, pick_effective, storable
from app.modules.assets.exceptions import (
    CurrencyNotFoundError,
    FutureDateError,
    InvalidDateRangeError,
    RateMissingError,
    UnknownCurrencyError,
)
from app.modules.assets.models.currencies import Currency
from app.modules.assets.models.fx_rates import FxRate
from app.modules.assets.repositories.currencies import CurrencyRepository
from app.modules.assets.repositories.fx_rates import FxRateRepository

type Via = Literal["identity", "direct", "inverse"]


@dataclass(frozen=True, slots=True)
class FxQuote:
    """Units of `to_currency` per one unit of `from_currency` on `rate_date`."""

    from_currency: str
    to_currency: str
    rate: Decimal
    rate_date: date
    source: str
    table_no: str | None
    is_synthetic: bool
    stale: bool
    via: Via


def _day(row: FxRate) -> date:
    return row.rate_date


def _source(row: FxRate) -> str:
    return row.source


class FxRateService:
    """Reads and writes the exchange-rate history between currencies."""

    def __init__(
        self,
        fx_repository: FxRateRepository,
        currency_repository: CurrencyRepository,
        today: Callable[[], date] = date.today,
    ) -> None:
        self._rates = fx_repository
        self._currencies = currency_repository
        self._today = today

    # --- Reads ---

    def get_rate(
        self, from_code: str, to_code: str, as_of: date | None = None
    ) -> FxQuote:
        """The rate on `as_of` (default today) between two currencies, direct or
        inverse; the observation that is newer wins, a direct one on a tie. The
        same currency is `identity`. Raises CurrencyNotFoundError, RateMissingError.
        """
        source_currency = self._get_currency(from_code)
        target_currency = self._get_currency(to_code)
        reference = as_of or self._today()
        if source_currency.id == target_currency.id:
            return FxQuote(
                from_currency=source_currency.code,
                to_currency=target_currency.code,
                rate=Decimal(1),
                rate_date=reference,
                source="identity",
                table_no=None,
                is_synthetic=False,
                stale=False,
                via="identity",
            )
        found = self._resolve(source_currency.id, target_currency.id, reference)
        if found is None:
            raise RateMissingError
        row, via = found
        return FxQuote(
            from_currency=source_currency.code,
            to_currency=target_currency.code,
            rate=row.rate if via == "direct" else invert_rate(row.rate),
            rate_date=row.rate_date,
            source=row.source,
            table_no=row.table_no,
            is_synthetic=row.is_synthetic,
            stale=is_stale(
                row.rate_date, today=reference, max_age_days=STALE_AFTER_DAYS
            ),
            via=via,
        )

    def history(
        self,
        from_code: str,
        to_code: str,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
        source: str | None = None,
    ) -> list[FxRate]:
        """Stored observations of the directed pair, oldest first. Raises
        CurrencyNotFoundError, InvalidDateRangeError."""
        source_currency = self._get_currency(from_code)
        target_currency = self._get_currency(to_code)
        if from_date is not None and to_date is not None and from_date > to_date:
            raise InvalidDateRangeError
        return self._rates.list_pair(
            source_currency.id,
            target_currency.id,
            from_date=from_date,
            to_date=to_date,
            source=source,
        )

    def last_provider_fetch(self) -> datetime | None:
        return self._rates.last_fetched_at()

    # --- Writes (own transaction) ---

    def set_manual_rate(
        self, from_currency_id: int, to_currency_id: int, rate_date: date, rate: Decimal
    ) -> FxRate:
        """Record (or replace) the manual rate of `rate_date`; it wins over a
        provider on the same day. Raises UnknownCurrencyError, FutureDateError."""
        with self._rates.transaction():
            source_currency = self._require(from_currency_id)
            target_currency = self._require(to_currency_id)
            if rate_date > self._today():
                raise FutureDateError
            row = self._rates.upsert(
                from_id=source_currency.id,
                to_id=target_currency.id,
                rate_date=rate_date,
                rate=rate,
                source=SOURCE_MANUAL,
            )
            self.sync_cached_rate(source_currency)
            self.sync_cached_rate(target_currency)
            return row

    # --- Cores for the refresh and CurrencyService (caller owns the transaction) ---

    def record_rate(
        self,
        source_currency: Currency,
        target_currency: Currency,
        rate: Decimal,
        *,
        rate_date: date,
        source: str,
        table_no: str | None = None,
        is_synthetic: bool = False,
    ) -> None:
        """Store one observation (idempotent per pair, day and source) and refresh
        the cached rates of both currencies. A rate that does not fit the column is
        dropped.

        No-commit core - transaction belongs to caller.
        """
        stored = storable(rate)
        if stored is None or source_currency.id == target_currency.id:
            return
        rate = stored
        self._rates.upsert(
            from_id=source_currency.id,
            to_id=target_currency.id,
            rate_date=rate_date,
            rate=rate,
            source=source,
            table_no=table_no,
            is_synthetic=is_synthetic,
        )
        self.sync_cached_rate(source_currency)
        self.sync_cached_rate(target_currency)

    def record_manual_rate_to_base(self, currency: Currency, rate: Decimal) -> None:
        """A hand-entered `exchange_rate` of a currency as today's manual rate to
        the system currency; nothing when it is the system currency or that
        currency does not exist yet.

        No-commit core - transaction belongs to caller.
        """
        base = self._currencies.find_by_code(DEFAULT_CURRENCY_CODE)
        if base is None or base.id == currency.id:
            return
        self.record_rate(
            currency, base, rate, rate_date=self._today(), source=SOURCE_MANUAL
        )

    def sync_cached_rate(self, currency: Currency) -> None:
        """Set `currency.exchange_rate` to the latest effective rate to the system
        currency; keep it when the history has none. No-commit core."""
        if currency.code == DEFAULT_CURRENCY_CODE:
            return
        base = self._currencies.find_by_code(DEFAULT_CURRENCY_CODE)
        if base is None:
            return
        found = self._resolve(currency.id, base.id, date.max)
        if found is None:
            return
        row, via = found
        rate = row.rate if via == "direct" else invert_rate(row.rate)
        if 0 < rate < MAX_PRICE_OR_RATE:
            currency.exchange_rate = rate

    # --- Helpers ---

    def _resolve(
        self, from_id: int, to_id: int, as_of: date
    ) -> tuple[FxRate, Literal["direct", "inverse"]] | None:
        direct = pick_effective(
            self._rates.latest_day_rows(from_id, to_id, _bounded(as_of)),
            day_of=_day,
            source_of=_source,
            known_providers=KNOWN_PROVIDER_SOURCES,
            as_of=date.max,
        )
        inverse = pick_effective(
            self._rates.latest_day_rows(to_id, from_id, _bounded(as_of)),
            day_of=_day,
            source_of=_source,
            known_providers=KNOWN_PROVIDER_SOURCES,
            as_of=date.max,
        )
        if direct is not None and (
            inverse is None or direct.rate_date >= inverse.rate_date
        ):
            return direct, "direct"
        if inverse is not None:
            return inverse, "inverse"
        return None

    def _get_currency(self, code: str) -> Currency:
        currency = self._currencies.find_by_code(code.strip().upper())
        if currency is None:
            raise CurrencyNotFoundError
        return currency

    def _require(self, currency_id: int) -> Currency:
        currency = self._currencies.find_by_id(currency_id)
        if currency is None:
            raise UnknownCurrencyError
        return currency


def _bounded(as_of: date) -> date | None:
    """`date.max` means "no upper bound" for the repository query."""
    return None if as_of == date.max else as_of
