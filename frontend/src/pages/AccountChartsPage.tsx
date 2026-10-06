import React, { useMemo, useState } from 'react';
import { Box, Typography, Grid, CircularProgress, Alert } from '@mui/material';
import dayjs from 'dayjs';

import { useAccountVectors } from '../hooks/useAccountVectors';
import { useCurrencySplit } from '../hooks/useCurrencySplit';
import { getErrorMessage } from '../lib/api';
import DateRangePicker from '../components/DateRangePicker';
import LineChartCard from '../components/charts/LineChartCard';
import AreaChartCard from '../components/charts/AreaChartCard';
import PieChartCard from '../components/charts/PieChartCard';
import { dropZeroSeries, returnPercent } from '../utils/portfolioSeries';

// The account's charts: every portfolio summed in the user's base currency (DEC-01).
// There is no allocation pie here: positions are per portfolio, and the per-ticker
// vector is left out because tickers can differ between portfolios (DEC-05).
// Investment Start: the default start of the charts (the same date as the IS button).
const INVESTMENT_START = '2023-10-01';

const AccountChartsPage: React.FC = () => {
  const [startDate, setStartDate] = useState(INVESTMENT_START);
  const [endDate, setEndDate] = useState(dayjs().format('YYYY-MM-DD'));

  const { data: vectors, isLoading, error } = useAccountVectors(startDate, endDate);

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

  const returnPercentData = useMemo(() => {
    if (!vectors?.date || !vectors?.profit_vector || !vectors?.net_deposits_vector) {
      return [];
    }
    const returnPcts = returnPercent(vectors.profit_vector, vectors.net_deposits_vector);
    return vectors.date.map((date, i) => ({ date, return_percent: returnPcts[i] }));
  }, [vectors]);

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

  const comparisonData = useMemo(() => {
    if (!vectors?.date) return [];
    return vectors.date.map((date, i) => ({
      date,
      'Wartość konta': vectors.pocket_value_vector?.[i] ?? 0,
      'Wpłaty netto': vectors.net_deposits_vector?.[i] ?? 0,
    }));
  }, [vectors]);

  // XIRR and drawdown are per day; a null day has no value (drawn as a gap).
  const riskData = useMemo(() => {
    if (!vectors?.date) return [];
    return vectors.date.map((date, i) => ({
      date,
      drawdown: vectors.drawdown_vector?.[i] ?? null,
      xirr: vectors.xirr_vector?.[i] ?? null,
    }));
  }, [vectors]);

  const currencySplit = useCurrencySplit();
  const currencyPie = useMemo(
    () => (currencySplit.data?.items ?? []).map((item) => ({ name: item.currency, value: item.value })),
    [currencySplit.data]
  );

  const hasNoOperations = !isLoading && !error && vectors !== undefined && !vectors.date;
  const errorMessage = error
    ? `Błąd podczas ładowania danych analitycznych: ${getErrorMessage(error)}.`
    : null;

  const handleDateChange = (start: string, end: string) => {
    setStartDate(start);
    setEndDate(end);
  };

  return (
    <Box>
      <Box display="flex" alignItems="center" gap={2} mb={2}>
        <Typography variant="h4" component="h1">
          Wykresy — całe konto
        </Typography>
      </Box>

      <Box mb={3}>
        <DateRangePicker startDate={startDate} endDate={endDate} onDateChange={handleDateChange} />
      </Box>

      {errorMessage && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          {errorMessage}
        </Alert>
      )}

      {hasNoOperations && (
        <Alert severity="info" sx={{ mb: 3 }}>
          Na koncie nie ma jeszcze operacji.
        </Alert>
      )}

      {isLoading && (
        <Box display="flex" justifyContent="center" py={4}>
          <CircularProgress />
        </Box>
      )}

      <Grid container spacing={3}>
        <Grid size={{ xs: 12 }}>
          <LineChartCard
            title="Wartość konta i wpłaty netto"
            subtitle="Łączna wartość wszystkich portfeli i suma wpłat minus wypłaty"
            data={comparisonData}
            dataKeys={['Wartość konta', 'Wpłaty netto']}
            colors={['#1976d2', '#ed6c02']}
            loading={isLoading}
            error={errorMessage}
            height={350}
          />
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <LineChartCard
            title="Zysk / Strata"
            subtitle="Profit/loss całego konta w czasie"
            data={timeSeriesData}
            dataKeys={['profit']}
            colors={['#2e7d32']}
            loading={isLoading}
            error={errorMessage}
            showReferenceLine
          />
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <LineChartCard
            title="Saldo kosztów transakcji"
            subtitle="Koszty nabycia pomniejszone o wpływy ze sprzedaży i opłaty"
            data={timeSeriesData}
            dataKeys={['transaction_cost']}
            colors={['#d32f2f']}
            loading={isLoading}
            error={errorMessage}
          />
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <LineChartCard
            title="Wolna gotówka"
            subtitle="Dostępne środki pieniężne wszystkich portfeli"
            data={timeSeriesData}
            dataKeys={['free_cash']}
            colors={['#0288d1']}
            loading={isLoading}
            error={errorMessage}
          />
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <LineChartCard
            title="Zwrot (%)"
            subtitle="Zwrot konta w stosunku do wpłat netto"
            data={returnPercentData}
            dataKeys={['return_percent']}
            colors={['#00838f']}
            loading={isLoading}
            error={errorMessage}
            yAxisFormatter={(value: number | null) => {
              if (value === null) return '';
              return `${value.toFixed(1)}%`;
            }}
            showReferenceLine
          />
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <LineChartCard
            title="XIRR (%)"
            subtitle="Rzeczywista roczna stopa zwrotu; pokazywana od trzech miesięcy po pierwszej wpłacie"
            data={riskData}
            dataKeys={['xirr']}
            colors={['#6a1b9a']}
            loading={isLoading}
            error={errorMessage}
            yAxisFormatter={(value: number | null) => {
              if (value === null) return '';
              return `${value.toFixed(1)}%`;
            }}
            showReferenceLine
          />
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <LineChartCard
            title="Drawdown (%)"
            subtitle="Spadek od szczytu zwrotu skumulowanego (wpłaty go nie zmieniają)"
            data={riskData}
            dataKeys={['drawdown']}
            colors={['#c62828']}
            loading={isLoading}
            error={errorMessage}
            yAxisFormatter={(value: number | null) => {
              if (value === null) return '';
              return `${value.toFixed(1)}%`;
            }}
          />
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <PieChartCard
            title="Podział na waluty"
            subtitle={`Bieżąca wartość wg waluty waloru, w ${currencySplit.data?.currency ?? 'walucie konta'}`}
            data={currencyPie}
            loading={currencySplit.isLoading}
            error={currencySplit.error ? getErrorMessage(currencySplit.error) : null}
          />
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          {assetClassesData.keys.length > 0 ? (
            <AreaChartCard
              title="Klasy aktywów — stos"
              subtitle="Wartość klas aktywów wszystkich portfeli w czasie"
              data={assetClassesData.data}
              dataKeys={assetClassesData.keys}
              loading={isLoading}
              error={errorMessage}
            />
          ) : (
            <LineChartCard
              title="Klasy aktywów — stos"
              subtitle="Brak danych o klasach aktywów"
              data={[]}
              dataKeys={[]}
              loading={isLoading}
              error={isLoading ? null : 'Brak danych o klasach aktywów'}
            />
          )}
        </Grid>
      </Grid>
    </Box>
  );
};

export default AccountChartsPage;
