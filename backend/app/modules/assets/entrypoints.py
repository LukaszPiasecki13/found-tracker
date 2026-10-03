"""Operations on `assets` that run outside an HTTP request (ADR-0002): the
scheduled and manual refreshes of prices and exchange rates.

The only place of this module that opens a session outside a request. Both jobs
are idempotent for daily closes: a second run on the same day rewrites the same
rows (the cached current price and rate are overwritten with the newest value).
HTTP requests never call the provider except through `refresh_prices`, started
as a background task by `POST /assets/refresh-prices`.
"""

from collections.abc import Sequence

from app.core.dependencies import session_scope
from app.modules.assets.wiring import build_asset_service, build_market_data_service


def refresh_prices(asset_ids: Sequence[int] | None = None) -> int:
    """Store today's provider price of the given assets, or of every active
    (non-archived) asset when `asset_ids` is `None`; returns how many were stored.

    Best-effort per asset: a failing ticker is logged and skipped.
    """
    with session_scope() as session:
        assets = build_asset_service(session)
        market_data = build_market_data_service(session)
        selected = (
            assets.list_assets()
            if asset_ids is None
            else assets.list_by_ids(list(asset_ids))
        )
        return market_data.refresh_asset_prices(selected)


def refresh_fx_rates() -> int:
    """Store today's provider rate of every currency to the system currency;
    returns how many currencies were updated."""
    with session_scope() as session:
        return build_market_data_service(session).refresh_currency_rates()
