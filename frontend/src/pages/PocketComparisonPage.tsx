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
} from '@mui/material';
import dayjs from 'dayjs';

import { usePockets } from '../hooks/usePockets';
import { usePocketVectors } from '../hooks/usePocketVectors';
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

  const { data: pockets, isLoading: pocketsLoading } = usePockets();

  // Fetch vectors for each selected pocket
  const pocket1Vectors = usePocketVectors(
    selectedPockets[0] || '', startDate, endDate, ['pocket_value_vector', 'profit_vector']
  );
  const pocket2Vectors = usePocketVectors(
    selectedPockets[1] || '', startDate, endDate, ['pocket_value_vector', 'profit_vector']
  );
  const pocket3Vectors = usePocketVectors(
    selectedPockets[2] || '', startDate, endDate, ['pocket_value_vector', 'profit_vector']
  );
  const pocket4Vectors = usePocketVectors(
    selectedPockets[3] || '', startDate, endDate, ['pocket_value_vector', 'profit_vector']
  );

  const allVectors = [pocket1Vectors, pocket2Vectors, pocket3Vectors, pocket4Vectors];
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

  // Build normalized comparison data (start = 100%)
  const normalizedValueData = useMemo(() => {
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
        if (v?.pocket_value_vector && v.pocket_value_vector.length > idx) {
          const startVal = v.pocket_value_vector[0] || 1;
          row[name] = ((v.pocket_value_vector[idx] / startVal) * 100);
        }
      });
      return row;
    });

    return { data, keys };
  }, [selectedPockets, pocket1Vectors.data, pocket2Vectors.data, pocket3Vectors.data, pocket4Vectors.data]);

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
  }, [selectedPockets, pocket1Vectors.data, pocket2Vectors.data, pocket3Vectors.data, pocket4Vectors.data]);

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
  }, [selectedPockets, pocket1Vectors.data, pocket2Vectors.data, pocket3Vectors.data, pocket4Vectors.data]);

  if (pocketsLoading) {
    return (
      <Box display="flex" justifyContent="center" py={4}>
        <CircularProgress />
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
          Wybierz co najmniej 2 portfele do porównania.
        </Alert>
      )}

      {selectedPockets.length > 0 && (
        <Grid container spacing={3}>
          <Grid size={{ xs: 12 }}>
            <LineChartCard
              title="Zwrot względny (%)"
              subtitle="Normalizacja do 100% na początku okresu"
              data={normalizedValueData.data}
              dataKeys={normalizedValueData.keys}
              colors={COLORS}
              loading={isAnyLoading}
              height={350}
              yAxisFormatter={(v) => `${v.toFixed(0)}%`}
              showReferenceLine
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
              showReferenceLine
            />
          </Grid>
        </Grid>
      )}
    </Box>
  );
};

export default PocketComparisonPage;
