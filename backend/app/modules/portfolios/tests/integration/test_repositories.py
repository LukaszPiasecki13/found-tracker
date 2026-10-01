"""Portfolios repositories on PostgreSQL. Nothing is committed: the rows are
flushed inside the test session's transaction and rolled back at the end."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.conftest import IntegrationData
from app.modules.assets.models import Asset, Currency
from app.modules.core_data.models import User
from app.modules.portfolios.exceptions import (
    OperationNotFoundError,
    PortfolioNotFoundError,
)
from app.modules.portfolios.models import Portfolio
from app.modules.portfolios.repositories import (
    OperationRepository,
    PortfolioRepository,
    PositionRepository,
)

D = Decimal
WHEN = datetime(2025, 3, 1, 12, tzinfo=UTC)


@pytest.fixture
def owner(integration_session: Session, integration_data: IntegrationData) -> User:
    user = User(
        email=f"{integration_data.value('repo')}@example.com", password_hash="x"
    )
    integration_session.add(user)
    integration_session.flush()
    return user


@pytest.fixture
def portfolio(
    integration_session: Session,
    integration_data: IntegrationData,
    owner: User,
    seeded_currency: Currency,
) -> Portfolio:
    return PortfolioRepository(integration_session).create(
        owner_id=owner.id,
        name=integration_data.value("repo"),
        base_currency_id=seeded_currency.id,
    )


def _operation(
    repo: OperationRepository, portfolio: Portfolio, when: datetime, notes: str
) -> int:
    return repo.create(
        portfolio_id=portfolio.id,
        asset_id=None,
        operation_type="deposit",
        quantity=D("0"),
        price=D("0"),
        amount=D("1"),
        fee=D("0"),
        fx_rate=D("1"),
        notes=notes,
        operation_date=when,
    ).id


def test_history_is_ordered_by_date_then_created_at_then_id(
    integration_session: Session, portfolio: Portfolio
) -> None:
    repo = OperationRepository(integration_session)
    later = _operation(repo, portfolio, WHEN, "later")
    first_tie = _operation(repo, portfolio, datetime(2025, 2, 1, tzinfo=UTC), "a")
    second_tie = _operation(repo, portfolio, datetime(2025, 2, 1, tzinfo=UTC), "b")

    history = repo.list_by_portfolio(portfolio.id)

    # Same transaction: equal `created_at` (now()), so `id` breaks the tie.
    assert [op.id for op in history] == [first_tie, second_tie, later]


def test_reads_are_scoped_to_the_owner(
    integration_session: Session, portfolio: Portfolio, owner: User
) -> None:
    portfolios = PortfolioRepository(integration_session)
    operations = OperationRepository(integration_session)
    operation_id = _operation(operations, portfolio, WHEN, "x")
    stranger = owner.id + 1_000_000

    assert portfolios.find_owned(portfolio.id, owner.id) is portfolio
    assert portfolios.find_owned(portfolio.id, stranger) is None
    assert portfolios.list_by_owner(stranger) == []
    with pytest.raises(PortfolioNotFoundError):
        portfolios.get_by_owner_and_name(stranger, portfolio.name)
    assert operations.find_owned(operation_id, owner.id) is not None
    with pytest.raises(OperationNotFoundError):
        operations.get_owned(operation_id, stranger)
    assert operations.list_by_owner(stranger) == []


def test_numeric_columns_round_on_write(
    integration_session: Session, portfolio: Portfolio, seeded_asset: Asset
) -> None:
    position = PositionRepository(integration_session).create(
        portfolio_id=portfolio.id,
        asset_id=seeded_asset.id,
        quantity=D("3"),
        average_buy_price=D("31") / D("3"),
        average_fx_rate=D("1"),
        total_fees=D("0.125"),
        total_dividends=D("0"),
    )
    portfolio.cash_balance = D("1.23456")
    PortfolioRepository(integration_session).update(portfolio)

    assert position.average_buy_price == D("10.333333333")
    assert position.total_fees == D("0.13")
    assert portfolio.cash_balance == D("1.235")


def test_valued_reads_load_positions_assets_and_currencies_eagerly(
    integration_session: Session, portfolio: Portfolio, seeded_asset: Asset
) -> None:
    PositionRepository(integration_session).create(
        portfolio_id=portfolio.id,
        asset_id=seeded_asset.id,
        quantity=D("1"),
        average_buy_price=D("1"),
        average_fx_rate=D("1"),
        total_fees=D("0"),
        total_dividends=D("0"),
    )
    integration_session.expire_all()

    [loaded] = PortfolioRepository(integration_session).list_by_owner(
        portfolio.owner_id
    )

    assert {"positions", "base_currency"}.isdisjoint(inspect(loaded).unloaded)
    [position] = loaded.positions
    assert "asset" not in inspect(position).unloaded
    assert {"currency", "asset_class"}.isdisjoint(inspect(position.asset).unloaded)


def test_reads_refresh_a_portfolio_already_in_the_session(
    integration_session: Session, portfolio: Portfolio, seeded_asset: Asset
) -> None:
    portfolios = PortfolioRepository(integration_session)
    loaded = portfolios.get_owned(portfolio.id, portfolio.owner_id)
    assert loaded.positions == []

    PositionRepository(integration_session).create(
        portfolio_id=portfolio.id,
        asset_id=seeded_asset.id,
        quantity=D("1"),
        average_buy_price=D("1"),
        average_fx_rate=D("1"),
        total_fees=D("0"),
        total_dividends=D("0"),
    )

    again = portfolios.get_owned(portfolio.id, portfolio.owner_id)
    assert again is loaded
    assert [p.asset_id for p in again.positions] == [seeded_asset.id]


def test_failed_transaction_rolls_everything_back(
    integration_session: Session, portfolio: Portfolio
) -> None:
    repo = PortfolioRepository(integration_session)
    portfolio_id, owner_id = portfolio.id, portfolio.owner_id

    with pytest.raises(RuntimeError), repo.transaction():
        portfolio.cash_balance = D("5")
        repo.update(portfolio)
        raise RuntimeError("boom")

    assert repo.find_owned(portfolio_id, owner_id) is None  # creation undone too
