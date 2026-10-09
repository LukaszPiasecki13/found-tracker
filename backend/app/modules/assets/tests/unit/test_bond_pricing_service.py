"""`BondPricingService.refresh_bond_prices` must commit in one transaction
(ADR-0001), isolating one bond's failure from the rest via a savepoint.

`price_repo` wires a real `SQLRepository.transaction()`/`savepoint()` to a
mocked session (see `conftest.py`), so `session.commit` reflects what the
service actually did - this is the exact gap that let a missing
`transaction()` call ship silently (every unit test mocked the repo calls
wholesale instead)."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.assets.services.bond_pricing import BondPricingService

TODAY = date(2027, 10, 7)

EDO_TERMS = SimpleNamespace(
    bond_symbol="EDO",
    series_code="EDO1036",
    nominal_value=Decimal("100.00"),
    issue_date=date(2026, 10, 1),
    maturity_date=date(2036, 10, 1),
    capitalization="annual",
    first_period_rate=Decimal("5.35"),
    reference_type="cpi",
    margin=Decimal("2.00"),
    redemption_fee=Decimal("3.00"),
)


@pytest.fixture
def bond_data() -> MagicMock:
    mock = MagicMock()
    mock.find_terms.return_value = EDO_TERMS
    return mock


@pytest.fixture
def assets() -> MagicMock:
    return MagicMock()


@pytest.fixture
def service(
    bond_data: MagicMock, price_repo: MagicMock, assets: MagicMock
) -> BondPricingService:
    return BondPricingService(bond_data, price_repo, assets)


def _bond_asset(asset_id: int = 1, currency_id: int = 7) -> SimpleNamespace:
    return SimpleNamespace(
        id=asset_id, currency_id=currency_id, current_price=Decimal("0")
    )


def test_refresh_bond_prices_commits_in_one_transaction(
    service: BondPricingService,
    price_repo: MagicMock,
    assets: MagicMock,
    session: MagicMock,
) -> None:
    bond = _bond_asset()

    ok = service.refresh_bond_prices([bond], TODAY)

    assert ok == 1
    price_repo.upsert.assert_called_once()
    _, kwargs = price_repo.upsert.call_args
    assert kwargs["asset_id"] == 1
    assert kwargs["source"] == "bonds"
    assert kwargs["is_synthetic"] is True
    assert bond.current_price > Decimal("0")
    assets.persist.assert_called_once_with(bond)
    session.commit.assert_called_once()
    session.rollback.assert_not_called()


def test_refresh_bond_prices_skips_bonds_without_registered_terms(
    service: BondPricingService,
    bond_data: MagicMock,
    price_repo: MagicMock,
    session: MagicMock,
) -> None:
    bond_data.find_terms.return_value = None
    bond = _bond_asset()

    assert service.refresh_bond_prices([bond], TODAY) == 0

    price_repo.upsert.assert_not_called()
    session.commit.assert_called_once()  # empty transaction still commits


def test_refresh_bond_prices_one_failure_does_not_lose_the_others(
    service: BondPricingService,
    bond_data: MagicMock,
    price_repo: MagicMock,
    session: MagicMock,
) -> None:
    broken_terms = SimpleNamespace(**{**vars(EDO_TERMS), "first_period_rate": None})
    bond_data.find_terms.side_effect = [broken_terms, EDO_TERMS]
    broken, healthy = _bond_asset(1), _bond_asset(2)

    ok = service.refresh_bond_prices([broken, healthy], TODAY)

    assert ok == 1
    price_repo.upsert.assert_called_once()
    session.commit.assert_called_once()
    session.rollback.assert_not_called()  # savepoint absorbs it, not the outer tx
