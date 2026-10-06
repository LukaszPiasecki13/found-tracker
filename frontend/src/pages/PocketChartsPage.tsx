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
import { getErrorMessage } from '../lib/api';
import { useOperations } from '../hooks/useOperations';
import DateRangePicker from '../components/DateRangePicker';
import LineChartCard from '../components/charts/LineChartCard';
import AreaChartCard from '../components/charts/AreaChartCard';
import PieChartCard from '../components/charts/PieChartCard';
import { dropZeroSeries, pieSlices, returnPercent } from '../utils/portfolioSeries';

const PocketChartsPage: React.FC = () => {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const pocketName = decodeURIComponent(slug || '');

  // Get operations to determine first operation date
  const { data: operations } = useOperations(pocketName);
  const firstOperationDate = useMemo(() => {
    if (!operations || operations.length === 0) {
      return dayjs().subtract(1, 'year').format('YYYY-MM-DD');
    }
    // Sort operations by date and get the earliest
    const sorted = [...operations].sort(
      (a, b) => new Date(a.operation_date).getTime() - new Date(b.operation_date).getTime()
    );
    return dayjs(sorted[0].operation_date).format('YYYY-MM-DD');
  }, [operations]);

  // null until the user picks a start date; the first operation date is the default
  // until then, so the default follows operations as they load
  const [userStartDate, setUserStartDate] = useState<string | null>(null);
  const startDate = userStartDate ?? firstOperationDate;
  const [endDate, setEndDate] = useState(dayjs().format('YYYY-MM-DD'));

  const { data: pocket, isLoading: pocketLoading, error: pocketError } = usePocketByName(pocketName);
  const {
    data: positions,
    isLoading: positionsLoading,
    error: positionsError,
  } = usePositions(pocketName);
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
      dividend_income: vectors.dividend_income_vector?.[i] ?? 0,
    }));
  }, [vectors]);

  // Calculate return percentage
  const returnPercentData = useMemo(() => {
    if (!vectors?.date || !vectors?.profit_vector || !vectors?.net_deposits_vector) {
      return [];
    }
    const returnPcts = returnPercent(
      vectors.profit_vector,
      vectors.net_deposits_vector
    );
    return vectors.date.map((date, i) => ({
      date,
      return_percent: returnPcts[i],
    }));
  }, [vectors]);

  // Data for assets stacked area chart
  const assetsData = useMemo(() => {
    if (!vectors?.date || !vectors?.assets) return { data: [], keys: [] };
    const keys = dropZeroSeries(vectors.assets);
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
    const keys = dropZeroSeries(vectors.asset_classes);
    const data = vectors.date.map((date, i) => {
      const row: Record<string, unknown> = { date };
      keys.forEach((key) => {
        row[key] = vectors.asset_classes[key]?.[i] ?? 0;
      });
      return row;
    });
    return { data, keys };
  }, [vectors]);

  // Pie chart: current position values by ticker plus the cash balance
  const allocationData = useMemo(() => {
    if (!positions) return [];
    const valueByTicker: Record<string, number> = {};
    positions.forEach((p) => {
      const ticker = p.asset.ticker;
      valueByTicker[ticker] = (valueByTicker[ticker] ?? 0) + (p.market_value || 0);
    });
    const freeCash = vectors?.free_cash_vector;
    const lastFreeCash = freeCash && freeCash.length > 0 ? freeCash[freeCash.length - 1] : 0;
    return pieSlices(valueByTicker, lastFreeCash);
  }, [positions, vectors]);

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
    setUserStartDate(start);
    setEndDate(end);
  };

  if (pocketLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="60vh">
        <CircularProgress />
      </Box>
    );
  }

  if (pocketError || !pocket) {
    return (
      <Box display="flex" flexDirection="column" justifyContent="center" alignItems="center" minHeight="60vh" gap={2}>
        <Typography variant="h5" color="error">
          Nie znaleziono portfela "{pocketName}"
        </Typography>
        <Button variant="contained" onClick={() => navigate('/')}>
          Powrót do listy portfeli
        </Button>
      </Box>
    );
  }

  const errorMessage = vectorsError
    ? `Błąd podczas ładowania danych analitycznych: ${getErrorMessage(vectorsError)}.`
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
            currency={pocket?.base_currency.code}
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
            currency={pocket?.base_currency.code}
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
            currency={pocket?.base_currency.code}
          />
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <LineChartCard
            title="Saldo kosztów transakcji"
            subtitle="Koszty nabycia pomniejszone o wpływy ze sprzedaży i opłaty"
            data={timeSeriesData}
            dataKeys={['transaction_cost']}
            colors={['#d32f2f']}
            loading={vectorsLoading}
            error={errorMessage}
            currency={pocket?.base_currency.code}
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
            currency={pocket?.base_currency.code}
          />
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <PieChartCard
            title="Alokacja aktywów"
            subtitle="Bieżący podział portfela"
            data={allocationData}
            loading={positionsLoading}
            error={positionsError ? 'Błąd podczas ładowania pozycji' : null}
          />
        </Grid>

        {/* Row 4 */}
        <Grid size={{ xs: 12, md: 6 }}>
          {assetsData.keys.length > 0 ? (
            <AreaChartCard
              title="Aktywa — stos"
              subtitle="Wartość poszczególnych aktywów w czasie (wartości w walutach natywnych aktywów)"
              data={assetsData.data}
              dataKeys={assetsData.keys}
              loading={vectorsLoading}
              error={errorMessage}
              currency={pocket?.base_currency.code}
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
              subtitle="Wartość klas aktywów w czasie (wartości w walutach natywnych aktywów)"
              data={assetClassesData.data}
              dataKeys={assetClassesData.keys}
              loading={vectorsLoading}
              error={errorMessage}
              currency={pocket?.base_currency.code}
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

        {/* Row 5 — Dividend income chart */}
        {vectors?.dividend_income_vector && (
          <Grid size={{ xs: 12, md: 6 }}>
            <LineChartCard
              title="Dywidendy skumulowane"
              subtitle="Skumulowany dochód z dywidend"
              data={timeSeriesData}
              dataKeys={['dividend_income']}
              colors={['#7b1fa2']}
              loading={vectorsLoading}
              error={errorMessage}
              currency={pocket?.base_currency.code}
            />
          </Grid>
        )}

        {/* Return percent chart */}
        <Grid size={{ xs: 12, md: 6 }}>
          <LineChartCard
            title="Zwrot (%)"
            subtitle="Zwrot z inwestycji w stosunku do wpłat"
            data={returnPercentData}
            dataKeys={['return_percent']}
            colors={['#00838f']}
            loading={vectorsLoading}
            error={errorMessage}
            yAxisFormatter={(value: number | null) => {
              if (value === null) return '';
              return `${value.toFixed(1)}%`;
            }}
            showReferenceLine
          />
        </Grid>

        {/* Row 6 — Comparison chart (full width) */}
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
            currency={pocket?.base_currency.code}
          />
        </Grid>
      </Grid>
    </Box>
  );
};

export default PocketChartsPage;
