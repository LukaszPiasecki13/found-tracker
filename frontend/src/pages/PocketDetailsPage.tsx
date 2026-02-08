import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Paper,
  Grid,
  Button,
  ButtonGroup,
  Chip,
  CircularProgress,
} from '@mui/material';
import {
  Add as AddIcon,
  Remove as RemoveIcon,
  ShowChart as ChartIcon,
  History as HistoryIcon,
  AccountBalance as WalletIcon,
} from '@mui/icons-material';
import { usePocketByName } from '../hooks/usePockets';
import { usePositions } from '../hooks/usePositions';
import PositionsTable from '../components/PositionsTable';
import BuyAssetDialog from '../components/dialogs/BuyAssetDialog';
import SellAssetDialog from '../components/dialogs/SellAssetDialog';
import CashOperationDialog from '../components/dialogs/CashOperationDialog';

const PocketDetailsPage: React.FC = () => {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const pocketName = decodeURIComponent(slug || '');

  const { data: pocket, isLoading: pocketLoading } = usePocketByName(pocketName);
  const { data: positions, isLoading: positionsLoading } = usePositions(pocketName);

  const [openBuyDialog, setOpenBuyDialog] = useState(false);
  const [openSellDialog, setOpenSellDialog] = useState(false);
  const [openCashDialog, setOpenCashDialog] = useState(false);

  if (pocketLoading || !pocket) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="60vh">
        <CircularProgress />
      </Box>
    );
  }

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('pl-PL', {
      style: 'currency',
      currency: pocket.base_currency.code,
    }).format(value);
  };

  const totalPositionsValue = positions?.reduce((sum, pos) => sum + (pos.market_value || 0), 0) || 0;
  const totalValue = pocket.cash_balance + totalPositionsValue;

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

      {/* Summary Cards */}
      <Grid container spacing={2} sx={{ mb: 4 }}>
        <Grid item xs={12} md={3}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="caption" color="text.secondary">
              Saldo gotówkowe
            </Typography>
            <Typography variant="h5" fontWeight="bold">
              {formatCurrency(pocket.cash_balance)}
            </Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} md={3}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="caption" color="text.secondary">
              Wartość pozycji
            </Typography>
            <Typography variant="h5" fontWeight="bold">
              {formatCurrency(totalPositionsValue)}
            </Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} md={3}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="caption" color="text.secondary">
              Całkowita wartość
            </Typography>
            <Typography variant="h5" fontWeight="bold">
              {formatCurrency(totalValue)}
            </Typography>
          </Paper>
        </Grid>
        <Grid item xs={12} md={3}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="caption" color="text.secondary">
              Zysk/Strata
            </Typography>
            <Typography
              variant="h5"
              fontWeight="bold"
              color={(pocket.total_profit_loss || 0) >= 0 ? 'success.main' : 'error.main'}
            >
              {formatCurrency(pocket.total_profit_loss || 0)}
            </Typography>
            {pocket.total_return_pct !== undefined && (
              <Typography variant="caption" color="text.secondary">
                ({pocket.total_return_pct.toFixed(2)}%)
              </Typography>
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
    </Box>
  );
};

export default PocketDetailsPage;
