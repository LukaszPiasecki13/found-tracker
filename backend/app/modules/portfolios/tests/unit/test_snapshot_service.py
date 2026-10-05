"""`SnapshotService` - lazily built daily rows and the time-weighted return
(ADR-0004, ADR-0016) with mocked repositories, a fake price series and an
in-memory `portfolios_daily`."""

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from functools import partial
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.core.market_data import MarketDataUnavailableError
from app.infrastructure.sql.repository import SQLRepository
from app.modules.portfolios.domain import DailySnapshotBuilder, PortfolioLedger
from app.modules.portfolios.models import PortfolioDaily
from app.modules.portfolios.services.snapshots import SnapshotService

D = Decimal
TODAY = date(2026, 1, 9)
ASSET = SimpleNamespace(id=5, currency_id=1)


def _at(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, 12, tzinfo=UTC)


def _operation(
    operation_type: str, day: date, operation_id: int, **values: Any
) -> SimpleNamespace:
    fields: dict[str, Any] = {
        "id": operation_id,
        "operation_type": operation_type,
        "asset_id": None,
        "asset": None,
        "quantity": D("0"),
        "price": D("0"),
        "amount": None,
        "fee": D("0"),
        "fx_rate": D("1"),
        "ratio": None,
        "operation_date": _at(day),
    }
    fields.update(values)
    return SimpleNamespace(**fields)


def _deposit(day: date, amount: str, operation_id: int = 1) -> SimpleNamespace:
    return _operation("deposit", day, operation_id, amount=D(amount))


def _buy(
    day: date,
    quantity: str,
    price: str,
    operation_id: int = 2,
    asset: SimpleNamespace = ASSET,
) -> SimpleNamespace:
    return _operation(
        "buy",
        day,
        operation_id,
        asset_id=asset.id,
        asset=asset,
        quantity=D(quantity),
        price=D(price),
    )


def _portfolio(**values: Any) -> SimpleNamespace:
    fields: dict[str, Any] = {
        "id": 1,
        "owner_id": 7,
        "base_currency_id": 1,
        "dirty_from": None,
        "positions": [],
    }
    fields.update(values)
    return SimpleNamespace(**fields)


def _series(closes: Callable[[date], Decimal]) -> Callable[..., SimpleNamespace]:
    """`PriceService.series(fill="forward")` with a close for every day."""

    def series(
        asset_id: int, *, from_date: date, to_date: date, fill: str
    ) -> SimpleNamespace:
        days = [
            from_date + timedelta(days=i) for i in range((to_date - from_date).days + 1)
        ]
        return SimpleNamespace(
            items=[SimpleNamespace(day=day, close=closes(day)) for day in days]
        )

    return series


def _closes(day: date) -> Decimal:
    """100 until the 6th, 110 from the 7th on."""
    return D("100") if day <= date(2026, 1, 6) else D("110")


@pytest.fixture
def stored() -> list[PortfolioDaily]:
    return []


@pytest.fixture
def daily_repo(session: MagicMock, stored: list[PortfolioDaily]) -> MagicMock:
    repo = MagicMock()
    repo.commit = session.commit
    repo.rollback = session.rollback
    repo.transaction = partial(SQLRepository.transaction, repo)

    def last_row(
        portfolio_id: int, *, before: date | None = None
    ) -> PortfolioDaily | None:
        rows = [row for row in stored if before is None or row.day < before]
        return max(rows, key=lambda row: row.day, default=None)

    def delete_from(portfolio_id: int, day: date) -> None:
        stored[:] = [row for row in stored if row.day < day]

    repo.last_row.side_effect = last_row
    repo.delete_from.side_effect = delete_from
    repo.add_many.side_effect = lambda rows: stored.extend(rows)
    return repo


@pytest.fixture
def prices() -> MagicMock:
    prices = MagicMock()
    prices.series.side_effect = _series(_closes)
    # Every asset has closes unless a test says otherwise.
    prices.latest_quotes.side_effect = lambda assets: {a.id: object() for a in assets}
    return prices


@pytest.fixture
def market_data() -> MagicMock:
    return MagicMock()


@pytest.fixture
def history() -> list[SimpleNamespace]:
    """Deposit 1000 and buy 10 at 100 on 5 January."""
    return [_deposit(date(2026, 1, 5), "1000"), _buy(date(2026, 1, 5), "10", "100")]


@pytest.fixture
def portfolio(portfolio_repo: MagicMock) -> Any:
    portfolio = _portfolio()
    portfolio_repo.get_owned.return_value = portfolio
    return portfolio


@pytest.fixture
def today() -> list[date]:
    return [TODAY]


@pytest.fixture
def service(
    portfolio_repo: MagicMock,
    daily_repo: MagicMock,
    operation_repo: MagicMock,
    prices: MagicMock,
    market_data: MagicMock,
    history: list[SimpleNamespace],
    portfolio: Any,
    today: list[date],
) -> SnapshotService:
    operation_repo.list_by_portfolio.side_effect = lambda _: list(history)
    return SnapshotService(
        portfolio_repo,
        daily_repo,
        operation_repo,
        prices,
        market_data,
        DailySnapshotBuilder(PortfolioLedger()),
        today=lambda: today[0],
    )


def test_a_cold_read_builds_every_day_up_to_yesterday(
    service: SnapshotService,
    portfolio: Any,
    market_data: MagicMock,
    stored: list[PortfolioDaily],
    session: MagicMock,
) -> None:
    # Today the portfolio is worth 1210: +10% on top of the stored +10%.
    result = service.twr(portfolio, D("1210"))

    assert result is not None
    assert result.pct == D("21")
    assert result.method == "daily_pp_v1"
    assert [row.day for row in stored] == [date(2026, 1, d) for d in (5, 6, 7, 8)]
    assert [row.value for row in stored] == [D("1000"), D("1000"), D("1100"), D("1100")]
    assert stored[-1].twr_index == D("1.1")
    assert portfolio.dirty_from is None
    [call] = market_data.backfill_closes.call_args_list
    assets, start, end = call.args
    assert [asset.id for asset in assets] == [ASSET.id]
    assert (start, end) == (date(2026, 1, 5) - timedelta(days=10), TODAY)
    session.commit.assert_called_once()


def test_a_current_portfolio_is_not_rebuilt_nor_refetched(
    service: SnapshotService,
    portfolio: Any,
    market_data: MagicMock,
    stored: list[PortfolioDaily],
    session: MagicMock,
) -> None:
    service.twr(portfolio, D("1210"))
    market_data.reset_mock()
    session.reset_mock()
    rows_before = list(stored)

    result = service.twr(portfolio, D("1100"))

    assert result is not None
    assert result.pct == D("10")
    market_data.backfill_closes.assert_not_called()
    session.commit.assert_not_called()
    assert stored == rows_before


def test_a_new_day_adds_only_that_day(
    service: SnapshotService,
    portfolio: Any,
    market_data: MagicMock,
    stored: list[PortfolioDaily],
    today: list[date],
) -> None:
    service.twr(portfolio, D("1100"))
    first_rows = list(stored)
    market_data.reset_mock()
    today[0] = date(2026, 1, 10)

    result = service.twr(portfolio, D("1100"))

    assert result is not None
    assert [row.day for row in stored] == [date(2026, 1, d) for d in (5, 6, 7, 8, 9)]
    assert stored[:4] == first_rows
    [call] = market_data.backfill_closes.call_args_list
    # Only the missing day (with the lookback a forward fill needs).
    assert call.args[1:] == (date(2026, 1, 9) - timedelta(days=10), date(2026, 1, 10))


def test_dirty_from_rebuilds_from_that_day_on_and_clears_the_mark(
    service: SnapshotService,
    portfolio: Any,
    stored: list[PortfolioDaily],
    history: list[SimpleNamespace],
) -> None:
    service.twr(portfolio, D("1100"))
    untouched = list(stored[:2])
    # A deposit of 500 on the 7th is recorded: the 7th on is stale.
    history.append(_deposit(date(2026, 1, 7), "500", operation_id=3))
    portfolio.dirty_from = date(2026, 1, 7)

    result = service.twr(portfolio, D("1600"))

    assert result is not None
    assert portfolio.dirty_from is None
    assert stored[:2] == untouched
    assert [row.day for row in stored] == [date(2026, 1, d) for d in (5, 6, 7, 8)]
    assert stored[2].inflow == D("500")
    assert stored[2].value == D("1600")
    # The 500 deposited on the 7th sits in cash that day, so the +10% on the
    # shares counts on 1000 of the 1500 at work: 1600 / 1500 = +6.67%.
    assert round(result.pct, 4) == D("6.6667")


def test_a_back_dated_change_before_the_first_row_rebuilds_everything(
    service: SnapshotService,
    portfolio: Any,
    stored: list[PortfolioDaily],
    history: list[SimpleNamespace],
) -> None:
    service.twr(portfolio, D("1100"))
    history.insert(0, _deposit(date(2026, 1, 3), "100", operation_id=9))
    portfolio.dirty_from = date(2026, 1, 3)

    service.twr(portfolio, D("1100"))

    assert stored[0].day == date(2026, 1, 3)
    assert stored[0].value == D("100")
    assert portfolio.dirty_from is None


def test_an_asset_in_another_currency_is_converted_at_its_last_trade_rate(
    service: SnapshotService,
    portfolio: Any,
    history: list[SimpleNamespace],
    stored: list[PortfolioDaily],
) -> None:
    # A USD share in a portfolio kept in PLN: bought at 4 PLN per USD.
    foreign = SimpleNamespace(id=6, currency_id=2)
    history[:] = [
        _deposit(date(2026, 1, 5), "4000"),
        _operation(
            "buy",
            date(2026, 1, 5),
            2,
            asset_id=foreign.id,
            asset=foreign,
            quantity=D("10"),
            price=D("100"),
            fx_rate=D("4"),
        ),
    ]

    result = service.twr(portfolio, D("4400"))

    assert result is not None
    # 10 shares at 100 -> 110 USD from the 7th, valued at the 4 PLN of the trade.
    assert [row.value for row in stored] == [D("4000"), D("4000"), D("4400"), D("4400")]
    # Today is built the same way (not from the 4400 handed in), so no jump.
    assert result.pct == D("10")
    assert result.method == "daily_pp_v1+trade_fx"


def test_without_operations_or_a_current_value_there_is_no_return(
    service: SnapshotService,
    portfolio: Any,
    history: list[SimpleNamespace],
) -> None:
    assert service.twr(portfolio, None) is None
    history.clear()
    assert service.twr(portfolio, D("0")) is None


def test_a_gap_in_the_closes_of_a_held_asset_gives_no_return_and_stores_nothing(
    service: SnapshotService,
    portfolio: Any,
    prices: MagicMock,
    stored: list[PortfolioDaily],
    session: MagicMock,
) -> None:
    # The asset has closes, but the series skips a day it was held.
    def series(
        asset_id: int, *, from_date: date, to_date: date, fill: str
    ) -> SimpleNamespace:
        return SimpleNamespace(
            items=[SimpleNamespace(day=date(2026, 1, 5), close=D("100"))]
        )

    prices.series.side_effect = series

    assert service.twr(portfolio, D("1100")) is None

    assert stored == []
    session.rollback.assert_called_once()
    session.commit.assert_not_called()


def test_an_asset_without_any_close_is_valued_at_its_last_trade_price(
    service: SnapshotService,
    portfolio: Any,
    prices: MagicMock,
    history: list[SimpleNamespace],
    stored: list[PortfolioDaily],
) -> None:
    # A ticker the provider does not know, bought and sold again: never priced.
    unknown = SimpleNamespace(id=9, currency_id=1)
    history[:] = [
        _deposit(date(2026, 1, 5), "1000"),
        _buy(date(2026, 1, 5), "10", "100", asset=unknown),
        _operation(
            "sell",
            date(2026, 1, 7),
            3,
            asset_id=unknown.id,
            asset=unknown,
            quantity=D("10"),
            price=D("120"),
        ),
    ]
    prices.series.side_effect = lambda *_, **__: SimpleNamespace(items=[])
    prices.latest_quotes.side_effect = lambda assets: {}

    result = service.twr(portfolio, D("1200"))

    assert result is not None
    # 1000 held at the 100 paid, then 1200 in cash after the sale at 120.
    assert [row.value for row in stored] == [D("1000"), D("1000"), D("1200"), D("1200")]
    assert result.pct == D("20")
    assert result.method == "daily_pp_v1+last_trade"


def test_an_asset_without_any_close_that_is_still_held_is_valued_at_its_last_trade(
    service: SnapshotService,
    portfolio: Any,
    prices: MagicMock,
    history: list[SimpleNamespace],
    stored: list[PortfolioDaily],
) -> None:
    unknown = SimpleNamespace(id=9, currency_id=1)
    history[:] = [
        _deposit(date(2026, 1, 5), "1000"),
        _buy(date(2026, 1, 5), "10", "100", asset=unknown),
    ]
    portfolio.positions = [SimpleNamespace(asset_id=unknown.id)]
    prices.series.side_effect = lambda *_, **__: SimpleNamespace(items=[])
    prices.latest_quotes.side_effect = lambda assets: {}

    # The live valuation (here 0, the stored price of an unknown asset) is not
    # what today is built from.
    result = service.twr(portfolio, D("0"))

    assert result is not None
    assert result.pct == 0
    assert result.method == "daily_pp_v1+last_trade"
    assert len(stored) == 4


def test_both_approximations_name_themselves(
    service: SnapshotService,
    portfolio: Any,
    prices: MagicMock,
    history: list[SimpleNamespace],
) -> None:
    unknown = SimpleNamespace(id=9, currency_id=2)
    history[:] = [
        _deposit(date(2026, 1, 5), "4000"),
        _operation(
            "buy",
            date(2026, 1, 5),
            2,
            asset_id=unknown.id,
            asset=unknown,
            quantity=D("10"),
            price=D("100"),
            fx_rate=D("4"),
        ),
    ]
    prices.series.side_effect = lambda *_, **__: SimpleNamespace(items=[])
    prices.latest_quotes.side_effect = lambda assets: {}

    result = service.twr(portfolio, D("4000"))

    assert result is not None
    assert result.method == "daily_pp_v1+last_trade+trade_fx"


def test_a_provider_failure_gives_no_return_and_stores_nothing(
    service: SnapshotService,
    portfolio: Any,
    market_data: MagicMock,
    stored: list[PortfolioDaily],
) -> None:
    market_data.backfill_closes.side_effect = MarketDataUnavailableError("down")

    assert service.twr(portfolio, D("1100")) is None

    assert stored == []


def test_a_portfolio_marked_dirty_meanwhile_is_left_for_the_next_read(
    service: SnapshotService,
    portfolio: Any,
    portfolio_repo: MagicMock,
    stored: list[PortfolioDaily],
) -> None:
    # Under the row lock the portfolio turns out to have been written in between.
    portfolio_repo.get_owned.return_value = _portfolio(dirty_from=date(2026, 1, 6))

    assert service.twr(portfolio, D("1100")) is None

    assert stored == []


def test_a_portfolio_whose_first_day_is_today_has_nothing_stored_yet(
    service: SnapshotService,
    portfolio: Any,
    history: list[SimpleNamespace],
    market_data: MagicMock,
    stored: list[PortfolioDaily],
) -> None:
    history[:] = [_deposit(TODAY, "500")]

    result = service.twr(portfolio, D("500"))

    assert result is not None
    assert result.pct == 0
    assert stored == []
    market_data.backfill_closes.assert_not_called()


def test_a_flow_of_today_is_not_a_gain(
    service: SnapshotService,
    portfolio: Any,
    history: list[SimpleNamespace],
) -> None:
    service.twr(portfolio, D("1100"))
    history.append(_deposit(TODAY, "100", operation_id=3))

    # 1100 yesterday, +100 deposited today, 1200 now: no gain today.
    result = service.twr(portfolio, D("1200"))

    assert result is not None
    assert result.pct == D("10")


def test_a_mark_on_a_portfolio_whose_first_day_is_now_today_drops_the_stale_rows(
    service: SnapshotService,
    portfolio: Any,
    history: list[SimpleNamespace],
    stored: list[PortfolioDaily],
) -> None:
    service.twr(portfolio, D("1100"))
    # The old operations are deleted and a new deposit lands today.
    history[:] = [_deposit(TODAY, "500")]
    portfolio.dirty_from = date(2026, 1, 5)

    result = service.twr(portfolio, D("500"))

    assert result is not None
    assert result.pct == 0
    assert stored == []
    assert portfolio.dirty_from is None


def test_a_deposit_dated_in_the_future_is_not_a_gain(
    service: SnapshotService, portfolio: Any, history: list[SimpleNamespace]
) -> None:
    service.twr(portfolio, D("1100"))
    # Booked ahead: the ledger and the valuation already hold it.
    history.append(_deposit(TODAY + timedelta(days=1), "500", operation_id=3))

    result = service.twr(portfolio, D("1600"))

    assert result is not None
    assert result.pct == D("10")


def test_a_mark_cleared_by_a_concurrent_rebuild_is_current_not_unknown(
    service: SnapshotService, portfolio: Any, portfolio_repo: MagicMock
) -> None:
    service.twr(portfolio, D("1100"))
    portfolio.dirty_from = date(2026, 1, 6)
    # Under the lock the other request has already rebuilt and cleared it.
    portfolio_repo.get_owned.return_value = _portfolio(dirty_from=None)

    result = service.twr(portfolio, D("1100"))

    assert result is not None
    assert result.pct == D("10")
