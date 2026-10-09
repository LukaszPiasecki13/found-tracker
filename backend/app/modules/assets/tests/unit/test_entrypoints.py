"""`assets.entrypoints`: the non-HTTP refresh jobs run in the given session scope
(ADR-0002), delegate to the services and report `ok`/`failed`; no commit here."""

from contextlib import contextmanager, nullcontext
from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.assets import entrypoints
from app.modules.assets import wiring as assets_wiring
from app.modules.assets.entrypoints import RefreshResult


class Scope:
    """A `SessionScope` double that records how often it was opened."""

    def __init__(self) -> None:
        self.session = MagicMock()
        self.opened = 0

    @contextmanager
    def __call__(self):
        self.opened += 1
        yield self.session


@pytest.fixture
def scope() -> Scope:
    return Scope()


@pytest.fixture
def services(monkeypatch: pytest.MonkeyPatch) -> tuple[MagicMock, MagicMock]:
    assets, market_data = MagicMock(), MagicMock()
    monkeypatch.setattr(entrypoints, "build_asset_service", lambda session: assets)
    monkeypatch.setattr(
        entrypoints, "build_market_data_service", lambda session: market_data
    )
    return assets, market_data


def _asset(archived: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        archived_at=datetime(2026, 1, 1, tzinfo=UTC) if archived else None
    )


def test_refresh_prices_of_given_ids_loads_them_and_counts_the_outcome(
    scope: Scope, services: tuple[MagicMock, MagicMock]
) -> None:
    assets, market_data = services
    loaded = [_asset(), _asset(), _asset()]
    assets.list_by_ids.return_value = loaded
    market_data.refresh_asset_prices.return_value = 2

    result = entrypoints.refresh_prices([4, 5, 6], scope)

    assert result == RefreshResult(ok=2, failed=1)
    assets.list_by_ids.assert_called_once_with([4, 5, 6])
    market_data.refresh_asset_prices.assert_called_once_with(loaded)
    scope.session.commit.assert_not_called()
    assert scope.opened == 1


def test_refresh_prices_without_ids_takes_every_active_asset(
    scope: Scope, services: tuple[MagicMock, MagicMock]
) -> None:
    assets, market_data = services
    active = [_asset()]
    assets.list_assets.return_value = active
    market_data.refresh_asset_prices.return_value = 1

    assert entrypoints.refresh_prices(None, scope) == RefreshResult(ok=1, failed=0)

    assets.list_assets.assert_called_once_with()
    assets.list_by_ids.assert_not_called()
    market_data.refresh_asset_prices.assert_called_once_with(active)


def test_archived_assets_are_not_refreshed_nor_counted_as_failures(
    scope: Scope, services: tuple[MagicMock, MagicMock]
) -> None:
    assets, market_data = services
    live = _asset()
    assets.list_by_ids.return_value = [live, _asset(archived=True)]
    market_data.refresh_asset_prices.return_value = 1

    result = entrypoints.refresh_prices([1, 2], scope)

    assert result == RefreshResult(ok=1, failed=0)
    market_data.refresh_asset_prices.assert_called_once_with([live])


def test_refresh_fx_rates_counts_currencies_without_a_rate_as_failed(
    scope: Scope, services: tuple[MagicMock, MagicMock]
) -> None:
    _, market_data = services
    market_data.list_currency_codes.return_value = ["USD", "EUR", "XXX"]
    market_data.refresh_currency_rates.return_value = 2

    result = entrypoints.refresh_fx_rates(scope)

    assert result == RefreshResult(ok=2, failed=1)
    market_data.refresh_currency_rates.assert_called_once_with()
    scope.session.commit.assert_not_called()
    assert scope.opened == 1


def _bond_asset(
    asset_id: int = 1, asset_type: str = "bond", archived: bool = False
) -> SimpleNamespace:
    """Helper to create a bond asset mock."""
    return SimpleNamespace(
        id=asset_id,
        ticker=f"BOND{asset_id}",
        asset_type=asset_type,
        archived_at=datetime(2026, 1, 1, tzinfo=UTC) if archived else None,
    )


@pytest.fixture
def bond_provider(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mocked `BondDataProvider` - without this, the entrypoint would build
    the real `BondDataProviderImpl` and hit the live network."""
    provider = MagicMock()
    provider.fetch_cpi_history.return_value = {}
    monkeypatch.setattr(assets_wiring, "build_bond_data_provider", lambda: provider)
    return provider


def test_refresh_bond_prices_filters_for_bonds_only(
    scope: Scope, monkeypatch: pytest.MonkeyPatch, bond_provider: MagicMock
) -> None:
    """Bond price refresh processes only non-archived bonds (asset_type='bond')."""
    assets_service = MagicMock()
    bond_pricing = MagicMock()

    monkeypatch.setattr(
        entrypoints, "build_asset_service", lambda session: assets_service
    )
    monkeypatch.setattr(
        entrypoints, "build_bond_pricing_service", lambda session: bond_pricing
    )

    # Mix of stock, bond, and archived assets
    assets = [
        _bond_asset(asset_type="bond"),  # Active bond
        _bond_asset(asset_type="stock"),  # Stock (not a bond)
        _bond_asset(asset_type="bond", archived=True),  # Archived bond
    ]
    assets_service.list_assets.return_value = assets
    bond_pricing.refresh_bond_prices.return_value = 1

    result = entrypoints.refresh_bond_prices(None, scope)

    # Only the first asset (active bond) should be processed
    assert result == RefreshResult(ok=1, failed=0)
    bond_pricing.refresh_bond_prices.assert_called_once()
    called_bonds = bond_pricing.refresh_bond_prices.call_args[0][0]
    assert len(called_bonds) == 1
    assert called_bonds[0].asset_type == "bond"
    assert called_bonds[0].archived_at is None


def test_refresh_bond_prices_with_specific_ids(
    scope: Scope, monkeypatch: pytest.MonkeyPatch, bond_provider: MagicMock
) -> None:
    """Bond price refresh can target specific asset IDs."""
    assets_service = MagicMock()
    bond_pricing = MagicMock()

    monkeypatch.setattr(
        entrypoints, "build_asset_service", lambda session: assets_service
    )
    monkeypatch.setattr(
        entrypoints, "build_bond_pricing_service", lambda session: bond_pricing
    )

    loaded = [_bond_asset(asset_type="bond"), _bond_asset(asset_type="bond")]
    assets_service.list_by_ids.return_value = loaded
    bond_pricing.refresh_bond_prices.return_value = 2

    result = entrypoints.refresh_bond_prices([42, 43], scope)

    assert result == RefreshResult(ok=2, failed=0)
    assets_service.list_by_ids.assert_called_once_with([42, 43])
    # Verify bond_pricing.refresh_bond_prices was called with loaded bonds and a date
    assert bond_pricing.refresh_bond_prices.call_count == 1
    call_args = bond_pricing.refresh_bond_prices.call_args[0]
    assert call_args[0] == loaded  # First arg: bonds list
    assert isinstance(call_args[1], date)  # Second arg: as_of date


def test_refresh_bond_prices_counts_failures(
    scope: Scope, monkeypatch: pytest.MonkeyPatch, bond_provider: MagicMock
) -> None:
    """Bond price refresh reports how many bonds failed (missing terms, calc error)."""
    assets_service = MagicMock()
    bond_pricing = MagicMock()

    monkeypatch.setattr(
        entrypoints, "build_asset_service", lambda session: assets_service
    )
    monkeypatch.setattr(
        entrypoints, "build_bond_pricing_service", lambda session: bond_pricing
    )

    bonds = [_bond_asset(asset_type="bond") for _ in range(5)]
    assets_service.list_assets.return_value = bonds
    bond_pricing.refresh_bond_prices.return_value = 3  # 3 succeeded, 2 failed

    result = entrypoints.refresh_bond_prices(None, scope)

    assert result == RefreshResult(ok=3, failed=2)
    # Verify bond_pricing.refresh_bond_prices was called with bonds and a date
    assert bond_pricing.refresh_bond_prices.call_count == 1
    call_args = bond_pricing.refresh_bond_prices.call_args[0]
    assert call_args[0] == bonds  # First arg: bonds list


def _fetched_terms(**overrides: object) -> SimpleNamespace:
    base = {
        "bond_symbol": "EDO",
        "series_code": "BOND1",
        "nominal_value": 100,
        "issue_date": date(2026, 10, 1),
        "maturity_date": date(2036, 10, 1),
        "capitalization": "annual",
        "first_period_rate": 5.35,
        "reference_type": "cpi",
        "margin": 2.0,
        "redemption_fee": 3.0,
    }
    return SimpleNamespace(**(base | overrides))


def test_sync_bond_terms_registers_from_provider_when_none_exist(
    scope: Scope, monkeypatch: pytest.MonkeyPatch
) -> None:
    assets_service, bond_data, provider = MagicMock(), MagicMock(), MagicMock()
    monkeypatch.setattr(
        entrypoints, "build_asset_service", lambda session: assets_service
    )
    monkeypatch.setattr(
        entrypoints, "build_bond_data_service", lambda session: bond_data
    )
    monkeypatch.setattr(assets_wiring, "build_bond_data_provider", lambda: provider)

    bond = _bond_asset(asset_id=1)
    assets_service.list_assets.return_value = [bond]
    bond_data.find_terms.return_value = None
    provider.fetch_series.return_value = _fetched_terms()

    result = entrypoints.sync_bond_terms(None, scope)

    assert result == RefreshResult(ok=1, failed=0)
    provider.fetch_series.assert_called_once_with("BOND1")
    bond_data.register_series.assert_called_once()
    _, kwargs = bond_data.register_series.call_args
    assert kwargs["asset_id"] == 1
    assert kwargs["source"] == "bonds"
    assert kwargs["fetched_at"] is not None


def test_sync_bond_terms_never_overwrites_a_manual_override(
    scope: Scope, monkeypatch: pytest.MonkeyPatch
) -> None:
    assets_service, bond_data, provider = MagicMock(), MagicMock(), MagicMock()
    monkeypatch.setattr(
        entrypoints, "build_asset_service", lambda session: assets_service
    )
    monkeypatch.setattr(
        entrypoints, "build_bond_data_service", lambda session: bond_data
    )
    monkeypatch.setattr(assets_wiring, "build_bond_data_provider", lambda: provider)

    bond = _bond_asset(asset_id=1)
    assets_service.list_assets.return_value = [bond]
    bond_data.find_terms.return_value = SimpleNamespace(source="manual")

    result = entrypoints.sync_bond_terms(None, scope)

    assert result == RefreshResult(ok=1, failed=0)
    provider.fetch_series.assert_not_called()
    bond_data.register_series.assert_not_called()


def test_sync_bond_terms_counts_unknown_series_as_failed(
    scope: Scope, monkeypatch: pytest.MonkeyPatch
) -> None:
    assets_service, bond_data, provider = MagicMock(), MagicMock(), MagicMock()
    monkeypatch.setattr(
        entrypoints, "build_asset_service", lambda session: assets_service
    )
    monkeypatch.setattr(
        entrypoints, "build_bond_data_service", lambda session: bond_data
    )
    monkeypatch.setattr(assets_wiring, "build_bond_data_provider", lambda: provider)

    bond = _bond_asset(asset_id=1)
    assets_service.list_assets.return_value = [bond]
    bond_data.find_terms.return_value = None
    provider.fetch_series.return_value = None  # feed has no such series

    result = entrypoints.sync_bond_terms(None, scope)

    assert result == RefreshResult(ok=0, failed=1)
    bond_data.register_series.assert_not_called()


# --- seed_benchmark_assets (benchmark comparison) ---


def test_seed_benchmark_assets_creates_and_commits_three_index_assets(
    scope: Scope, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-02: seeding writes under one transaction (the function's own session
    scope never commits by itself) and tags every benchmark `asset_type="index"`."""
    asset_service, currency_service, asset_repo = MagicMock(), MagicMock(), MagicMock()
    asset_repo.transaction.return_value = nullcontext()
    monkeypatch.setattr(
        entrypoints, "build_asset_service", lambda session: asset_service
    )
    monkeypatch.setattr(
        entrypoints, "build_currency_service", lambda session: currency_service
    )
    monkeypatch.setattr(entrypoints, "AssetRepository", lambda session: asset_repo)
    currency_service.get_or_create_by_code.side_effect = lambda code: SimpleNamespace(
        id={"USD": 1, "PLN": 2}[code]
    )
    created = {
        "^GSPC": SimpleNamespace(id=10, asset_type="stock"),
        "^NDX": SimpleNamespace(id=11, asset_type="stock"),
        # Already correctly tagged from a prior run - must stay idempotent.
        "ETFBW20TR.WA": SimpleNamespace(id=12, asset_type="index"),
    }
    asset_service.get_or_create_by_ticker.side_effect = lambda ticker, **kwargs: (
        created[ticker]
    )

    result = entrypoints.seed_benchmark_assets(scope)

    asset_repo.transaction.assert_called_once()
    assert result.asset_ids == [10, 11, 12]
    assert created["^GSPC"].asset_type == "index"
    assert created["^NDX"].asset_type == "index"
    # Only the two that needed fixing go through `update`.
    assert asset_repo.update.call_count == 2
    asset_service.get_or_create_by_ticker.assert_any_call(
        "^GSPC", asset_class_name="Index", fallback_currency_id=1
    )
    asset_service.get_or_create_by_ticker.assert_any_call(
        "ETFBW20TR.WA", asset_class_name="Index", fallback_currency_id=2
    )


def test_sync_bond_terms_counts_provider_outage_as_failed(
    scope: Scope, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.errors import BondDataUnavailableError

    assets_service, bond_data, provider = MagicMock(), MagicMock(), MagicMock()
    monkeypatch.setattr(
        entrypoints, "build_asset_service", lambda session: assets_service
    )
    monkeypatch.setattr(
        entrypoints, "build_bond_data_service", lambda session: bond_data
    )
    monkeypatch.setattr(assets_wiring, "build_bond_data_provider", lambda: provider)

    bond = _bond_asset(asset_id=1)
    assets_service.list_assets.return_value = [bond]
    bond_data.find_terms.return_value = None
    provider.fetch_series.side_effect = BondDataUnavailableError("down")

    result = entrypoints.sync_bond_terms(None, scope)

    assert result == RefreshResult(ok=0, failed=1)
    bond_data.register_series.assert_not_called()
