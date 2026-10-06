import React from 'react';
import { Box, Button, ButtonGroup, TextField } from '@mui/material';
import dayjs from 'dayjs';

interface DateRangePickerProps {
  startDate: string;
  endDate: string;
  onDateChange: (startDate: string, endDate: string) => void;
}

interface Preset {
  label: string;
  title?: string;
  // Relative presets: months back from today (0 = year to date).
  months?: number;
  // A fixed start date, `YYYY-MM-DD`, instead of a relative one.
  fixedStart?: string;
}

const presets: Preset[] = [
  { label: '1M', months: 1 },
  { label: '3M', months: 3 },
  { label: '6M', months: 6 },
  { label: '1R', months: 12 },
  { label: '2R', months: 24 },
  {
    label: 'PI',
    title: 'Profesjonalne inwestowanie (od 01.10.2023)',
    fixedStart: '2023-10-01',
  },
  { label: 'YTD', months: 0 },
];

const presetStart = (preset: Preset): string => {
  if (preset.fixedStart) return preset.fixedStart;
  if (preset.months === 0) return dayjs().startOf('year').format('YYYY-MM-DD');
  return dayjs().subtract(preset.months ?? 0, 'month').format('YYYY-MM-DD');
};

const DateRangePicker: React.FC<DateRangePickerProps> = ({
  startDate,
  endDate,
  onDateChange,
}) => {
  const handlePreset = (preset: Preset) => {
    onDateChange(presetStart(preset), dayjs().format('YYYY-MM-DD'));
  };

  return (
    <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
      <ButtonGroup size="small" variant="outlined">
        {presets.map((preset) => {
          const isActive = startDate === presetStart(preset);

          return (
            <Button
              key={preset.label}
              title={preset.title}
              variant={isActive ? 'contained' : 'outlined'}
              onClick={() => handlePreset(preset)}
            >
              {preset.label}
            </Button>
          );
        })}
      </ButtonGroup>

      <TextField
        type="date"
        label="Od"
        size="small"
        value={startDate}
        onChange={(e) => onDateChange(e.target.value, endDate)}
        slotProps={{ inputLabel: { shrink: true } }}
        sx={{ width: 160 }}
      />

      <TextField
        type="date"
        label="Do"
        size="small"
        value={endDate}
        onChange={(e) => onDateChange(startDate, e.target.value)}
        slotProps={{ inputLabel: { shrink: true } }}
        sx={{ width: 160 }}
      />
    </Box>
  );
};

export default DateRangePicker;
