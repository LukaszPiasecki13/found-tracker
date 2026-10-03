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
from dataclasses import dataclass

from app.core.dependencies import SessionScope, session_scope
from app.modules.assets.wiring import build_asset_service, build_market_data_service


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
