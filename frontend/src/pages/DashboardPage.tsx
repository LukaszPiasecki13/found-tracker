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
  const totalMetrics = useMemo(() => {
    if (!pockets) return { totalValue: 0, totalDeposited: 0, totalProfit: 0, pocketCount: 0 };

    const plnRate = Number(currencies?.find((c) => c.code === 'PLN')?.exchange_rate) || 0;
    const toPln = (amount: number | null | undefined, pocket: Pocket) => {
      const baseRate = Number(pocket.base_currency.exchange_rate) || 0;
      const factor = plnRate > 0 ? baseRate / plnRate : 1;
      return (Number(amount) || 0) * factor;
    };
    const sum = (pick: (pocket: Pocket) => number | null | undefined) =>
      pockets.reduce((total, pocket) => total + toPln(pick(pocket), pocket), 0);

    return {
      totalValue: sum((pocket) => pocket.total_value ?? pocket.cash_balance),
      totalDeposited: sum((pocket) => pocket.total_deposited),
      totalProfit: sum((pocket) => pocket.total_profit_loss),
      pocketCount: pockets.length,
    };
  }, [pockets, currencies]);

  // A portfolio with a position lacking a currency rate has no profit figure (null): its
  // profit is left out of the sum, so say so instead of showing a silently lower total.
  const hasUnvaluedPocket = pockets?.some((pocket) => pocket.rate_missing === true) ?? false;

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Dashboard
      </Typography>

      {hasUnvaluedPocket && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          Część portfeli ma pozycje bez kursu waluty — ich wartość i wynik nie są w pełni wliczone do sum.
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
