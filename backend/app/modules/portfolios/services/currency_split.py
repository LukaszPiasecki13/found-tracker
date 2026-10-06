"""Currency split of the current holdings: what the owner holds, by the currency each
part is quoted in.

A position counts in its asset's currency; a portfolio's cash counts in its base
currency. The values are the current ones (`PositionService`) and, for the account,
are converted to the account currency at the current rate. A position without a
rate is left out and counted as `unpriced`, never valued at 1.
"""

from collections import defaultdict
from decimal import Decimal

from app.modules.assets.services.currencies import CurrencyService
from app.modules.assets.services.fx_rates import FxRateService
from app.modules.portfolios.exceptions import PortfolioNotFoundError
from app.modules.portfolios.repositories.portfolios import PortfolioRepository
from app.modules.portfolios.schemas.currency_split import (
    CurrencySplitItem,
    CurrencySplitResponse,
)
from app.modules.portfolios.services.account_metrics import ACCOUNT_FALLBACK_CURRENCY
from app.modules.portfolios.services.positions import PositionService


class CurrencySplitService:
    """Read model of the currency split (ADR-0003: a DTO, no entity behind it)."""

    def __init__(
        self,
        portfolio_repo: PortfolioRepository,
        positions: PositionService,
        currencies: CurrencyService,
        fx_rates: FxRateService,
    ) -> None:
        self._portfolios = portfolio_repo
        self._positions = positions
        self._currencies = currencies
        self._fx_rates = fx_rates

    def split(
        self,
        owner_id: int,
        portfolio_name: str | None,
        base_currency_id: int | None,
    ) -> CurrencySplitResponse:
        """Raises PortfolioNotFoundError for a named portfolio the owner does not have;
        RATE_MISSING when a portfolio's currency has no rate to the display currency."""
        portfolios = self._portfolios.list_by_owner(owner_id, portfolio_name)
        if portfolio_name is not None and not portfolios:
            raise PortfolioNotFoundError
        display = (
            portfolios[0].base_currency.code
            if portfolio_name is not None and portfolios
            else self._account_currency(base_currency_id)
        )

        totals: defaultdict[str, Decimal] = defaultdict(lambda: Decimal(0))
        unpriced = 0
        for portfolio in portfolios:
            base = portfolio.base_currency.code
            rate = self._fx_rates.get_rate(base, display).rate
            held: defaultdict[str, Decimal] = defaultdict(lambda: Decimal(0))
            for position in self._positions.list_valued(owner_id, portfolio.name):
                if position.market_value is None:
                    unpriced += 1
                    continue
                held[position.asset.currency.code] += Decimal(
                    str(position.market_value)
                )
            held[base] += portfolio.cash_balance
            for code, value in held.items():
                totals[code] += value * rate

        items = [
            CurrencySplitItem(currency=code, value=float(value))
            for code, value in sorted(totals.items(), key=lambda item: -item[1])
        ]
        return CurrencySplitResponse(currency=display, items=items, unpriced=unpriced)

    def _account_currency(self, base_currency_id: int | None) -> str:
        if base_currency_id is None:
            return ACCOUNT_FALLBACK_CURRENCY
        currency = self._currencies.find_by_id(base_currency_id)
        return currency.code if currency is not None else ACCOUNT_FALLBACK_CURRENCY
