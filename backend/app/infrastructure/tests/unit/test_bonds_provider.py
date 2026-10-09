"""`BondDataProviderImpl` with `_fetch_text` replaced - never hits the network.

Fixture strings are real records observed live on
https://0xbartix.github.io/portfel-dane/v1/ (obligacje.txt, cpi.txt,
stopa_ref_teraz.txt) and cross-checked against the independently researched
facts in `.tmp/tasks/obligacje-skarbowe/20261007-094548/external-research/`
(e.g. EDO1036 = 5.35% first-year rate, 2.00% margin, 3.00 PLN redemption fee;
TOS1228's 1.00 PLN fee matches the known post-September-2024 increase, while
the earlier TOS1225's 0.70 PLN fee predates it).
"""

from datetime import date
from decimal import Decimal

import pytest

from app.core.errors import BondDataUnavailableError
from app.infrastructure.market_data import bonds
from app.infrastructure.market_data.bonds import (
    BondDataProviderImpl,
    _parse_bond_entry,
    _series_maturity_date,
)

OBLIGACJE_FIXTURE = (
    "B;COI0124024001250070;EDO1036053502000300;TOS1225068500000070;TOS1228046500000100"
)
CPI_FIXTURE = "S2014011005100710071003100210030998099710341029"
REFERENCE_RATE_FIXTURE = "R037520260305"


@pytest.fixture(autouse=True)
def fake_fetch(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Maps a `portfel-dane` path to canned text; defaults to the fixtures
    above but a test can overwrite an entry or delete it to simulate an
    outage."""
    responses = {
        "obligacje.txt": OBLIGACJE_FIXTURE,
        "cpi.txt": CPI_FIXTURE,
        "stopa_ref_teraz.txt": REFERENCE_RATE_FIXTURE,
    }

    def _fake_fetch_text(path: str) -> str:
        if path not in responses:
            raise BondDataUnavailableError(f"no fixture for {path}")
        return responses[path]

    monkeypatch.setattr(bonds, "_fetch_text", _fake_fetch_text)
    return responses


def test_series_maturity_date_from_series_code() -> None:
    assert _series_maturity_date("EDO1036") == date(2036, 10, 1)


def test_parse_bond_entry_edo() -> None:
    terms = _parse_bond_entry("EDO1036053502000300")
    assert terms is not None
    assert terms.bond_symbol == "EDO"
    assert terms.series_code == "EDO1036"
    assert terms.maturity_date == date(2036, 10, 1)
    assert terms.issue_date == date(2026, 10, 1)
    assert terms.capitalization == "annual"
    assert terms.reference_type == "cpi"
    assert terms.first_period_rate == Decimal("5.35")
    assert terms.margin == Decimal("2.00")
    assert terms.redemption_fee == Decimal("3.00")


def test_parse_bond_entry_tos_has_no_margin() -> None:
    terms = _parse_bond_entry("TOS1228046500000100")
    assert terms is not None
    assert terms.reference_type == "fixed"
    assert terms.margin is None
    assert terms.first_period_rate == Decimal("4.65")
    assert terms.redemption_fee == Decimal("1.00")


def test_parse_bond_entry_rejects_wrong_length() -> None:
    assert _parse_bond_entry("TOO_SHORT") is None


def test_parse_bond_entry_rejects_unknown_symbol() -> None:
    assert _parse_bond_entry("ZZZ1036053502000300") is None


def test_fetch_series_returns_known_series() -> None:
    provider = BondDataProviderImpl()

    terms = provider.fetch_series("EDO1036")

    assert terms is not None
    assert terms.series_code == "EDO1036"
    assert terms.first_period_rate == Decimal("5.35")


def test_fetch_series_returns_none_for_unknown_series() -> None:
    provider = BondDataProviderImpl()

    assert provider.fetch_series("ZZZ9999") is None


def test_fetch_series_raises_unavailable_on_fetch_failure(
    fake_fetch: dict[str, str],
) -> None:
    del fake_fetch["obligacje.txt"]
    provider = BondDataProviderImpl()

    with pytest.raises(BondDataUnavailableError):
        provider.fetch_series("EDO1036")


def test_fetch_reference_rate_parses_percent() -> None:
    provider = BondDataProviderImpl()

    assert provider.fetch_reference_rate() == Decimal("3.75")


def test_fetch_cpi_history_parses_the_full_monthly_series() -> None:
    provider = BondDataProviderImpl()

    history = provider.fetch_cpi_history()

    assert history[date(2014, 1, 1)] == Decimal("0.5")
    assert history[date(2014, 6, 1)] == Decimal("0.3")
    assert history[date(2014, 7, 1)] == Decimal("-0.2")
    assert history[date(2014, 10, 1)] == Decimal("2.9")
    assert len(history) == 10


def test_fetch_cpi_converts_index_to_rate() -> None:
    provider = BondDataProviderImpl()

    # Fixture's last 4-digit chunk is "1029" -> index 102.9 -> 2.9% y/y.
    assert provider.fetch_cpi() == Decimal("2.9")


def test_fetch_cpi_returns_none_when_feed_has_no_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bonds, "_fetch_text", lambda path: "S201401")
    provider = BondDataProviderImpl()

    assert provider.fetch_cpi() is None
