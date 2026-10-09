"""The portfolio ledger: how operations change cash and positions.

Level 2 of the domain (DOM-9): a component (DOM-10). `PortfolioLedger` is the
single place where an operation is validated and applied - `OperationService`
uses it both for recording one new operation (`apply` on the current state) and
for rebuilding a portfolio from its whole history after an edit or a delete
(`rebuild`). Values are immutable; nothing here rounds (ADR-0010: the `Numeric`
columns round on write, at the persistence boundary).
"""

from collections.abc import Iterable
from dataclasses import dataclass, replace
from decimal import Decimal

from app.modules.portfolios.domain.enums import (
    ASSET_OPERATIONS,
    CASH_OPERATIONS,
    INCOME_COST_OPERATIONS,
    OperationType,
)
from app.modules.portfolios.domain.errors import (
    AssetNotAllowedError,
    AssetRequiredError,
    InsufficientCashError,
    InsufficientQuantityError,
    InvalidOperationError,
    PositionNotFoundError,
)
from app.modules.portfolios.domain.protocols import (
    OperationLike,
    PortfolioBalanceLike,
    PositionLike,
)

_ZERO = Decimal("0")
_ONE = Decimal("1")

# Brokers settle fractional-share trades to the cent, so a real account may sit a few
# cents below zero after a purchase (ADR-0021). Only a buy may overdraw, by this much.
BUY_OVERDRAFT_TOLERANCE = Decimal("0.50")


def _operation_type(value: str) -> OperationType:
    try:
        return OperationType(value)
    except ValueError as err:
        raise InvalidOperationError(
            f"Unsupported operation type: {value}", field="operation_type"
        ) from err


@dataclass(frozen=True, slots=True)
class OperationInput:
    """One operation as the ledger applies it. `amount` matters only for cash
    operations and dividends; `quantity`/`price` only for buy and sell; `ratio`
    only for a split."""

    operation_type: OperationType
    asset_id: int | None = None
    quantity: Decimal = _ZERO
    price: Decimal = _ZERO
    amount: Decimal | None = None
    fee: Decimal = _ZERO
    fx_rate: Decimal = _ONE
    ratio: Decimal | None = None

    @classmethod
    def from_operation(cls, operation: OperationLike) -> OperationInput:
        """From a recorded operation; an unknown type is an
        `InvalidOperationError`."""
        return cls(
            operation_type=_operation_type(operation.operation_type),
            asset_id=operation.asset_id,
            quantity=operation.quantity,
            price=operation.price,
            amount=operation.amount,
            fee=operation.fee,
            fx_rate=operation.fx_rate,
            ratio=operation.ratio,
        )


@dataclass(frozen=True, slots=True)
class PositionState:
    """A position: quantity held, weighted average buy price (fees included,
    in the asset's currency), weighted average FX rate, accumulated fees and
    dividends."""

    asset_id: int
    quantity: Decimal
    average_buy_price: Decimal
    average_fx_rate: Decimal
    total_fees: Decimal = _ZERO
    total_dividends: Decimal = _ZERO

    @classmethod
    def from_position(cls, position: PositionLike) -> PositionState:
        return cls(
            asset_id=position.asset_id,
            quantity=position.quantity,
            average_buy_price=position.average_buy_price,
            average_fx_rate=position.average_fx_rate,
            total_fees=position.total_fees,
            total_dividends=position.total_dividends,
        )


@dataclass(frozen=True, slots=True)
class LedgerState:
    """Cash, net deposits and open positions of one portfolio (in the order
    the positions were opened)."""

    cash_balance: Decimal = _ZERO
    total_deposited: Decimal = _ZERO
    positions: tuple[PositionState, ...] = ()

    @classmethod
    def of(
        cls, portfolio: PortfolioBalanceLike, positions: Iterable[PositionLike]
    ) -> LedgerState:
        """The current state of a stored portfolio and its positions."""
        return cls(
            cash_balance=portfolio.cash_balance,
            total_deposited=portfolio.total_deposited,
            positions=tuple(PositionState.from_position(p) for p in positions),
        )

    def position(self, asset_id: int) -> PositionState | None:
        for position in self.positions:
            if position.asset_id == asset_id:
                return position
        return None

    def with_position(self, updated: PositionState) -> tuple[PositionState, ...]:
        """Positions with `updated` replacing the one for its asset, or
        appended when the asset has none yet."""
        if self.position(updated.asset_id) is None:
            return (*self.positions, updated)
        return tuple(
            updated if p.asset_id == updated.asset_id else p for p in self.positions
        )

    def without_position(self, asset_id: int) -> tuple[PositionState, ...]:
        return tuple(p for p in self.positions if p.asset_id != asset_id)


# --- Validation rules ---


def _require_positive(field: str, value: Decimal | None) -> None:
    if value is None or not value.is_finite() or value <= _ZERO:
        raise InvalidOperationError(f"{field} must be > 0", field=field)


def _require_non_negative(field: str, value: Decimal) -> None:
    if not value.is_finite() or value < _ZERO:
        raise InvalidOperationError(f"{field} must be >= 0", field=field)


def _asset_id(operation: OperationInput) -> int:
    if operation.asset_id is None:
        raise AssetRequiredError(operation.operation_type)
    return operation.asset_id


def _amount(operation: OperationInput) -> Decimal:
    if operation.amount is None:
        raise InvalidOperationError("amount must be > 0", field="amount")
    return operation.amount


def _ratio(operation: OperationInput) -> Decimal:
    if operation.ratio is None:
        raise InvalidOperationError("ratio must be > 0", field="ratio")
    return operation.ratio


# --- Effects (called only after validation) ---


def _buy(state: LedgerState, operation: OperationInput) -> LedgerState:
    asset_id = _asset_id(operation)
    quantity, price, fee = operation.quantity, operation.price, operation.fee
    fx_rate = operation.fx_rate
    total_cost = (quantity * price + fee) * fx_rate
    if state.cash_balance + BUY_OVERDRAFT_TOLERANCE < total_cost:
        raise InsufficientCashError(state.cash_balance, total_cost)

    held = state.position(asset_id)
    if held is None:
        position = PositionState(
            asset_id=asset_id,
            quantity=quantity,
            average_buy_price=(quantity * price + fee) / quantity,
            average_fx_rate=fx_rate,
            total_fees=fee,
        )
    else:
        new_quantity = held.quantity + quantity
        position = replace(
            held,
            quantity=new_quantity,
            average_buy_price=(
                held.quantity * held.average_buy_price + quantity * price + fee
            )
            / new_quantity,
            average_fx_rate=(held.quantity * held.average_fx_rate + quantity * fx_rate)
            / new_quantity,
            total_fees=held.total_fees + fee,
        )
    return replace(
        state,
        cash_balance=state.cash_balance - total_cost,
        positions=state.with_position(position),
    )


def _sell(state: LedgerState, operation: OperationInput) -> LedgerState:
    asset_id = _asset_id(operation)
    quantity = operation.quantity
    held = state.position(asset_id)
    if held is None:
        raise PositionNotFoundError(operation.operation_type, asset_id)
    if held.quantity < quantity:
        raise InsufficientQuantityError(held.quantity, quantity)

    proceeds = (quantity * operation.price - operation.fee) * operation.fx_rate
    remaining = held.quantity - quantity
    if remaining == _ZERO:
        positions = state.without_position(asset_id)
    else:
        positions = state.with_position(
            replace(
                held, quantity=remaining, total_fees=held.total_fees + operation.fee
            )
        )
    return replace(
        state, cash_balance=state.cash_balance + proceeds, positions=positions
    )


def _deposit(state: LedgerState, operation: OperationInput) -> LedgerState:
    amount = _amount(operation)
    return replace(
        state,
        cash_balance=state.cash_balance + (amount - operation.fee),
        total_deposited=state.total_deposited + amount,
    )


def _withdraw(state: LedgerState, operation: OperationInput) -> LedgerState:
    amount = _amount(operation)
    total_withdrawal = amount + operation.fee
    if state.cash_balance < total_withdrawal:
        raise InsufficientCashError(state.cash_balance, total_withdrawal)
    return replace(
        state,
        cash_balance=state.cash_balance - total_withdrawal,
        total_deposited=state.total_deposited - amount,
    )


def _interest(state: LedgerState, operation: OperationInput) -> LedgerState:
    """Interest on free funds: cash grows, deposits stay (it is profit)."""
    amount = _amount(operation)
    return replace(state, cash_balance=state.cash_balance + (amount - operation.fee))


def _charge(state: LedgerState, operation: OperationInput) -> LedgerState:
    """A charge (e.g. tax on interest): cash shrinks, deposits stay."""
    amount = _amount(operation)
    total = amount + operation.fee
    if state.cash_balance < total:
        raise InsufficientCashError(state.cash_balance, total)
    return replace(state, cash_balance=state.cash_balance - total)


def _dividend(state: LedgerState, operation: OperationInput) -> LedgerState:
    asset_id = _asset_id(operation)
    amount = _amount(operation)
    held = state.position(asset_id)
    if held is None:
        raise PositionNotFoundError(operation.operation_type, asset_id)
    position = replace(held, total_dividends=held.total_dividends + amount)
    return replace(
        state,
        cash_balance=state.cash_balance + (amount - operation.fee) * operation.fx_rate,
        positions=state.with_position(position),
    )


def _bond_interest(state: LedgerState, operation: OperationInput) -> LedgerState:
    """Bond coupon/interest: increases cash and reuses total_dividends field."""
    asset_id = _asset_id(operation)
    amount = _amount(operation)
    held = state.position(asset_id)
    if held is None:
        raise PositionNotFoundError(operation.operation_type, asset_id)
    position = replace(held, total_dividends=held.total_dividends + amount)
    return replace(
        state,
        cash_balance=state.cash_balance + (amount - operation.fee) * operation.fx_rate,
        positions=state.with_position(position),
    )


def _split(state: LedgerState, operation: OperationInput) -> LedgerState:
    """A split: the held quantity grows `ratio` times and the unit price shrinks
    as much, so the position's total cost stays and no cash moves."""
    asset_id = _asset_id(operation)
    ratio = _ratio(operation)
    held = state.position(asset_id)
    if held is None:
        raise PositionNotFoundError(operation.operation_type, asset_id)
    position = replace(
        held,
        quantity=held.quantity * ratio,
        average_buy_price=held.average_buy_price / ratio,
    )
    return replace(state, positions=state.with_position(position))


class PortfolioLedger:
    """Validates operations and folds them into a portfolio's `LedgerState`.

    The single domain surface `OperationService` talks to (DOM-10), built in
    `wiring.py`. Rules: buy/sell need an asset, quantity > 0, price > 0,
    fee >= 0, fx_rate > 0; deposit/withdrawal need amount > 0, fee >= 0 and no
    asset; interest/fee need amount > 0, fee >= 0 and no asset (cash moves,
    deposits do not); dividend needs an asset, amount > 0, fee >= 0, fx_rate > 0;
    split needs an asset and ratio > 0 (cash does not move).
    """

    def validate(self, operation: OperationInput) -> None:
        """Raises a `PortfolioDomainError` subclass for an invalid operation."""
        operation_type = operation.operation_type
        if operation_type in ASSET_OPERATIONS and operation.asset_id is None:
            raise AssetRequiredError(operation_type)
        if (
            operation_type in CASH_OPERATIONS | INCOME_COST_OPERATIONS
            and operation.asset_id is not None
        ):
            raise AssetNotAllowedError(operation_type)

        match operation_type:
            case OperationType.BUY | OperationType.SELL:
                _require_positive("quantity", operation.quantity)
                _require_positive("price", operation.price)
                _require_non_negative("fee", operation.fee)
                _require_positive("fx_rate", operation.fx_rate)
            case (
                OperationType.DEPOSIT
                | OperationType.WITHDRAWAL
                | OperationType.INTEREST
                | OperationType.FEE
            ):
                _require_positive("amount", operation.amount)
                _require_non_negative("fee", operation.fee)
            case OperationType.DIVIDEND | OperationType.BOND_INTEREST:
                _require_positive("amount", operation.amount)
                _require_non_negative("fee", operation.fee)
                _require_positive("fx_rate", operation.fx_rate)
            case OperationType.SPLIT:
                _require_positive("ratio", operation.ratio)

    def apply(self, state: LedgerState, operation: OperationInput) -> LedgerState:
        """`state` after `operation`; validates first. Raises a
        `PortfolioDomainError` subclass (invalid operation, insufficient cash
        or quantity, no position to sell or pay a dividend on)."""
        self.validate(operation)
        match operation.operation_type:
            case OperationType.BUY:
                return _buy(state, operation)
            case OperationType.SELL:
                return _sell(state, operation)
            case OperationType.DEPOSIT:
                return _deposit(state, operation)
            case OperationType.WITHDRAWAL:
                return _withdraw(state, operation)
            case OperationType.DIVIDEND:
                return _dividend(state, operation)
            case OperationType.BOND_INTEREST:
                return _bond_interest(state, operation)
            case OperationType.INTEREST:
                return _interest(state, operation)
            case OperationType.FEE:
                return _charge(state, operation)
            case OperationType.SPLIT:
                return _split(state, operation)

    def rebuild(self, operations: Iterable[OperationInput]) -> LedgerState:
        """Fold a whole history, already in chronological order
        (`operation_date`, `created_at`, `id`), from an empty portfolio."""
        state = LedgerState()
        for operation in operations:
            state = self.apply(state, operation)
        return state
