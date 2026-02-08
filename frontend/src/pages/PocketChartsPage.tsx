import React, { useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Grid,
  Button,
  CircularProgress,
  Alert,
} from '@mui/material';
import { ArrowBack as ArrowBackIcon } from '@mui/icons-material';
import dayjs from 'dayjs';

import { usePocketByName } from '../hooks/usePockets';
import { usePositions } from '../hooks/usePositions';
import { usePocketVectors } from '../hooks/usePocketVectors';
import DateRangePicker from '../components/DateRangePicker';
import LineChartCard from '../components/charts/LineChartCard';
import AreaChartCard from '../components/charts/AreaChartCard';
import PieChartCard from '../components/charts/PieChartCard';

const PocketChartsPage: React.FC = () => {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const pocketName = decodeURIComponent(slug || '');

  const [startDate, setStartDate] = useState(
    dayjs().subtract(1, 'year').format('YYYY-MM-DD')
  );
  const [endDate, setEndDate] = useState(dayjs().format('YYYY-MM-DD'));

  const { data: pocket, isLoading: pocketLoading } = usePocketByName(pocketName);
  const { data: positions } = usePositions(pocketName);
  const {
    data: vectors,
    isLoading: vectorsLoading,
    error: vectorsError,
  } = usePocketVectors(pocketName, startDate, endDate);

  // Transform vector data into recharts-compatible format
  const timeSeriesData = useMemo(() => {
    if (!vectors?.date) return [];
    return vectors.date.map((date, i) => ({
      date,
      pocket_value: vectors.pocket_value_vector?.[i] ?? 0,
      profit: vectors.profit_vector?.[i] ?? 0,
      net_deposits: vectors.net_deposits_vector?.[i] ?? 0,
      transaction_cost: vectors.transaction_cost_vector?.[i] ?? 0,
      free_cash: vectors.free_cash_vector?.[i] ?? 0,
    }));
  }, [vectors]);

  // Data for assets stacked area chart
  const assetsData = useMemo(() => {
    if (!vectors?.date || !vectors?.assets) return { data: [], keys: [] };
    const keys = Object.keys(vectors.assets);
    const data = vectors.date.map((date, i) => {
      const row: Record<string, unknown> = { date };
      keys.forEach((key) => {
        row[key] = vectors.assets[key]?.[i] ?? 0;
      });
      return row;
    });
    return { data, keys };
  }, [vectors]);

  // Data for asset classes stacked area chart
  const assetClassesData = useMemo(() => {
    if (!vectors?.date || !vectors?.asset_classes) return { data: [], keys: [] };
    const keys = Object.keys(vectors.asset_classes);
    const data = vectors.date.map((date, i) => {
      const row: Record<string, unknown> = { date };
      keys.forEach((key) => {
        row[key] = vectors.asset_classes[key]?.[i] ?? 0;
      });
      return row;
    });
    return { data, keys };
  }, [vectors]);

  // Pie chart data from current positions
  const allocationData = useMemo(() => {
    if (!positions) return [];
    return positions
      .filter((p) => (p.market_value || 0) > 0)
      .map((p) => ({
        name: p.asset.ticker,
        value: p.market_value || 0,
      }));
  }, [positions]);

  // Combined: portfolio value vs net deposits
  const comparisonData = useMemo(() => {
    if (!vectors?.date) return [];
    return vectors.date.map((date, i) => ({
      date,
      'Wartość portfela': vectors.pocket_value_vector?.[i] ?? 0,
      'Wpłaty netto': vectors.net_deposits_vector?.[i] ?? 0,
    }));
  }, [vectors]);

  const handleDateChange = (start: string, end: string) => {
    setStartDate(start);
    setEndDate(end);
  };

  if (pocketLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="60vh">
        <CircularProgress />
      </Box>
    );
  }

  const errorMessage = vectorsError
    ? 'Błąd podczas ładowania danych analitycznych. Sprawdź czy portfel posiada operacje w wybranym zakresie dat.'
    : null;

  return (
    <Box>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Box display="flex" alignItems="center" gap={2}>
          <Button
            startIcon={<ArrowBackIcon />}
            onClick={() => navigate(`/pockets/${slug}`)}
          >
            Powrót
          </Button>
          <Typography variant="h4" component="h1">
            Wykresy — {pocket?.name}
          </Typography>
        </Box>
      </Box>

      {/* Date Range Picker */}
      <Box mb={3}>
        <DateRangePicker
          startDate={startDate}
          endDate={endDate}
          onDateChange={handleDateChange}
        />
      </Box>

      {errorMessage && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          {errorMessage}
        </Alert>
      )}

      {/* Charts Grid 2x4 + pie */}
      <Grid container spacing={3}>
        {/* Row 1 */}
        <Grid size={{ xs: 12, md: 6 }}>
          <LineChartCard
            title="Wartość portfela"
            subtitle="Całkowita wartość portfela w czasie"
            data={timeSeriesData}
            dataKeys={['pocket_value']}
            colors={['#1976d2']}
            loading={vectorsLoading}
            error={errorMessage}
          />
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <LineChartCard
            title="Zysk / Strata"
            subtitle="Profit/loss w czasie"
            data={timeSeriesData}
            dataKeys={['profit']}
            colors={['#2e7d32']}
            loading={vectorsLoading}
            error={errorMessage}
            showReferenceLine
          />
        </Grid>

        {/* Row 2 */}
        <Grid size={{ xs: 12, md: 6 }}>
          <LineChartCard
            title="Wpłaty netto"
            subtitle="Suma wpłat minus wypłaty"
            data={timeSeriesData}
            dataKeys={['net_deposits']}
            colors={['#ed6c02']}
            loading={vectorsLoading}
            error={errorMessage}
          />
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <LineChartCard
            title="Koszty transakcji"
            subtitle="Skumulowane koszty nabycia aktywów"
            data={timeSeriesData}
            dataKeys={['transaction_cost']}
            colors={['#d32f2f']}
            loading={vectorsLoading}
            error={errorMessage}
          />
        </Grid>

        {/* Row 3 */}
        <Grid size={{ xs: 12, md: 6 }}>
          <LineChartCard
            title="Wolna gotówka"
            subtitle="Dostępne środki pieniężne"
            data={timeSeriesData}
            dataKeys={['free_cash']}
            colors={['#0288d1']}
            loading={vectorsLoading}
            error={errorMessage}
          />
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <PieChartCard
            title="Alokacja aktywów"
            subtitle="Bieżący podział portfela"
            data={allocationData}
            loading={!positions}
          />
        </Grid>

        {/* Row 4 */}
        <Grid size={{ xs: 12, md: 6 }}>
          {assetsData.keys.length > 0 ? (
            <AreaChartCard
              title="Aktywa — stos"
              subtitle="Wartość poszczególnych aktywów w czasie"
              data={assetsData.data}
              dataKeys={assetsData.keys}
              loading={vectorsLoading}
              error={errorMessage}
            />
          ) : (
            <LineChartCard
              title="Aktywa — stos"
              subtitle="Brak danych o aktywach"
              data={[]}
              dataKeys={[]}
              loading={vectorsLoading}
              error={vectorsLoading ? null : 'Brak danych o aktywach'}
            />
          )}
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          {assetClassesData.keys.length > 0 ? (
            <AreaChartCard
              title="Klasy aktywów — stos"
              subtitle="Wartość klas aktywów w czasie"
              data={assetClassesData.data}
              dataKeys={assetClassesData.keys}
              loading={vectorsLoading}
              error={errorMessage}
            />
          ) : (
            <LineChartCard
              title="Klasy aktywów — stos"
              subtitle="Brak danych o klasach aktywów"
              data={[]}
              dataKeys={[]}
              loading={vectorsLoading}
              error={vectorsLoading ? null : 'Brak danych o klasach aktywów'}
            />
          )}
        </Grid>

        {/* Row 5 — Comparison chart (full width) */}
        <Grid size={{ xs: 12 }}>
          <LineChartCard
            title="Wartość portfela vs Wpłaty netto"
            subtitle="Porównanie wartości portfela z sumą wpłat"
            data={comparisonData}
            dataKeys={['Wartość portfela', 'Wpłaty netto']}
            colors={['#1976d2', '#ed6c02']}
            loading={vectorsLoading}
            error={errorMessage}
            height={350}
          />
        </Grid>
      </Grid>
    </Box>
  );
};

export default PocketChartsPage;
