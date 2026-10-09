"""Bond pricing service: calculates and stores synthetic bond prices."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.core.errors import BondAccrualFailedError
from app.modules.assets.constants import SOURCE_BONDS
from app.modules.assets.domain.bond_accrual import BondTerms as DomainBondTerms
from app.modules.assets.domain.bond_accrual import accrue_interest
from app.modules.assets.models.assets import Asset
from app.modules.assets.models.bond_terms import BondTerms
from app.modules.assets.repositories.assets import AssetRepository
from app.modules.assets.repositories.prices import PriceRepository
from app.modules.assets.services.bond_data import BondDataService


def _to_domain_terms(orm: BondTerms) -> DomainBondTerms:
    """Convert the ORM `BondTerms` row to the domain layer's own copy of the
    dataclass (domain/ may depend only on stdlib, never on an ORM model)."""
    return DomainBondTerms(
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


@dataclass(frozen=True, slots=True)
class RefreshResult:
    """Result of a bond price refresh operation."""

    ok: int  # Number successfully calculated and stored
    failed: int  # Number that failed (e.g., missing terms, calculation error)


class BondPricingService:
    """Calculates and stores synthetic bond prices (daily accrual)."""

    def __init__(
        self,
        bond_data: BondDataService,
        prices: PriceRepository,
        assets: AssetRepository,
    ) -> None:
        self._bond_data = bond_data
        self._prices = prices
        self._assets = assets

    def calculate_price(
        self,
        terms: BondTerms,
        as_of: date,
        nbp_rate: Decimal | None = None,
        cpi_history: Mapping[date, Decimal] | None = None,
    ) -> Decimal:
        """Calculate synthetic price for a bond on a given date.

        Formula: nominal_value * accrue_interest_coefficient

        Raises BondAccrualFailedError if calculation fails (e.g., invalid dates).
        """
        try:
            domain_terms = _to_domain_terms(terms)
            coefficient = accrue_interest(domain_terms, as_of, nbp_rate, cpi_history)
            return terms.nominal_value * coefficient
        except (ValueError, TypeError) as e:
            raise BondAccrualFailedError(
                f"Failed to calculate bond price for {terms.series_code}: {e!s}"
            ) from e

    def refresh_bond_prices(
        self,
        bonds: list[Asset],
        as_of: date,
        nbp_rate: Decimal | None = None,
        cpi_history: Mapping[date, Decimal] | None = None,
    ) -> int:
        """Calculate and store today's synthetic prices for bonds.

        Returns: number of bonds successfully updated.

        For each bond asset:
        1. Load BondTerms
        2. Calculate synthetic price = nominal * accrual_coefficient
        3. Store in assets_price with source="bonds", is_synthetic=True
        4. Update Asset.current_price cache

        Skips bonds without registered terms (missing BondTerms).
        Skips calculation errors (logs but continues).
        """
        ok_count = 0

        with self._prices.transaction():
            for bond_asset in bonds:
                terms_orm = self._bond_data.find_terms(bond_asset.id)
                if terms_orm is None:
                    # No terms registered for this bond, skip
                    continue

                try:
                    # One bond failing must not roll back the others.
                    with self._prices.savepoint():
                        synthetic_price = self.calculate_price(
                            terms_orm, as_of, nbp_rate, cpi_history
                        )
                        self._prices.upsert(
                            asset_id=bond_asset.id,
                            price_date=as_of,
                            close=synthetic_price,
                            currency_id=bond_asset.currency_id,
                            source=SOURCE_BONDS,
                            is_synthetic=True,
                        )
                        bond_asset.current_price = synthetic_price
                        self._assets.persist(bond_asset)
                except BondAccrualFailedError:
                    # Skip this bond on error (e.g., missing CPI for
                    # inflation-linked bonds). Logging is done by the
                    # caller/infrastructure layer.
                    continue
                else:
                    ok_count += 1

        return ok_count
