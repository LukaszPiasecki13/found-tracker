import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  CardContent,
  Typography,
  Grid,
  Box,
  IconButton,
  Button,
  CircularProgress,
  Chip,
} from '@mui/material';
import {
  Delete as DeleteIcon,
  Add as AddIcon,
  TrendingUp as TrendingUpIcon,
} from '@mui/icons-material';
import { usePockets, useDeletePocket } from '../hooks/usePockets';
import AddPocketDialog from './dialogs/AddPocketDialog';

const PocketsList: React.FC = () => {
  const navigate = useNavigate();
  const [openAddDialog, setOpenAddDialog] = useState(false);
  const { data: pockets, isLoading, error } = usePockets();
  const deletePocketMutation = useDeletePocket();

  const handleDelete = (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    if (window.confirm('Czy na pewno chcesz usunąć ten portfel?')) {
      deletePocketMutation.mutate(id);
    }
  };

  const handlePocketClick = (name: string) => {
    navigate(`/pockets/${encodeURIComponent(name)}`);
  };

  const formatCurrency = (value: number, currencyCode: string) => {
    return new Intl.NumberFormat('pl-PL', {
      style: 'currency',
      currency: currencyCode,
    }).format(value);
  };

  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" p={4}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Typography color="error">
        Błąd podczas ładowania portfeli
      </Typography>
    );
  }

  return (
    <>
      <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h5" component="h2">
          Moje Portfele
        </Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => setOpenAddDialog(true)}
        >
          Dodaj portfel
        </Button>
      </Box>

      <Grid container spacing={2}>
        {pockets && pockets.length === 0 ? (
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography align="center" color="text.secondary">
                  Brak portfeli. Dodaj swój pierwszy portfel!
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        ) : (
          pockets?.map((pocket) => (
            <Grid item xs={12} sm={6} md={4} key={pocket.id}>
              <Card
                sx={{
                  cursor: 'pointer',
                  transition: 'transform 0.2s, box-shadow 0.2s',
                  '&:hover': {
                    transform: 'translateY(-4px)',
                    boxShadow: 4,
                  },
                }}
                onClick={() => handlePocketClick(pocket.name)}
              >
                <CardContent>
                  <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={2}>
                    <Box>
                      <Typography variant="h6" component="h3">
                        {pocket.name}
                      </Typography>
                      <Chip
                        label={pocket.base_currency_detail.code}
                        size="small"
                        sx={{ mt: 0.5 }}
                      />
                    </Box>
                    <IconButton
                      size="small"
                      onClick={(e) => handleDelete(e, pocket.id)}
                      disabled={deletePocketMutation.isPending}
                    >
                      <DeleteIcon />
                    </IconButton>
                  </Box>

                  <Box>
                    <Typography variant="body2" color="text.secondary">
                      Saldo gotówkowe
                    </Typography>
                    <Typography variant="h6" gutterBottom>
                      {formatCurrency(pocket.cash_balance, pocket.base_currency_detail.code)}
                    </Typography>

                    <Typography variant="body2" color="text.secondary">
                      Całkowite wpłaty
                    </Typography>
                    <Typography variant="body1">
                      {formatCurrency(pocket.total_deposited, pocket.base_currency_detail.code)}
                    </Typography>

                    {pocket.total_profit_loss !== undefined && (
                      <Box mt={1}>
                        <Typography variant="body2" color="text.secondary">
                          Zysk/Strata
                        </Typography>
                        <Box display="flex" alignItems="center" gap={0.5}>
                          <TrendingUpIcon
                            fontSize="small"
                            color={pocket.total_profit_loss >= 0 ? 'success' : 'error'}
                          />
                          <Typography
                            variant="body1"
                            color={pocket.total_profit_loss >= 0 ? 'success.main' : 'error.main'}
                          >
                            {formatCurrency(pocket.total_profit_loss, pocket.base_currency_detail.code)}
                            {pocket.total_return_pct !== undefined && (
                              <> ({pocket.total_return_pct.toFixed(2)}%)</>
                            )}
                          </Typography>
                        </Box>
                      </Box>
                    )}
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          ))
        )}
      </Grid>

      <AddPocketDialog
        open={openAddDialog}
        onClose={() => setOpenAddDialog(false)}
      />
    </>
  );
};

export default PocketsList;
