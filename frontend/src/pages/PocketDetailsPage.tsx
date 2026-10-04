import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Alert,
  Box,
  Typography,
  Paper,
  Grid,
  Button,
  ButtonGroup,
  Chip,
  CircularProgress,
  Skeleton,
} from '@mui/material';
import {
  Add as AddIcon,
  Remove as RemoveIcon,
  Edit as EditIcon,
  ShowChart as ChartIcon,
  History as HistoryIcon,
  AccountBalance as WalletIcon,
  CloudUpload as ImportIcon,
} from '@mui/icons-material';
import { usePocketByName } from '../hooks/usePockets';
import { usePositions } from '../hooks/usePositions';
import PositionsTable from '../components/PositionsTable';
import RateMissingChip from '../components/RateMissingChip';
import BuyAssetDialog from '../components/dialogs/BuyAssetDialog';
import SellAssetDialog from '../components/dialogs/SellAssetDialog';
import CashOperationDialog from '../components/dialogs/CashOperationDialog';
import ImportDialog from '../components/dialogs/ImportDialog';
import EditPocketDialog from '../components/dialogs/EditPocketDialog';

const PocketDetailsPage: React.FC = () => {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const pocketName = decodeURIComponent(slug || '');

  const { data: pocket, isLoading: pocketLoading, error: pocketError } = usePocketByName(pocketName);
  const { data: positions, isLoading: positionsLoading } = usePositions(pocketName);

  const [openBuyDialog, setOpenBuyDialog] = useState(false);
  const [openSellDialog, setOpenSellDialog] = useState(false);
  const [openCashDialog, setOpenCashDialog] = useState(false);
  const [openImportDialog, setOpenImportDialog] = useState(false);
  const [openEditDialog, setOpenEditDialog] = useState(false);

  if (pocketLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="60vh">
        <CircularProgress />
      </Box>
    );
  }

  if (pocketError || !pocket) {
    return (
      <Box display="flex" flexDirection="column" justifyContent="center" alignItems="center" minHeight="60vh" gap={2}>
        <Typography variant="h5" color="error">
          Nie znaleziono portfela "{pocketName}"
        </Typography>
        <Button variant="contained" onClick={() => navigate('/')}>
          Powrót do listy portfeli
        </Button>
      </Box>
    );
  }

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('pl-PL', {
      style: 'currency',
      currency: pocket.base_currency.code,
    }).format(value);
  };

  const cashBalance = Number(pocket.cash_balance) || 0;
  const totalDeposited = Number(pocket.total_deposited) || 0;
  // Totals come from the freshly valued positions; when any position has no currency rate
  // they cannot be computed (null) rather than shown as a misleading partial sum.
  // The positions endpoint refreshes rates first, so once it has answered it is authoritative;
  // the pocket flag (no refresh) only covers the time the positions are still loading.
  const rateMissing = positions
    ? positions.some((pos) => pos.rate_missing === true)
    : pocket.rate_missing === true;
  const totalPositionsValue = rateMissing
    ? null
    : positions
      ? positions.reduce((sum, pos) => sum + Number(pos.market_value ?? 0), 0)
      : (pocket.positions_value ?? null);
  const totalValue = totalPositionsValue === null ? null : cashBalance + totalPositionsValue;
  const totalProfitLoss = totalValue === null ? null : totalValue - totalDeposited;
  const totalReturnPct =
    totalProfitLoss === null ? null : totalDeposited === 0 ? 0 : (totalProfitLoss / totalDeposited) * 100;

  return (
    <Box>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" component="h1" gutterBottom>
            {pocket.name}
          </Typography>
          <Chip label={pocket.base_currency.code} />
        </Box>

        <ButtonGroup variant="outlined">
          <Button
            startIcon={<EditIcon />}
            onClick={() => setOpenEditDialog(true)}
          >
            Edytuj
          </Button>
          <Button
            startIcon={<ChartIcon />}
            onClick={() => navigate(`/pockets/${slug}/charts`)}
          >
            Wykresy
          </Button>
          <Button
            startIcon={<HistoryIcon />}
            onClick={() => navigate(`/pockets/${slug}/history`)}
          >
            Historia
          </Button>
        </ButtonGroup>
      </Box>

      {rateMissing && !positionsLoading && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          Dla części pozycji brakuje kursu waluty wobec waluty portfela — wartość portfela i wynik
          nie mogą zostać policzone.
        </Alert>
      )}

      {/* Summary Cards */}
      <Grid container spacing={2} sx={{ mb: 4 }}>
        <Grid size={{ xs: 12, md: 3 }}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="caption" color="text.secondary">
              Saldo gotówkowe
            </Typography>
            <Typography variant="h5" fontWeight="bold">
              {formatCurrency(cashBalance)}
            </Typography>
          </Paper>
        </Grid>
        <Grid size={{ xs: 12, md: 3 }}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="caption" color="text.secondary">
              Wartość pozycji
            </Typography>
            {positionsLoading ? (
              <Skeleton width={120} height={40} />
            ) : totalPositionsValue === null ? (
              <RateMissingChip />
            ) : (
              <Typography variant="h5" fontWeight="bold">
                {formatCurrency(totalPositionsValue)}
              </Typography>
            )}
          </Paper>
        </Grid>
        <Grid size={{ xs: 12, md: 3 }}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="caption" color="text.secondary">
              Całkowita wartość
            </Typography>
            {positionsLoading ? (
              <Skeleton width={120} height={40} />
            ) : totalValue === null ? (
              <RateMissingChip />
            ) : (
              <Typography variant="h5" fontWeight="bold">
                {formatCurrency(totalValue)}
              </Typography>
            )}
          </Paper>
        </Grid>
        <Grid size={{ xs: 12, md: 3 }}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="caption" color="text.secondary">
              Zysk/Strata
            </Typography>
            {positionsLoading ? (
              <Skeleton width={120} height={40} />
            ) : totalProfitLoss === null ? (
              <RateMissingChip />
            ) : (
              <>
                <Typography
                  variant="h5"
                  fontWeight="bold"
                  color={totalProfitLoss >= 0 ? 'success.main' : 'error.main'}
                >
                  {formatCurrency(totalProfitLoss)}
                </Typography>
                {totalReturnPct !== null && (
                  <Typography variant="caption" color="text.secondary">
                    ({totalReturnPct.toFixed(2)}%)
                  </Typography>
                )}
              </>
            )}
          </Paper>
        </Grid>
      </Grid>

      {/* Action Buttons */}
      <Box display="flex" gap={2} mb={3}>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => setOpenBuyDialog(true)}
        >
          Kup aktywo
        </Button>
        <Button
          variant="outlined"
          startIcon={<RemoveIcon />}
          onClick={() => setOpenSellDialog(true)}
          disabled={!positions || positions.length === 0}
        >
          Sprzedaj
        </Button>
        <Button
          variant="outlined"
          startIcon={<WalletIcon />}
          onClick={() => setOpenCashDialog(true)}
        >
          Gotówka
        </Button>
        <Button
          variant="outlined"
          startIcon={<ImportIcon />}
          onClick={() => setOpenImportDialog(true)}
        >
          Import
        </Button>
      </Box>

      {/* Positions Table */}
      <Box>
        <Typography variant="h6" gutterBottom>
          Pozycje
        </Typography>
        <PositionsTable
          positions={positions || []}
          isLoading={positionsLoading}
          currencyCode={pocket.base_currency.code}
        />
      </Box>

      {/* Dialogs */}
      <BuyAssetDialog 
        open={openBuyDialog} 
        onClose={() => setOpenBuyDialog(false)}
        pocketId={pocket.id}
      />
      <SellAssetDialog 
        open={openSellDialog} 
        onClose={() => setOpenSellDialog(false)}
        pocketId={pocket.id}
        positions={positions || []}
      />
      <CashOperationDialog
        open={openCashDialog}
        onClose={() => setOpenCashDialog(false)}
        pocketId={pocket.id}
      />
      <ImportDialog
        open={openImportDialog}
        onClose={() => setOpenImportDialog(false)}
        pocketId={pocket.id}
      />
      {openEditDialog && (
        <EditPocketDialog
          pocket={pocket}
          onClose={() => setOpenEditDialog(false)}
          onSaved={(updated) => {
            // The route is keyed by the portfolio name, so a rename moves the page.
            if (updated.name !== pocket.name) {
              navigate(`/pockets/${encodeURIComponent(updated.name)}`, { replace: true });
            }
          }}
        />
      )}
    </Box>
  );
};

export default PocketDetailsPage;
