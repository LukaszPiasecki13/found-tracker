from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

import app.infrastructure.sql.models_registry  # noqa: F401
from app.modules.assets.models.assets import Asset
from app.modules.portfolios.models import Portfolio, Position
from app.modules.portfolios.repository import (
    OperationRepository,
    PortfolioRepository,
    PositionRepository,
)
from app.modules.portfolios.services.portfolio_service import PortfolioService
from app.modules.portfolios.services.transaction_service import TransactionService


def _portfolio_with_position(session: Session) -> tuple[Portfolio, Position]:
    position = session.query(Position).order_by(Position.id).first()
    if position is None:
        pytest.fail("Integration database needs at least one portfolio position")
    portfolio = session.get(Portfolio, position.portfolio_id)
    if portfolio is None:
        pytest.fail("Position references a missing portfolio")
    return portfolio, position


def test_postgres_relationships_load_from_seeded_database(
    postgres_session: Session,
) -> None:
    portfolio, position = _portfolio_with_position(postgres_session)

    assert portfolio.owner_id is not None
    assert position.portfolio_id == portfolio.id
    assert position.asset_id is not None
    assert postgres_session.get(Asset, position.asset_id) is not None


def test_postgres_operation_repository_returns_chronological_history(
    postgres_session: Session,
) -> None:
    portfolio, _ = _portfolio_with_position(postgres_session)
    operations = OperationRepository(postgres_session).list_by_portfolio(portfolio.id)

    assert operations
    assert all(operation.portfolio_id == portfolio.id for operation in operations)
    sort_keys = [
        (operation.operation_date, operation.created_at, operation.id)
        for operation in operations
    ]
    assert sort_keys == sorted(sort_keys)


def test_postgres_buy_and_sell_use_real_repositories(
    postgres_session: Session,
) -> None:
    portfolio, position = _portfolio_with_position(postgres_session)
    asset = postgres_session.get(Asset, position.asset_id)
    if asset is None:
        pytest.fail("Position references a missing asset")

    before_cash = Decimal(str(portfolio.cash_balance))
    before_quantity = Decimal(str(position.quantity))
    service = TransactionService(
        PortfolioRepository(postgres_session), PositionRepository(postgres_session)
    )

    service.execute_buy(
        {
            "portfolio": portfolio,
            "asset": asset,
            "quantity": Decimal("1"),
            "price": Decimal("1"),
            "fee": Decimal("0.01"),
            "fx_rate": Decimal("1"),
        }
    )
    service.execute_sell(
        {
            "portfolio": portfolio,
            "asset": asset,
            "quantity": Decimal("1"),
            "price": Decimal("1.25"),
            "fee": Decimal("0.01"),
            "fx_rate": Decimal("1"),
        }
    )

    postgres_session.flush()
    refreshed_position = PositionRepository(
        postgres_session
    ).get_by_portfolio_and_asset(portfolio.id, asset.id)
    assert refreshed_position is not None
    assert Decimal(str(refreshed_position.quantity)) == before_quantity
    assert Decimal(str(portfolio.cash_balance)) == before_cash + Decimal("0.23")


def test_postgres_transaction_rolls_back_service_changes(
    postgres_session: Session,
) -> None:
    portfolio, _ = _portfolio_with_position(postgres_session)
    before_cash = Decimal(str(portfolio.cash_balance))
    portfolio_service = PortfolioService(
        PortfolioRepository(postgres_session),
        OperationRepository(postgres_session),
        PositionRepository(postgres_session),
    )

    portfolio_service.deposit_cash(
        {"portfolio": portfolio, "amount": Decimal("7"), "fee": Decimal("0")}
    )
    postgres_session.rollback()
    postgres_session.expire_all()

    restored = postgres_session.get(Portfolio, portfolio.id)
    assert restored is not None
    assert Decimal(str(restored.cash_balance)) == before_cash
