from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.assets.exceptions import (
    AssetArchivedError,
    AssetNotFoundError,
    FutureDateError,
    InvalidDateRangeError,
    PriceCurrencyMismatchError,
    PriceNotFoundError,
)
from app.modules.assets.services.prices import PriceService

TODAY = date(2026, 10, 2)


def _asset(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "id": 1,
        "currency_id": 5,
        "current_price": Decimal("0"),
        "archived_at": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _row(day: date, source: str = "yahoo", close: str = "10", **extra: object):
    values: dict[str, object] = {
        "asset_id": 1,
        "price_date": day,
        "close": Decimal(close),
        "currency_id": 5,
        "source": source,
        "is_synthetic": False,
    }
    values.update(extra)
    return SimpleNamespace(**values)


@pytest.fixture
def service(price_repo: MagicMock, asset_repo: MagicMock) -> PriceService:
    return PriceService(price_repo, asset_repo, today=lambda: TODAY)


# --- find_close ---


def test_find_close_prices_the_latest_day_not_after_as_of(
    service: PriceService, price_repo: MagicMock, asset_repo: MagicMock
) -> None:
    asset_repo.get_by_id.return_value = _asset()
    price_repo.latest_day_rows.return_value = [_row(date(2026, 10, 1), close="12.5")]

    quote = service.find_close(1, date(2026, 10, 2))

    assert quote is not None
    assert (quote.close, quote.price_date, quote.source) == (
        Decimal("12.5"),
        date(2026, 10, 1),
        "yahoo",
    )
    assert quote.stale is False
    price_repo.latest_day_rows.assert_called_once_with(1, date(2026, 10, 2))


def test_find_close_defaults_to_today_and_flags_an_old_close_as_stale(
    service: PriceService, price_repo: MagicMock, asset_repo: MagicMock
) -> None:
    asset_repo.get_by_id.return_value = _asset()
    price_repo.latest_day_rows.return_value = [_row(date(2026, 9, 1))]

    quote = service.find_close(1)

    assert quote is not None
    assert quote.stale is True
    price_repo.latest_day_rows.assert_called_once_with(1, TODAY)


def test_find_close_of_an_asset_without_prices_is_none(
    service: PriceService, price_repo: MagicMock, asset_repo: MagicMock
) -> None:
    asset_repo.get_by_id.return_value = _asset()
    price_repo.latest_day_rows.return_value = []

    assert service.find_close(1) is None


def test_find_close_manual_wins_over_a_provider_on_the_same_day(
    service: PriceService, price_repo: MagicMock, asset_repo: MagicMock
) -> None:
    day = date(2026, 10, 1)
    asset_repo.get_by_id.return_value = _asset()
    price_repo.latest_day_rows.return_value = [
        _row(day, "yahoo", "10"),
        _row(day, "manual", "11"),
    ]

    quote = service.find_close(1)

    assert quote is not None
    assert (quote.source, quote.close) == ("manual", Decimal("11"))


def test_find_close_propagates_an_unknown_asset(
    service: PriceService, asset_repo: MagicMock
) -> None:
    asset_repo.get_by_id.side_effect = AssetNotFoundError

    with pytest.raises(AssetNotFoundError):
        service.find_close(1)


# --- latest_quotes ---


def test_latest_quotes_groups_rows_per_asset_and_omits_priceless_assets(
    service: PriceService, price_repo: MagicMock
) -> None:
    priced, priceless = _asset(id=1), _asset(id=2)
    price_repo.latest_day_rows_for.return_value = [
        _row(date(2026, 10, 2), "yahoo", "10", asset_id=1),
        _row(date(2026, 10, 2), "manual", "9", asset_id=1),
    ]

    quotes = service.latest_quotes([priced, priceless])

    assert set(quotes) == {1}
    assert quotes[1].source == "manual"
    price_repo.latest_day_rows_for.assert_called_once_with([1, 2])


# --- series ---


def test_series_returns_the_winning_source_of_every_day(
    service: PriceService, price_repo: MagicMock, asset_repo: MagicMock
) -> None:
    d1, d2 = date(2026, 9, 1), date(2026, 9, 2)
    asset_repo.get_by_id.return_value = _asset()
    price_repo.list_for_asset.return_value = [
        _row(d1, "yahoo", "10"),
        _row(d1, "manual", "11"),
        _row(d2, "yahoo", "12"),
    ]

    series = service.series(1, from_date=d1, to_date=d2)

    assert [(i.day, i.close, i.source) for i in series.items] == [
        (d1, Decimal("11"), "manual"),
        (d2, Decimal("12"), "yahoo"),
    ]
    assert series.currency_id == 5
    price_repo.list_for_asset.assert_called_once_with(
        1, up_to=d2, from_date=d1, source=None
    )


def test_series_can_be_limited_to_one_source(
    service: PriceService, price_repo: MagicMock, asset_repo: MagicMock
) -> None:
    asset_repo.get_by_id.return_value = _asset()
    price_repo.list_for_asset.return_value = []

    service.series(1, source="manual")

    price_repo.list_for_asset.assert_called_once_with(
        1, up_to=None, from_date=None, source="manual"
    )


def test_forward_fill_carries_the_last_close_over_missing_days(
    service: PriceService, price_repo: MagicMock, asset_repo: MagicMock
) -> None:
    asset_repo.get_by_id.return_value = _asset()
    # Observed before the range and again on the 3rd; nothing on the 2nd and 4th.
    price_repo.list_for_asset.return_value = [
        _row(date(2026, 8, 20), close="9"),
        _row(date(2026, 9, 3), close="10"),
    ]

    series = service.series(
        1, from_date=date(2026, 9, 1), to_date=date(2026, 9, 4), fill="forward"
    )

    assert [(i.day, i.price_date, i.close) for i in series.items] == [
        (date(2026, 9, 1), date(2026, 8, 20), Decimal("9")),
        (date(2026, 9, 2), date(2026, 8, 20), Decimal("9")),
        (date(2026, 9, 3), date(2026, 9, 3), Decimal("10")),
        (date(2026, 9, 4), date(2026, 9, 3), Decimal("10")),
    ]
    # 12 days carried on the 1st: past the 7-day freshness limit.
    assert series.items[0].stale is True
    assert series.items[2].stale is False


def test_forward_fill_skips_days_before_the_first_observation(
    service: PriceService, price_repo: MagicMock, asset_repo: MagicMock
) -> None:
    asset_repo.get_by_id.return_value = _asset()
    price_repo.list_for_asset.return_value = [_row(date(2026, 9, 3), close="10")]

    series = service.series(
        1, from_date=date(2026, 9, 1), to_date=date(2026, 9, 4), fill="forward"
    )

    assert [i.day for i in series.items] == [date(2026, 9, 3), date(2026, 9, 4)]


def test_forward_fill_ends_today_when_no_end_is_given(
    service: PriceService, price_repo: MagicMock, asset_repo: MagicMock
) -> None:
    asset_repo.get_by_id.return_value = _asset()
    price_repo.list_for_asset.return_value = [_row(date(2026, 10, 1))]

    series = service.series(1, from_date=date(2026, 10, 1), fill="forward")

    assert series.items[-1].day == TODAY


@pytest.mark.parametrize(
    "kwargs",
    [
        {"from_date": date(2026, 9, 5), "to_date": date(2026, 9, 1)},
        {"fill": "forward"},  # needs a start
        {"fill": "forward", "from_date": date(2000, 1, 1)},  # too long
    ],
)
def test_series_rejects_bad_ranges(
    service: PriceService, asset_repo: MagicMock, kwargs: dict[str, object]
) -> None:
    asset_repo.get_by_id.return_value = _asset()

    with pytest.raises(InvalidDateRangeError) as exc_info:
        service.series(1, **kwargs)  # type: ignore[arg-type]

    assert exc_info.value.code == "INVALID_DATE_RANGE"


# --- manual prices ---


def test_set_manual_price_upserts_a_manual_row_and_syncs_the_cache(
    service: PriceService,
    price_repo: MagicMock,
    asset_repo: MagicMock,
    session: MagicMock,
) -> None:
    asset = _asset()
    asset_repo.get_by_id.return_value = asset
    price_repo.latest_day_rows.return_value = [
        _row(date(2026, 10, 1), "manual", "42.5")
    ]

    service.set_manual_price(1, date(2026, 10, 1), Decimal("42.5"))

    price_repo.upsert.assert_called_once_with(
        asset_id=1,
        price_date=date(2026, 10, 1),
        close=Decimal("42.5"),
        currency_id=5,
        source="manual",
        is_synthetic=False,
    )
    assert asset.current_price == Decimal("42.5")
    session.commit.assert_called_once()


def test_a_backdated_manual_price_does_not_move_the_cache_off_a_newer_close(
    service: PriceService, price_repo: MagicMock, asset_repo: MagicMock
) -> None:
    asset = _asset(current_price=Decimal("50"))
    asset_repo.get_by_id.return_value = asset
    price_repo.latest_day_rows.return_value = [_row(TODAY, "yahoo", "50")]

    service.set_manual_price(1, date(2026, 9, 1), Decimal("40"))

    assert asset.current_price == Decimal("50")


@pytest.mark.parametrize(
    ("asset", "price_date", "currency_id", "error"),
    [
        (
            _asset(archived_at=datetime(2026, 1, 1, tzinfo=UTC)),
            TODAY,
            None,
            AssetArchivedError,
        ),
        (_asset(), date(2026, 10, 3), None, FutureDateError),
        (_asset(), TODAY, 99, PriceCurrencyMismatchError),
    ],
)
def test_set_manual_price_rejections_roll_back(
    service: PriceService,
    price_repo: MagicMock,
    asset_repo: MagicMock,
    session: MagicMock,
    asset: SimpleNamespace,
    price_date: date,
    currency_id: int | None,
    error: type[Exception],
) -> None:
    asset_repo.get_by_id.return_value = asset

    with pytest.raises(error):
        service.set_manual_price(1, price_date, Decimal("1"), currency_id)

    price_repo.upsert.assert_not_called()
    session.rollback.assert_called_once()
    session.commit.assert_not_called()


def test_set_manual_price_accepts_the_assets_own_currency(
    service: PriceService, price_repo: MagicMock, asset_repo: MagicMock
) -> None:
    asset_repo.get_by_id.return_value = _asset()
    price_repo.latest_day_rows.return_value = []

    service.set_manual_price(1, TODAY, Decimal("1"), currency_id=5)

    price_repo.upsert.assert_called_once()


def test_delete_manual_price_removes_the_manual_row_and_resyncs(
    service: PriceService,
    price_repo: MagicMock,
    asset_repo: MagicMock,
    session: MagicMock,
) -> None:
    asset = _asset(current_price=Decimal("42.5"))
    asset_repo.get_by_id.return_value = asset
    manual = _row(TODAY, "manual", "42.5")
    price_repo.find.return_value = manual
    price_repo.latest_day_rows.return_value = [_row(date(2026, 10, 1), "yahoo", "40")]

    service.delete_manual_price(1, TODAY)

    price_repo.find.assert_called_once_with(1, TODAY, "manual")
    price_repo.delete.assert_called_once_with(manual)
    assert asset.current_price == Decimal("40")
    session.commit.assert_called_once()


def test_deleting_the_last_price_keeps_the_cached_one(
    service: PriceService, price_repo: MagicMock, asset_repo: MagicMock
) -> None:
    asset = _asset(current_price=Decimal("42.5"))
    asset_repo.get_by_id.return_value = asset
    price_repo.find.return_value = _row(TODAY, "manual")
    price_repo.latest_day_rows.return_value = []

    service.delete_manual_price(1, TODAY)

    assert asset.current_price == Decimal("42.5")


def test_delete_manual_price_without_one_is_404(
    service: PriceService,
    price_repo: MagicMock,
    asset_repo: MagicMock,
    session: MagicMock,
) -> None:
    asset_repo.get_by_id.return_value = _asset()
    price_repo.find.return_value = None

    with pytest.raises(PriceNotFoundError) as exc_info:
        service.delete_manual_price(1, TODAY)

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "PRICE_NOT_FOUND"
    price_repo.delete.assert_not_called()
    session.rollback.assert_called_once()


def test_delete_manual_price_of_an_archived_asset_is_refused(
    service: PriceService, asset_repo: MagicMock
) -> None:
    asset_repo.get_by_id.return_value = _asset(
        archived_at=datetime(2026, 1, 1, tzinfo=UTC)
    )

    with pytest.raises(AssetArchivedError):
        service.delete_manual_price(1, TODAY)


# --- cores ---


def test_record_closes_stores_positive_closes_and_syncs_once(
    service: PriceService, price_repo: MagicMock
) -> None:
    asset = _asset()
    price_repo.latest_day_rows.return_value = [_row(date(2026, 10, 2), close="12")]

    stored = service.record_closes(
        asset,
        {
            date(2026, 10, 1): Decimal("11"),
            date(2026, 10, 2): Decimal("12"),
            date(2026, 9, 30): Decimal("0"),
            date(2026, 9, 29): Decimal("-1"),
        },
        source="yahoo",
        is_synthetic=False,
    )

    assert stored == 2
    assert price_repo.upsert.call_count == 2
    assert asset.current_price == Decimal("12")
    price_repo.latest_day_rows.assert_called_once()


def test_record_closes_of_nothing_leaves_the_cache_alone(
    service: PriceService, price_repo: MagicMock
) -> None:
    asset = _asset(current_price=Decimal("7"))

    assert service.record_closes(asset, {}, source="yahoo", is_synthetic=False) == 0

    price_repo.latest_day_rows.assert_not_called()
    assert asset.current_price == Decimal("7")


def test_record_manual_price_today_ignores_zero(
    service: PriceService, price_repo: MagicMock
) -> None:
    service.record_manual_price_today(_asset(), Decimal("0"))

    price_repo.upsert.assert_not_called()


def test_record_manual_price_today_writes_a_manual_row_dated_today(
    service: PriceService, price_repo: MagicMock
) -> None:
    asset = _asset()
    price_repo.latest_day_rows.return_value = [_row(TODAY, "manual", "3")]

    service.record_manual_price_today(asset, Decimal("3"))

    assert price_repo.upsert.call_args.kwargs["price_date"] == TODAY
    assert price_repo.upsert.call_args.kwargs["source"] == "manual"
    assert asset.current_price == Decimal("3")
