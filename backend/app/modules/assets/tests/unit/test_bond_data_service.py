"""`BondDataService.register_series` must commit in one transaction (ADR-0001).

The `bond_terms_repo` fixture wires a real `SQLRepository.transaction()` to a
mocked session (see `conftest.py`), so `session.commit`/`rollback` reflect
what the service actually did - not just what a fully-mocked repo claims."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.assets.exceptions import InvalidBondTermsError
from app.modules.assets.services.bond_data import BondDataService

EDO_TERMS: dict[str, object] = {
    "asset_id": 1,
    "bond_symbol": "EDO",
    "series_code": "EDO1036",
    "nominal_value": Decimal("100.00"),
    "issue_date": date(2026, 10, 1),
    "maturity_date": date(2036, 10, 1),
    "capitalization": "annual",
    "first_period_rate": Decimal("5.35"),
    "reference_type": "cpi",
    "margin": Decimal("2.00"),
    "redemption_fee": Decimal("3.00"),
}


@pytest.fixture
def service(bond_terms_repo: MagicMock) -> BondDataService:
    return BondDataService(bond_terms_repo)


def test_register_series_commits_in_one_transaction(
    service: BondDataService, bond_terms_repo: MagicMock, session: MagicMock
) -> None:
    saved = SimpleNamespace(**EDO_TERMS)
    bond_terms_repo.upsert.return_value = saved

    assert service.register_series(**EDO_TERMS) is saved

    bond_terms_repo.upsert.assert_called_once_with(
        **EDO_TERMS, source="bonds", fetched_at=None
    )
    session.commit.assert_called_once()
    session.rollback.assert_not_called()


def test_register_series_rejects_maturity_before_issue(
    service: BondDataService, bond_terms_repo: MagicMock, session: MagicMock
) -> None:
    bad_terms = EDO_TERMS | {"maturity_date": date(2020, 1, 1)}

    with pytest.raises(
        InvalidBondTermsError, match="Maturity date must be after issue date"
    ):
        service.register_series(**bad_terms)

    bond_terms_repo.upsert.assert_not_called()
    session.commit.assert_not_called()


def test_find_terms_delegates_to_repository(
    service: BondDataService, bond_terms_repo: MagicMock
) -> None:
    bond_terms_repo.find_by_asset_id.return_value = None

    assert service.find_terms(1) is None
    bond_terms_repo.find_by_asset_id.assert_called_once_with(1)
