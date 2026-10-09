"""Operations on `assets` that run outside an HTTP request (ADR-0002): the
scheduled and manual refreshes of prices and exchange rates.

Each takes the `SessionScope` to run in (default: the real one), so tests and a
future CLI driver share the same functions. Both jobs are idempotent for daily
closes: a second run on the same day rewrites the same rows (the cached current
price and rate are overwritten with the newest value). A failing ticker or
currency is counted in `failed` and never stops the rest. HTTP requests never
call the provider except through `refresh_prices`, started as a background task
by `POST /assets/refresh-prices`.
"""

from collections.abc import Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from app.core.dependencies import SessionScope, session_scope
from app.core.errors import BondDataUnavailableError
from app.modules.assets import wiring as assets_wiring
from app.modules.assets.constants import SOURCE_BONDS
from app.modules.assets.repositories.assets import AssetRepository
from app.modules.assets.wiring import (
    build_asset_service,
    build_bond_data_service,
    build_bond_pricing_service,
    build_currency_service,
    build_daily_refresh_service,
    build_market_data_service,
)


@dataclass(frozen=True, slots=True)
class RefreshResult:
    """How many items were stored (`ok`) and how many were skipped (`failed`:
    no quote, provider outage, unusable value)."""

    ok: int
    failed: int


def refresh_prices(
    asset_ids: Sequence[int] | None = None, scope: SessionScope = session_scope
) -> RefreshResult:
    """Store today's provider price of the given assets, or of every active
    (non-archived) asset when `asset_ids` is `None`. Archived assets are left out
    of both counts."""
    with scope() as session:
        assets = build_asset_service(session)
        market_data = build_market_data_service(session)
        selected = (
            assets.list_assets()
            if asset_ids is None
            else assets.list_by_ids(list(asset_ids))
        )
        active = [asset for asset in selected if asset.archived_at is None]
        ok = market_data.refresh_asset_prices(active)
        return RefreshResult(ok=ok, failed=len(active) - ok)


def refresh_fx_rates(scope: SessionScope = session_scope) -> RefreshResult:
    """Store today's provider rate of every currency to the system currency (the
    system currency itself counts as `ok`)."""
    with scope() as session:
        market_data = build_market_data_service(session)
        total = len(market_data.list_currency_codes())
        ok = market_data.refresh_currency_rates()
        return RefreshResult(ok=ok, failed=total - ok)


def sync_bond_terms(
    asset_ids: Sequence[int] | None = None, scope: SessionScope = session_scope
) -> RefreshResult:
    """Fetch bond series terms from the provider for bond assets that have no
    manually-entered terms (`source="manual"` always wins and is never
    overwritten automatically). A series the provider does not know about is
    skipped, not an error; a provider outage counts every selected bond as
    failed rather than stopping the run."""
    with scope() as session:
        assets = build_asset_service(session)
        bond_data = build_bond_data_service(session)
        provider = assets_wiring.build_bond_data_provider()
        selected = (
            assets.list_assets()
            if asset_ids is None
            else assets.list_by_ids(list(asset_ids))
        )
        active_bonds = [
            a for a in selected if a.archived_at is None and a.asset_type == "bond"
        ]
        ok = 0
        for bond_asset in active_bonds:
            existing = bond_data.find_terms(bond_asset.id)
            if existing is not None and existing.source == "manual":
                ok += 1  # already has authoritative terms, nothing to do
                continue
            try:
                terms = provider.fetch_series(bond_asset.ticker)
            except BondDataUnavailableError:
                continue
            if terms is None:
                continue
            bond_data.register_series(
                asset_id=bond_asset.id,
                bond_symbol=terms.bond_symbol,
                series_code=terms.series_code,
                nominal_value=terms.nominal_value,
                issue_date=terms.issue_date,
                maturity_date=terms.maturity_date,
                capitalization=terms.capitalization,
                first_period_rate=terms.first_period_rate,
                reference_type=terms.reference_type,
                margin=terms.margin,
                redemption_fee=terms.redemption_fee,
                source=SOURCE_BONDS,
                fetched_at=datetime.now(UTC),
            )
            ok += 1
        return RefreshResult(ok=ok, failed=len(active_bonds) - ok)


def refresh_bond_prices(
    asset_ids: Sequence[int] | None = None, scope: SessionScope = session_scope
) -> RefreshResult:
    """Calculate and store today's synthetic prices for registered bonds.

    For each non-archived bond asset:
    1. Load BondTerms (skip if missing)
    2. Calculate accrual coefficient (skip on error). Each capitalization
       year looks up its own CPI reading from the provider's full history
       (falls back to the margin alone for a year with no reading, per
       `accrue_interest`). The NBP reference rate is not fetched here:
       ROR/DOR (the only types that key off it) pay their coupon out in
       cash rather than capitalizing it into price, so `accrue_interest`
       never consumes it for pricing.
    3. Store synthetic price = nominal * coefficient to assets_price
    4. Update Asset.current_price cache

    Each bond contributes to the count only if all steps succeed.
    """
    with scope() as session:
        assets = build_asset_service(session)
        bond_pricing = build_bond_pricing_service(session)
        provider = assets_wiring.build_bond_data_provider()
        selected = (
            assets.list_assets()
            if asset_ids is None
            else assets.list_by_ids(list(asset_ids))
        )
        # Filter for active bonds (not archived, asset_type="bond")
        active_bonds = [
            a for a in selected if a.archived_at is None and a.asset_type == "bond"
        ]
        cpi_history: dict[date, Decimal] | None = None
        with suppress(BondDataUnavailableError):
            cpi_history = provider.fetch_cpi_history()  # None on outage
        ok = bond_pricing.refresh_bond_prices(
            active_bonds, date.today(), cpi_history=cpi_history
        )
        return RefreshResult(ok=ok, failed=len(active_bonds) - ok)


def daily_refresh(scope: SessionScope = session_scope) -> None:
    """The day's job (ADR-0017): today's FX rates, stock/ETF prices, bond
    series terms, and bond prices, then the run is marked finished. A failed
    run is not marked finished and may be started again after
    `STALE_RUN_AFTER`; a rerun rewrites the same rows."""
    day = date.today()
    refresh_fx_rates(scope)
    refresh_prices(None, scope)
    sync_bond_terms(None, scope)
    refresh_bond_prices(None, scope)
    with scope() as session:
        build_daily_refresh_service(session).finish(day)


@dataclass(frozen=True, slots=True)
class SeedBenchmarkAssetsResult:
    """Result of seeding benchmark assets."""

    asset_ids: list[int]


def seed_benchmark_assets(
    scope: SessionScope = session_scope,
) -> SeedBenchmarkAssetsResult:
    """Create three benchmark assets (S&P500, Nasdaq-100, WIG20) if they don't
    exist. Each is created with asset_type="index" and the currency from the
    market-data provider; only when the provider has no quote does it fall back
    to the currency named per ticker below. Idempotent: existing assets are
    left unchanged."""
    # Ticker, asset class name, fallback currency code (used only if the
    # provider has no quote for the ticker at seed time).
    benchmark_specs = [
        ("^GSPC", "Index", "USD"),  # S&P500
        ("^NDX", "Index", "USD"),  # Nasdaq-100
        ("ETFBW20TR.WA", "Index", "PLN"),  # WIG20 proxy, listed on the GPW
    ]
    asset_ids = []
    with scope() as session:
        asset_service = build_asset_service(session)
        asset_repo = AssetRepository(session)
        currency_service = build_currency_service(session)
        with asset_repo.transaction():
            for ticker, asset_class_name, fallback_currency_code in benchmark_specs:
                fallback_currency_id = currency_service.get_or_create_by_code(
                    fallback_currency_code
                ).id
                asset = asset_service.get_or_create_by_ticker(
                    ticker,
                    asset_class_name=asset_class_name,
                    fallback_currency_id=fallback_currency_id,
                )
                if asset.asset_type != "index":
                    asset.asset_type = "index"
                    asset_repo.update(asset)
                asset_ids.append(asset.id)
    return SeedBenchmarkAssetsResult(asset_ids=asset_ids)
