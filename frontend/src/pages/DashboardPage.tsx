import { useMemo } from "react";
import { PortfolioOverview } from "../components/portfolio-overview";
import PocketsList from "../components/PocketsList";
import { Alert, Box, Typography, Divider } from "@mui/material";
import { usePockets } from "../hooks/usePockets";

export default function DashboardPage() {
  const { data: pockets, isLoading } = usePockets();

  // Calculate total metrics
  const totalMetrics = useMemo(() => {
    if (!pockets) return { totalValue: 0, totalDeposited: 0, totalProfit: 0, pocketCount: 0 };

    const totalValue = pockets.reduce((sum, pocket) => sum + (Number(pocket.cash_balance) || 0), 0);
    const totalDeposited = pockets.reduce((sum, pocket) => sum + (Number(pocket.total_deposited) || 0), 0);
    const totalProfit = pockets.reduce((sum, pocket) => sum + (Number(pocket.total_profit_loss) || 0), 0);

    return {
      totalValue,
      totalDeposited,
      totalProfit,
      pocketCount: pockets.length,
    };
  }, [pockets]);

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
          Część portfeli ma pozycje bez kursu waluty — ich wynik nie jest wliczony do sumy zysku.
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
