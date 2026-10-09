"""Bond data adapter (`BondDataProvider` port) backed by `portfel-dane`.

No official API exists for Polish retail treasury bond series terms, the NBP
reference rate, or monthly CPI — confirmed by research (see
`.tmp/tasks/obligacje-skarbowe/20261007-094548/external-research/`). The
community project `0xbartix/portfel-dane` (https://github.com/0xbartix/portfel-dane)
republishes all three hourly, derived from official Ministry of Finance "Lista
Emisyjna" PDFs and NBP/GUS figures, as small fixed-width flat files on GitHub
Pages. Manual override (`BondDataService.register_series` with
`source="manual"`) remains the fallback when a series is missing or the feed
is unavailable.

File formats (reverse-engineered from the live feed; see the project's own
README for the field list, not the exact byte offsets):

- `obligacje.txt`: one line, `B` + semicolon-separated 19-char records, each
  `KOD(7)` + `rate(4)` + `margin(4)` + `fee(4)`, all three numeric fields
  scaled x100. `KOD` is bond symbol (3 chars) + maturity month (2 digits) +
  maturity year, last 2 digits (2 digits) — e.g. "EDO1036" matures 2036-10.
- `stopa_ref_teraz.txt`: `R` + current NBP reference rate (4 digits, x100) +
  effective date (8 digits, YYYYMMDD).
- `cpi.txt`: `S` + first month (6 digits, YYYYMM) + one 4-digit CPI y/y index
  value (x10, base 100) per month since then, concatenated with no separator.
"""

from datetime import date
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from dateutil.relativedelta import relativedelta  # type: ignore[import-untyped]

from app.core.errors import BondDataUnavailableError
from app.core.market_data import BondTerms

_BASE_URL = "https://0xbartix.github.io/portfel-dane/v1"
_TIMEOUT_SECONDS = 10
_ENTRY_LENGTH = 19

# Bond term length in months, keyed by the symbol prefix of the series code
# (e.g. "EDO1036" -> "EDO"). Source: obligacjeskarbowe.pl product pages.
_TERM_MONTHS = {
    "OTS": 3,
    "ROR": 12,
    "DOR": 24,
    "TOS": 36,
    "COI": 48,
    "EDO": 120,
    "ROS": 72,
    "ROD": 144,
}

# Capitalization and reference-rate behaviour per bond symbol (DEC-06):
# "none" means interest is paid out in cash (ROR/DOR monthly, COI annually)
# rather than compounded into the synthetic price.
_CAPITALIZATION = {
    "OTS": "none",
    "ROR": "none",
    "DOR": "none",
    "TOS": "annual",
    "COI": "none",
    "EDO": "annual",
    "ROS": "annual",
    "ROD": "annual",
}
_REFERENCE_TYPE = {
    "OTS": "fixed",
    "ROR": "nbp_reference",
    "DOR": "nbp_reference",
    "TOS": "fixed",
    "COI": "cpi",
    "EDO": "cpi",
    "ROS": "cpi",
    "ROD": "cpi",
}


def _fetch_text(path: str) -> str:
    try:
        with urlopen(f"{_BASE_URL}/{path}", timeout=_TIMEOUT_SECONDS) as response:
            raw: bytes = response.read()
            return raw.decode("utf-8")
    except (URLError, HTTPError, TimeoutError, OSError, UnicodeDecodeError) as exc:
        raise BondDataUnavailableError(
            f"Could not fetch {path} from portfel-dane: {exc}"
        ) from exc


def _parse_scaled(field: str, scale: str) -> Decimal:
    try:
        return Decimal(field) / Decimal(scale)
    except InvalidOperation as exc:
        raise BondDataUnavailableError(
            f"Malformed numeric field {field!r} in portfel-dane data"
        ) from exc


def _shift_month(d: date, months: int) -> date:
    """`d`'s month shifted by `months` (positive or negative), day fixed to
    1 - `cpi.txt` entries are always a month's first day."""
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _series_maturity_date(series_code: str) -> date:
    """`obligacje.txt` keys each series by maturity month/year, not issue
    date (e.g. "EDO1036", sold October 2026, matures October 2036). The feed
    has no maturity day, so this assumes the 1st; exact day is cosmetic for
    accrual (only full elapsed years/months matter for every current bond
    type) but can be corrected via manual override if ever needed."""
    month = int(series_code[3:5])
    year_2digit = int(series_code[5:7])
    return date(2000 + year_2digit, month, 1)


def _parse_bond_entry(entry: str) -> BondTerms | None:
    """Parse one `obligacje.txt` record: `KOD(7)` + `rate(4)` + `margin(4)` +
    `fee(4)`, all numeric fields scaled x100."""
    if len(entry) != _ENTRY_LENGTH:
        return None
    series_code = entry[:7]
    symbol = series_code[:3]
    term_months = _TERM_MONTHS.get(symbol)
    if term_months is None:
        return None
    maturity_date = _series_maturity_date(series_code)
    issue_date = maturity_date - relativedelta(months=term_months)
    rate = _parse_scaled(entry[7:11], "100")
    margin = _parse_scaled(entry[11:15], "100")
    fee = _parse_scaled(entry[15:19], "100")
    reference_type = _REFERENCE_TYPE[symbol]
    return BondTerms(
        bond_symbol=symbol,
        series_code=series_code,
        nominal_value=Decimal("100.00"),
        issue_date=issue_date,
        maturity_date=maturity_date,
        capitalization=_CAPITALIZATION[symbol],
        first_period_rate=rate,
        reference_type=reference_type,
        margin=margin if reference_type != "fixed" else None,
        redemption_fee=fee,
    )


class BondDataProviderImpl:
    """`BondDataProvider` backed by the `portfel-dane` flat-file feed."""

    def fetch_series(self, symbol: str) -> BondTerms | None:
        """Bond terms for series code `symbol` (e.g. "EDO1036"), or `None` if
        the feed has no such series. Raises `BondDataUnavailableError` if the
        feed cannot be fetched or is not in the expected format."""
        body = _fetch_text("obligacje.txt").strip()
        if not body.startswith("B"):
            raise BondDataUnavailableError(
                "Unexpected obligacje.txt format: missing 'B' record marker"
            )
        for raw_entry in body[1:].split(";"):
            entry = raw_entry.strip()
            if len(entry) >= 7 and entry[:7] == symbol:
                return _parse_bond_entry(entry)
        return None

    def fetch_reference_rate(self) -> Decimal:
        """Current NBP reference rate (percent per year). ROR/DOR key their
        coupon off it, but pay it out in cash rather than capitalizing it
        into price, so `accrue_interest` does not consume this value today;
        reserved for a future coupon-amount calculator. Raises
        `BondDataUnavailableError` on fetch/parse failure."""
        body = _fetch_text("stopa_ref_teraz.txt").strip()
        if not body.startswith("R") or len(body) != 13:
            raise BondDataUnavailableError(
                f"Unexpected stopa_ref_teraz.txt format: {body!r}"
            )
        return _parse_scaled(body[1:5], "100")

    def fetch_cpi(self) -> Decimal | None:
        """Most recently published monthly CPI y/y (percent). `None` if the
        feed carries no values yet. Raises `BondDataUnavailableError` on
        fetch/parse failure."""
        history = self.fetch_cpi_history()
        if not history:
            return None
        return history[max(history)]

    def fetch_cpi_history(self) -> dict[date, Decimal]:
        """Every published monthly CPI y/y (percent) since the feed's first
        month, keyed by that month's first day. `accrue_interest` looks up
        each capitalization year's *own* reading here instead of reusing
        one "current" value for a bond's whole history. Raises
        `BondDataUnavailableError` on fetch/parse failure."""
        body = _fetch_text("cpi.txt").strip()
        if not body.startswith("S") or len(body) < 7:
            raise BondDataUnavailableError(f"Unexpected cpi.txt format: {body!r}")
        start_month = date(int(body[1:5]), int(body[5:7]), 1)
        digits = body[7:]
        history: dict[date, Decimal] = {}
        for i in range(0, len(digits) - 3, 4):
            # The feed stores a CPI index (base 100, x10); accrue_interest()
            # takes a y/y percentage, so convert index -> rate (e.g. 103.4 -> 3.4%).
            index = _parse_scaled(digits[i : i + 4], "10")
            history[_shift_month(start_month, i // 4)] = index - Decimal("100")
        return history
