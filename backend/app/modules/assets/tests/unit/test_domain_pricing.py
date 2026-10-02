from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.modules.assets.domain import (
    best_per_day,
    invert_rate,
    is_stale,
    pick_effective,
    source_rank,
)

PROVIDERS = frozenset({"yahoo"})


def _obs(day: date, source: str, value: str = "1") -> SimpleNamespace:
    return SimpleNamespace(day=day, source=source, value=Decimal(value))


def _day(item: SimpleNamespace) -> date:
    return item.day


def _source(item: SimpleNamespace) -> str:
    return item.source


def test_source_precedence_is_manual_then_providers_then_the_unknown() -> None:
    assert source_rank("manual", PROVIDERS) == 0
    assert source_rank("yahoo", PROVIDERS) == 1
    assert source_rank("whatever", PROVIDERS) == 1000


def test_pick_effective_takes_the_latest_day_not_after_as_of() -> None:
    old = _obs(date(2026, 9, 1), "yahoo")
    recent = _obs(date(2026, 9, 10), "yahoo")
    future = _obs(date(2026, 9, 20), "yahoo")

    chosen = pick_effective(
        [old, recent, future],
        day_of=_day,
        source_of=_source,
        known_providers=PROVIDERS,
        as_of=date(2026, 9, 15),
    )

    assert chosen is recent


def test_pick_effective_prefers_manual_over_a_provider_on_the_same_day() -> None:
    day = date(2026, 9, 10)
    provider = _obs(day, "yahoo")
    manual = _obs(day, "manual")
    other = _obs(day, "zzz")

    chosen = pick_effective(
        [other, provider, manual],
        day_of=_day,
        source_of=_source,
        known_providers=PROVIDERS,
        as_of=day,
    )

    assert chosen is manual


def test_a_newer_provider_day_beats_an_older_manual_one() -> None:
    manual = _obs(date(2026, 9, 1), "manual")
    provider = _obs(date(2026, 9, 2), "yahoo")

    chosen = pick_effective(
        [manual, provider],
        day_of=_day,
        source_of=_source,
        known_providers=PROVIDERS,
        as_of=date(2026, 9, 5),
    )

    assert chosen is provider


def test_unknown_sources_tie_break_by_name_for_a_stable_choice() -> None:
    day = date(2026, 9, 10)
    b = _obs(day, "b-source")
    a = _obs(day, "a-source")

    chosen = pick_effective(
        [b, a], day_of=_day, source_of=_source, known_providers=PROVIDERS, as_of=day
    )

    assert chosen is a


def test_pick_effective_is_none_when_nothing_is_old_enough() -> None:
    assert (
        pick_effective(
            [_obs(date(2026, 9, 10), "yahoo")],
            day_of=_day,
            source_of=_source,
            known_providers=PROVIDERS,
            as_of=date(2026, 9, 9),
        )
        is None
    )
    assert (
        pick_effective(
            [],
            day_of=_day,
            source_of=_source,
            known_providers=PROVIDERS,
            as_of=date.max,
        )
        is None
    )


def test_best_per_day_keeps_one_winner_for_every_day() -> None:
    d1, d2 = date(2026, 9, 1), date(2026, 9, 2)
    manual_d1 = _obs(d1, "manual")
    yahoo_d1 = _obs(d1, "yahoo")
    yahoo_d2 = _obs(d2, "yahoo")

    winners = best_per_day(
        [yahoo_d1, yahoo_d2, manual_d1],
        day_of=_day,
        source_of=_source,
        known_providers=PROVIDERS,
    )

    assert winners == {d1: manual_d1, d2: yahoo_d2}


@pytest.mark.parametrize(
    ("observed", "stale"),
    [
        (None, True),
        (date(2026, 10, 2), False),
        (date(2026, 9, 25), False),  # exactly 7 days: still fresh
        (date(2026, 9, 24), True),
    ],
)
def test_is_stale_after_the_threshold(observed: date | None, stale: bool) -> None:
    assert is_stale(observed, today=date(2026, 10, 2), max_age_days=7) is stale


def test_invert_rate_rounds_to_the_stored_nine_places() -> None:
    assert invert_rate(Decimal("4")) == Decimal("0.250000000")
    assert invert_rate(Decimal("3")) == Decimal("0.333333333")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1", "1.000000000"),
        ("0.0000000014", "0.000000001"),
        ("999999999.9999999994", "999999999.999999999"),
        ("0.0000000004", None),  # rounds to zero
        ("0", None),
        ("-1", None),
        ("1000000000", None),  # overflows Numeric(18, 9)
    ],
)
def test_storable_rounds_to_the_column_or_refuses(value: str, expected: str | None):
    from app.modules.assets.domain import storable

    result = storable(Decimal(value))

    assert result == (Decimal(expected) if expected else None)
