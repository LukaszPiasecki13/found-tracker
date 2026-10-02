"""Cross rates between currencies, for valuing positions quoted abroad.

`assets` stores every currency's rate as "units of the system currency (USD)
per one unit" (`MarketDataService.refresh_currency_rates`), so the rate that
turns one unit of currency `from` into currency `to` is `rate[from] / rate[to]`.
Not stored anywhere: composed here, read-only, for the valuation.

Until currencies get a rate history (ADR-0015) a stored rate of exactly 1 on a
currency other than USD is the column default, not a quote: such a currency
has no rate, and a position that needs it is valued as "rate missing" instead
of silently at 1.
"""

from collections.abc import Iterable
from decimal import Decimal

from app.modules.assets.constants import DEFAULT_CURRENCY_CODE
from app.modules.assets.services.currencies import CurrencyService
from app.modules.portfolios.domain import FxMap

_ONE = Decimal("1")


def _usd_rate(code: str, stored_rate: Decimal) -> Decimal | None:
    """USD per one unit of the currency, or `None` when it has no quote."""
    if code == DEFAULT_CURRENCY_CODE:
        return _ONE
    if stored_rate > 0 and stored_rate != _ONE:
        return stored_rate
    return None


class FxMapBuilder:
    """Builds the `(from currency id, to currency id) -> rate` map a valuation
    needs. One `CurrencyService` read per `build`; nothing is committed."""

    def __init__(self, currency_service: CurrencyService) -> None:
        self._currencies = currency_service

    def build(self, base_currency_ids: Iterable[int]) -> FxMap:
        """Rates into each of the given base currencies, from every other
        currency that has a rate. A base without a rate gets none."""
        bases = set(base_currency_ids)
        usd_rates = {}
        for currency in self._currencies.list_currencies():
            rate = _usd_rate(currency.code, currency.exchange_rate)
            if rate is not None:
                usd_rates[currency.id] = rate
        return {
            (source, base): usd_rates[source] / usd_rates[base]
            for base in bases
            if base in usd_rates
            for source in usd_rates
            if source != base
        }
