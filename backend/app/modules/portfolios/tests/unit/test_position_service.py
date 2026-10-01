from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, call

import pytest

from app.modules.portfolios.domain import PortfolioValuator
from app.modules.portfolios.exceptions import PortfolioNotFoundError
from app.modules.portfolios.services.positions import PositionService

D = Decimal
NOW = datetime(2026, 1, 2, tzinfo=UTC)


def _position(position_id: int, current_price: str) -> SimpleNamespace:
    currency = SimpleNamespace(
        id=1, code="PLN", exchange_rate=D("1"), base_currency_id=None
    )
    asset = SimpleNamespace(
        id=position_id * 10,
        ticker=f"T{position_id}",
        name="Asset",
        asset_class=SimpleNamespace(id=1, name="Stock"),
        currency=currency,
        currency_id=1,
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
def market_data() -> MagicMock:
    return MagicMock()


@pytest.fixture
def service(
    portfolios: MagicMock, position_repo: MagicMock, market_data: MagicMock
) -> PositionService:
    return PositionService(portfolios, position_repo, market_data, PortfolioValuator())


def test_refresh_valued_refreshes_market_data_then_values_in_the_given_order(
    service: PositionService,
    portfolios: MagicMock,
    position_repo: MagicMock,
    market_data: MagicMock,
) -> None:
    portfolios.get_owned_by_name.return_value = SimpleNamespace(
        id=1,
        base_currency_id=1,
        base_currency=SimpleNamespace(exchange_rate=D("1")),
        cash_balance=D("80"),
        total_deposited=D("100"),
    )
    positions = [_position(2, "12"), _position(1, "8")]
    position_repo.list_by_portfolio.return_value = positions
    order = MagicMock()
    order.attach_mock(market_data.refresh_currency_rates, "rates")
    order.attach_mock(position_repo.list_by_portfolio, "positions")
    order.attach_mock(market_data.refresh_asset_prices, "prices")

    result = service.refresh_valued(7, "Main")

    portfolios.get_owned_by_name.assert_called_once_with(7, "Main")
    # Prices are refreshed, then the positions are read again for the valuation.
    assert [c[0] for c in order.mock_calls] == [
        "rates",
        "positions",
        "prices",
        "positions",
    ]
    assert order.mock_calls[1] == call.positions(1)
    refreshed = list(market_data.refresh_asset_prices.call_args.args[0])
    assert refreshed == [positions[0].asset, positions[1].asset]
    assert [p.id for p in result] == [2, 1]
    assert [p.market_value for p in result] == [D("12.000"), D("8.000")]
    # total value = cash 80 + 12 + 8
    assert [p.portfolio_weight_pct for p in result] == [D("12.0000"), D("8.0000")]


def test_list_valued_is_a_pure_read(
    service: PositionService,
    portfolios: MagicMock,
    position_repo: MagicMock,
    market_data: MagicMock,
) -> None:
    portfolios.get_owned_by_name.return_value = SimpleNamespace(
        id=1,
        base_currency_id=1,
        base_currency=SimpleNamespace(exchange_rate=D("1")),
        cash_balance=D("80"),
        total_deposited=D("100"),
    )
    position_repo.list_by_portfolio.return_value = [_position(2, "12")]

    result = service.list_valued(7, "Main")

    assert [p.id for p in result] == [2]
    market_data.refresh_currency_rates.assert_not_called()
    market_data.refresh_asset_prices.assert_not_called()


def test_unknown_portfolio_name_is_404_before_any_refresh(
    service: PositionService, portfolios: MagicMock, market_data: MagicMock
) -> None:
    portfolios.get_owned_by_name.side_effect = PortfolioNotFoundError

    with pytest.raises(PortfolioNotFoundError):
        service.refresh_valued(7, "Nope")

    market_data.refresh_currency_rates.assert_not_called()
