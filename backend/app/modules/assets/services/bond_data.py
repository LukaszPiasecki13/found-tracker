"""Bond data service: manages bond series parameters and registration."""

from datetime import date, datetime
from decimal import Decimal

from app.core.market_data import BondTerms as BondTermsPort
from app.modules.assets.exceptions import InvalidBondTermsError
from app.modules.assets.models.bond_terms import BondTerms
from app.modules.assets.repositories.bond_terms import BondTermsRepository


class BondDataService:
    """Manages bond series data: registration, lookup, and validation."""

    def __init__(self, repository: BondTermsRepository) -> None:
        self._repo = repository

    def get_terms(self, asset_id: int) -> BondTerms:
        """Get bond terms for an asset or raise BondTermsNotFoundError."""
        return self._repo.get_by_asset_id(asset_id)

    def find_terms(self, asset_id: int) -> BondTerms | None:
        """Find bond terms for an asset, or None if not registered."""
        return self._repo.find_by_asset_id(asset_id)

    def register_series(
        self,
        asset_id: int,
        bond_symbol: str,
        series_code: str,
        nominal_value: Decimal,
        issue_date: date,
        maturity_date: date,
        capitalization: str,
        first_period_rate: Decimal | None,
        reference_type: str | None,
        margin: Decimal | None,
        redemption_fee: Decimal,
        source: str = "bonds",
        fetched_at: datetime | None = None,
    ) -> BondTerms:
        """Register or update bond series parameters for an asset.

        Validates that maturity_date > issue_date and first_period_rate >= 0 if present.
        """
        self._validate_bond_terms(issue_date, maturity_date, first_period_rate, margin)

        with self._repo.transaction():
            return self._repo.upsert(
                asset_id=asset_id,
                bond_symbol=bond_symbol,
                series_code=series_code,
                nominal_value=nominal_value,
                issue_date=issue_date,
                maturity_date=maturity_date,
                capitalization=capitalization,
                first_period_rate=first_period_rate,
                reference_type=reference_type,
                margin=margin,
                redemption_fee=redemption_fee,
                source=source,
                fetched_at=fetched_at,
            )

    @staticmethod
    def _validate_bond_terms(
        issue_date: date,
        maturity_date: date,
        first_period_rate: Decimal | None,
        margin: Decimal | None,
    ) -> None:
        """Validate bond terms for consistency."""
        if maturity_date <= issue_date:
            raise InvalidBondTermsError("Maturity date must be after issue date")

        if first_period_rate is not None and first_period_rate < Decimal("0"):
            raise InvalidBondTermsError("First period rate must be non-negative")

        if margin is not None and margin < Decimal("0"):
            raise InvalidBondTermsError("Margin must be non-negative")

    def to_port(self, orm: BondTerms) -> BondTermsPort:
        """Convert ORM model to port dataclass."""
        return BondTermsPort(
            bond_symbol=orm.bond_symbol,
            series_code=orm.series_code,
            nominal_value=orm.nominal_value,
            issue_date=orm.issue_date,
            maturity_date=orm.maturity_date,
            capitalization=orm.capitalization,
            first_period_rate=orm.first_period_rate,
            reference_type=orm.reference_type,
            margin=orm.margin,
            redemption_fee=orm.redemption_fee,
        )
