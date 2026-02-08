import React from 'react';
import { Box, Button, ButtonGroup, TextField } from '@mui/material';
import dayjs from 'dayjs';

interface DateRangePickerProps {
  startDate: string;
  endDate: string;
  onDateChange: (startDate: string, endDate: string) => void;
}

const presets = [
  { label: '1M', months: 1 },
  { label: '3M', months: 3 },
  { label: '6M', months: 6 },
  { label: '1R', months: 12 },
  { label: '2R', months: 24 },
  { label: 'YTD', months: 0 }, // special case
];

const DateRangePicker: React.FC<DateRangePickerProps> = ({
  startDate,
  endDate,
  onDateChange,
}) => {
  const handlePreset = (months: number) => {
    const end = dayjs().format('YYYY-MM-DD');
    let start: string;

    if (months === 0) {
      // YTD
      start = dayjs().startOf('year').format('YYYY-MM-DD');
    } else {
      start = dayjs().subtract(months, 'month').format('YYYY-MM-DD');
    }

    onDateChange(start, end);
  };

  return (
    <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
      <ButtonGroup size="small" variant="outlined">
        {presets.map((preset) => {
          const isActive =
            preset.months === 0
              ? startDate === dayjs().startOf('year').format('YYYY-MM-DD')
              : startDate ===
                dayjs().subtract(preset.months, 'month').format('YYYY-MM-DD');

          return (
            <Button
              key={preset.label}
              variant={isActive ? 'contained' : 'outlined'}
              onClick={() => handlePreset(preset.months)}
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
