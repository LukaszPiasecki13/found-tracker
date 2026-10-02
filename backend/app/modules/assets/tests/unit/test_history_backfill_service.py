from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.assets.services.history import HistoryBackfillService

TODAY = date(2026, 10, 2)


def _asset(id: int, price: str, updated: datetime | None) -> SimpleNamespace:
    return SimpleNamespace(
        id=id, current_price=Decimal(price), currency_id=9, updated_at=updated
    )


def _currency(id: int, code: str, rate: str) -> SimpleNamespace:
    return SimpleNamespace(id=id, code=code, exchange_rate=Decimal(rate))


@pytest.fixture
def service(
    asset_repo: MagicMock,
    currency_repo: MagicMock,
    price_repo: MagicMock,
    fx_repo: MagicMock,
) -> HistoryBackfillService:
    price_repo.asset_ids_with_prices.return_value = set()
    fx_repo.currency_ids_with_rates.return_value = set()
    asset_repo.list_all.return_value = []
    currency_repo.list_all.return_value = []
    currency_repo.find_by_code.return_value = _currency(1, "USD", "1")
    return HistoryBackfillService(
        asset_repo, currency_repo, price_repo, fx_repo, today=lambda: TODAY
    )


def test_priceless_history_gets_one_legacy_row_per_priced_asset(
    service: HistoryBackfillService,
    asset_repo: MagicMock,
    price_repo: MagicMock,
    session: MagicMock,
) -> None:
    asset_repo.list_all.return_value = [
        _asset(1, "10", datetime(2026, 5, 3, 12, tzinfo=UTC)),
        _asset(2, "0", None),  # no price to preserve
        _asset(3, "7", None),  # no timestamp: dated today
        _asset(4, "5", datetime(2026, 5, 4, tzinfo=UTC)),  # already has history
    ]
    price_repo.asset_ids_with_prices.return_value = {4}

    result = service.backfill()

    assert result.prices == 2
    assert [
        (c.kwargs["asset_id"], c.kwargs["price_date"], c.kwargs["close"])
        for c in price_repo.upsert.call_args_list
    ] == [
        (1, date(2026, 5, 3), Decimal("10")),
        (3, TODAY, Decimal("7")),
    ]
    for call in price_repo.upsert.call_args_list:
        assert (call.kwargs["source"], call.kwargs["is_synthetic"]) == ("legacy", True)
        assert call.kwargs["currency_id"] == 9
    asset_repo.list_all.assert_called_once_with(include_archived=True)
    session.commit.assert_called_once()


def test_cached_rates_other_than_the_placeholder_become_legacy_rows(
    service: HistoryBackfillService,
    currency_repo: MagicMock,
    fx_repo: MagicMock,
) -> None:
    currency_repo.list_all.return_value = [
        _currency(1, "USD", "1"),  # the system currency itself
        _currency(2, "EUR", "1.08"),
        _currency(3, "XXX", "1"),  # the column default: not a quote
        _currency(4, "PLN", "0.25"),  # already has history
        _currency(5, "BAD", "0"),
    ]
    fx_repo.currency_ids_with_rates.return_value = {4}

    result = service.backfill()

    assert result.rates == 1
    fx_repo.upsert.assert_called_once_with(
        from_id=2,
        to_id=1,
        rate_date=TODAY,
        rate=Decimal("1.08"),
        source="legacy",
        is_synthetic=True,
    )


def test_without_the_system_currency_no_rates_are_seeded(
    service: HistoryBackfillService, currency_repo: MagicMock, fx_repo: MagicMock
) -> None:
    currency_repo.find_by_code.return_value = None
    currency_repo.list_all.return_value = [_currency(2, "EUR", "1.08")]

    assert service.backfill().rates == 0

    fx_repo.upsert.assert_not_called()


def test_a_failure_rolls_everything_back(
    service: HistoryBackfillService,
    asset_repo: MagicMock,
    price_repo: MagicMock,
    session: MagicMock,
) -> None:
    asset_repo.list_all.return_value = [_asset(1, "10", None)]
    price_repo.upsert.side_effect = RuntimeError("boom")

    with pytest.raises(RuntimeError):
        service.backfill()

    session.rollback.assert_called_once()
    session.commit.assert_not_called()
