"""Instrument identifiers: ISIN, MIC and country code normalization.

Pure functions - no I/O, no clock.
"""

import re

_ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
_MIC_RE = re.compile(r"^[A-Z0-9]{4}$")
_COUNTRY_RE = re.compile(r"^[A-Z]{2}$")


def _luhn_ok(digits: str) -> bool:
    total = 0
    for index, char in enumerate(reversed(digits)):
        value = int(char)
        if index % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def normalize_isin(raw: str) -> str | None:
    """The upper-cased ISIN when `raw` is a valid one (12 characters, ISO 6166
    check digit), otherwise `None`."""
    isin = raw.strip().upper()
    if not _ISIN_RE.match(isin):
        return None
    # Letters expand to two digits (A=10 ... Z=35); then the Luhn check applies.
    expanded = "".join(str(int(char, 36)) for char in isin)
    return isin if _luhn_ok(expanded) else None


def normalize_mic(raw: str) -> str | None:
    """The upper-cased ISO 10383 MIC (4 alphanumerics), otherwise `None`."""
    mic = raw.strip().upper()
    return mic if _MIC_RE.match(mic) else None


def normalize_country(raw: str) -> str | None:
    """The upper-cased ISO 3166-1 alpha-2 shape (2 letters), otherwise `None`."""
    country = raw.strip().upper()
    return country if _COUNTRY_RE.match(country) else None
