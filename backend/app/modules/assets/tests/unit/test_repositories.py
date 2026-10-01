from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.core.errors import NotFoundError
from app.modules.assets.models import Asset, AssetClass, Currency
from app.modules.assets.repositories import (
    AssetClassRepository,
    AssetRepository,
    CurrencyRepository,
)


def _session_finding(result: object) -> MagicMock:
    session = MagicMock()
    session.execute.return_value.scalar_one_or_none.return_value = result
    return session


@pytest.mark.parametrize(
    ("repository_class", "code"),
    [
        (AssetRepository, "ASSET_NOT_FOUND"),
        (AssetClassRepository, "ASSET_CLASS_NOT_FOUND"),
        (CurrencyRepository, "CURRENCY_NOT_FOUND"),
    ],
)
def test_get_by_id_raises_not_found_with_code(
    repository_class: type, code: str
) -> None:
    repository = repository_class(_session_finding(None))

    with pytest.raises(NotFoundError) as exc_info:
        repository.get_by_id(1)

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == code


@pytest.mark.parametrize(
    "repository_class", [AssetRepository, AssetClassRepository, CurrencyRepository]
)
def test_find_by_id_returns_none_when_missing(repository_class: type) -> None:
    assert repository_class(_session_finding(None)).find_by_id(1) is None


def test_asset_create_adds_flushes_and_refreshes_without_committing() -> None:
    session = MagicMock()

    asset = AssetRepository(session).create(
        ticker="AAPL", name="Apple", asset_class_id=1, currency_id=2
    )

    assert isinstance(asset, Asset)
    assert (asset.ticker, asset.current_price) == ("AAPL", Decimal("0"))
    session.add.assert_called_once_with(asset)
    session.flush.assert_called_once()
    session.refresh.assert_called_once_with(asset)
    session.commit.assert_not_called()


def test_asset_class_create_adds_and_flushes_without_committing() -> None:
    session = MagicMock()

    asset_class = AssetClassRepository(session).create("ETF")

    assert isinstance(asset_class, AssetClass)
    session.add.assert_called_once_with(asset_class)
    session.flush.assert_called_once()
    session.commit.assert_not_called()


def test_currency_create_defaults_to_rate_one_without_committing() -> None:
    session = MagicMock()

    currency = CurrencyRepository(session).create(code="EUR")

    assert isinstance(currency, Currency)
    assert currency.exchange_rate == Decimal("1")
    assert currency.base_currency_id is None
    session.flush.assert_called_once()
    session.commit.assert_not_called()


@pytest.mark.parametrize(
    "repository_class", [AssetRepository, AssetClassRepository, CurrencyRepository]
)
def test_delete_flushes_so_reference_violations_surface_inside_the_transaction(
    repository_class: type,
) -> None:
    session = MagicMock()
    entity = object()

    repository_class(session).delete(entity)

    session.delete.assert_called_once_with(entity)
    session.flush.assert_called_once()
    session.commit.assert_not_called()


def test_find_by_ticker_does_not_normalize() -> None:
    """Normalization belongs to the service; the repository matches exactly."""
    session = _session_finding(None)

    AssetRepository(session).find_by_ticker("aapl")

    statement = session.execute.call_args.args[0]
    assert statement.compile().params == {"ticker_1": "aapl"}
