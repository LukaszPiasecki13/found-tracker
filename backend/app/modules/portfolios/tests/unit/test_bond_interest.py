"""Tests for BOND_INTEREST operation in PortfolioLedger (domain layer).

Mirrors dividend tests but for bond coupon/interest payments.
"""

from decimal import Decimal

import pytest

from app.modules.portfolios.domain import (
    AssetRequiredError,
    InvalidOperationError,
    LedgerState,
    OperationInput,
    OperationType,
    PortfolioLedger,
    PositionNotFoundError,
    PositionState,
)

D = Decimal
BOND_ASSET = 42


@pytest.fixture
def ledger() -> PortfolioLedger:
    return PortfolioLedger()


def cash(amount: str) -> LedgerState:
    return LedgerState(cash_balance=D(amount))


def position(
    asset_id: int = BOND_ASSET, quantity: str = "10", avg_price: str = "100"
) -> PositionState:
    return PositionState(
        asset_id=asset_id,
        quantity=D(quantity),
        average_buy_price=D(avg_price),
        average_fx_rate=D("1.0"),
    )


def bond_interest(
    amount: str, fee: str = "0", fx_rate: str = "1", asset: int = BOND_ASSET
) -> OperationInput:
    """Helper to create a BOND_INTEREST operation."""
    return OperationInput(
        OperationType.BOND_INTEREST,
        asset_id=asset,
        amount=D(amount),
        fee=D(fee),
        fx_rate=D(fx_rate),
    )


class TestBondInterestValidation:
    """Validation rules for BOND_INTEREST operations."""

    def test_bond_interest_requires_asset_id(self, ledger: PortfolioLedger) -> None:
        """BOND_INTEREST requires an asset_id (bond position must exist)."""
        operation = OperationInput(
            OperationType.BOND_INTEREST,
            asset_id=None,  # Missing
            amount=D("10.50"),
            fee=D("0"),
            fx_rate=D("1.0"),
        )

        with pytest.raises(AssetRequiredError):
            ledger.validate(operation)

    def test_bond_interest_requires_positive_amount(
        self, ledger: PortfolioLedger
    ) -> None:
        """BOND_INTEREST requires amount > 0."""
        operation = OperationInput(
            OperationType.BOND_INTEREST,
            asset_id=BOND_ASSET,
            amount=D("0"),  # Invalid
            fee=D("0"),
            fx_rate=D("1.0"),
        )

        with pytest.raises(InvalidOperationError):
            ledger.validate(operation)

    def test_bond_interest_requires_non_negative_fee(
        self, ledger: PortfolioLedger
    ) -> None:
        """BOND_INTEREST requires fee >= 0."""
        operation = OperationInput(
            OperationType.BOND_INTEREST,
            asset_id=BOND_ASSET,
            amount=D("10.50"),
            fee=D("-1.0"),  # Invalid
            fx_rate=D("1.0"),
        )

        with pytest.raises(InvalidOperationError):
            ledger.validate(operation)

    def test_bond_interest_requires_positive_fx_rate(
        self, ledger: PortfolioLedger
    ) -> None:
        """BOND_INTEREST requires fx_rate > 0."""
        operation = OperationInput(
            OperationType.BOND_INTEREST,
            asset_id=BOND_ASSET,
            amount=D("10.50"),
            fee=D("0"),
            fx_rate=D("0"),  # Invalid
        )

        with pytest.raises(InvalidOperationError):
            ledger.validate(operation)


class TestBondInterestApplication:
    """BOND_INTEREST effect on portfolio state."""

    def test_bond_interest_increases_cash(self, ledger: PortfolioLedger) -> None:
        """Bond coupon payment increases cash balance."""
        state = LedgerState(
            cash_balance=D("1000"),
            positions=(position(BOND_ASSET, quantity="10"),),
        )

        result = ledger.apply(state, bond_interest("10.50"))

        assert result.cash_balance == D("1010.50")

    def test_bond_interest_with_fee(self, ledger: PortfolioLedger) -> None:
        """Bond coupon minus fee (e.g., tax withholding) increases cash."""
        state = LedgerState(
            cash_balance=D("1000"),
            positions=(position(BOND_ASSET, quantity="10"),),
        )

        # Coupon 10.50, tax 1.90 (19% Belka)
        result = ledger.apply(state, bond_interest("10.50", fee="1.90"))

        assert result.cash_balance == D("1008.60")  # 1000 + 10.50 - 1.90

    def test_bond_interest_with_foreign_currency(self, ledger: PortfolioLedger) -> None:
        """Bond coupon in foreign currency is converted using fx_rate."""
        state = LedgerState(
            cash_balance=D("1000"),
            positions=(position(BOND_ASSET, quantity="10"),),
        )

        # 10 EUR at rate 4.35 PLN/EUR = 43.50 PLN
        result = ledger.apply(state, bond_interest("10.00", fee="0", fx_rate="4.35"))

        assert result.cash_balance == D("1043.50")

    def test_bond_interest_increases_total_dividends(
        self, ledger: PortfolioLedger
    ) -> None:
        """Bond interest increases the position's total_dividends (reused)."""
        pos = position(BOND_ASSET, quantity="10")
        state = LedgerState(cash_balance=D("1000"), positions=(pos,))

        result = ledger.apply(state, bond_interest("10.50"))

        assert len(result.positions) == 1
        assert result.positions[0].total_dividends == D("10.50")

    def test_bond_interest_does_not_change_position_quantity(
        self, ledger: PortfolioLedger
    ) -> None:
        """Bond interest does not affect position quantity (same size)."""
        pos = position(BOND_ASSET, quantity="10")
        state = LedgerState(cash_balance=D("1000"), positions=(pos,))

        result = ledger.apply(state, bond_interest("10.50"))

        assert result.positions[0].quantity == D("10")

    def test_bond_interest_on_nonexistent_position_raises(
        self, ledger: PortfolioLedger
    ) -> None:
        """Cannot pay coupon on a position you don't hold."""
        state = LedgerState(cash_balance=D("1000"), positions=())

        with pytest.raises(PositionNotFoundError):
            ledger.apply(state, bond_interest("10.50", asset=BOND_ASSET))

    def test_bond_interest_multiple_coupons_accumulate(
        self, ledger: PortfolioLedger
    ) -> None:
        """Multiple coupon payments accumulate in total_dividends."""
        pos = position(BOND_ASSET, quantity="10", avg_price="100")
        state = LedgerState(cash_balance=D("1000"), positions=(pos,))

        # First coupon
        state = ledger.apply(state, bond_interest("10.50", fee="0"))
        assert state.positions[0].total_dividends == D("10.50")
        assert state.cash_balance == D("1010.50")

        # Second coupon
        state = ledger.apply(state, bond_interest("10.50", fee="0"))
        assert state.positions[0].total_dividends == D("21.00")
        assert state.cash_balance == D("1021.00")


class TestBondInterestParity:
    """BOND_INTEREST mirrors DIVIDEND semantics."""

    def test_bond_interest_like_dividend_but_for_bonds(
        self, ledger: PortfolioLedger
    ) -> None:
        """BOND_INTEREST behaves like DIVIDEND, for a different asset type."""
        dividend_op = OperationInput(
            OperationType.DIVIDEND,
            asset_id=BOND_ASSET,
            amount=D("10.50"),
            fee=D("0.50"),
            fx_rate=D("1.0"),
        )

        bond_interest_op = OperationInput(
            OperationType.BOND_INTEREST,
            asset_id=BOND_ASSET,
            amount=D("10.50"),
            fee=D("0.50"),
            fx_rate=D("1.0"),
        )

        pos = position(BOND_ASSET, quantity="10")
        state = LedgerState(cash_balance=D("1000"), positions=(pos,))

        # Both should update cash and total_dividends identically
        dividend_result = ledger.apply(state, dividend_op)
        bond_result = ledger.apply(state, bond_interest_op)

        assert dividend_result.cash_balance == bond_result.cash_balance
        dividend_total = dividend_result.positions[0].total_dividends
        bond_total = bond_result.positions[0].total_dividends
        assert dividend_total == bond_total
