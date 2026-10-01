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

from app.modules.portfolios.domain import OperationType, PortfolioLedger
from app.modules.portfolios.exceptions import (
    AssetClassRequiredError,
    ConcurrentChangeError,
    OperationNotFoundError,
    OperationRejectedError,
    PortfolioNotFoundError,
    UnknownAssetError,
)
from app.modules.portfolios.schemas.operations import (
    OperationCreateRequest,
    OperationUpdateRequest,
)
from app.modules.portfolios.services.operations import OperationService

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
def service(
    portfolio_repo: MagicMock,
    position_repo: MagicMock,
    operation_repo: MagicMock,
    assets: MagicMock,
) -> OperationService:
    portfolio_repo.update.side_effect = lambda entity: entity
    position_repo.update.side_effect = lambda entity: entity
    operation_repo.update.side_effect = lambda entity: entity
    return OperationService(
        portfolio_repo, position_repo, operation_repo, assets, PortfolioLedger()
    )


# --- record ---


def test_record_deposit_updates_cash_and_stores_the_operation(
    service: OperationService,
    portfolio_repo: MagicMock,
    position_repo: MagicMock,
    operation_repo: MagicMock,
    session: MagicMock,
) -> None:
    portfolio = _portfolio(cash="10", deposited="10")
    portfolio_repo.get_owned.return_value = portfolio
    position_repo.list_by_portfolio.return_value = []
    created = SimpleNamespace(id=9)
    operation_repo.create.return_value = created

    result = service.record(_request(amount="100.5", fee="0.5", notes="n"), 7)

    assert result is created
    portfolio_repo.get_owned.assert_called_once_with(1, 7)
    assert (portfolio.cash_balance, portfolio.total_deposited) == (D("110"), D("110.5"))
    operation_repo.create.assert_called_once_with(
        portfolio_id=1,
        asset_id=None,
        operation_type="deposit",
        quantity=D("0"),
        price=D("0"),
        amount=D("100.5"),
        fee=D("0.5"),
        fx_rate=D("1"),
        notes="n",
        operation_date=datetime(2026, 1, 2),
    )
    session.commit.assert_called_once()
    session.rollback.assert_not_called()


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
) -> None:
    portfolio_repo.get_owned.return_value = _portfolio()
    row = _row(quantity="10")
    position_repo.list_by_portfolio.return_value = [row]
    assets.find_by_id.return_value = SimpleNamespace(id=ASSET_ID)

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
) -> None:
    portfolio = _portfolio(cash="0")
    portfolio_repo.get_owned.return_value = portfolio
    row = _row(quantity="10")
    position_repo.list_by_portfolio.return_value = [row]
    assets.find_by_id.return_value = SimpleNamespace(id=ASSET_ID)

    service.record(
        _request(operation_type="sell", asset_id=ASSET_ID, quantity=10, price=25),
        7,
    )

    position_repo.delete.assert_called_once_with(row)
    assert portfolio.cash_balance == D("250")


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
        return SimpleNamespace(id=42)

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
        "cdr", asset_class_name="Stock", currency_id=3
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
    operation_repo: MagicMock,
    assets: MagicMock,
    session: MagicMock,
) -> None:
    portfolio = _portfolio(cash="10")
    portfolio_repo.get_owned.return_value = portfolio
    position_repo.list_by_portfolio.return_value = []
    assets.find_by_ticker.return_value = None
    assets.get_or_create_by_ticker.return_value = SimpleNamespace(id=42)

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
    operation_repo.create.assert_not_called()
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
    assets.find_by_id.return_value = SimpleNamespace(id=ASSET_ID)

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
    assets.find_by_ticker.return_value = SimpleNamespace(id=ASSET_ID)

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


def test_operation_types_are_the_frontend_ones() -> None:
    assert {t.value for t in OperationType} == {
        "buy",
        "sell",
        "deposit",
        "withdrawal",
        "dividend",
    }
