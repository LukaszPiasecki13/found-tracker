import pytest

from app.modules.assets.domain import normalize_country, normalize_isin, normalize_mic


@pytest.mark.parametrize(
    "isin",
    [
        "US0378331005",  # Apple
        "PLPKO0000016",  # PKO BP
        "IE00B4L5Y983",  # iShares MSCI World
    ],
)
def test_valid_isins_are_accepted_and_uppercased(isin: str) -> None:
    assert normalize_isin(f"  {isin.lower()} ") == isin


@pytest.mark.parametrize(
    "isin",
    [
        "US0378331006",  # wrong check digit
        "US037833100",  # too short
        "US03783310055",  # too long
        "1S0378331005",  # country part not letters
        "US037833100X",  # check digit not a digit
        "",
    ],
)
def test_invalid_isins_are_rejected(isin: str) -> None:
    assert normalize_isin(isin) is None


def test_mic_is_four_alphanumerics_uppercased() -> None:
    assert normalize_mic(" xwar ") == "XWAR"
    assert normalize_mic("XNY") is None
    assert normalize_mic("XNYSE") is None
    assert normalize_mic("XN-S") is None


def test_country_is_two_letters_uppercased() -> None:
    assert normalize_country(" pl") == "PL"
    assert normalize_country("POL") is None
    assert normalize_country("P1") is None
