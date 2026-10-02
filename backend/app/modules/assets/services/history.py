"""One-off seeding of the price and FX history from the cached columns.

Data that predates `assets_price` / `assets_fx_rate` has only `current_price` and
`exchange_rate`. Until a refresh runs, every such asset would read as having no
price and no currency pair would resolve. This copies each cache that has no
history yet into one `legacy` row (lowest precedence, synthetic) so the history
starts consistent; running it again changes nothing.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from app.modules.assets.constants import DEFAULT_CURRENCY_CODE, SOURCE_LEGACY
from app.modules.assets.repositories.assets import AssetRepository
from app.modules.assets.repositories.currencies import CurrencyRepository
from app.modules.assets.repositories.fx_rates import FxRateRepository
from app.modules.assets.repositories.prices import PriceRepository


@dataclass(frozen=True, slots=True)
class BackfillResult:
    prices: int
    rates: int


class HistoryBackfillService:
    def __init__(
        self,
        asset_repository: AssetRepository,
        currency_repository: CurrencyRepository,
        price_repository: PriceRepository,
        fx_repository: FxRateRepository,
        today: Callable[[], date] = date.today,
    ) -> None:
        self._assets = asset_repository
        self._currencies = currency_repository
        self._prices = price_repository
        self._rates = fx_repository
        self._today = today

    def backfill(self) -> BackfillResult:
        """Seed history for every asset with a positive cached price and every
        non-system currency with a cached rate other than the placeholder 1, when
        it has none yet. All or nothing."""
        with self._assets.transaction():
            prices = self._backfill_prices()
            rates = self._backfill_rates()
        return BackfillResult(prices=prices, rates=rates)

    def _backfill_prices(self) -> int:
        seeded = self._prices.asset_ids_with_prices()
        count = 0
        for asset in self._assets.list_all(include_archived=True):
            if asset.id in seeded or asset.current_price <= 0:
                continue
            observed = asset.updated_at.date() if asset.updated_at else self._today()
            self._prices.upsert(
                asset_id=asset.id,
                price_date=observed,
                close=asset.current_price,
                currency_id=asset.currency_id,
                source=SOURCE_LEGACY,
                is_synthetic=True,
            )
            count += 1
        return count

    def _backfill_rates(self) -> int:
        base = self._currencies.find_by_code(DEFAULT_CURRENCY_CODE)
        if base is None:
            return 0
        seeded = self._rates.currency_ids_with_rates()
        count = 0
        for currency in self._currencies.list_all():
            # A cached 1 on a non-system currency is the column default, not a quote.
            if (
                currency.id == base.id
                or currency.id in seeded
                or currency.exchange_rate <= 0
                or currency.exchange_rate == 1
            ):
                continue
            self._rates.upsert(
                from_id=currency.id,
                to_id=base.id,
                rate_date=self._today(),
                rate=currency.exchange_rate,
                source=SOURCE_LEGACY,
                is_synthetic=True,
            )
            count += 1
        return count
