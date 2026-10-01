from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from sqlalchemy.orm import Session

if __package__ in {None, ""}:
    backend_root = Path(__file__).resolve().parents[1]
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))
    os.chdir(backend_root)

import app.infrastructure.sql.models_registry  # noqa: F401
from app.core.config import get_settings
from app.infrastructure.sql.factory import sql_factory
from app.modules.assets.models import Asset, AssetClass, Currency
from app.modules.core_data.models import User
from app.modules.portfolios.models import Operation, Portfolio, Position
from app.modules.security.services.password import hash_password

if __package__ in {None, ""}:
    from seed.seed_data import (
        ASSET_CLASSES,
        ASSETS,
        CURRENCIES,
        OPERATIONS,
        PORTFOLIOS,
        POSITIONS,
        SEED_USER_EMAIL,
        SEED_USER_PASSWORD,
    )
else:
    from .seed_data import (
        ASSET_CLASSES,
        ASSETS,
        CURRENCIES,
        OPERATIONS,
        PORTFOLIOS,
        POSITIONS,
        SEED_USER_EMAIL,
        SEED_USER_PASSWORD,
    )

logger = logging.getLogger(__name__)


def _set_attr(obj: object, name: str, value: object) -> None:
    setattr(cast(Any, obj), name, value)


def _upsert_user(session: Session) -> User:
    user = session.query(User).filter(User.email == SEED_USER_EMAIL).one_or_none()
    password_hash = hash_password(SEED_USER_PASSWORD)
    if user is None:
        user = User(
            email=SEED_USER_EMAIL,
            password_hash=password_hash,
            is_active=True,
        )
        session.add(user)
        session.flush()
        return user

    user.password_hash = password_hash
    user.is_active = True
    session.flush()
    return user


def _upsert_currency(session: Session, code: str, exchange_rate: Decimal) -> Currency:
    currency = session.query(Currency).filter(Currency.code == code).one_or_none()
    if currency is None:
        currency = Currency(code=code)
        session.add(currency)
    _set_attr(currency, "exchange_rate", exchange_rate)
    session.flush()
    return currency


def _upsert_asset_class(session: Session, name: str) -> AssetClass:
    asset_class = (
        session.query(AssetClass).filter(AssetClass.name == name).one_or_none()
    )
    if asset_class is None:
        asset_class = AssetClass(name=name)
        session.add(asset_class)
    session.flush()
    return asset_class


def _upsert_asset(
    session: Session,
    *,
    ticker: str,
    name: str,
    asset_class: AssetClass,
    currency: Currency,
    current_price: Decimal,
    exchange: str,
    sector: str,
) -> Asset:
    asset = session.query(Asset).filter(Asset.ticker == ticker).one_or_none()
    if asset is None:
        asset = Asset(ticker=ticker)
        session.add(asset)
    _set_attr(asset, "name", name)
    _set_attr(asset, "asset_class", asset_class)
    _set_attr(asset, "currency", currency)
    _set_attr(asset, "current_price", current_price)
    _set_attr(asset, "exchange", exchange)
    _set_attr(asset, "sector", sector)
    session.flush()
    return asset


def _clear_user_portfolios(session: Session, owner_id: int) -> None:
    portfolios = session.query(Portfolio).filter(Portfolio.owner_id == owner_id).all()
    for portfolio in portfolios:
        session.delete(portfolio)
    session.flush()


def _upsert_portfolio(
    session: Session,
    *,
    owner_id: int,
    name: str,
    base_currency: Currency,
    cash_balance: Decimal,
    total_deposited: Decimal,
    is_active: bool,
) -> Portfolio:
    portfolio = (
        session.query(Portfolio)
        .filter(Portfolio.owner_id == owner_id, Portfolio.name == name)
        .one_or_none()
    )
    if portfolio is None:
        portfolio = Portfolio(owner_id=owner_id, name=name)
        session.add(portfolio)
    _set_attr(portfolio, "base_currency", base_currency)
    _set_attr(portfolio, "cash_balance", cash_balance)
    _set_attr(portfolio, "total_deposited", total_deposited)
    _set_attr(portfolio, "is_active", is_active)
    session.flush()
    return portfolio


def _upsert_position(
    session: Session,
    *,
    portfolio: Portfolio,
    asset: Asset,
    quantity: Decimal,
    average_buy_price: Decimal,
    average_fx_rate: Decimal,
    total_fees: Decimal,
    total_dividends: Decimal,
) -> Position:
    position = (
        session.query(Position)
        .filter(
            Position.portfolio_id == portfolio.id,
            Position.asset_id == asset.id,
        )
        .one_or_none()
    )
    if position is None:
        position = Position(portfolio=portfolio, asset=asset)
        session.add(position)
    _set_attr(position, "quantity", quantity)
    _set_attr(position, "average_buy_price", average_buy_price)
    _set_attr(position, "average_fx_rate", average_fx_rate)
    _set_attr(position, "total_fees", total_fees)
    _set_attr(position, "total_dividends", total_dividends)
    session.flush()
    return position


def _create_operation(
    session: Session,
    *,
    portfolio: Portfolio,
    asset: Asset | None,
    operation_type: str,
    quantity: Decimal,
    price: Decimal,
    amount: Decimal | None,
    fee: Decimal,
    fx_rate: Decimal,
    notes: str,
    operation_date: datetime,
) -> Operation:
    operation = Operation(
        portfolio=portfolio,
        asset=asset,
        operation_type=operation_type,
        quantity=quantity,
        price=price,
        amount=amount,
        fee=fee,
        fx_rate=fx_rate,
        notes=notes,
        operation_date=operation_date,
    )
    session.add(operation)
    session.flush()
    return operation


def seed_database(session: Session) -> None:
    currency_map: dict[str, Currency] = {}
    asset_class_map: dict[str, AssetClass] = {}
    asset_map: dict[str, Asset] = {}
    portfolio_map: dict[str, Portfolio] = {}

    user = _upsert_user(session)

    for currency_seed in CURRENCIES:
        currency_map[currency_seed.code] = _upsert_currency(
            session,
            currency_seed.code,
            currency_seed.exchange_rate,
        )

    for currency_seed in CURRENCIES:
        if currency_seed.base_currency_code is None:
            continue
        currency = currency_map[currency_seed.code]
        _set_attr(
            currency,
            "base_currency",
            currency_map[currency_seed.base_currency_code],
        )
        _set_attr(currency, "exchange_rate", currency_seed.exchange_rate)
        session.flush()

    for asset_class_seed in ASSET_CLASSES:
        asset_class_map[asset_class_seed.name] = _upsert_asset_class(
            session, asset_class_seed.name
        )

    for asset_seed in ASSETS:
        asset_map[asset_seed.ticker] = _upsert_asset(
            session,
            ticker=asset_seed.ticker,
            name=asset_seed.name,
            asset_class=asset_class_map[asset_seed.asset_class_name],
            currency=currency_map[asset_seed.currency_code],
            current_price=asset_seed.current_price,
            exchange=asset_seed.exchange,
            sector=asset_seed.sector,
        )

    _clear_user_portfolios(session, user.id)

    for portfolio_seed in PORTFOLIOS:
        portfolio_map[portfolio_seed.name] = _upsert_portfolio(
            session,
            owner_id=user.id,
            name=portfolio_seed.name,
            base_currency=currency_map[portfolio_seed.base_currency_code],
            cash_balance=portfolio_seed.cash_balance,
            total_deposited=portfolio_seed.total_deposited,
            is_active=portfolio_seed.is_active,
        )

    for position_seed in POSITIONS:
        _upsert_position(
            session,
            portfolio=portfolio_map[position_seed.portfolio_name],
            asset=asset_map[position_seed.ticker],
            quantity=position_seed.quantity,
            average_buy_price=position_seed.average_buy_price,
            average_fx_rate=position_seed.average_fx_rate,
            total_fees=position_seed.total_fees,
            total_dividends=position_seed.total_dividends,
        )

    now = datetime.now(UTC)
    for operation_seed in OPERATIONS:
        _create_operation(
            session,
            portfolio=portfolio_map[operation_seed.portfolio_name],
            asset=(
                asset_map.get(operation_seed.ticker) if operation_seed.ticker else None
            ),
            operation_type=operation_seed.operation_type,
            quantity=operation_seed.quantity,
            price=operation_seed.price,
            amount=operation_seed.amount,
            fee=operation_seed.fee,
            fx_rate=operation_seed.fx_rate,
            notes=operation_seed.notes,
            operation_date=now - timedelta(days=operation_seed.days_ago),
        )


def build_session() -> Session:
    settings = get_settings()
    engine = sql_factory.get_or_create_engine(
        settings.database_url,
        settings.database_schema,
    )
    session_factory = sql_factory.create_session_factory(
        engine,
        use_scoped_session=False,
    )
    return session_factory()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed the Found Tracker database.")
    parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    # The seed creates a demo account with a known password and replaces that
    # account's portfolios, so it must never touch a production-like database.
    if get_settings().is_production:
        logger.error(
            "Refusing to seed demo data when ENVIRONMENT is staging/production"
        )
        return 1

    session = build_session()
    try:
        with session.begin():
            seed_database(session)
    finally:
        session.close()

    logger.info("Seed completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
