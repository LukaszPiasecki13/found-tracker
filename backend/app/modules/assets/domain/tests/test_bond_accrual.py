"""Tests for bond accrual calculation (domain layer)."""

from datetime import date
from decimal import Decimal

import pytest

from app.modules.assets.domain.bond_accrual import (
    BondTerms,
    accrue_interest,
)


class TestAccrueOTS:
    """OTS (3 months): fixed rate, no daily accrual."""

    def test_ots_returns_one_always(self):
        """OTS returns 1.0 throughout (interest paid at maturity, not accrued)."""
        terms = BondTerms(
            bond_symbol="OTS",
            series_code="OTS0001",
            nominal_value=Decimal("100.00"),
            issue_date=date(2024, 10, 1),
            maturity_date=date(2025, 1, 1),
            capitalization="none",
            first_period_rate=Decimal("2.00"),
            reference_type="fixed",
            margin=None,
            redemption_fee=Decimal("0.00"),
        )

        # On issue date
        result = accrue_interest(terms, date(2024, 10, 1))
        assert result == Decimal("1.0")

        # Mid-term
        result = accrue_interest(terms, date(2024, 11, 1))
        assert result == Decimal("1.0")

        # At maturity
        result = accrue_interest(terms, date(2025, 1, 1))
        assert result == Decimal("1.0")


class TestAccrueROR:
    """ROR (1 year): monthly payouts, no capitalization."""

    def test_ror_returns_one_always(self):
        """ROR returns 1.0 (interest paid out monthly, not accrued in price)."""
        terms = BondTerms(
            bond_symbol="ROR",
            series_code="ROR0001",
            nominal_value=Decimal("100.00"),
            issue_date=date(2024, 1, 1),
            maturity_date=date(2025, 1, 1),
            capitalization="monthly",
            first_period_rate=Decimal("3.00"),
            reference_type="nbp_reference",
            margin=None,
            redemption_fee=Decimal("0.50"),
        )

        result = accrue_interest(terms, date(2024, 1, 1))
        assert result == Decimal("1.0")

        result = accrue_interest(terms, date(2024, 6, 1))
        assert result == Decimal("1.0")

        result = accrue_interest(terms, date(2025, 1, 1))
        assert result == Decimal("1.0")


class TestAccrueDOR:
    """DOR (2 years): monthly payouts, no capitalization."""

    def test_dor_returns_one_always(self):
        """DOR returns 1.0 (interest paid out monthly, not accrued in price)."""
        terms = BondTerms(
            bond_symbol="DOR",
            series_code="DOR0001",
            nominal_value=Decimal("100.00"),
            issue_date=date(2024, 1, 1),
            maturity_date=date(2026, 1, 1),
            capitalization="monthly",
            first_period_rate=Decimal("4.00"),
            reference_type="nbp_reference",
            margin=None,
            redemption_fee=Decimal("0.70"),
        )

        result = accrue_interest(terms, date(2024, 1, 1))
        assert result == Decimal("1.0")

        result = accrue_interest(terms, date(2025, 1, 1))
        assert result == Decimal("1.0")

        result = accrue_interest(terms, date(2026, 1, 1))
        assert result == Decimal("1.0")


class TestAccrueTOS:
    """TOS (3 years): fixed rate, annual capitalization."""

    def test_tos_annual_capitalization(self):
        """TOS capitalizes annually with fixed rate.

        Example: TOS1029 with 4.40% rate
        - After 1 year: 1.0440
        - After 2 years: (1.0440)^2 = 1.089936
        - After 3 years: (1.0440)^3 ≈ 1.1379
        """
        terms = BondTerms(
            bond_symbol="TOS",
            series_code="TOS1029",
            nominal_value=Decimal("100.00"),
            issue_date=date(2024, 3, 31),
            maturity_date=date(2027, 3, 31),
            capitalization="annual",
            first_period_rate=Decimal("4.40"),
            reference_type="fixed",
            margin=None,
            redemption_fee=Decimal("1.00"),
        )

        # End of year 1
        result = accrue_interest(terms, date(2025, 3, 31))
        assert abs(result - Decimal("1.0440")) < Decimal("0.001")

        # End of year 3
        result = accrue_interest(terms, date(2027, 3, 31))
        expected = Decimal("1.0440") ** 3  # ≈ 1.1379
        assert abs(result - expected) < Decimal("0.001")


class TestAccrueCOI:
    """COI (4 years): year 1 fixed, years 2-4 CPI+margin, annual payouts."""

    def test_coi_returns_one_annual_payouts(self):
        """COI returns 1.0 (interest paid out annually, not accrued)."""
        terms = BondTerms(
            bond_symbol="COI",
            series_code="COI0001",
            nominal_value=Decimal("100.00"),
            issue_date=date(2024, 1, 1),
            maturity_date=date(2028, 1, 1),
            capitalization="annual",
            first_period_rate=Decimal("3.50"),
            reference_type="cpi",
            margin=Decimal("1.50"),
            redemption_fee=Decimal("2.00"),
        )

        result = accrue_interest(terms, date(2024, 1, 1))
        assert result == Decimal("1.0")

        result = accrue_interest(terms, date(2026, 1, 1))
        assert result == Decimal("1.0")

        result = accrue_interest(terms, date(2028, 1, 1))
        assert result == Decimal("1.0")


class TestAccrueEDO:
    """EDO (10 years): year 1 fixed, years 2-10 CPI+2.00pp, annual capitalization."""

    def test_edo_year_1_capitalization(self):
        """EDO year 1 capitalizes with fixed rate (5.35% for EDO1036)."""
        terms = BondTerms(
            bond_symbol="EDO",
            series_code="EDO1036",
            nominal_value=Decimal("100.00"),
            issue_date=date(2024, 3, 31),
            maturity_date=date(2034, 3, 31),
            capitalization="annual",
            first_period_rate=Decimal("5.35"),
            reference_type="cpi",
            margin=Decimal("2.00"),
            redemption_fee=Decimal("3.00"),
        )

        # End of year 1
        result = accrue_interest(terms, date(2025, 3, 31))
        assert abs(result - Decimal("1.0535")) < Decimal("0.001")

    def test_edo_year_2_with_cpi(self):
        """EDO year 2+ applies CPI+2.00pp capitalization.

        The year-2 anniversary is 2025-03-31; `accrue_interest` looks up
        that year's own reading one month back (2025-02), per
        `_CPI_REFERENCE_LAG_MONTHS`.
        """
        terms = BondTerms(
            bond_symbol="EDO",
            series_code="EDO1036",
            nominal_value=Decimal("100.00"),
            issue_date=date(2024, 3, 31),
            maturity_date=date(2034, 3, 31),
            capitalization="annual",
            first_period_rate=Decimal("5.35"),
            reference_type="cpi",
            margin=Decimal("2.00"),
            redemption_fee=Decimal("3.00"),
        )

        # End of year 2 with CPI=5.10%
        # 1.0535 * (1 + 0.0510 + 0.0200) = 1.0535 * 1.0710 ≈ 1.1283
        result = accrue_interest(
            terms,
            date(2026, 3, 31),
            cpi_history={date(2025, 2, 1): Decimal("5.10")},
        )
        expected = Decimal("1.0535") * Decimal("1.0710")
        assert abs(result - expected) < Decimal("0.001")

    def test_edo_negative_cpi_floor_at_margin(self):
        """EDO uses max(cpi, 0) + margin; so negative CPI floors at margin."""
        terms = BondTerms(
            bond_symbol="EDO",
            series_code="EDO1036",
            nominal_value=Decimal("100.00"),
            issue_date=date(2024, 3, 31),
            maturity_date=date(2034, 3, 31),
            capitalization="annual",
            first_period_rate=Decimal("5.35"),
            reference_type="cpi",
            margin=Decimal("2.00"),
            redemption_fee=Decimal("3.00"),
        )

        # Year 2 with negative CPI (-1.00%): floor at 0 + 2.00 = 2.00%
        result = accrue_interest(
            terms,
            date(2026, 3, 31),
            cpi_history={date(2025, 2, 1): Decimal("-1.00")},
        )
        expected = Decimal("1.0535") * Decimal("1.0200")
        assert abs(result - expected) < Decimal("0.001")

    def test_edo_year_3_uses_its_own_cpi_not_year_2s_or_todays(self):
        """Regression for B2: each capitalization year must compound at its
        *own* historical CPI reading, not one value reused for every year.

        Year 2 anniversary (2025-03-31) references 2025-02's CPI (5.10%);
        year 3 anniversary (2026-03-31) references 2026-02's CPI (8.00%) -
        deliberately different, so reusing either value for both years
        would produce a different (wrong) number from this test's
        expectation.
        """
        terms = BondTerms(
            bond_symbol="EDO",
            series_code="EDO1036",
            nominal_value=Decimal("100.00"),
            issue_date=date(2024, 3, 31),
            maturity_date=date(2034, 3, 31),
            capitalization="annual",
            first_period_rate=Decimal("5.35"),
            reference_type="cpi",
            margin=Decimal("2.00"),
            redemption_fee=Decimal("3.00"),
        )
        cpi_history = {
            date(2025, 2, 1): Decimal("5.10"),  # year 2's own reading
            date(2026, 2, 1): Decimal("8.00"),  # year 3's own reading
        }

        result = accrue_interest(terms, date(2027, 3, 31), cpi_history=cpi_history)

        expected = Decimal("1.0535") * Decimal("1.0710") * Decimal("1.1000")
        assert abs(result - expected) < Decimal("0.0001")
        # The old (buggy) behaviour of reusing year 3's 8.00% for year 2 too
        # would give a visibly different number - assert we're not that.
        wrong_reused_today = Decimal("1.0535") * Decimal("1.1000") * Decimal("1.1000")
        assert abs(result - wrong_reused_today) > Decimal("0.001")

    def test_edo_year_with_no_published_cpi_falls_back_to_margin_only(self):
        """A capitalization year whose reading isn't in `cpi_history` (too
        recent, or no history supplied) uses the margin alone for that
        year - not a crash, not another year's value."""
        terms = BondTerms(
            bond_symbol="EDO",
            series_code="EDO1036",
            nominal_value=Decimal("100.00"),
            issue_date=date(2024, 3, 31),
            maturity_date=date(2034, 3, 31),
            capitalization="annual",
            first_period_rate=Decimal("5.35"),
            reference_type="cpi",
            margin=Decimal("2.00"),
            redemption_fee=Decimal("3.00"),
        )

        result = accrue_interest(terms, date(2026, 3, 31), cpi_history={})

        expected = Decimal("1.0535") * Decimal("1.0200")  # margin-only
        assert abs(result - expected) < Decimal("0.001")


class TestAccrueROS:
    """ROS (6 years): year 1 fixed, years 2-6 CPI+2.00pp, annual capitalization."""

    def test_ros_year_1_capitalization(self):
        """ROS year 1 capitalizes with fixed rate."""
        terms = BondTerms(
            bond_symbol="ROS",
            series_code="ROS0001",
            nominal_value=Decimal("100.00"),
            issue_date=date(2024, 1, 1),
            maturity_date=date(2030, 1, 1),
            capitalization="annual",
            first_period_rate=Decimal("4.50"),
            reference_type="cpi",
            margin=Decimal("2.00"),
            redemption_fee=Decimal("2.00"),
        )

        result = accrue_interest(terms, date(2025, 1, 1))
        assert abs(result - Decimal("1.0450")) < Decimal("0.001")


class TestAccrueROD:
    """ROD (12 years): year 1 fixed, years 2-12 CPI+2.50pp, annual capitalization."""

    def test_rod_year_1_capitalization(self):
        """ROD year 1 capitalizes with fixed rate."""
        terms = BondTerms(
            bond_symbol="ROD",
            series_code="ROD0001",
            nominal_value=Decimal("100.00"),
            issue_date=date(2024, 1, 1),
            maturity_date=date(2036, 1, 1),
            capitalization="annual",
            first_period_rate=Decimal("5.00"),
            reference_type="cpi",
            margin=Decimal("2.50"),
            redemption_fee=Decimal("3.00"),
        )

        result = accrue_interest(terms, date(2025, 1, 1))
        assert abs(result - Decimal("1.0500")) < Decimal("0.001")


class TestAccrueErrorCases:
    """Error handling: invalid bond terms."""

    def test_accrue_before_issue_date_raises(self):
        """Cannot accrue interest before bond is issued."""
        terms = BondTerms(
            bond_symbol="TOS",
            series_code="TOS0001",
            nominal_value=Decimal("100.00"),
            issue_date=date(2025, 1, 1),
            maturity_date=date(2028, 1, 1),
            capitalization="annual",
            first_period_rate=Decimal("4.00"),
            reference_type="fixed",
            margin=None,
            redemption_fee=Decimal("1.00"),
        )

        with pytest.raises(ValueError, match="before issue date"):
            accrue_interest(terms, date(2024, 1, 1))

    def test_maturity_before_issue_raises(self):
        """Maturity date must be after issue date."""
        terms = BondTerms(
            bond_symbol="TOS",
            series_code="TOS0001",
            nominal_value=Decimal("100.00"),
            issue_date=date(2025, 1, 1),
            maturity_date=date(2025, 1, 1),  # Same day, invalid
            capitalization="annual",
            first_period_rate=Decimal("4.00"),
            reference_type="fixed",
            margin=None,
            redemption_fee=Decimal("1.00"),
        )

        with pytest.raises(ValueError, match="maturity_date must be after issue_date"):
            accrue_interest(terms, date(2025, 1, 1))

    def test_accrue_after_maturity_uses_maturity(self):
        """Accrual after maturity is calculated as-of maturity (no further growth)."""
        terms = BondTerms(
            bond_symbol="TOS",
            series_code="TOS0001",
            nominal_value=Decimal("100.00"),
            issue_date=date(2024, 1, 1),
            maturity_date=date(2027, 1, 1),
            capitalization="annual",
            first_period_rate=Decimal("4.00"),
            reference_type="fixed",
            margin=None,
            redemption_fee=Decimal("1.00"),
        )

        # Accrue on maturity date
        result_on_maturity = accrue_interest(terms, date(2027, 1, 1))

        # Accrue after maturity (should be same)
        result_after_maturity = accrue_interest(terms, date(2027, 6, 1))

        assert result_on_maturity == result_after_maturity

    def test_unknown_bond_type_raises(self):
        """Unknown bond symbol raises ValueError."""
        terms = BondTerms(
            bond_symbol="UNKNOWN",
            series_code="UNK0001",
            nominal_value=Decimal("100.00"),
            issue_date=date(2024, 1, 1),
            maturity_date=date(2027, 1, 1),
            capitalization="annual",
            first_period_rate=Decimal("4.00"),
            reference_type="fixed",
            margin=None,
            redemption_fee=Decimal("1.00"),
        )

        with pytest.raises(ValueError, match="Unknown bond type"):
            accrue_interest(terms, date(2024, 1, 1))
