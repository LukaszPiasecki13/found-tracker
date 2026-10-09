"""Bond terms repository for data access."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select

from app.core.errors import BondTermsNotFoundError
from app.infrastructure.sql.repository import SQLRepository
from app.modules.assets.models.bond_terms import BondTerms


class BondTermsRepository(SQLRepository):
    """Repository for BondTerms model database operations."""

    def get_by_asset_id(self, asset_id: int) -> BondTerms:
        """Get bond terms by asset_id or raise BondTermsNotFoundError."""
        terms = self.find_by_asset_id(asset_id)
        if terms is None:
            raise BondTermsNotFoundError(f"Bond terms not found for asset {asset_id}")
        return terms

    def find_by_asset_id(self, asset_id: int) -> BondTerms | None:
        """Find bond terms by asset_id, or None if not found."""
        stmt = select(BondTerms).where(BondTerms.asset_id == asset_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def upsert(
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
        """Create or update bond terms for an asset.

        Returns the saved BondTerms record (refreshed to include server defaults).
        """

        existing = self.find_by_asset_id(asset_id)

        if existing is not None:
            # Update existing record
            existing.bond_symbol = bond_symbol
            existing.series_code = series_code
            existing.nominal_value = nominal_value
            existing.issue_date = issue_date
            existing.maturity_date = maturity_date
            existing.capitalization = capitalization
            existing.first_period_rate = first_period_rate
            existing.reference_type = reference_type
            existing.margin = margin
            existing.redemption_fee = redemption_fee
            existing.source = source
            existing.fetched_at = fetched_at
            return self.persist(existing)

        # Create new record
        terms = BondTerms(
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
        return self.save_new(terms)

    def delete(self, terms: BondTerms) -> None:
        """Delete bond terms record."""
        self.session.delete(terms)
        self.flush()
