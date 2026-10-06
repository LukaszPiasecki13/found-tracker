from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.portfolios.domain import PortfolioValuator
from app.modules.portfolios.exceptions import PortfolioNotFoundError
from app.modules.portfolios.services.positions import PositionService

D = Decimal
NOW = datetime(2026, 1, 2, tzinfo=UTC)


def _position(
    position_id: int, current_price: str, *, currency_id: int = 1
) -> SimpleNamespace:
    currency = SimpleNamespace(
        id=currency_id, code="PLN", exchange_rate=D("1"), base_currency_id=None
    )
    asset = SimpleNamespace(
        id=position_id * 10,
        ticker=f"T{position_id}",
        name="Asset",
        asset_class=SimpleNamespace(id=1, name="Stock"),
        currency=currency,
        currency_id=currency_id,
        current_price=D(current_price),
        exchange="",
        sector="",
        updated_at=NOW,
    )
    return SimpleNamespace(
        id=position_id,
        portfolio_id=1,
        asset_id=asset.id,
        asset=asset,
        quantity=D("1"),
        average_buy_price=D("10"),
        average_fx_rate=D("1"),
        total_fees=D("0"),
        total_dividends=D("0"),
        opened_at=NOW,
        updated_at=NOW,
    )


@pytest.fixture
def portfolios() -> MagicMock:
    return MagicMock()


@pytest.fixture
def fx_builder() -> MagicMock:
    builder = MagicMock()
    builder.build.return_value = {}
    return builder


@pytest.fixture
def service(
    portfolios: MagicMock,
    position_repo: MagicMock,
    fx_builder: MagicMock,
) -> PositionService:
    return PositionService(portfolios, position_repo, PortfolioValuator(), fx_builder)


def test_held_asset_ids_are_the_assets_of_the_portfolio_positions(
    service: PositionService,
    portfolios: MagicMock,
    position_repo: MagicMock,
) -> None:
    portfolios.get_owned_by_name.return_value = SimpleNamespace(id=1)
    position_repo.list_by_portfolio.return_value = [
        _position(2, "12"),
        _position(1, "8"),
    ]

    ids = service.held_asset_ids(7, "Main")

    portfolios.get_owned_by_name.assert_called_once_with(7, "Main")
    assert ids == [20, 10]


def test_list_valued_is_a_pure_read(
    service: PositionService,
    portfolios: MagicMock,
    position_repo: MagicMock,
) -> None:
    portfolios.get_owned_by_name.return_value = SimpleNamespace(
        id=1,
        base_currency_id=1,
        cash_balance=D("80"),
        total_deposited=D("100"),
    )
    position_repo.list_by_portfolio.return_value = [_position(2, "12")]

    result = service.list_valued(7, "Main")

    assert [p.id for p in result] == [2]


def test_unknown_portfolio_name_is_404(
    service: PositionService, portfolios: MagicMock
) -> None:
    portfolios.get_owned_by_name.side_effect = PortfolioNotFoundError

    with pytest.raises(PortfolioNotFoundError):
        service.held_asset_ids(7, "Nope")


def test_a_position_in_a_currency_without_a_rate_is_flagged_not_valued(
    service: PositionService,
    portfolios: MagicMock,
    position_repo: MagicMock,
    fx_builder: MagicMock,
) -> None:
    portfolios.get_owned_by_name.return_value = SimpleNamespace(
        id=1, base_currency_id=1, cash_balance=D("80"), total_deposited=D("100")
    )
    position_repo.list_by_portfolio.return_value = [
        _position(1, "12"),
        _position(2, "5", currency_id=4),
    ]
    fx_builder.build.return_value = {}

    priced, unpriced = service.list_valued(7, "Main")

    assert priced.rate_missing is False
    assert priced.market_value == D("12.000")
    assert priced.portfolio_weight_pct is None
    assert unpriced.rate_missing is True
    assert unpriced.market_value is None
    assert unpriced.cost_basis_in_portfolio_currency == D("10.000")


def test_the_rates_built_after_the_refresh_reach_the_valuation(
    service: PositionService,
    portfolios: MagicMock,
    position_repo: MagicMock,
    fx_builder: MagicMock,
) -> None:
    portfolios.get_owned_by_name.return_value = SimpleNamespace(
        id=1, base_currency_id=1, cash_balance=D("0"), total_deposited=D("0")
    )
    position_repo.list_by_portfolio.return_value = [_position(1, "10", currency_id=2)]
    fx_builder.build.return_value = {(2, 1): D("4.32")}

    [position] = service.list_valued(7, "Main")

    assert position.rate_missing is False
    assert position.market_value == D("43.200")
