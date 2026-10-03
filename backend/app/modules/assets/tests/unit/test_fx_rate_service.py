from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.assets.exceptions import (
    CurrencyNotFoundError,
    FutureDateError,
    InvalidDateRangeError,
    RateMissingError,
    UnknownCurrencyError,
)
from app.modules.assets.services.fx_rates import FxRateService

TODAY = date(2026, 10, 2)

USD = SimpleNamespace(id=1, code="USD", exchange_rate=Decimal("1"))
PLN = SimpleNamespace(id=2, code="PLN", exchange_rate=Decimal("1"))
EUR = SimpleNamespace(id=3, code="EUR", exchange_rate=Decimal("1"))
BY_CODE = {c.code: c for c in (USD, PLN, EUR)}
BY_ID = {c.id: c for c in (USD, PLN, EUR)}


def _rate(
    from_id: int, to_id: int, day: date, rate: str, source: str = "yahoo", **extra
):
    values: dict[str, object] = {
        "from_currency_id": from_id,
        "to_currency_id": to_id,
        "rate_date": day,
        "rate": Decimal(rate),
        "source": source,
        "is_synthetic": False,
    }
    values.update(extra)
    return SimpleNamespace(**values)


@pytest.fixture(autouse=True)
def _reset_currencies() -> None:
    for currency in (USD, PLN, EUR):
        currency.exchange_rate = Decimal("1")


@pytest.fixture
def currency_repo(currency_repo: MagicMock) -> MagicMock:
    currency_repo.find_by_code.side_effect = BY_CODE.get
    currency_repo.find_by_id.side_effect = BY_ID.get
    return currency_repo


@pytest.fixture
def service(fx_repo: MagicMock, currency_repo: MagicMock) -> FxRateService:
    fx_repo.latest_day_rows.return_value = []
    return FxRateService(fx_repo, currency_repo, today=lambda: TODAY)


def _rows(fx_repo: MagicMock, mapping: dict[tuple[int, int], list[SimpleNamespace]]):
    fx_repo.latest_day_rows.side_effect = lambda from_id, to_id, as_of=None: (
        mapping.get((from_id, to_id), [])
    )


# --- get_rate ---


def test_get_rate_returns_a_direct_rate_with_its_evidence(
    service: FxRateService, fx_repo: MagicMock
) -> None:
    _rows(
        fx_repo,
        {(PLN.id, USD.id): [_rate(PLN.id, USD.id, date(2026, 10, 1), "0.26", "nbp")]},
    )

    quote = service.get_rate("pln", "usd", date(2026, 10, 2))

    assert (quote.from_currency, quote.to_currency) == ("PLN", "USD")
    assert (quote.rate, quote.via, quote.source) == (Decimal("0.26"), "direct", "nbp")
    assert quote.rate_date == date(2026, 10, 1)
    assert quote.stale is False


def test_get_rate_inverts_a_stored_opposite_pair(
    service: FxRateService, fx_repo: MagicMock
) -> None:
    _rows(fx_repo, {(USD.id, PLN.id): [_rate(USD.id, PLN.id, TODAY, "4")]})

    quote = service.get_rate("PLN", "USD")

    assert (quote.rate, quote.via) == (Decimal("0.250000000"), "inverse")


def test_the_newer_observation_wins_between_direct_and_inverse(
    service: FxRateService, fx_repo: MagicMock
) -> None:
    _rows(
        fx_repo,
        {
            (PLN.id, USD.id): [_rate(PLN.id, USD.id, date(2026, 9, 1), "0.2")],
            (USD.id, PLN.id): [_rate(USD.id, PLN.id, date(2026, 9, 20), "4")],
        },
    )

    quote = service.get_rate("PLN", "USD")

    assert quote.via == "inverse"
    assert quote.stale is True  # 12 days old on TODAY


def test_a_direct_rate_wins_a_same_day_tie(
    service: FxRateService, fx_repo: MagicMock
) -> None:
    _rows(
        fx_repo,
        {
            (PLN.id, USD.id): [_rate(PLN.id, USD.id, TODAY, "0.26")],
            (USD.id, PLN.id): [_rate(USD.id, PLN.id, TODAY, "4")],
        },
    )

    assert service.get_rate("PLN", "USD").via == "direct"


def test_manual_beats_a_provider_on_the_same_day(
    service: FxRateService, fx_repo: MagicMock
) -> None:
    _rows(
        fx_repo,
        {
            (PLN.id, USD.id): [
                _rate(PLN.id, USD.id, TODAY, "0.26", "yahoo"),
                _rate(PLN.id, USD.id, TODAY, "0.30", "manual"),
            ]
        },
    )

    quote = service.get_rate("PLN", "USD")

    assert (quote.source, quote.rate) == ("manual", Decimal("0.30"))


def test_the_same_currency_is_identity(service: FxRateService) -> None:
    quote = service.get_rate("pln", "PLN", date(2026, 1, 1))

    assert (quote.rate, quote.via, quote.rate_date) == (
        Decimal(1),
        "identity",
        date(2026, 1, 1),
    )


def test_a_missing_rate_is_404_rate_missing(service: FxRateService) -> None:
    with pytest.raises(RateMissingError) as exc_info:
        service.get_rate("PLN", "EUR")

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "RATE_MISSING"


def test_an_unknown_currency_is_404(service: FxRateService) -> None:
    with pytest.raises(CurrencyNotFoundError):
        service.get_rate("PLN", "ZZZ")


def test_get_rate_looks_up_as_of_the_given_day(
    service: FxRateService, fx_repo: MagicMock
) -> None:
    with pytest.raises(RateMissingError):
        service.get_rate("PLN", "USD", date(2026, 9, 1))

    fx_repo.latest_day_rows.assert_any_call(PLN.id, USD.id, date(2026, 9, 1))
    fx_repo.latest_day_rows.assert_any_call(USD.id, PLN.id, date(2026, 9, 1))


# --- history ---


def test_history_lists_the_directed_pair(
    service: FxRateService, fx_repo: MagicMock
) -> None:
    rows = [_rate(PLN.id, USD.id, TODAY, "0.26")]
    fx_repo.list_pair.return_value = rows

    result = service.history(
        "pln", "usd", from_date=date(2026, 9, 1), to_date=TODAY, source="nbp"
    )

    assert result is rows
    fx_repo.list_pair.assert_called_once_with(
        PLN.id, USD.id, from_date=date(2026, 9, 1), to_date=TODAY, source="nbp"
    )


def test_history_rejects_an_inverted_range(service: FxRateService) -> None:
    with pytest.raises(InvalidDateRangeError):
        service.history("PLN", "USD", from_date=TODAY, to_date=date(2026, 9, 1))


# --- manual rates ---


def test_set_manual_rate_writes_a_manual_row_and_syncs_both_caches(
    service: FxRateService, fx_repo: MagicMock, session: MagicMock
) -> None:
    _rows(fx_repo, {(PLN.id, USD.id): [_rate(PLN.id, USD.id, TODAY, "0.26", "manual")]})

    service.set_manual_rate(PLN.id, USD.id, TODAY, Decimal("0.26"))

    fx_repo.upsert.assert_called_once_with(
        from_id=PLN.id,
        to_id=USD.id,
        rate_date=TODAY,
        rate=Decimal("0.26"),
        source="manual",
    )
    assert PLN.exchange_rate == Decimal("0.26")
    assert USD.exchange_rate == Decimal("1")
    session.commit.assert_called_once()


def test_set_manual_rate_of_the_inverse_pair_sets_the_inverted_cache(
    service: FxRateService, fx_repo: MagicMock
) -> None:
    _rows(fx_repo, {(USD.id, PLN.id): [_rate(USD.id, PLN.id, TODAY, "4", "manual")]})

    service.set_manual_rate(USD.id, PLN.id, TODAY, Decimal("4"))

    assert PLN.exchange_rate == Decimal("0.250000000")


@pytest.mark.parametrize(
    ("from_id", "to_id", "day", "error"),
    [
        (99, USD.id, TODAY, UnknownCurrencyError),
        (PLN.id, 99, TODAY, UnknownCurrencyError),
        (PLN.id, USD.id, date(2026, 10, 3), FutureDateError),
    ],
)
def test_set_manual_rate_rejections_roll_back(
    service: FxRateService,
    fx_repo: MagicMock,
    session: MagicMock,
    from_id: int,
    to_id: int,
    day: date,
    error: type[Exception],
) -> None:
    with pytest.raises(error):
        service.set_manual_rate(from_id, to_id, day, Decimal("1"))

    fx_repo.upsert.assert_not_called()
    session.rollback.assert_called_once()


# --- cores ---


def test_record_rate_upserts_and_refreshes_the_cache_of_the_non_base_currency(
    service: FxRateService, fx_repo: MagicMock
) -> None:
    _rows(fx_repo, {(EUR.id, USD.id): [_rate(EUR.id, USD.id, TODAY, "1.08")]})

    service.record_rate(
        EUR, USD, Decimal("1.08"), rate_date=TODAY, source="yahoo", is_synthetic=True
    )

    fx_repo.upsert.assert_called_once_with(
        from_id=EUR.id,
        to_id=USD.id,
        rate_date=TODAY,
        rate=Decimal("1.08"),
        source="yahoo",
        is_synthetic=True,
    )
    assert EUR.exchange_rate == Decimal("1.08")
    assert USD.exchange_rate == Decimal("1")


@pytest.mark.parametrize("rate", ["0", "-1"])
def test_record_rate_drops_a_non_positive_rate(
    service: FxRateService, fx_repo: MagicMock, rate: str
) -> None:
    service.record_rate(EUR, USD, Decimal(rate), rate_date=TODAY, source="yahoo")

    fx_repo.upsert.assert_not_called()


def test_record_rate_drops_a_currency_against_itself(
    service: FxRateService, fx_repo: MagicMock
) -> None:
    service.record_rate(EUR, EUR, Decimal("1"), rate_date=TODAY, source="yahoo")

    fx_repo.upsert.assert_not_called()


def test_the_cache_is_kept_when_the_history_has_no_rate(
    service: FxRateService,
) -> None:
    EUR.exchange_rate = Decimal("1.5")

    service.sync_cached_rate(EUR)

    assert EUR.exchange_rate == Decimal("1.5")


def test_the_cache_is_not_derived_without_the_system_currency(
    service: FxRateService, currency_repo: MagicMock, fx_repo: MagicMock
) -> None:
    currency_repo.find_by_code.side_effect = lambda code: None
    EUR.exchange_rate = Decimal("1.5")

    service.sync_cached_rate(EUR)

    fx_repo.latest_day_rows.assert_not_called()
    assert EUR.exchange_rate == Decimal("1.5")


def test_the_cache_of_the_system_currency_is_never_derived(
    service: FxRateService, fx_repo: MagicMock
) -> None:
    service.sync_cached_rate(USD)

    fx_repo.latest_day_rows.assert_not_called()


def test_an_absurd_inverted_rate_does_not_overflow_the_cache(
    service: FxRateService, fx_repo: MagicMock
) -> None:
    # 1 / 0.000000001 = 1e9: does not fit Numeric(18, 9).
    _rows(
        fx_repo,
        {(USD.id, EUR.id): [_rate(USD.id, EUR.id, TODAY, "0.000000001")]},
    )
    EUR.exchange_rate = Decimal("1.5")

    service.sync_cached_rate(EUR)

    assert EUR.exchange_rate == Decimal("1.5")


def test_record_manual_rate_to_base_writes_a_manual_row_dated_today(
    service: FxRateService, fx_repo: MagicMock
) -> None:
    _rows(fx_repo, {(EUR.id, USD.id): [_rate(EUR.id, USD.id, TODAY, "1.1", "manual")]})

    service.record_manual_rate_to_base(EUR, Decimal("1.1"))

    kwargs = fx_repo.upsert.call_args.kwargs
    assert (kwargs["rate_date"], kwargs["source"]) == (TODAY, "manual")
    assert EUR.exchange_rate == Decimal("1.1")


def test_record_manual_rate_to_base_ignores_the_system_currency(
    service: FxRateService, fx_repo: MagicMock
) -> None:
    service.record_manual_rate_to_base(USD, Decimal("2"))

    fx_repo.upsert.assert_not_called()


def test_record_manual_rate_to_base_without_a_system_currency_is_a_noop(
    service: FxRateService, currency_repo: MagicMock, fx_repo: MagicMock
) -> None:
    currency_repo.find_by_code.side_effect = lambda code: None

    service.record_manual_rate_to_base(EUR, Decimal("1.1"))

    fx_repo.upsert.assert_not_called()
