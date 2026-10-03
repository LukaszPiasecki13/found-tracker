import { useMemo } from "react";
import { PortfolioOverview } from "../components/portfolio-overview";
import PocketsList from "../components/PocketsList";
import { Alert, Box, Typography, Divider } from "@mui/material";
import { useCurrencies, usePockets } from "../hooks/usePockets";
import type { Pocket } from "../types/api";

export default function DashboardPage() {
  const { data: pockets, isLoading: pocketsLoading } = usePockets();
  const { data: currencies, isLoading: currenciesLoading } = useCurrencies();
  const isLoading = pocketsLoading || currenciesLoading;

  // Totals are shown in PLN (the overview's display currency). Currency rates are
  // quoted against USD, so a pocket's amount converts via base rate / PLN rate.
  const plnRate = Number(currencies?.find((c) => c.code === 'PLN')?.exchange_rate) || 0;
  const rateUnavailable = !!currencies && plnRate <= 0;

  // A portfolio with a position lacking a currency rate has no value/profit (null). It is
  // left out of every sum (value, deposits and profit alike) so the percentage stays consistent.
  const unvaluedCount = pockets?.filter((pocket) => pocket.rate_missing === true).length ?? 0;

  const totalMetrics = useMemo(() => {
    const empty = { totalValue: 0, totalDeposited: 0, totalProfit: 0, pocketCount: 0 };
    if (!pockets) return empty;
    const pocketCount = pockets.length;
    if (plnRate <= 0) return { ...empty, pocketCount };

    const valued = pockets.filter((pocket) => pocket.rate_missing !== true);
    const sum = (pick: (pocket: Pocket) => number | null | undefined) =>
      valued.reduce((total, pocket) => {
        const baseRate = Number(pocket.base_currency.exchange_rate) || 0;
        return total + (Number(pick(pocket)) || 0) * (baseRate / plnRate);
      }, 0);

    return {
      totalValue: sum((pocket) => pocket.total_value ?? pocket.cash_balance),
      totalDeposited: sum((pocket) => pocket.total_deposited),
      totalProfit: sum((pocket) => pocket.total_profit_loss),
      pocketCount,
    };
  }, [pockets, plnRate]);

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Dashboard
      </Typography>

      {rateUnavailable && (
        <Alert severity="error" sx={{ mb: 2 }}>
          Brak kursu PLN — nie można przeliczyć sum portfeli na złote.
        </Alert>
      )}
      {unvaluedCount > 0 && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          Liczba portfeli z pozycjami bez kursu waluty: {unvaluedCount} — nie są wliczone do sum poniżej.
        </Alert>
      )}

      <PortfolioOverview
        totalValue={totalMetrics.totalValue}
        totalProfit={totalMetrics.totalProfit}
        investedCapital={totalMetrics.totalDeposited}
        positionsCount={totalMetrics.pocketCount}
        isLoading={isLoading}
      />

      <Divider sx={{ my: 4 }} />

      <PocketsList />
    </Box>
  );
}
