import React, { useMemo } from "react";
import { PortfolioOverview } from "../components/portfolio-overview";
import PocketsList from "../components/PocketsList";
import { Box, Typography, Divider } from "@mui/material";
import { usePockets } from "../hooks/usePockets";

export default function DashboardPage() {
  const { data: pockets, isLoading } = usePockets();

  // Calculate total metrics
  const totalMetrics = useMemo(() => {
    if (!pockets) return { totalValue: 0, totalDeposited: 0, totalProfit: 0, pocketCount: 0 };

    const totalValue = pockets.reduce((sum, pocket) => sum + (pocket.cash_balance || 0), 0);
    const totalDeposited = pockets.reduce((sum, pocket) => sum + (pocket.total_deposited || 0), 0);
    const totalProfit = pockets.reduce((sum, pocket) => sum + (pocket.total_profit_loss || 0), 0);

    return {
      totalValue,
      totalDeposited,
      totalProfit,
      pocketCount: pockets.length,
    };
  }, [pockets]);

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Dashboard
      </Typography>
      
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
