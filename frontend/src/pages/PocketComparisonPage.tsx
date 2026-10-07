import React, { useState, useMemo } from 'react';
import {
  Box,
  Typography,
  Grid,
  Checkbox,
  FormGroup,
  FormControlLabel,
  Paper,
  CircularProgress,
  Alert,
  Button,
} from '@mui/material';
import dayjs from 'dayjs';

import { usePockets } from '../hooks/usePockets';
import { usePocketVectors } from '../hooks/usePocketVectors';
import { getErrorMessage } from '../lib/api';
import DateRangePicker from '../components/DateRangePicker';
import LineChartCard from '../components/charts/LineChartCard';

const COLORS = [
  '#1976d2', '#9c27b0', '#2e7d32', '#ed6c02', '#d32f2f',
  '#0288d1', '#7b1fa2', '#388e3c', '#f57c00', '#c62828',
];

const PocketComparisonPage: React.FC = () => {
  const [startDate, setStartDate] = useState(
    dayjs().subtract(1, 'year').format('YYYY-MM-DD')
  );
  const [endDate, setEndDate] = useState(dayjs().format('YYYY-MM-DD'));
  const [selectedPockets, setSelectedPockets] = useState<string[]>([]);

  const { data: pockets, isLoading: pocketsLoading, error: pocketsError } = usePockets();

  // Fetch vectors for each selected pocket
  const pocket1Vectors = usePocketVectors(
    selectedPockets[0] || '', startDate, endDate, ['pocket_value_vector', 'profit_vector', 'twr_index_vector']
  );
  const pocket2Vectors = usePocketVectors(
    selectedPockets[1] || '', startDate, endDate, ['pocket_value_vector', 'profit_vector', 'twr_index_vector']
  );
  const pocket3Vectors = usePocketVectors(
    selectedPockets[2] || '', startDate, endDate, ['pocket_value_vector', 'profit_vector', 'twr_index_vector']
  );
  const pocket4Vectors = usePocketVectors(
    selectedPockets[3] || '', startDate, endDate, ['pocket_value_vector', 'profit_vector', 'twr_index_vector']
  );

  const allVectors = useMemo(
    () => [pocket1Vectors, pocket2Vectors, pocket3Vectors, pocket4Vectors],
    [pocket1Vectors, pocket2Vectors, pocket3Vectors, pocket4Vectors]
  );
  const isAnyLoading = selectedPockets.some((_, i) => allVectors[i]?.isLoading);

  const handleTogglePocket = (pocketName: string) => {
    setSelectedPockets((prev) => {
      if (prev.includes(pocketName)) {
        return prev.filter((p) => p !== pocketName);
      }
      if (prev.length >= 4) return prev; // max 4
      return [...prev, pocketName];
    });
  };

  // Build return data from TWR index (time-weighted return)
  const returnData = useMemo(() => {
    if (selectedPockets.length === 0) return { data: [], keys: [] };

    // Find the longest date vector
    let dates: string[] = [];
    selectedPockets.forEach((_, i) => {
      const v = allVectors[i]?.data;
      if (v?.date && v.date.length > dates.length) {
        dates = v.date;
      }
    });

    if (dates.length === 0) return { data: [], keys: [] };

    const keys = selectedPockets.map((name) => name);

    const data = dates.map((date, idx) => {
      const row: Record<string, unknown> = { date };
      selectedPockets.forEach((name, i) => {
        const v = allVectors[i]?.data;
        if (v?.twr_index_vector != null && v.twr_index_vector.length > idx) {
          // F3 & F5: DEC-07 - TWR normalized to base 0: (1.0 = 0%, 1.05 = 5%)
          const twr = v.twr_index_vector[idx];
          row[name] = twr != null ? (twr - 1) * 100 : undefined;
        }
      });
      return row;
    });

    return { data, keys };
  }, [selectedPockets, allVectors]);

  // Calculate base dates (first positive value date) for each portfolio
  const baseDates = useMemo(() => {
    const result: (string | null)[] = [];

    if (selectedPockets.length === 0) return result;

    // Find the longest date vector
    let dates: string[] = [];
    selectedPockets.forEach((_, i) => {
      const v = allVectors[i]?.data;
      if (v?.date && v.date.length > dates.length) {
        dates = v.date;
      }
    });

    selectedPockets.forEach((_, i) => {
      const v = allVectors[i]?.data;
      if (v?.pocket_value_vector) {
        const firstPositiveIdx = v.pocket_value_vector.findIndex((val) => val > 0);
        result.push(firstPositiveIdx >= 0 ? dates[firstPositiveIdx] : null);
      } else {
        result.push(null);
      }
    });

    return result;
  }, [selectedPockets, allVectors]);

  // F2: Compute vectors error message once (find first non-null error)
  const vectorsErrorMessage = useMemo(() => {
    const vectorError = [
      pocket1Vectors.error,
      pocket2Vectors.error,
      pocket3Vectors.error,
      pocket4Vectors.error,
    ].find((err) => err);
    return vectorError ? getErrorMessage(vectorError) : null;
  }, [pocket1Vectors.error, pocket2Vectors.error, pocket3Vectors.error, pocket4Vectors.error]);

  // Absolute profit comparison
  const profitData = useMemo(() => {
    if (selectedPockets.length === 0) return { data: [], keys: [] };

    let dates: string[] = [];
    selectedPockets.forEach((_, i) => {
      const v = allVectors[i]?.data;
      if (v?.date && v.date.length > dates.length) {
        dates = v.date;
      }
    });

    if (dates.length === 0) return { data: [], keys: [] };

    const keys = selectedPockets.map((name) => `${name}`);

    const data = dates.map((date, idx) => {
      const row: Record<string, unknown> = { date };
      selectedPockets.forEach((name, i) => {
        const v = allVectors[i]?.data;
        if (v?.profit_vector && v.profit_vector.length > idx) {
          row[name] = v.profit_vector[idx];
        }
      });
      return row;
    });

    return { data, keys };
  }, [selectedPockets, allVectors]);

  // Absolute value comparison
  const valueData = useMemo(() => {
    if (selectedPockets.length === 0) return { data: [], keys: [] };

    let dates: string[] = [];
    selectedPockets.forEach((_, i) => {
      const v = allVectors[i]?.data;
      if (v?.date && v.date.length > dates.length) {
        dates = v.date;
      }
    });

    if (dates.length === 0) return { data: [], keys: [] };

    const keys = selectedPockets.map((name) => `${name}`);

    const data = dates.map((date, idx) => {
      const row: Record<string, unknown> = { date };
      selectedPockets.forEach((name, i) => {
        const v = allVectors[i]?.data;
        if (v?.pocket_value_vector && v.pocket_value_vector.length > idx) {
          row[name] = v.pocket_value_vector[idx];
        }
      });
      return row;
    });

    return { data, keys };
  }, [selectedPockets, allVectors]);

  if (pocketsLoading) {
    return (
      <Box display="flex" justifyContent="center" py={4}>
        <CircularProgress />
      </Box>
    );
  }

  // F1: Early return for pocketsError (ADR-0007 pattern)
  if (pocketsError) {
    return (
      <Box display="flex" flexDirection="column" justifyContent="center" alignItems="center" minHeight="60vh" gap={2}>
        <Typography variant="h5" color="error">
          Błąd podczas ładowania portfeli: {getErrorMessage(pocketsError)}
        </Typography>
        <Button variant="contained" onClick={() => window.location.reload()}>
          Spróbuj ponownie
        </Button>
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Porównaj portfele
      </Typography>

      <Box mb={3}>
        <DateRangePicker
          startDate={startDate}
          endDate={endDate}
          onDateChange={(s, e) => { setStartDate(s); setEndDate(e); }}
        />
      </Box>

      <Paper sx={{ p: 2, mb: 3 }}>
        <Typography variant="subtitle2" gutterBottom>
          Wybierz portfele (max 4):
        </Typography>
        <FormGroup row>
          {pockets?.map((pocket, i) => (
            <FormControlLabel
              key={pocket.id}
              control={
                <Checkbox
                  checked={selectedPockets.includes(pocket.name)}
                  onChange={() => handleTogglePocket(pocket.name)}
                  disabled={
                    !selectedPockets.includes(pocket.name) &&
                    selectedPockets.length >= 4
                  }
                  sx={{
                    color: COLORS[i % COLORS.length],
                    '&.Mui-checked': { color: COLORS[i % COLORS.length] },
                  }}
                />
              }
              label={pocket.name}
            />
          ))}
        </FormGroup>
      </Paper>

      {selectedPockets.length === 0 && (
        <Alert severity="info">
          Wybierz co najmniej 1 portfel, aby zobaczyć wykresy. Wybierz 2 lub więcej, aby porównać.
        </Alert>
      )}

      {selectedPockets.length > 0 && (
        <Grid container spacing={3}>
          <Grid size={{ xs: 12 }}>
            <LineChartCard
              title="Zwrot względny (%)"
              subtitle={
                baseDates.some((d) => d !== null)
                  ? returnData.keys
                    .map((name, i) => {
                      const baseDate = baseDates[i];
                      if (baseDate) {
                        return `${name}: ${dayjs(baseDate).format('DD.MM.YYYY')}`;
                      }
                      return `${name}: brak wartości w zakresie`;
                    })
                    .join(' | ')
                  : 'Brak danych o wartości portfela w zakresie'
              }
              data={returnData.data}
              dataKeys={returnData.keys}
              colors={COLORS}
              loading={isAnyLoading}
              error={vectorsErrorMessage}
              height={350}
              yAxisFormatter={(v: number | null) => {
                if (v === null) return '';
                return `${v.toFixed(1)}%`;
              }}
              showReferenceLine={false}
            />
          </Grid>

          <Grid size={{ xs: 12, md: 6 }}>
            <LineChartCard
              title="Wartość portfeli"
              subtitle="Porównanie wartości bezwzględnych"
              data={valueData.data}
              dataKeys={valueData.keys}
              colors={COLORS}
              loading={isAnyLoading}
              error={vectorsErrorMessage}
            />
          </Grid>

          <Grid size={{ xs: 12, md: 6 }}>
            <LineChartCard
              title="Profit / Loss"
              subtitle="Porównanie zysków"
              data={profitData.data}
              dataKeys={profitData.keys}
              colors={COLORS}
              loading={isAnyLoading}
              error={vectorsErrorMessage}
              showReferenceLine
            />
          </Grid>
        </Grid>
      )}
    </Box>
  );
};

export default PocketComparisonPage;
