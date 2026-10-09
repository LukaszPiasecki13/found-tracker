"""Pydantic schemas for bond series terms: provider search (prefill) and
registration against an existing `asset_type="bond"` asset."""

from datetime import date
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.market_data import BondTerms as BondTermsPort
from app.core.schemas import DecimalNumber

# OTS, ROR, DOR, TOS, COI, EDO, ROS, ROD - the eight current retail series;
# see `assets/domain/bond_accrual.py` for what each one does.
BOND_SYMBOLS = ("OTS", "ROR", "DOR", "TOS", "COI", "EDO", "ROS", "ROD")
CAPITALIZATIONS = ("none", "monthly", "annual")
REFERENCE_TYPES = ("fixed", "nbp_reference", "cpi")


def _check_choice(value: str, choices: tuple[str, ...], field: str) -> str:
    if value not in choices:
        raise ValueError(f"{field} must be one of: {', '.join(choices)}")
    return value


class BondTermsCreateRequest(BaseModel):
    """What a user submits to register a bond series for an asset. Always
    stored with `source="manual"` (the API layer sets it), so the daily
    sync job never overwrites it."""

    model_config = ConfigDict(extra="forbid")

    bond_symbol: str
    series_code: str = Field(min_length=1, max_length=20)
    nominal_value: DecimalNumber = Decimal("100.00")
    issue_date: date
    maturity_date: date
    capitalization: str
    first_period_rate: DecimalNumber | None = None
    reference_type: str | None = None
    margin: DecimalNumber | None = None
    redemption_fee: DecimalNumber

    @field_validator("bond_symbol")
    @classmethod
    def _check_bond_symbol(cls, value: str) -> str:
        return _check_choice(value, BOND_SYMBOLS, "bond_symbol")

    @field_validator("capitalization")
    @classmethod
    def _check_capitalization(cls, value: str) -> str:
        return _check_choice(value, CAPITALIZATIONS, "capitalization")

    @field_validator("reference_type")
    @classmethod
    def _check_reference_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _check_choice(value, REFERENCE_TYPES, "reference_type")


class BondTermsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    asset_id: int
    bond_symbol: str
    series_code: str
    nominal_value: DecimalNumber
    issue_date: date
    maturity_date: date
    capitalization: str
    first_period_rate: DecimalNumber | None
    reference_type: str | None
    margin: DecimalNumber | None
    redemption_fee: DecimalNumber
    source: str


class BondSeriesSearchResponse(BaseModel):
    """What the data provider returned for a series code - prefill data for
    the registration form, not yet saved against any asset."""

    bond_symbol: str
    series_code: str
    nominal_value: DecimalNumber
    issue_date: date
    maturity_date: date
    capitalization: str
    first_period_rate: DecimalNumber | None
    reference_type: str | None
    margin: DecimalNumber | None
    redemption_fee: DecimalNumber

    @classmethod
    def from_port(cls, terms: BondTermsPort) -> Self:
        return cls(
            bond_symbol=terms.bond_symbol,
            series_code=terms.series_code,
            nominal_value=terms.nominal_value,
            issue_date=terms.issue_date,
            maturity_date=terms.maturity_date,
            capitalization=terms.capitalization,
            first_period_rate=terms.first_period_rate,
            reference_type=terms.reference_type,
            margin=terms.margin,
            redemption_fee=terms.redemption_fee,
        )
