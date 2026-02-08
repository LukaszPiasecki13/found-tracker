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
  IconButton,
} from '@mui/material';
import { Delete as DeleteIcon } from '@mui/icons-material';
import dayjs from 'dayjs';
import type { Operation } from '../types/api';
import { useDeleteOperation } from '../hooks/useOperations';

interface OperationsTableProps {
  operations: Operation[];
  isLoading?: boolean;
  showPocket?: boolean;
}

const columnHelper = createColumnHelper<Operation>();

const OperationsTable: React.FC<OperationsTableProps> = ({ operations, isLoading, showPocket = false }) => {
  const [sorting, setSorting] = React.useState<SortingState>([]);
  const deleteOperationMutation = useDeleteOperation();

  const handleDelete = (id: number) => {
    if (window.confirm('Czy na pewno chcesz usunąć tę operację? Spowoduje to cofnięcie jej efektów.')) {
      deleteOperationMutation.mutate(id);
    }
  };

  const getOperationTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      buy: 'Kupno',
      sell: 'Sprzedaż',
      deposit: 'Wpłata',
      withdrawal: 'Wypłata',
      dividend: 'Dywidenda',
    };
    return labels[type] || type;
  };

  const getOperationTypeColor = (type: string) => {
    const colors: Record<string, any> = {
      buy: 'success',
      sell: 'warning',
      deposit: 'info',
      withdrawal: 'error',
      dividend: 'primary',
    };
    return colors[type] || 'default';
  };

  const columns = useMemo(
    () => [
      columnHelper.accessor('operation_date', {
        header: 'Data',
        cell: (info) => dayjs(info.getValue()).format('DD.MM.YYYY'),
      }),
      columnHelper.accessor('operation_type', {
        header: 'Typ',
        cell: (info) => (
          <Chip
            label={getOperationTypeLabel(info.getValue())}
            size="small"
            color={getOperationTypeColor(info.getValue())}
          />
        ),
      }),
      ...(showPocket
        ? [
            columnHelper.display({
              id: 'pocket',
              header: 'Portfel',
              cell: () => <Typography variant="body2">-</Typography>, // Would need pocket name from API
            }),
          ]
        : []),
      columnHelper.accessor((row) => row.asset?.ticker || '-', {
        id: 'ticker',
        header: 'Ticker',
        cell: (info) => (
          <Box>
            <Typography variant="body2" fontWeight="bold">
              {info.getValue()}
            </Typography>
            {info.row.original.asset && (
              <Typography variant="caption" color="text.secondary">
                {info.row.original.asset.name}
              </Typography>
            )}
          </Box>
        ),
      }),
      columnHelper.accessor('quantity', {
        header: 'Ilość',
        cell: (info) => {
          const value = Number(info.getValue());
          return !isNaN(value) ? value.toFixed(4) : '-';
        },
      }),
      columnHelper.accessor('price', {
        header: 'Cena',
        cell: (info) => {
          const value = Number(info.getValue());
          return !isNaN(value) ? value.toFixed(2) : '-';
        },
      }),
      columnHelper.accessor('fee', {
        header: 'Prowizja',
        cell: (info) => {
          const value = Number(info.getValue());
          return !isNaN(value) ? value.toFixed(2) : '-';
        },
      }),
      columnHelper.accessor('amount', {
        header: 'Kwota',
        cell: (info) => (
          <Typography
            variant="body2"
            fontWeight="bold"
            color={
              ['buy', 'withdrawal'].includes(info.row.original.operation_type)
                ? 'error.main'
                : 'success.main'
            }
          >
            {['buy', 'withdrawal'].includes(info.row.original.operation_type) ? '-' : '+'}
            {(() => {
              const value = Number(info.getValue());
              return !isNaN(value) ? value.toFixed(2) : '-';
            })()}
          </Typography>
        ),
      }),
      columnHelper.accessor('notes', {
        header: 'Notatki',
        cell: (info) => (
          <Typography variant="caption" color="text.secondary">
            {info.getValue() || '-'}
          </Typography>
        ),
      }),
      columnHelper.display({
        id: 'actions',
        header: 'Akcje',
        cell: (info) => (
          <IconButton
            size="small"
            onClick={() => handleDelete(info.row.original.id)}
            disabled={deleteOperationMutation.isPending}
          >
            <DeleteIcon fontSize="small" />
          </IconButton>
        ),
      }),
    ],
    [showPocket, deleteOperationMutation.isPending]
  );

  const table = useReactTable({
    data: operations,
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

  if (!operations || operations.length === 0) {
    return (
      <Paper sx={{ p: 4, textAlign: 'center' }}>
        <Typography color="text.secondary">Brak operacji</Typography>
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

export default OperationsTable;
