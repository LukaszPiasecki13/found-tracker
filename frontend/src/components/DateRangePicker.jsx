import React, { useState } from 'react';
import { Grid } from '@mui/material';
import { LocalizationProvider } from "@mui/x-date-pickers";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import { DatePicker } from "@mui/x-date-pickers/DatePicker";

export default function DateRangePicker ({ initialStartDate, initialEndDate, onDateChange }) {
  const [startDate, setStartDate] = useState(initialStartDate);
  const [endDate, setEndDate] = useState(initialEndDate);

  const handleStartDateChange = (newStartDate) => {
    setStartDate(newStartDate);
    onDateChange(newStartDate, endDate);
  };

  const handleEndDateChange = (newEndDate) => {
    setEndDate(newEndDate);
    onDateChange(startDate, newEndDate);
  };

  return (
    <Grid container justifyContent="flex-end">
      <Grid item xs={3} sm={2}>
        <LocalizationProvider dateAdapter={AdapterDayjs}>
          <DatePicker
            label="START DATE"
            value={startDate}
            format="DD/MM/YYYY"
            onChange={handleStartDateChange}
          />
        </LocalizationProvider>
      </Grid>
      <Grid item xs={3} sm={2}>
        <LocalizationProvider dateAdapter={AdapterDayjs}>
          <DatePicker
            label="STOP DATE"
            value={endDate}
            format="DD/MM/YYYY"
            onChange={handleEndDateChange}
          />
        </LocalizationProvider>
      </Grid>
    </Grid>
  );
}



