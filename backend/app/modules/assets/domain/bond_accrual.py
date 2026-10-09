"""Bond accrual calculation: pure domain logic for interest accumulation.

Level 1 of the domain (ADR-0005): stateless, no ORM/I/O, stdlib only.
Duplicates `BondTerms` from `core/market_data.py` rather than importing it,
because `domain/` may depend only on the standard library (CLAUDE.md
"Granice modulow"), and `core/` is not part of the standard library.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

_ZERO = Decimal("0")
_ONE = Decimal("1")
_DAYS_PER_YEAR = 365

# How many months before a capitalization anniversary the referenced CPI
# reading was published. Not verified against the legal "Lista Emisyjna"
# text (see `external-research/`, "what is confirmed, what is inferred") -
# this is a documented approximation, not a cited formula.
_CPI_REFERENCE_LAG_MONTHS = 1


@dataclass(frozen=True, slots=True)
class BondTerms:
    """Bond series terms duplicated from `core/market_data.py` for the
    domain layer (see module docstring for why)."""

    bond_symbol: str  # OTS, ROR, DOR, TOS, COI, EDO, ROS, ROD
    series_code: str  # e.g., "EDO1036"
    nominal_value: Decimal
    issue_date: date
    maturity_date: date
    capitalization: str  # "none" / "monthly" / "annual"
    first_period_rate: Decimal | None
    reference_type: str | None
    margin: Decimal | None
    redemption_fee: Decimal


def _shift_month(d: date, months: int) -> date:
    """`d`'s month shifted by `months` (positive or negative), day fixed to
    1 - `cpi_history` is always keyed by the first of the month."""
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _add_years(d: date, years: int) -> date:
    """`d` plus whole `years`, clamped to day 28 if that date doesn't exist
    (29 Feb on a non-leap target year)."""
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        return d.replace(year=d.year + years, day=28)


def _cpi_for_anniversary(
    anniversary: date, cpi_history: Mapping[date, Decimal] | None
) -> Decimal | None:
    """The CPI y/y reading in effect for the coupon year starting at
    `anniversary`, or `None` if unavailable (too recent, or no history
    supplied) - callers fall back to margin-only for that year."""
    if cpi_history is None:
        return None
    reference_month = _shift_month(
        date(anniversary.year, anniversary.month, 1), -_CPI_REFERENCE_LAG_MONTHS
    )
    return cpi_history.get(reference_month)


def _cpi_plus_margin_rate(cpi: Decimal | None, margin: Decimal) -> Decimal:
    """Annual rate for a CPI-indexed year: CPI (floored at 0%) plus margin,
    or just the margin when CPI isn't available (conservative fallback)."""
    margin_fraction = margin / Decimal("100")
    if cpi is None:
        return margin_fraction
    return max(cpi / Decimal("100"), _ZERO) + margin_fraction


def _compound_from_year_2(
    coefficient: Decimal,
    issue_date: date,
    days_elapsed: int,
    cpi_history: Mapping[date, Decimal] | None,
    margin: Decimal,
) -> Decimal:
    """Compound `coefficient` annually from year 2 onward, each year at
    *that year's own* CPI+margin (not a single "current" value reused for
    every elapsed year), including a proportional accrual for the current
    partial year."""
    full_years = int(days_elapsed // _DAYS_PER_YEAR)
    for year_num in range(2, full_years + 1):
        anniversary = _add_years(issue_date, year_num - 1)
        cpi = _cpi_for_anniversary(anniversary, cpi_history)
        coefficient *= _ONE + _cpi_plus_margin_rate(cpi, margin)

    days_in_last_year = days_elapsed % _DAYS_PER_YEAR
    if full_years > 0 and days_in_last_year > 0:
        anniversary = _add_years(issue_date, full_years)
        cpi = _cpi_for_anniversary(anniversary, cpi_history)
        rate = _cpi_plus_margin_rate(cpi, margin)
        partial_fraction = Decimal(days_in_last_year) / Decimal(_DAYS_PER_YEAR)
        coefficient *= (_ONE + rate) ** partial_fraction
    return coefficient


def accrue_interest(
    terms: BondTerms,
    as_of: date,
    nbp_rate: Decimal | None = None,
    cpi_history: Mapping[date, Decimal] | None = None,
) -> Decimal:
    """Calculate the bond accrual coefficient as of `as_of`.

    Returns a coefficient (`Decimal`) to multiply `nominal_value` by: e.g. a
    coefficient of `Decimal("1.0350")` means price = nominal * 1.0350.

    `cpi_history` maps the first day of a month to that month's published
    y/y CPI (percent); each capitalization year looks up its own reading
    rather than reusing one "current" value for the whole history (that
    would both misprice older bonds and make the price jump retroactively
    on every CPI release). A year whose reading isn't in `cpi_history`
    falls back to margin-only.

    Raises `ValueError` if `as_of` is before `issue_date`, or if
    `maturity_date <= issue_date`. `as_of` after `maturity_date` is clamped
    to `maturity_date` (no further growth once matured).

    Per bond type (see `external-research/` for the underlying research):
    - OTS: no daily accrual; interest is paid once at redemption.
    - ROR / DOR: interest is paid out monthly, never capitalized into price.
    - TOS: fixed rate, capitalized annually.
    - COI: interest is paid out annually (CPI+margin from year 2), never
      capitalized into price.
    - EDO / ROS / ROD: capitalized annually (CPI+margin from year 2, fixed
      rate in year 1), paid out only at redemption/maturity.
    """
    if as_of < terms.issue_date:
        raise ValueError(
            f"Cannot accrue interest before issue date ({terms.issue_date}); "
            f"as_of={as_of}"
        )
    if terms.maturity_date <= terms.issue_date:
        raise ValueError("Invalid bond: maturity_date must be after issue_date")

    calculation_date = min(as_of, terms.maturity_date)

    match terms.bond_symbol:
        case "OTS":
            return _accrue_ots(terms, calculation_date)
        case "ROR":
            return _accrue_ror(terms, calculation_date)
        case "DOR":
            return _accrue_dor(terms, calculation_date)
        case "TOS":
            return _accrue_tos(terms, calculation_date)
        case "COI":
            return _accrue_coi(terms, calculation_date, cpi_history)
        case "EDO":
            return _accrue_edo(terms, calculation_date, cpi_history)
        case "ROS":
            return _accrue_ros(terms, calculation_date, cpi_history)
        case "ROD":
            return _accrue_rod(terms, calculation_date, cpi_history)
        case _:
            raise ValueError(f"Unknown bond type: {terms.bond_symbol}")


def _accrue_ots(terms: BondTerms, as_of: date) -> Decimal:
    """OTS (3 months): fixed rate, no daily accrual; interest is paid once
    at redemption, so the synthetic price stays at nominal throughout."""
    return _ONE


def _accrue_ror(terms: BondTerms, as_of: date) -> Decimal:
    """ROR (1 year): interest is paid out monthly, never capitalized into
    the synthetic price."""
    return _ONE


def _accrue_dor(terms: BondTerms, as_of: date) -> Decimal:
    """DOR (2 years): interest is paid out monthly, never capitalized into
    the synthetic price."""
    return _ONE


def _accrue_tos(terms: BondTerms, as_of: date) -> Decimal:
    """TOS (3 years): fixed rate, capitalized annually.

    Example (TOS1029, rate 4.40%): after 1 year, 1.0440; after 3 years,
    (1.0440)^3 = 1.137934.
    """
    if terms.first_period_rate is None:
        raise ValueError("TOS requires first_period_rate")

    rate = terms.first_period_rate / Decimal("100")
    days_elapsed = (as_of - terms.issue_date).days
    full_years = days_elapsed // _DAYS_PER_YEAR
    coefficient = (_ONE + rate) ** int(full_years)

    days_in_last_year = days_elapsed % _DAYS_PER_YEAR
    if days_in_last_year > 0:
        partial_fraction = Decimal(days_in_last_year) / Decimal(_DAYS_PER_YEAR)
        coefficient *= (_ONE + rate) ** partial_fraction

    return coefficient


def _accrue_coi(
    terms: BondTerms, as_of: date, cpi_history: Mapping[date, Decimal] | None
) -> Decimal:
    """COI (4 years): year 1 fixed, years 2-4 CPI+margin, but paid out to
    the holder annually rather than capitalized, so the synthetic price
    stays at nominal throughout."""
    return _ONE


def _accrue_edo(
    terms: BondTerms, as_of: date, cpi_history: Mapping[date, Decimal] | None
) -> Decimal:
    """EDO (10 years): year 1 fixed rate, years 2-10 CPI+margin, capitalized
    annually (no cash payout until redemption/maturity). Each year 2+ uses
    *that year's own* CPI reading from `cpi_history`, not a reused "today".

    Example (EDO1036, first_period_rate 5.35%, margin 2.00%): after year 1,
    1.0535; after year 2 at CPI 5.10%, 1.0535 * 1.0710 = 1.128339.
    """
    if terms.first_period_rate is None:
        raise ValueError("EDO requires first_period_rate")
    if terms.margin is None:
        raise ValueError("EDO requires margin")

    days_elapsed = (as_of - terms.issue_date).days
    rate_year1 = terms.first_period_rate / Decimal("100")
    coefficient = _ONE + rate_year1
    return _compound_from_year_2(
        coefficient, terms.issue_date, days_elapsed, cpi_history, terms.margin
    )


def _accrue_ros(
    terms: BondTerms, as_of: date, cpi_history: Mapping[date, Decimal] | None
) -> Decimal:
    """ROS (6 years, Rodzina 800+): year 1 fixed rate, years 2-6
    CPI+2.00pp, capitalized annually. Same shape as EDO.

    Registered `margin` wins; 2.00pp is only a fallback for terms
    registered without one (e.g. an incomplete manual override).
    """
    if terms.first_period_rate is None:
        raise ValueError("ROS requires first_period_rate")

    margin = terms.margin if terms.margin is not None else Decimal("2.00")
    days_elapsed = (as_of - terms.issue_date).days
    rate_year1 = terms.first_period_rate / Decimal("100")
    coefficient = _ONE + rate_year1
    return _compound_from_year_2(
        coefficient, terms.issue_date, days_elapsed, cpi_history, margin
    )


def _accrue_rod(
    terms: BondTerms, as_of: date, cpi_history: Mapping[date, Decimal] | None
) -> Decimal:
    """ROD (12 years, Rodzina 800+): year 1 fixed rate, years 2-12
    CPI+2.50pp, capitalized annually. Same shape as EDO/ROS.

    Registered `margin` wins; 2.50pp is only a fallback for terms
    registered without one (e.g. an incomplete manual override).
    """
    if terms.first_period_rate is None:
        raise ValueError("ROD requires first_period_rate")

    margin = terms.margin if terms.margin is not None else Decimal("2.50")
    days_elapsed = (as_of - terms.issue_date).days
    rate_year1 = terms.first_period_rate / Decimal("100")
    coefficient = _ONE + rate_year1
    return _compound_from_year_2(
        coefficient, terms.issue_date, days_elapsed, cpi_history, margin
    )
