"""Daily snapshots and the portfolio's time-weighted return (ADR-0004, ADR-0016).

`SnapshotService` keeps `portfolios_daily` current for one portfolio and turns it
into the cumulative return. A write of an operation only marks the portfolio
`dirty_from` (in its own transaction); the rows are rebuilt lazily here, on the
next read: from the first stale day to yesterday, under a row lock on the
portfolio. Today is never stored - it is added live from the current valuation.

Closes come from the `assets` history (`PriceService`, ADR-0015); the provider's
daily closes for the days being built are stored first (`backfill_closes`), so a
later read only ever fetches the days that are new. Anything that makes the
number unreliable - an asset quoted in another currency than the portfolio (no
historical FX yet), a missing close, a provider failure - gives no return at all
(`None`), never a wrong one, and stores nothing.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.core.market_data import MarketDataUnavailableError
from app.modules.assets.models import Asset
from app.modules.assets.services.market_data import MarketDataService
from app.modules.assets.services.prices import PriceService
from app.modules.portfolios.domain import (
    TWR_METHOD,
    Closes,
    DailyRow,
    DailySnapshotBuilder,
    DatedOperation,
    OperationInput,
    PortfolioDomainError,
    external_flow,
    return_pct,
    twr_method,
)
from app.modules.portfolios.models import Operation, Portfolio, PortfolioDaily
from app.modules.portfolios.repositories.daily import DailyRepository
from app.modules.portfolios.repositories.operations import OperationRepository
from app.modules.portfolios.repositories.portfolios import PortfolioRepository

logger = logging.getLogger(__name__)

# Days before the first built day whose close is read too: a forward fill needs a
# close to carry across a weekend or a holiday (and a series is capped, see below).
_LOOKBACK = timedelta(days=10)
_ONE_DAY = timedelta(days=1)
# `PriceService.series` caps one forward-filled series; a cold build of a very old
# portfolio is cut into windows of this many days.
_WINDOW_DAYS = 3000


def _utc_today() -> date:
    return datetime.now(UTC).date()


def operation_day(moment: datetime) -> date:
    """The calendar day (UTC) an operation lands on."""
    if moment.tzinfo is None:
        return moment.date()
    return moment.astimezone(UTC).date()


def _row(stored: PortfolioDaily) -> DailyRow:
    return DailyRow(
        day=stored.day,
        value=stored.value,
        cash=stored.cash,
        inflow=stored.inflow,
        outflow=stored.outflow,
        r_day=stored.r_day,
        twr_index=stored.twr_index,
    )


@dataclass(frozen=True, slots=True)
class TwrResult:
    """The cumulative time-weighted return in percent and how it was computed."""

    pct: Decimal
    method: str = TWR_METHOD


class SnapshotService:
    """Daily rows and the return of the owner's portfolios."""

    def __init__(
        self,
        portfolio_repo: PortfolioRepository,
        daily_repo: DailyRepository,
        operation_repo: OperationRepository,
        price_service: PriceService,
        market_data: MarketDataService,
        builder: DailySnapshotBuilder,
        today: Callable[[], date] = _utc_today,
    ) -> None:
        self._portfolios = portfolio_repo
        self._daily = daily_repo
        self._operations = operation_repo
        self._prices = price_service
        self._market_data = market_data
        self._builder = builder
        self._today = today

    def twr(
        self, portfolio: Portfolio, current_value: Decimal | None
    ) -> TwrResult | None:
        """The portfolio's cumulative return since its first operation, in
        percent; `None` when it cannot be told (no operations, no current value,
        a missing close, a provider failure).

        Two approximations keep an otherwise unknowable portfolio computable, and
        name themselves in `method`: an asset with no market price at all is valued
        at its last trade price, and an asset quoted in another currency than the
        portfolio's is converted at its last trade's `fx_rate`. Then today is built
        by the same rules as the days before it (not from the live valuation, which
        uses current prices and rates), so that no jump appears between them."""
        if current_value is None:
            return None
        history = self._operations.list_by_portfolio(portfolio.id)
        if not history:
            return None
        assets = _assets_of(history)
        foreign = {
            asset.id
            for asset in assets
            if asset.currency_id != portfolio.base_currency_id
        }
        dated = _dated(history)
        today = self._today()
        yesterday = today - _ONE_DAY
        try:
            first_day = dated[0].day
            if not self._is_current(
                portfolio, first_day, yesterday
            ) and not self._rebuild(portfolio, assets, foreign, first_day, yesterday):
                return None
            # After the rebuild: it is what fetches an asset's missing history.
            priceless = self._priceless(assets)
            stored = self._daily.last_row(portfolio.id)
            previous = _row(stored) if stored is not None else None
            if priceless or foreign:
                index = self._index_today(dated, assets, foreign, previous, today)
            else:
                flow = sum(
                    (external_flow(d.operation) for d in dated if d.day >= today),
                    Decimal(0),
                )
                index = self._builder.index_after(previous, flow, current_value)
        except MarketDataUnavailableError, PortfolioDomainError:
            logger.info(
                "Return of portfolio %s not computed", portfolio.id, exc_info=True
            )
            return None
        method = twr_method(last_trade=bool(priceless), trade_fx=bool(foreign))
        return TwrResult(return_pct(index), method)

    def _index_today(
        self,
        dated: list[DatedOperation],
        assets: list[Asset],
        foreign: set[int],
        previous: DailyRow | None,
        today: date,
    ) -> Decimal:
        """The cumulative index at the end of today, built (not stored) like the
        stored days: today's row on top of yesterday's."""
        closes = self._closes(assets, today, today)
        rows = self._builder.build(
            dated, closes, start=today, end=today, previous=previous, foreign=foreign
        )
        if rows:
            return rows[-1].twr_index
        return previous.twr_index if previous else Decimal(1)

    def _priceless(self, assets: list[Asset]) -> set[int]:
        """The assets that have no close at all (the provider does not know them)."""
        quotes = self._prices.latest_quotes(assets)
        return {asset.id for asset in assets if asset.id not in quotes}

    # --- Rebuild ---

    def _is_current(
        self, portfolio: Portfolio, first_day: date, yesterday: date
    ) -> bool:
        """Whether the stored rows already reach yesterday and none is stale (a
        portfolio whose first day is today has nothing to store yet)."""
        if portfolio.dirty_from is not None:
            return False
        if first_day > yesterday:
            return True
        last = self._daily.last_row(portfolio.id)
        return last is not None and last.day >= yesterday

    def _rebuild(
        self,
        portfolio: Portfolio,
        assets: list[Asset],
        foreign: set[int],
        first_day: date,
        yesterday: date,
    ) -> bool:
        """Store the days from the first stale one to yesterday. `False` when the
        portfolio changed under us (the next read rebuilds); raises
        MarketDataUnavailableError, PortfolioDomainError (a missing close, a
        refused history)."""
        kept = self._daily.last_row(portfolio.id, before=portfolio.dirty_from)
        first = kept.day + _ONE_DAY if kept is not None else first_day
        if first <= yesterday and assets:
            # Provider closes are fetched, and committed, before the row lock.
            self._market_data.backfill_closes(
                assets, first - _LOOKBACK, yesterday + _ONE_DAY
            )
        dirty_seen = portfolio.dirty_from
        with self._daily.transaction():
            self._portfolios.lock_owned(portfolio.id, portfolio.owner_id)
            fresh = self._portfolios.get_owned(portfolio.id, portfolio.owner_id)
            if fresh.dirty_from != dirty_seen:
                # Someone rebuilt and cleared the mark meanwhile (current); or a
                # write marked it (the next read rebuilds).
                return fresh.dirty_from is None
            history = self._operations.list_by_portfolio(portfolio.id)
            dated = _dated(history)
            kept = self._daily.last_row(portfolio.id, before=fresh.dirty_from)
            start = kept.day + _ONE_DAY if kept is not None else dated[0].day
            rows = self._build(
                dated, _assets_of(history), foreign, start, yesterday, kept
            )
            # Stale rows start at `dirty_from`, which may lie before `start` when
            # nothing is left to build up to yesterday.
            stale = min(start, fresh.dirty_from or start)
            self._daily.delete_from(portfolio.id, stale)
            self._daily.add_many(
                PortfolioDaily(
                    portfolio_id=portfolio.id,
                    day=row.day,
                    value=row.value,
                    cash=row.cash,
                    inflow=row.inflow,
                    outflow=row.outflow,
                    r_day=row.r_day,
                    twr_index=row.twr_index,
                )
                for row in rows
            )
            fresh.dirty_from = None
            self._portfolios.update(fresh)
        return True

    def _build(
        self,
        dated: list[DatedOperation],
        assets: list[Asset],
        foreign: set[int],
        start: date,
        end: date,
        kept: PortfolioDaily | None,
    ) -> list[DailyRow]:
        """Rows for `start..end`, in windows the price series can serve."""
        rows: list[DailyRow] = []
        previous = _row(kept) if kept is not None else None
        while start <= end:
            window_end = min(end, start + timedelta(days=_WINDOW_DAYS))
            closes = self._closes(assets, start, window_end)
            built = self._builder.build(
                dated,
                closes,
                start=start,
                end=window_end,
                previous=previous,
                foreign=foreign,
            )
            rows.extend(built)
            previous = built[-1] if built else previous
            start = window_end + _ONE_DAY
        return rows

    def _closes(self, assets: list[Asset], start: date, end: date) -> Closes:
        """Each asset's closes for `start..end`, carried forward over days without
        one (a series starts `_LOOKBACK` earlier so the first day has a close)."""
        closes: dict[int, dict[date, Decimal]] = {}
        for asset in assets:
            series = self._prices.series(
                asset.id, from_date=start - _LOOKBACK, to_date=end, fill="forward"
            )
            closes[asset.id] = {item.day: item.close for item in series.items}
        return closes


def _assets_of(history: list[Operation]) -> list[Asset]:
    seen: dict[int, Asset] = {}
    for operation in history:
        if operation.asset is not None:
            seen[operation.asset.id] = operation.asset
    return list(seen.values())


def _dated(history: list[Operation]) -> list[DatedOperation]:
    return [
        DatedOperation(
            operation_day(op.operation_date), OperationInput.from_operation(op)
        )
        for op in history
    ]
