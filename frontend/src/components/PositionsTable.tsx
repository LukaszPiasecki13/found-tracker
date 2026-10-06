import React, { useMemo } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  getExpandedRowModel,
  flexRender,
  createColumnHelper,
} from '@tanstack/react-table';
import type { ExpandedState, SortingState } from '@tanstack/table-core';
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
  IconButton,
  TableFooter,
} from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
} from '@mui/icons-material';
import type { Position } from '../types/api';
import RateMissingChip from './RateMissingChip';
import PositionDetails from './PositionDetails';
import { NO_VALUE, formatMoney, formatPercent } from '../utils/formatMoney';

interface PositionsTableProps {
  positions: Position[];
  isLoading?: boolean;
  currencyCode: string;
}

const columnHelper = createColumnHelper<Position>();

const PercentCell: React.FC<{ value: number | null | undefined; bold?: boolean }> = ({
  value,
  bold,
}) => {
  if (value == null) return <>{NO_VALUE}</>;
  return (
    <Typography
      variant="body2"
      color={value >= 0 ? 'success.main' : 'error.main'}
      fontWeight={bold ? 'bold' : undefined}
    >
      {formatPercent(value)}
    </Typography>
  );
};

const PositionsTable: React.FC<PositionsTableProps> = ({ positions, isLoading, currencyCode }) => {
  const [sorting, setSorting] = React.useState<SortingState>([]);
  const [expanded, setExpanded] = React.useState<ExpandedState>({});

  const columns = useMemo(
    () => [
      columnHelper.display({
        id: 'expand',
        enableSorting: false,
        header: '',
        cell: ({ row }) => (
          <IconButton
            size="small"
            onClick={row.getToggleExpandedHandler()}
            aria-label="Szczegóły pozycji"
          >
            {row.getIsExpanded() ? (
              <ExpandLessIcon fontSize="small" />
            ) : (
              <ExpandMoreIcon fontSize="small" />
            )}
          </IconButton>
        ),
      }),
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
        cell: (info) =>
          formatMoney(info.getValue(), info.row.original.asset.currency.code, 'code'),
      }),
      columnHelper.accessor((row) => row.asset.current_price, {
        id: 'current_price',
        header: 'Cena aktualna',
        cell: (info) =>
          formatMoney(info.getValue(), info.row.original.asset.currency.code, 'code'),
      }),
      columnHelper.accessor('price_change_pct', {
        header: 'Zmiana ceny %',
        cell: (info) => <PercentCell value={info.getValue()} />,
      }),
      columnHelper.accessor('market_value', {
        header: `Wartość (${currencyCode})`,
        cell: (info) => {
          const value = info.getValue();
          if (value == null) {
            return info.row.original.rate_missing ? <RateMissingChip /> : NO_VALUE;
          }
          return formatMoney(Number(value), currencyCode);
        },
      }),
      columnHelper.accessor('unrealized_pnl', {
        header: `Zysk/Strata (${currencyCode})`,
        cell: (info) => {
          const value = info.getValue();
          if (value == null) return NO_VALUE;
          const amount = Number(value);
          return (
            <Box
              display="flex"
              alignItems="center"
              title="Bez dywidend i odsetek"
            >
              {amount >= 0 ? (
                <TrendingUpIcon fontSize="small" color="success" />
              ) : (
                <TrendingDownIcon fontSize="small" color="error" />
              )}
              <Typography
                variant="body2"
                color={amount >= 0 ? 'success.main' : 'error.main'}
                sx={{ ml: 0.5 }}
              >
                {formatMoney(amount, currencyCode)}
              </Typography>
            </Box>
          );
        },
      }),
      columnHelper.accessor('return_pct', {
        header: `Zwrot % (${currencyCode})`,
        cell: (info) => <PercentCell value={info.getValue()} bold />,
      }),
      columnHelper.accessor('portfolio_weight_pct', {
        header: 'Udział %',
        cell: (info) => {
          const value = info.getValue();
          return value == null ? NO_VALUE : `${Number(value).toFixed(2)}%`;
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
      expanded,
    },
    onSortingChange: setSorting,
    onExpandedChange: setExpanded,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getExpandedRowModel: getExpandedRowModel(),
  });

  // Totals in the portfolio's currency; no partial sum when a rate is missing,
  // the same rule as the backend (DEC-2).
  const totals = useMemo(() => {
    if (positions.some((p) => p.market_value == null || p.unrealized_pnl == null)) {
      return undefined;
    }
    return {
      value: positions.reduce((sum, p) => sum + (p.market_value ?? 0), 0),
      profit: positions.reduce((sum, p) => sum + (p.unrealized_pnl ?? 0), 0),
    };
  }, [positions]);

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
                  sx={{
                    cursor: header.column.getCanSort() ? 'pointer' : 'default',
                    fontWeight: 'bold',
                  }}
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
            <React.Fragment key={row.id}>
              <TableRow hover>
                {row.getVisibleCells().map((cell) => (
                  <TableCell key={cell.id}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
              {row.getIsExpanded() && (
                <TableRow>
                  <TableCell colSpan={columns.length} sx={{ bgcolor: 'action.hover' }}>
                    <PositionDetails position={row.original} currencyCode={currencyCode} />
                  </TableCell>
                </TableRow>
              )}
            </React.Fragment>
          ))}
        </TableBody>
        <TableFooter>
          <TableRow>
            <TableCell colSpan={7} sx={{ fontWeight: 'bold' }}>
              Suma
            </TableCell>
            <TableCell sx={{ fontWeight: 'bold' }}>
              {formatMoney(totals?.value, currencyCode)}
            </TableCell>
            <TableCell sx={{ fontWeight: 'bold' }}>
              {formatMoney(totals?.profit, currencyCode)}
            </TableCell>
            <TableCell colSpan={2} />
          </TableRow>
        </TableFooter>
      </Table>
    </TableContainer>
  );
};

export default PositionsTable;
