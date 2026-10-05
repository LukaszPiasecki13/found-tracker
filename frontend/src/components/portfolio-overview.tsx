import { Card, CardContent, Typography, Box, Grid, Skeleton } from "@mui/material"
import {
  TrendingUp as TrendingUpIcon,
  AttachMoney as AttachMoneyIcon,
  Percent as PercentIcon,
  AccountBalanceWallet as WalletIcon,
} from "@mui/icons-material"

interface PortfolioOverviewProps {
  totalValue: number;
  totalProfit: number;
  investedCapital: number;
  positionsCount: number;
  /**
   * TEMPORARY: a value-weighted average of the portfolios' TWR, shown as an
   * approximation. Replace with a true TWR of the combined portfolio (needs a
   * historical FX series, see ADR-0015). `null` when no portfolio has a return.
   */
  returnPct?: number | null;
  isLoading?: boolean;
}

export function PortfolioOverview({
  totalValue,
  totalProfit,
  investedCapital,
  positionsCount,
  returnPct = null,
  isLoading = false,
}: PortfolioOverviewProps) {
  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('pl-PL', {
      style: 'currency',
      currency: 'PLN',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  // TEMPORARY (see `returnPct`): until the combined TWR exists, the dashboard shows
  // the weighted average of the portfolios' TWR, not profit over net deposits.
  const profitPercent = returnPct ?? 0;

  return (
    <Box sx={{ width: '100%', py: 3 }}>
      <Grid container spacing={3}>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <Card>
            <CardContent>
              <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", mb: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  Całkowita wartość
                </Typography>
                <WalletIcon sx={{ color: "text.secondary" }} />
              </Box>
              {isLoading ? (
                <Skeleton variant="text" width="60%" height={48} />
              ) : (
                <>
                  <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>
                    {formatCurrency(totalValue)}
                  </Typography>
                  <Box sx={{ display: "flex", alignItems: "center", color: totalProfit >= 0 ? "success.main" : "error.main" }}>
                    <TrendingUpIcon sx={{ fontSize: 16, mr: 0.5 }} />
                    <Typography variant="body2">
                      {formatCurrency(totalProfit)} ({profitPercent.toFixed(2)}%)
                    </Typography>
                  </Box>
                </>
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <Card>
            <CardContent>
              <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", mb: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  Zysk/Strata
                </Typography>
                <PercentIcon sx={{ color: "text.secondary" }} />
              </Box>
              {isLoading ? (
                <Skeleton variant="text" width="60%" height={48} />
              ) : (
                <>
                  <Typography 
                    variant="h4" 
                    sx={{ 
                      fontWeight: 700, 
                      mb: 1, 
                      color: totalProfit >= 0 ? "success.main" : "error.main" 
                    }}
                  >
                    {totalProfit >= 0 ? '+' : ''}{formatCurrency(totalProfit)}
                  </Typography>
                  <Box sx={{ display: "flex", alignItems: "center", color: totalProfit >= 0 ? "success.main" : "error.main" }}>
                    <TrendingUpIcon sx={{ fontSize: 16, mr: 0.5 }} />
                    <Typography variant="body2">
                      {returnPct === null ? '—' : `${profitPercent >= 0 ? '+' : ''}${profitPercent.toFixed(2)}%`}
                      {' '}
                      <Typography component="span" variant="caption" color="text.secondary">
                        (przybliżenie TWR)
                      </Typography>
                    </Typography>
                  </Box>
                </>
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <Card>
            <CardContent>
              <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", mb: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  Zainwestowane
                </Typography>
                <AttachMoneyIcon sx={{ color: "text.secondary" }} />
              </Box>
              {isLoading ? (
                <Skeleton variant="text" width="60%" height={48} />
              ) : (
                <>
                  <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>
                    {formatCurrency(investedCapital)}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Kapitał początkowy
                  </Typography>
                </>
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <Card>
            <CardContent>
              <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", mb: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  Portfele
                </Typography>
                <TrendingUpIcon sx={{ color: "text.secondary" }} />
              </Box>
              {isLoading ? (
                <Skeleton variant="text" width="40%" height={48} />
              ) : (
                <>
                  <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>
                    {positionsCount}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Aktywnych portfeli
                  </Typography>
                </>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  )
}
