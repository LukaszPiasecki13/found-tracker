"""Price and FX-rate history rules: source precedence, the effective value of a
day, staleness. Pure functions - the caller supplies "today"."""

from collections.abc import Callable, Iterable
from datetime import date
from decimal import Decimal

MANUAL_SOURCE = "manual"
# Rank of a source nobody configured; the lowest precedence.
UNKNOWN_SOURCE_RANK = 1000
# Provider sources known today; a provider without a listing priority ranks 1.
_PROVIDER_RANK = 1


def source_rank(source: str, known_providers: frozenset[str]) -> int:
    """`manual` always wins (0); a known provider next; anything else last."""
    if source == MANUAL_SOURCE:
        return 0
    if source in known_providers:
        return _PROVIDER_RANK
    return UNKNOWN_SOURCE_RANK


def pick_effective[T](
    observations: Iterable[T],
    *,
    day_of: Callable[[T], date],
    source_of: Callable[[T], str],
    known_providers: frozenset[str],
    as_of: date,
) -> T | None:
    """The observation that prices `as_of`: the latest day not after `as_of`;
    among that day's sources the best rank (ties broken by source name so the
    choice is deterministic). `None` when nothing is that old."""
    eligible = [item for item in observations if day_of(item) <= as_of]
    if not eligible:
        return None
    latest = max(day_of(item) for item in eligible)
    same_day = [item for item in eligible if day_of(item) == latest]
    return min(
        same_day,
        key=lambda item: (
            source_rank(source_of(item), known_providers),
            source_of(item),
        ),
    )


def best_per_day[T](
    observations: Iterable[T],
    *,
    day_of: Callable[[T], date],
    source_of: Callable[[T], str],
    known_providers: frozenset[str],
) -> dict[date, T]:
    """The winning observation of each day that has any (same precedence as
    `pick_effective`)."""
    by_day: dict[date, list[T]] = {}
    for item in observations:
        by_day.setdefault(day_of(item), []).append(item)
    return {
        day: min(
            items,
            key=lambda item: (
                source_rank(source_of(item), known_providers),
                source_of(item),
            ),
        )
        for day, items in by_day.items()
    }


def is_stale(observed_on: date | None, *, today: date, max_age_days: int) -> bool:
    """True when there is no observation or it is older than `max_age_days`."""
    if observed_on is None:
        return True
    return (today - observed_on).days > max_age_days


def invert_rate(rate: Decimal) -> Decimal:
    """The reverse quote of a positive rate, to the 9 places the rate column
    stores (`Numeric(18, 9)`)."""
    return (Decimal(1) / rate).quantize(Decimal("0.000000001"))
