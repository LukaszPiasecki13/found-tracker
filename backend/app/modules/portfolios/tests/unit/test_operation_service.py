"""`OperationService` with mocked repositories sharing one mocked session and
the real `PortfolioLedger`: one transaction per write, the ledger's verdict as
400 + code, nothing committed on failure."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.modules.assets.exceptions import AssetArchivedError
from app.modules.portfolios.domain import OperationType, PortfolioLedger
from app.modules.portfolios.exceptions import (
    AssetClassRequiredError,
    ConcurrentChangeError,
    ImportBatchHasEditsError,
    ImportCommitRejectedError,
    OperationNotFoundError,
    OperationRejectedError,
    PortfolioNotFoundError,
    UnknownAssetError,
)
from app.modules.portfolios.schemas.operations import (
    OperationCreateRequest,
    OperationUpdateRequest,
)
from app.modules.portfolios.services.operations import (
    OperationDraft,
    OperationService,
)

D = Decimal
WHEN = datetime(2026, 1, 2, tzinfo=UTC)
ASSET_ID = 5


def _portfolio(cash: str = "1000", deposited: str = "1000") -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        owner_id=7,
        base_currency_id=3,
        cash_balance=D(cash),
        total_deposited=D(deposited),
    )


def _row(asset_id: int = ASSET_ID, quantity: str = "10", **values: Any) -> Any:
    fields: dict[str, Any] = {
        "id": 100 + asset_id,
        "asset_id": asset_id,
        "quantity": D(quantity),
        "average_buy_price": D("20"),
        "average_fx_rate": D("1"),
        "total_fees": D("0"),
        "total_dividends": D("0"),
        "opened_at": datetime(2020, 1, 1, tzinfo=UTC),
    }
    fields.update(values)
    return SimpleNamespace(**fields)


def _stored(operation_type: str, **values: Any) -> SimpleNamespace:
    fields: dict[str, Any] = {
        "id": 1,
        "portfolio_id": 1,
        "operation_type": operation_type,
        "asset_id": None,
        "quantity": D("0"),
        "price": D("0"),
        "amount": None,
        "fee": D("0"),
        "fx_rate": D("1"),
        "ratio": None,
        "notes": None,
        "operation_date": WHEN,
    }
    fields.update(values)
    return SimpleNamespace(**fields)


def _request(**values: Any) -> OperationCreateRequest:
    payload: dict[str, Any] = {
        "portfolio_id": 1,
        "operation_type": "deposit",
        "amount": 100,
        "operation_date": "2026-01-02",
    }
    payload.update(values)
    return OperationCreateRequest.model_validate(payload)


@pytest.fixture
def assets() -> MagicMock:
    return MagicMock()


@pytest.fixture
def history() -> list[SimpleNamespace]:
    """The stored operations of portfolio 1; a recorded operation joins it."""
    return [_stored("deposit", id=1, amount=D("1000"))]


@pytest.fixture
def service(
    portfolio_repo: MagicMock,
    position_repo: MagicMock,
    operation_repo: MagicMock,
    assets: MagicMock,
    history: list[SimpleNamespace],
) -> OperationService:
    def create(**values: Any) -> SimpleNamespace:
        operation = _stored(values.pop("operation_type"), id=len(history) + 1, **values)
        history.append(operation)
        # From now on the replay reads the history, in the repository's order.
        operation_repo.list_by_portfolio.side_effect = lambda _: sorted(
            history, key=lambda op: (op.operation_date.replace(tzinfo=None), op.id)
        )
        return operation

    def create_many(operations: Any) -> list[Any]:
        # Convert Operation models to SimpleNamespace with assigned IDs for testing.
        result = []
        for operation in operations:
            # Assign ID if not already set.
            if not hasattr(operation, "id") or operation.id is None:
                op_ns = SimpleNamespace(
                    id=len(history) + 1,
                    portfolio_id=operation.portfolio_id,
                    asset_id=operation.asset_id,
                    operation_type=operation.operation_type,
                    quantity=operation.quantity,
                    price=operation.price,
                    amount=operation.amount,
                    fee=operation.fee,
                    fx_rate=operation.fx_rate,
                    ratio=operation.ratio,
                    notes=operation.notes,
                    operation_date=operation.operation_date,
                    external_ref=operation.external_ref,
                    import_batch_id=operation.import_batch_id,
                )
            else:
                # Already has ID (shouldn't happen in normal flow).
                op_ns = operation
            history.append(op_ns)
            result.append(op_ns)
        # Update list_by_portfolio to return sorted history.
        operation_repo.list_by_portfolio.side_effect = lambda _: sorted(
            history, key=lambda op: (op.operation_date.replace(tzinfo=None), op.id)
        )
        return result

    portfolio_repo.update.side_effect = lambda entity: entity
    position_repo.update.side_effect = lambda entity: entity
    operation_repo.update.side_effect = lambda entity: entity
    operation_repo.create.side_effect = create
    operation_repo.create_many.side_effect = create_many

    return OperationService(
        portfolio_repo, position_repo, operation_repo, assets, PortfolioLedger()
    )


# --- record ---


def test_record_deposit_rebuilds_cash_and_stores_the_operation(
    service: OperationService,
    portfolio_repo: MagicMock,
    position_repo: MagicMock,
    operation_repo: MagicMock,
    history: list[SimpleNamespace],
    session: MagicMock,
) -> None:
    history.clear()
    portfolio = _portfolio(cash="10", deposited="10")
    portfolio_repo.get_owned.return_value = portfolio
    position_repo.list_by_portfolio.return_value = []

    result = service.record(_request(amount="100.5", fee="0.5", notes="n"), 7)

    assert result is history[-1]
    portfolio_repo.lock_owned.assert_called_once_with(1, 7)
    portfolio_repo.get_owned.assert_called_with(1, 7)
    assert (portfolio.cash_balance, portfolio.total_deposited) == (D("100"), D("100.5"))
    operation_repo.create.assert_called_once_with(
        portfolio_id=1,
        asset_id=None,
        operation_type="deposit",
        quantity=D("0"),
        price=D("0"),
        amount=D("100.5"),
        fee=D("0.5"),
        fx_rate=D("1"),
        ratio=None,
        notes="n",
        operation_date=datetime(2026, 1, 2),
    )
    session.commit.assert_called_once()
    session.rollback.assert_not_called()


def test_back_dated_sell_without_a_position_then_is_rejected(
    service: OperationService,
    portfolio_repo: MagicMock,
    position_repo: MagicMock,
    assets: MagicMock,
    history: list[SimpleNamespace],
    session: MagicMock,
) -> None:
    # The buy is later than the new sell: replayed in date order the sell has
    # nothing to sell, though the current state holds the position.
    history.append(
        _stored(
            "buy",
            id=2,
            asset_id=ASSET_ID,
            quantity=D("10"),
            price=D("20"),
            operation_date=datetime(2026, 3, 1, tzinfo=UTC),
        )
    )
    portfolio_repo.get_owned.return_value = _portfolio()
    position_repo.list_by_portfolio.return_value = [_row(quantity="10")]
    assets.find_by_id.return_value = SimpleNamespace(id=ASSET_ID, archived_at=None)

    with pytest.raises(OperationRejectedError) as exc_info:
        service.record(
            _request(operation_type="sell", asset_id=ASSET_ID, quantity=1, price=1),
            7,
        )

    assert exc_info.value.code == "POSITION_NOT_FOUND"
    session.commit.assert_not_called()


def test_record_translates_a_unique_race_into_a_409_and_rolls_back(
    service: OperationService,
    portfolio_repo: MagicMock,
    position_repo: MagicMock,
    assets: MagicMock,
    session: MagicMock,
) -> None:
    portfolio_repo.get_owned.return_value = _portfolio()
    position_repo.list_by_portfolio.return_value = []
    assets.find_by_ticker.return_value = None
    assets.get_or_create_by_ticker.side_effect = IntegrityError(
        "insert", {}, Exception()
    )

    with pytest.raises(ConcurrentChangeError) as exc_info:
        service.record(
            _request(
                operation_type="buy",
                ticker="NEW",
                asset_class="Stock",
                quantity=1,
                price=1,
                amount=None,
            ),
            7,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "CONCURRENT_CHANGE"
    session.commit.assert_not_called()
    session.rollback.assert_called_once()


def test_record_buy_of_held_asset_updates_the_row_in_place(
    service: OperationService,
    portfolio_repo: MagicMock,
    position_repo: MagicMock,
    assets: MagicMock,
    history: list[SimpleNamespace],
) -> None:
    portfolio_repo.get_owned.return_value = _portfolio()
    row = _row(quantity="10")
    position_repo.list_by_portfolio.return_value = [row]
    assets.find_by_id.return_value = SimpleNamespace(id=ASSET_ID, archived_at=None)
    history.append(
        _stored("buy", id=2, asset_id=ASSET_ID, quantity=D("10"), price=D("20"))
    )

    service.record(
        _request(operation_type="buy", asset_id=ASSET_ID, quantity=10, price=30, fee=2),
        7,
    )

    assert row.quantity == D("20")
    assert row.average_buy_price == D("25.1")  # (10 * 20 + 10 * 30 + 2) / 20
    assert row.total_fees == D("2")
    assert row.opened_at == datetime(2020, 1, 1, tzinfo=UTC)
    position_repo.update.assert_called_once_with(row)
    position_repo.create.assert_not_called()
    position_repo.delete.assert_not_called()


def test_record_sell_of_everything_deletes_the_row(
    service: OperationService,
    portfolio_repo: MagicMock,
    position_repo: MagicMock,
    assets: MagicMock,
    history: list[SimpleNamespace],
) -> None:
    portfolio = _portfolio(cash="0")
    portfolio_repo.get_owned.return_value = portfolio
    row = _row(quantity="10")
    position_repo.list_by_portfolio.return_value = [row]
    assets.find_by_id.return_value = SimpleNamespace(id=ASSET_ID, archived_at=None)
    history.append(
        _stored("buy", id=2, asset_id=ASSET_ID, quantity=D("10"), price=D("100"))
    )

    service.record(
        _request(operation_type="sell", asset_id=ASSET_ID, quantity=10, price=25),
        7,
    )

    position_repo.delete.assert_called_once_with(row)
    assert portfolio.cash_balance == D("250")  # 1000 - 1000 + 250


def test_record_buy_of_new_ticker_creates_asset_inside_the_same_transaction(
    service: OperationService,
    portfolio_repo: MagicMock,
    position_repo: MagicMock,
    assets: MagicMock,
    session: MagicMock,
) -> None:
    portfolio_repo.get_owned.return_value = _portfolio()
    position_repo.list_by_portfolio.return_value = []
    assets.find_by_ticker.return_value = None

    def get_or_create(ticker: str, **_: Any) -> SimpleNamespace:
        # No-commit core (ADR-0008): called while the transaction is open.
        assert session.commit.call_count == 0
        return SimpleNamespace(id=42, archived_at=None)

    assets.get_or_create_by_ticker.side_effect = get_or_create

    service.record(
        _request(
            operation_type="buy",
            ticker="cdr",
            asset_class="Stock",
            quantity=2,
            price=100,
            fee=1,
        ),
        7,
    )

    assets.get_or_create_by_ticker.assert_called_once_with(
        "cdr", asset_class_name="Stock", fallback_currency_id=3
    )
    position_repo.create.assert_called_once_with(
        portfolio_id=1,
        asset_id=42,
        quantity=D("2"),
        average_buy_price=D("100.5"),
        average_fx_rate=D("1"),
        total_fees=D("1"),
        total_dividends=D("0"),
    )
    session.commit.assert_called_once()


def test_rejected_operation_rolls_back_the_new_asset_and_commits_nothing(
    service: OperationService,
    portfolio_repo: MagicMock,
    position_repo: MagicMock,
    assets: MagicMock,
    history: list[SimpleNamespace],
    session: MagicMock,
) -> None:
    history[:] = [_stored("deposit", id=1, amount=D("10"))]
    portfolio = _portfolio(cash="10")
    portfolio_repo.get_owned.return_value = portfolio
    position_repo.list_by_portfolio.return_value = []
    assets.find_by_ticker.return_value = None
    assets.get_or_create_by_ticker.return_value = SimpleNamespace(
        id=42, archived_at=None
    )

    with pytest.raises(OperationRejectedError) as exc_info:
        service.record(
            _request(
                operation_type="buy",
                ticker="CDR",
                asset_class="Stock",
                quantity=2,
                price=100,
            ),
            7,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "INSUFFICIENT_CASH"
    assert isinstance(exc_info.value.__cause__, ValueError)
    assets.get_or_create_by_ticker.assert_called_once()
    session.rollback.assert_called_once()
    session.commit.assert_not_called()
    portfolio_repo.update.assert_not_called()
    assert portfolio.cash_balance == D("10")


@pytest.mark.parametrize(
    ("values", "code"),
    [
        (
            {"operation_type": "buy", "quantity": 0, "price": 1},
            "OPERATION_REQUIRES_ASSET",
        ),
        ({"amount": 0}, "INVALID_OPERATION"),
        ({"amount": 1, "fee": -1}, "INVALID_OPERATION"),
        (
            {"operation_type": "dividend", "asset_id": ASSET_ID, "amount": 1},
            "POSITION_NOT_FOUND",
        ),
        ({"operation_type": "withdrawal", "amount": 2000}, "INSUFFICIENT_CASH"),
        ({"asset_id": ASSET_ID}, "OPERATION_FORBIDS_ASSET"),
    ],
)
def test_ledger_rules_reach_the_client_as_400_with_the_domain_code(
    service: OperationService,
    portfolio_repo: MagicMock,
    position_repo: MagicMock,
    assets: MagicMock,
    session: MagicMock,
    values: dict[str, Any],
    code: str,
) -> None:
    portfolio_repo.get_owned.return_value = _portfolio()
    position_repo.list_by_portfolio.return_value = []
    assets.find_by_id.return_value = SimpleNamespace(id=ASSET_ID, archived_at=None)

    with pytest.raises(OperationRejectedError) as exc_info:
        service.record(_request(**values), 7)

    assert exc_info.value.code == code
    session.commit.assert_not_called()


def test_unknown_ticker_without_asset_class_is_400_asset_not_found(
    service: OperationService,
    portfolio_repo: MagicMock,
    assets: MagicMock,
    session: MagicMock,
) -> None:
    portfolio_repo.get_owned.return_value = _portfolio()
    assets.find_by_ticker.return_value = None

    with pytest.raises(AssetClassRequiredError) as exc_info:
        service.record(_request(operation_type="buy", ticker="NOPE"), 7)

    assert (exc_info.value.status_code, exc_info.value.code) == (400, "ASSET_NOT_FOUND")
    assets.get_or_create_by_ticker.assert_not_called()
    session.rollback.assert_called_once()


def test_unknown_asset_id_is_400_asset_not_found(
    service: OperationService, portfolio_repo: MagicMock, assets: MagicMock
) -> None:
    portfolio_repo.get_owned.return_value = _portfolio()
    assets.find_by_id.return_value = None

    with pytest.raises(UnknownAssetError) as exc_info:
        service.record(_request(operation_type="buy", asset_id=999), 7)

    assert (exc_info.value.status_code, exc_info.value.code) == (400, "ASSET_NOT_FOUND")


def test_known_ticker_is_reused_without_creating(
    service: OperationService,
    portfolio_repo: MagicMock,
    position_repo: MagicMock,
    assets: MagicMock,
) -> None:
    portfolio_repo.get_owned.return_value = _portfolio()
    position_repo.list_by_portfolio.return_value = []
    assets.find_by_ticker.return_value = SimpleNamespace(id=ASSET_ID, archived_at=None)

    service.record(
        _request(
            operation_type="buy", ticker="AAPL", asset_class="X", quantity=1, price=1
        ),
        7,
    )

    assets.get_or_create_by_ticker.assert_not_called()
    assert position_repo.create.call_args.kwargs["asset_id"] == ASSET_ID


def test_record_in_another_owners_portfolio_is_404(
    service: OperationService,
    portfolio_repo: MagicMock,
    operation_repo: MagicMock,
    session: MagicMock,
) -> None:
    portfolio_repo.get_owned.side_effect = PortfolioNotFoundError

    with pytest.raises(PortfolioNotFoundError):
        service.record(_request(), 8)

    operation_repo.create.assert_not_called()
    session.commit.assert_not_called()


# --- update / delete: rebuild from history ---


def _history() -> list[SimpleNamespace]:
    return [
        _stored("deposit", id=1, amount=D("1000")),
        _stored(
            "buy", id=2, asset_id=ASSET_ID, quantity=D("10"), price=D("20"), fee=D("2")
        ),
    ]


def test_update_changes_fields_and_rebuilds_the_portfolio(
    service: OperationService,
    portfolio_repo: MagicMock,
    position_repo: MagicMock,
    operation_repo: MagicMock,
    session: MagicMock,
) -> None:
    history = _history()
    buy = history[1]
    operation_repo.get_owned.return_value = buy
    operation_repo.list_by_portfolio.return_value = history
    portfolio = _portfolio(cash="798")
    portfolio_repo.get_owned.return_value = portfolio
    row = _row(quantity="10", average_buy_price=D("20.2"), total_fees=D("2"))
    position_repo.list_by_portfolio.return_value = [row]

    result = service.update(
        2, OperationUpdateRequest(price=D("30"), fee=None, notes=None), owner_id=7
    )

    assert result is buy
    assert (buy.price, buy.fee, buy.notes) == (D("30"), D("2"), None)
    operation_repo.get_owned.assert_called_once_with(2, 7)
    portfolio_repo.get_owned.assert_called_once_with(1, 7)
    assert portfolio.cash_balance == D("698")
    assert row.average_buy_price == D("30.2")
    position_repo.update.assert_called_once_with(row)
    session.commit.assert_called_once()


def test_update_breaking_the_history_is_400_and_commits_nothing(
    service: OperationService,
    portfolio_repo: MagicMock,
    operation_repo: MagicMock,
    session: MagicMock,
) -> None:
    history = _history()
    operation_repo.get_owned.return_value = history[1]
    operation_repo.list_by_portfolio.return_value = history
    portfolio = _portfolio(cash="798")
    portfolio_repo.get_owned.return_value = portfolio

    with pytest.raises(OperationRejectedError) as exc_info:
        service.update(2, OperationUpdateRequest(quantity=D("1000")), owner_id=7)

    assert exc_info.value.code == "INSUFFICIENT_CASH"
    session.rollback.assert_called_once()
    session.commit.assert_not_called()
    portfolio_repo.update.assert_not_called()


def test_update_to_a_non_positive_value_is_rejected_by_the_ledger(
    service: OperationService,
    portfolio_repo: MagicMock,
    operation_repo: MagicMock,
) -> None:
    history = _history()
    operation_repo.get_owned.return_value = history[1]
    operation_repo.list_by_portfolio.return_value = history
    portfolio_repo.get_owned.return_value = _portfolio()

    with pytest.raises(OperationRejectedError) as exc_info:
        service.update(2, OperationUpdateRequest(quantity=D("-1")), owner_id=7)

    assert exc_info.value.code == "INVALID_OPERATION"
    assert "quantity" in exc_info.value.message


def test_delete_removes_the_operation_and_rebuilds_without_it(
    service: OperationService,
    portfolio_repo: MagicMock,
    position_repo: MagicMock,
    operation_repo: MagicMock,
    session: MagicMock,
) -> None:
    history = _history()
    buy = history[1]
    operation_repo.get_owned.return_value = buy
    operation_repo.list_by_portfolio.return_value = history[:1]  # after the delete
    portfolio = _portfolio(cash="798")
    portfolio_repo.get_owned.return_value = portfolio
    row = _row()
    position_repo.list_by_portfolio.return_value = [row]

    service.delete(2, owner_id=7)

    operation_repo.delete.assert_called_once_with(buy)
    assert (portfolio.cash_balance, portfolio.total_deposited) == (
        D("1000"),
        D("1000"),
    )
    position_repo.delete.assert_called_once_with(row)
    position_repo.create.assert_not_called()
    session.commit.assert_called_once()


def test_delete_of_a_deposit_later_buys_need_is_400_and_nothing_is_deleted(
    service: OperationService,
    portfolio_repo: MagicMock,
    operation_repo: MagicMock,
    session: MagicMock,
) -> None:
    history = _history()
    operation_repo.get_owned.return_value = history[0]
    operation_repo.list_by_portfolio.return_value = history[1:]
    portfolio_repo.get_owned.return_value = _portfolio()

    with pytest.raises(OperationRejectedError) as exc_info:
        service.delete(1, owner_id=7)

    assert exc_info.value.code == "INSUFFICIENT_CASH"
    session.rollback.assert_called_once()
    session.commit.assert_not_called()


def test_another_owners_operation_is_404(
    service: OperationService, operation_repo: MagicMock, session: MagicMock
) -> None:
    operation_repo.get_owned.side_effect = OperationNotFoundError

    with pytest.raises(OperationNotFoundError) as exc_info:
        service.delete(1, owner_id=8)

    assert (exc_info.value.status_code, exc_info.value.code) == (
        404,
        "OPERATION_NOT_FOUND",
    )
    operation_repo.delete.assert_not_called()
    session.commit.assert_not_called()


def test_rebuild_rejects_an_unknown_stored_type(
    service: OperationService,
    portfolio_repo: MagicMock,
    operation_repo: MagicMock,
) -> None:
    operation_repo.get_owned.return_value = _stored("deposit", amount=D("1"))
    operation_repo.list_by_portfolio.return_value = [_stored("transfer")]
    portfolio_repo.get_owned.return_value = _portfolio()

    with pytest.raises(OperationRejectedError) as exc_info:
        service.update(1, OperationUpdateRequest(notes="x"), owner_id=7)

    assert exc_info.value.code == "INVALID_OPERATION"


def test_list_operations_is_owner_scoped(
    service: OperationService, operation_repo: MagicMock
) -> None:
    operation_repo.list_by_owner.return_value = []

    assert service.list_operations(7, "Main") == []
    operation_repo.list_by_owner.assert_called_once_with(7, "Main")


def test_operation_types_are_the_catalog_the_api_documents() -> None:
    assert {t.value for t in OperationType} == {
        "buy",
        "sell",
        "deposit",
        "withdrawal",
        "dividend",
        "interest",
        "fee",
        "split",
    }


@pytest.mark.parametrize("by", ["asset_id", "ticker"])
def test_an_archived_asset_takes_no_new_operation(
    service: OperationService,
    portfolio_repo: MagicMock,
    operation_repo: MagicMock,
    assets: MagicMock,
    session: MagicMock,
    by: str,
) -> None:
    archived = SimpleNamespace(
        id=ASSET_ID, archived_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    portfolio_repo.get_owned.return_value = _portfolio()
    assets.find_by_id.return_value = archived
    assets.find_by_ticker.return_value = archived
    asset_arg: dict[str, Any] = (
        {"asset_id": ASSET_ID}
        if by == "asset_id"
        else {"ticker": "AAPL", "asset_class": "X"}
    )

    with pytest.raises(AssetArchivedError) as exc_info:
        service.record(
            _request(operation_type="buy", quantity=1, price=1, **asset_arg), 7
        )

    assert (exc_info.value.status_code, exc_info.value.code) == (409, "ASSET_ARCHIVED")
    operation_repo.create.assert_not_called()
    session.commit.assert_not_called()


# --- edited_at (DEC-06) ---


def test_update_marks_the_operation_edited_only_when_a_field_really_changes(
    service: OperationService,
    portfolio_repo: MagicMock,
    position_repo: MagicMock,
    operation_repo: MagicMock,
) -> None:
    history = _history()
    buy = history[1]
    operation_repo.get_owned.return_value = buy
    operation_repo.list_by_portfolio.return_value = history
    portfolio_repo.get_owned.return_value = _portfolio(cash="798")
    position_repo.list_by_portfolio.return_value = [_row(quantity="10")]

    service.update(2, OperationUpdateRequest(price=D("20"), fee=D("2")), owner_id=7)
    assert getattr(buy, "edited_at", None) is None

    service.update(2, OperationUpdateRequest(price=D("21")), owner_id=7)
    assert buy.edited_at is not None


# --- record_many_core / revert_import_batch_core (import) ---


def _draft(row_number: int, operation_type: str, **values: Any) -> OperationDraft:
    return OperationDraft(
        row_number=row_number,
        operation_type=operation_type,
        operation_date=WHEN,
        external_ref=f"src:{row_number}",
        **values,
    )


def test_record_many_core_stores_every_draft_and_rebuilds_once_without_committing(
    service: OperationService,
    portfolio_repo: MagicMock,
    position_repo: MagicMock,
    operation_repo: MagicMock,
    session: MagicMock,
) -> None:
    portfolio = _portfolio(cash="0", deposited="0")
    portfolio_repo.get_owned.return_value = portfolio
    position_repo.list_by_portfolio.return_value = []
    drafts = [
        _draft(11, "interest", amount=D("5")),
        _draft(12, "buy", asset_id=ASSET_ID, quantity=D("10"), price=D("20")),
    ]

    created = service.record_many_core(drafts, 1, 7, import_batch_id=9)

    assert len(created) == 2
    portfolio_repo.lock_owned.assert_called_once_with(1, 7)
    # Verify that create_many was called with operations list.
    operation_repo.create_many.assert_called_once()
    operations = operation_repo.create_many.call_args[0][0]
    refs = [op.external_ref for op in operations]
    assert refs == ["src:11", "src:12"]
    assert {op.import_batch_id for op in operations} == {9}
    # One rebuild: the portfolio is written once; the caller owns the commit.
    portfolio_repo.update.assert_called_once_with(portfolio)
    # The fixture history's deposit 1000, + 5 interest, - 10 x 20 bought.
    assert portfolio.cash_balance == D("805")
    session.commit.assert_not_called()


def test_record_many_core_names_the_row_the_ledger_refused(
    service: OperationService,
    portfolio_repo: MagicMock,
    position_repo: MagicMock,
    session: MagicMock,
) -> None:
    portfolio_repo.get_owned.return_value = _portfolio()
    position_repo.list_by_portfolio.return_value = []
    drafts = [
        _draft(11, "interest", amount=D("5")),
        _draft(12, "buy", asset_id=ASSET_ID, quantity=D("100"), price=D("20")),
    ]

    with pytest.raises(ImportCommitRejectedError) as exc_info:
        service.record_many_core(drafts, 1, 7, import_batch_id=9)

    error = exc_info.value
    assert (error.row_number, error.code) == (12, "IMPORT_COMMIT_REJECTED")
    assert error.reason_code == "INSUFFICIENT_CASH"
    assert error.status_code == 400


def test_revert_deletes_the_batch_operations_and_rebuilds(
    service: OperationService,
    portfolio_repo: MagicMock,
    position_repo: MagicMock,
    operation_repo: MagicMock,
) -> None:
    history = _history()
    imported = [_stored("interest", id=3, amount=D("5"), edited_at=None)]
    operation_repo.list_by_import_batch.return_value = imported
    operation_repo.list_by_portfolio.return_value = history[:1]
    portfolio_repo.get_owned.return_value = _portfolio()
    position_repo.list_by_portfolio.return_value = []

    service.revert_import_batch_core(9, 1, 7)

    operation_repo.delete.assert_called_once_with(imported[0])
    portfolio_repo.update.assert_called_once()


def test_revert_refuses_when_an_operation_was_edited_and_deletes_nothing(
    service: OperationService, operation_repo: MagicMock
) -> None:
    operation_repo.list_by_import_batch.return_value = [
        _stored("interest", id=3, amount=D("5"), edited_at=None),
        _stored("fee", id=4, amount=D("1"), edited_at=WHEN),
    ]

    with pytest.raises(ImportBatchHasEditsError) as exc_info:
        service.revert_import_batch_core(9, 1, 7)

    assert exc_info.value.operation_ids == [4]
    assert exc_info.value.code == "IMPORT_BATCH_HAS_EDITS"
    operation_repo.delete.assert_not_called()


# --- preview_state ---


def test_preview_state_replays_history_with_drafts_and_stores_nothing(
    service: OperationService,
    portfolio_repo: MagicMock,
    operation_repo: MagicMock,
) -> None:
    portfolio_repo.get_owned.return_value = _portfolio()
    operation_repo.list_by_portfolio.return_value = [
        _stored("deposit", id=1, amount=D("1000"))
    ]

    state = service.preview_state(1, 7, [_draft(11, "interest", amount=D("5"))])

    assert state.cash_balance == D("1005")
    portfolio_repo.update.assert_not_called()
    operation_repo.create.assert_not_called()


def test_preview_state_reports_a_history_the_ledger_refuses(
    service: OperationService,
    portfolio_repo: MagicMock,
    operation_repo: MagicMock,
) -> None:
    portfolio_repo.get_owned.return_value = _portfolio()
    operation_repo.list_by_portfolio.return_value = []

    with pytest.raises(OperationRejectedError):
        service.preview_state(1, 7, [_draft(11, "fee", amount=D("5"))])


def test_record_many_core_with_no_drafts_stores_nothing(
    service: OperationService, portfolio_repo: MagicMock, operation_repo: MagicMock
) -> None:
    assert service.record_many_core([], 1, 7, import_batch_id=9) == []

    operation_repo.create_many.assert_not_called()
    portfolio_repo.update.assert_not_called()


# --- dividends_without_position ---


def test_a_dividend_after_the_position_was_closed_is_refused_the_others_not(
    service: OperationService,
    portfolio_repo: MagicMock,
    operation_repo: MagicMock,
) -> None:
    portfolio_repo.get_owned.return_value = _portfolio()
    operation_repo.list_by_portfolio.return_value = [
        _stored(
            "deposit",
            id=1,
            amount=D("1000"),
            operation_date=datetime(2026, 1, 1, tzinfo=UTC),
        ),
    ]
    day = lambda n: datetime(2026, 1, n, tzinfo=UTC)  # noqa: E731
    drafts = [
        OperationDraft(
            10, "buy", day(2), asset_id=ASSET_ID, quantity=D("2"), price=D("10")
        ),
        OperationDraft(11, "dividend", day(3), asset_id=ASSET_ID, amount=D("1")),
        OperationDraft(
            12, "sell", day(4), asset_id=ASSET_ID, quantity=D("2"), price=D("10")
        ),
        OperationDraft(13, "dividend", day(5), asset_id=ASSET_ID, amount=D("1")),
    ]

    assert service.dividends_without_position(1, 7, drafts) == {13}


def test_replay_for_dividends_stops_quietly_at_another_refusal(
    service: OperationService, portfolio_repo: MagicMock, operation_repo: MagicMock
) -> None:
    portfolio_repo.get_owned.return_value = _portfolio()
    operation_repo.list_by_portfolio.return_value = []
    drafts = [
        _draft(1, "fee", amount=D("5")),
        _draft(2, "dividend", asset_id=ASSET_ID, amount=D("1")),
    ]

    assert service.dividends_without_position(1, 7, drafts) == set()


def test_preview_names_the_draft_row_the_ledger_refused(
    service: OperationService, portfolio_repo: MagicMock, operation_repo: MagicMock
) -> None:
    portfolio_repo.get_owned.return_value = _portfolio()
    operation_repo.list_by_portfolio.return_value = []
    drafts = [_draft(4, "deposit", amount=D("5")), _draft(9, "fee", amount=D("50"))]

    with pytest.raises(OperationRejectedError) as exc_info:
        service.preview_state(1, 7, drafts)

    assert exc_info.value.row_number == 9


def test_the_dividend_replay_books_a_refused_dividend_as_income(
    service: OperationService, portfolio_repo: MagicMock, operation_repo: MagicMock
) -> None:
    """Its cash pays for the buy after it; without it the replay would stop at
    the buy and never see the dividends further on."""
    portfolio_repo.get_owned.return_value = _portfolio()
    operation_repo.list_by_portfolio.return_value = []
    day = lambda n: datetime(2026, 1, n, tzinfo=UTC)  # noqa: E731
    drafts = [
        OperationDraft(1, "deposit", day(1), amount=D("100")),
        OperationDraft(2, "dividend", day(2), asset_id=ASSET_ID, amount=D("50")),
        OperationDraft(
            3, "buy", day(3), asset_id=ASSET_ID, quantity=D("1"), price=D("120")
        ),
        OperationDraft(
            4, "sell", day(4), asset_id=ASSET_ID, quantity=D("1"), price=D("120")
        ),
        OperationDraft(5, "dividend", day(5), asset_id=ASSET_ID, amount=D("1")),
    ]

    assert service.dividends_without_position(1, 7, drafts) == {2, 5}
