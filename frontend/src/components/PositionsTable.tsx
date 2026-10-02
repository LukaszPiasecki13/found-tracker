import React, { useMemo } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  flexRender,
  createColumnHelper,
} from '@tanstack/react-table';
import type { SortingState } from '@tanstack/table-core';
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Box,
  Typography,
  Chip,
  CircularProgress,
} from '@mui/material';
import { TrendingUp as TrendingUpIcon, TrendingDown as TrendingDownIcon } from '@mui/icons-material';
import type { Position } from '../types/api';
import RateMissingChip from './RateMissingChip';

interface PositionsTableProps {
  positions: Position[];
  isLoading?: boolean;
  currencyCode: string;
}

const columnHelper = createColumnHelper<Position>();

const NO_VALUE = '—';

const PositionsTable: React.FC<PositionsTableProps> = ({ positions, isLoading, currencyCode }) => {
  const [sorting, setSorting] = React.useState<SortingState>([]);

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('pl-PL', {
      style: 'currency',
      currency: currencyCode,
      minimumFractionDigits: 2,
    }).format(value);
  };

  const formatPercent = (value: number) => {
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
  };

  const columns = useMemo(
    () => [
      columnHelper.accessor((row) => row.asset.ticker, {
        id: 'ticker',
        header: 'Ticker',
        cell: (info) => (
          <Box>
            <Typography variant="body2" fontWeight="bold">
              {info.getValue()}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {info.row.original.asset.name}
            </Typography>
          </Box>
        ),
      }),
      columnHelper.accessor((row) => row.asset.asset_class.name, {
        id: 'asset_class',
        header: 'Klasa',
        cell: (info) => <Chip label={info.getValue()} size="small" />,
      }),
      columnHelper.accessor('quantity', {
        header: 'Ilość',
        cell: (info) => {
          const value = Number(info.getValue());
          return isNaN(value) ? '' : value.toFixed(4);
        },
      }),
      columnHelper.accessor('average_buy_price', {
        header: 'Śr. cena zakupu',
        cell: (info) => {
          const row = info.row.original;
          const quantity = Number(row.quantity) || 0;
          const costBasis = Number(row.cost_basis_in_portfolio_currency) || 0;
          const avgPrice = quantity > 0 ? costBasis / quantity : Number(row.average_buy_price) || 0;
          return formatCurrency(avgPrice);
        },
      }),
      columnHelper.accessor((row) => row.asset.current_price, {
        id: 'current_price',
        header: 'Cena aktualna',
        cell: (info) => {
          const row = info.row.original;
          const quantity = Number(row.quantity) || 0;
          if (quantity > 0 && row.market_value != null) {
            return formatCurrency(Number(row.market_value) / quantity);
          }
          return NO_VALUE;
        },
      }),
      columnHelper.accessor('market_value', {
        header: 'Wartość rynkowa',
        cell: (info) => {
          const value = info.getValue();
          if (value == null) {
            return info.row.original.rate_missing ? <RateMissingChip /> : NO_VALUE;
          }
          return formatCurrency(Number(value));
        },
      }),
      columnHelper.accessor('unrealized_pnl', {
        header: 'Zysk/Strata',
        cell: (info) => {
          if (info.getValue() == null) return NO_VALUE;
          const value = Number(info.getValue());
          return (
            <Box display="flex" alignItems="center">
              {value >= 0 ? (
                <TrendingUpIcon fontSize="small" color="success" />
              ) : (
                <TrendingDownIcon fontSize="small" color="error" />
              )}
              <Typography
                variant="body2"
                color={value >= 0 ? 'success.main' : 'error.main'}
                sx={{ ml: 0.5 }}
              >
                {formatCurrency(value)}
              </Typography>
            </Box>
          );
        },
      }),
      columnHelper.accessor('return_pct', {
        header: 'Stopa zwrotu',
        cell: (info) => {
          if (info.getValue() == null) return NO_VALUE;
          const value = Number(info.getValue());
          return (
            <Typography
              variant="body2"
              color={value >= 0 ? 'success.main' : 'error.main'}
              fontWeight="bold"
            >
              {formatPercent(value)}
            </Typography>
          );
        },
      }),
      columnHelper.accessor('portfolio_weight_pct', {
        header: 'Udział %',
        cell: (info) => {
          if (info.getValue() == null) return NO_VALUE;
          return `${Number(info.getValue()).toFixed(2)}%`;
        },
      }),
    ],
    [currencyCode]
  );

  const table = useReactTable({
    data: positions,
    columns,
    state: {
      sorting,
    },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  });

  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" p={4}>
        <CircularProgress />
      </Box>
    );
  }

  if (!positions || positions.length === 0) {
    return (
      <Paper sx={{ p: 4, textAlign: 'center' }}>
        <Typography color="text.secondary">
          Brak pozycji w tym portfelu
        </Typography>
      </Paper>
    );
  }

  return (
    <TableContainer component={Paper}>
      <Table>
        <TableHead>
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <TableCell
                  key={header.id}
                  onClick={header.column.getToggleSortingHandler()}
                  sx={{ cursor: 'pointer', fontWeight: 'bold' }}
                >
                  {header.isPlaceholder
                    ? null
                    : flexRender(header.column.columnDef.header, header.getContext())}
                  {{
                    asc: ' 🔼',
                    desc: ' 🔽',
                  }[header.column.getIsSorted() as string] ?? null}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableHead>
        <TableBody>
          {table.getRowModel().rows.map((row) => (
            <TableRow key={row.id} hover>
              {row.getVisibleCells().map((cell) => (
                <TableCell key={cell.id}>
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
};

export default PositionsTable;
