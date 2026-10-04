import React from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  Typography,
} from '@mui/material';
import dayjs from 'dayjs';
import type { ImportRow, ImportRowStatus } from '../../types/api';

interface ImportRowsTableProps {
  rows: ImportRow[];
}

const getRowStatusColor = (
  status: ImportRowStatus
): 'success' | 'default' | 'warning' | 'error' => {
  const colors: Record<
    ImportRowStatus,
    'success' | 'default' | 'warning' | 'error'
  > = {
    ok: 'success',
    duplicate: 'default',
    unrecognized: 'warning',
    error: 'error',
    skip: 'default',
  };
  return colors[status];
};

const getRowStatusLabel = (status: ImportRowStatus) => {
  const labels: Record<ImportRowStatus, string> = {
    ok: 'OK',
    duplicate: 'Duplikat',
    unrecognized: 'Nieznane',
    error: 'Błąd',
    skip: 'Pomiń',
  };
  return labels[status];
};

export const ImportRowsTable: React.FC<ImportRowsTableProps> = ({ rows }) => {
  return (
    <TableContainer component={Paper} sx={{ mb: 3 }}>
      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Wiersz</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>Typ operacji</TableCell>
            <TableCell>Data</TableCell>
            <TableCell>Ticker</TableCell>
            <TableCell>Ilość</TableCell>
            <TableCell>Cena</TableCell>
            <TableCell>Kwota</TableCell>
            <TableCell>Komunikat</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row, idx) => (
            <TableRow key={idx} hover>
              <TableCell>{row.row_number}</TableCell>
              <TableCell>
                <Chip
                  label={getRowStatusLabel(row.row_status)}
                  color={getRowStatusColor(row.row_status)}
                  size="small"
                />
              </TableCell>
              <TableCell>{row.payload.operation_type || '-'}</TableCell>
              <TableCell>
                {row.payload.operation_date
                  ? dayjs(row.payload.operation_date).format('DD.MM.YYYY')
                  : '-'}
              </TableCell>
              <TableCell>{row.payload.ticker || '-'}</TableCell>
              <TableCell>{row.payload.quantity || '-'}</TableCell>
              <TableCell>{row.payload.price || '-'}</TableCell>
              <TableCell>{row.payload.amount || '-'}</TableCell>
              <TableCell>
                <Typography variant="caption" color="text.secondary">
                  {row.message || '-'}
                </Typography>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
};
