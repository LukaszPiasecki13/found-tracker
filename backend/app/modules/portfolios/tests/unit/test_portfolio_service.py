from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.modules.portfolios.domain import PortfolioValuator
from app.modules.portfolios.exceptions import (
    PortfolioAlreadyExistsError,
    PortfolioCurrencyLockedError,
    PortfolioNotFoundError,
    UnknownCurrencyError,
)
from app.modules.portfolios.schemas.portfolios import (
    PortfolioCreateRequest,
    PortfolioUpdateRequest,
)
from app.modules.portfolios.services.portfolios import PortfolioService
from app.modules.portfolios.services.snapshots import TwrResult

D = Decimal
NOW = datetime(2026, 1, 2, tzinfo=UTC)


def _currency(currency_id: int = 1, rate: str = "1") -> SimpleNamespace:
    return SimpleNamespace(
        id=currency_id,
        code=f"C{currency_id:02d}",
        exchange_rate=D(rate),
        base_currency_id=None,
    )


def _position(
    position_id: int,
    quantity: str,
    average_price: str,
    current_price: str,
    currency: SimpleNamespace,
    fees: str = "0",
) -> SimpleNamespace:
    asset = SimpleNamespace(
        id=position_id * 10,
        ticker=f"T{position_id}",
        name=f"Asset {position_id}",
        asset_class=SimpleNamespace(id=1, name="Stock"),
        currency=currency,
        currency_id=currency.id,
        current_price=D(current_price),
        exchange="X",
        sector="",
        updated_at=NOW,
    )
    return SimpleNamespace(
        id=position_id,
        portfolio_id=1,
        asset_id=asset.id,
        asset=asset,
        quantity=D(quantity),
        average_buy_price=D(average_price),
        average_fx_rate=D("1"),
        total_fees=D(fees),
        total_dividends=D("0"),
        opened_at=NOW,
        updated_at=NOW,
    )


def _portfolio(positions: list | None = None, **overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "id": 1,
        "owner_id": 7,
        "name": "Main",
        "base_currency_id": 1,
        "base_currency": _currency(),
        "cash_balance": D("100.000"),
        "total_deposited": D("400.000"),
        "is_active": True,
        "created_at": NOW,
        "updated_at": NOW,
        "positions": positions or [],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.fixture
def currencies() -> MagicMock:
    return MagicMock()


@pytest.fixture
def fx_builder() -> MagicMock:
    builder = MagicMock()
    builder.build.return_value = {}
    return builder


@pytest.fixture
def snapshots() -> MagicMock:
    """`SnapshotService`: the time-weighted return is its business, not this one's."""
    snapshots = MagicMock()
    snapshots.twr.return_value = TwrResult(D("12.3456"))
    return snapshots


@pytest.fixture
def service(
    portfolio_repo: MagicMock,
    currencies: MagicMock,
    fx_builder: MagicMock,
    snapshots: MagicMock,
) -> PortfolioService:
    return PortfolioService(
        portfolio_repo, currencies, PortfolioValuator(), fx_builder, snapshots
    )


def _integrity_error() -> IntegrityError:
    return IntegrityError("INSERT ...", {}, Exception("unique"))


# --- create ---


def test_create_stores_an_empty_portfolio_and_commits(
    service: PortfolioService, portfolio_repo: MagicMock, session: MagicMock
) -> None:
    portfolio_repo.find_by_owner_and_name.return_value = None
    created = _portfolio()
    portfolio_repo.create.return_value = created

    result = service.create(PortfolioCreateRequest(name="Main", base_currency_id=1), 7)

    assert result is created
    portfolio_repo.create.assert_called_once_with(
        owner_id=7, name="Main", base_currency_id=1
    )
    session.commit.assert_called_once()


def test_create_rejects_a_duplicate_name_with_409(
    service: PortfolioService, portfolio_repo: MagicMock, session: MagicMock
) -> None:
    portfolio_repo.find_by_owner_and_name.return_value = _portfolio()

    with pytest.raises(PortfolioAlreadyExistsError) as exc_info:
        service.create(PortfolioCreateRequest(name="Main", base_currency_id=1), 7)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "PORTFOLIO_ALREADY_EXISTS"
    portfolio_repo.create.assert_not_called()
    session.rollback.assert_called_once()
    session.commit.assert_not_called()


def test_create_rejects_an_unknown_currency_with_400(
    service: PortfolioService, portfolio_repo: MagicMock, currencies: MagicMock
) -> None:
    portfolio_repo.find_by_owner_and_name.return_value = None
    currencies.find_by_id.return_value = None

    with pytest.raises(UnknownCurrencyError) as exc_info:
        service.create(PortfolioCreateRequest(name="Main", base_currency_id=9), 7)

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "CURRENCY_NOT_FOUND"
    portfolio_repo.create.assert_not_called()


def test_create_translates_a_lost_race_on_the_unique_name(
    service: PortfolioService, portfolio_repo: MagicMock, session: MagicMock
) -> None:
    portfolio_repo.find_by_owner_and_name.side_effect = [None, _portfolio()]
    portfolio_repo.create.side_effect = _integrity_error()

    with pytest.raises(PortfolioAlreadyExistsError) as exc_info:
        service.create(PortfolioCreateRequest(name="Main", base_currency_id=1), 7)

    assert isinstance(exc_info.value.__cause__, IntegrityError)
    session.rollback.assert_called_once()


# --- update / delete ---


def test_update_ignores_nulls_and_sets_given_fields(
    service: PortfolioService, portfolio_repo: MagicMock, session: MagicMock
) -> None:
    portfolio = _portfolio()
    portfolio_repo.get_owned.return_value = portfolio
    portfolio_repo.find_by_owner_and_name.return_value = None
    portfolio_repo.update.side_effect = lambda entity: entity

    service.update(
        1, PortfolioUpdateRequest(name="Renamed", base_currency_id=None), owner_id=7
    )

    assert (portfolio.name, portfolio.base_currency_id) == ("Renamed", 1)
    portfolio_repo.get_owned.assert_called_once_with(1, 7)
    session.commit.assert_called_once()


def test_update_keeping_its_own_name_is_not_a_conflict(
    service: PortfolioService, portfolio_repo: MagicMock
) -> None:
    portfolio = _portfolio()
    portfolio_repo.get_owned.return_value = portfolio
    portfolio_repo.find_by_owner_and_name.return_value = portfolio

    service.update(1, PortfolioUpdateRequest(name="Main"), owner_id=7)

    portfolio_repo.update.assert_called_once_with(portfolio)


def test_update_onto_another_portfolios_name_is_409(
    service: PortfolioService, portfolio_repo: MagicMock, session: MagicMock
) -> None:
    portfolio_repo.get_owned.return_value = _portfolio()
    portfolio_repo.find_by_owner_and_name.return_value = _portfolio(id=2)

    with pytest.raises(PortfolioAlreadyExistsError):
        service.update(1, PortfolioUpdateRequest(name="Other"), owner_id=7)

    session.commit.assert_not_called()


def test_update_to_an_unknown_currency_is_400(
    service: PortfolioService, portfolio_repo: MagicMock, currencies: MagicMock
) -> None:
    portfolio_repo.get_owned.return_value = _portfolio()
    currencies.find_by_id.return_value = None

    with pytest.raises(UnknownCurrencyError):
        service.update(1, PortfolioUpdateRequest(base_currency_id=99), owner_id=7)

    portfolio_repo.update.assert_not_called()


def test_base_currency_cannot_change_once_there_are_operations(
    service: PortfolioService, portfolio_repo: MagicMock, session: MagicMock
) -> None:
    portfolio_repo.get_owned.return_value = _portfolio()
    portfolio_repo.has_operations.return_value = True

    with pytest.raises(PortfolioCurrencyLockedError) as exc_info:
        service.update(1, PortfolioUpdateRequest(base_currency_id=2), owner_id=7)

    assert exc_info.value.code == "PORTFOLIO_CURRENCY_LOCKED"
    portfolio_repo.update.assert_not_called()
    session.commit.assert_not_called()


def test_base_currency_changes_while_the_portfolio_has_no_operations(
    service: PortfolioService, portfolio_repo: MagicMock
) -> None:
    portfolio = _portfolio()
    portfolio_repo.get_owned.return_value = portfolio
    portfolio_repo.has_operations.return_value = False

    service.update(1, PortfolioUpdateRequest(base_currency_id=2), owner_id=7)

    assert portfolio.base_currency_id == 2


def test_another_owners_portfolio_is_not_found(
    service: PortfolioService, portfolio_repo: MagicMock, session: MagicMock
) -> None:
    portfolio_repo.get_owned.side_effect = PortfolioNotFoundError

    with pytest.raises(PortfolioNotFoundError) as exc_info:
        service.delete(1, owner_id=8)

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "PORTFOLIO_NOT_FOUND"
    portfolio_repo.delete.assert_not_called()
    session.commit.assert_not_called()


def test_delete_removes_and_commits(
    service: PortfolioService, portfolio_repo: MagicMock, session: MagicMock
) -> None:
    portfolio = _portfolio()
    portfolio_repo.get_owned.return_value = portfolio

    service.delete(1, owner_id=7)

    portfolio_repo.delete.assert_called_once_with(portfolio)
    session.commit.assert_called_once()


# --- read models ---


def test_list_summaries_values_each_portfolio_and_rounds_at_the_boundary(
    service: PortfolioService,
    portfolio_repo: MagicMock,
    fx_builder: MagicMock,
    snapshots: MagicMock,
) -> None:
    fx_builder.build.return_value = {(2, 1): D("3.9")}
    usd = _currency(2, rate="999")
    positions = [
        _position(1, "3", "10", "33.3333", _currency(), fees="1.25"),
        _position(2, "1", "100", "101", usd, fees="0.5"),
    ]
    portfolio_repo.list_by_owner.return_value = [_portfolio(positions)]

    [summary] = service.list_summaries(7, name="Main")

    portfolio_repo.list_by_owner.assert_called_once_with(7, name="Main")
    # 3 * 33.3333 + 101 * 3.9 = 99.9999 + 393.9
    assert summary.positions_value == D("493.900")  # 493.8999 -> 3 places
    assert summary.total_value == D("593.900")
    assert summary.total_profit_loss == D("193.900")
    # The return is the snapshots' time-weighted one, valued at the total value.
    assert summary.total_return_pct == D("12.3456")
    assert summary.return_method == "daily_pp_v1"
    [call] = snapshots.twr.call_args_list
    assert call.args[1] == D("593.8999")
    assert summary.total_fees == D("1.75")
    assert summary.rate_missing is False
    assert summary.base_currency.id == 1
    body = summary.model_dump(mode="json")
    assert body["positions_value"] == 493.9
    assert body["cash_balance"] == 100.0


def test_get_detail_has_valued_positions_with_weights(
    service: PortfolioService, portfolio_repo: MagicMock
) -> None:
    positions = [
        _position(1, "2", "40", "50", _currency()),
        _position(2, "1", "10", "0", _currency()),
    ]
    portfolio_repo.get_owned.return_value = _portfolio(positions)

    detail = service.get_detail(1, owner_id=7)

    portfolio_repo.get_owned.assert_called_once_with(1, 7)
    assert detail.total_value == D("200.000")  # cash 100 + 100 + 0
    assert detail.updated_at == NOW
    first, second = detail.positions
    assert (first.id, first.market_value, first.unrealized_pnl) == (
        1,
        D("100.000"),
        D("20.000"),
    )
    assert first.return_pct == D("25.0000")
    assert first.portfolio_weight_pct == D("50.0000")
    assert (second.market_value, second.return_pct) == (D("0.000"), D("-100.0000"))
    assert first.asset.ticker == "T1"


def test_rounding_is_half_even_like_pythons_round(
    service: PortfolioService, portfolio_repo: MagicMock
) -> None:
    # market value 0.0125 -> 0.012 (half-even), cost 0.0135 -> 0.014
    positions = [_position(1, "1", "0.0135", "0.0125", _currency())]
    portfolio_repo.get_owned.return_value = _portfolio(positions)

    position = service.get_detail(1, owner_id=7).positions[0]

    assert position.market_value == D("0.012")
    assert position.cost_basis == D("0.014")


def test_list_summaries_builds_the_rate_map_once_for_every_base_currency(
    service: PortfolioService, portfolio_repo: MagicMock, fx_builder: MagicMock
) -> None:
    pln = _portfolio(id=1, base_currency_id=1)
    usd = _portfolio(id=2, base_currency_id=2, base_currency=_currency(2))
    portfolio_repo.list_by_owner.return_value = [pln, usd]

    service.list_summaries(7)

    fx_builder.build.assert_called_once()
    assert set(fx_builder.build.call_args.args[0]) == {1, 2}


def test_get_detail_builds_the_rate_map_for_the_portfolio_currency(
    service: PortfolioService, portfolio_repo: MagicMock, fx_builder: MagicMock
) -> None:
    portfolio_repo.get_owned.return_value = _portfolio(base_currency_id=1)

    service.get_detail(1, owner_id=7)

    fx_builder.build.assert_called_once()
    assert set(fx_builder.build.call_args.args[0]) == {1}


def test_get_detail_flags_a_position_whose_currency_has_no_rate(
    service: PortfolioService,
    portfolio_repo: MagicMock,
    fx_builder: MagicMock,
    snapshots: MagicMock,
) -> None:
    fx_builder.build.return_value = {}
    snapshots.twr.return_value = None
    gbp = _currency(4)
    positions = [
        _position(1, "2", "40", "50", _currency()),
        _position(2, "10", "2", "2.5", gbp),
    ]
    portfolio_repo.get_owned.return_value = _portfolio(positions)

    detail = service.get_detail(1, owner_id=7)

    assert detail.rate_missing is True
    assert detail.positions_value is None
    assert detail.total_value is None
    assert detail.total_profit_loss is None
    assert detail.total_return_pct is None
    assert detail.return_method is None
    # No total value to value the return at.
    assert snapshots.twr.call_args.args[1] is None
    priced, unpriced = detail.positions
    assert priced.rate_missing is False
    assert priced.market_value == D("100.000")
    assert priced.portfolio_weight_pct is None
    assert unpriced.rate_missing is True
    assert unpriced.market_value is None
    assert unpriced.cost_basis == D("20.000")
    body = detail.model_dump(mode="json")
    assert body["total_value"] is None
    assert body["rate_missing"] is True
    assert body["positions"][1]["market_value"] is None
