import React from 'react';
import { Chip, Tooltip } from '@mui/material';

/** Marks a value that could not be computed because no currency rate was available. */
const RateMissingChip: React.FC = () => (
  <Tooltip title="Brak kursu waluty tego waloru wobec waluty portfela — wartości nie da się policzyć.">
    <Chip label="Brak kursu" size="small" color="warning" />
  </Tooltip>
);

export default RateMissingChip;
