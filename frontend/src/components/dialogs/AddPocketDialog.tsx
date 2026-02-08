import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  MenuItem,
  CircularProgress,
  Box,
} from '@mui/material';
import { useCreatePocket, useCurrencies } from '../../hooks/usePockets';

interface AddPocketDialogProps {
  open: boolean;
  onClose: () => void;
}

const AddPocketDialog: React.FC<AddPocketDialogProps> = ({ open, onClose }) => {
  const [name, setName] = useState('');
  const [baseCurrency, setBaseCurrency] = useState<number | ''>('');
  const { data: currencies, isLoading: currenciesLoading } = useCurrencies();
  const createPocketMutation = useCreatePocket();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!name || !baseCurrency) {
      return;
    }

    try {
      await createPocketMutation.mutateAsync({
        name,
        base_currency: baseCurrency as number,
      });
      handleClose();
    } catch (error) {
      // Error is handled by the mutation
    }
  };

  const handleClose = () => {
    setName('');
    setBaseCurrency('');
    onClose();
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <form onSubmit={handleSubmit}>
        <DialogTitle>Dodaj nowy portfel</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            <TextField
              label="Nazwa portfela"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              fullWidth
              autoFocus
              disabled={createPocketMutation.isPending}
            />

            <TextField
              select
              label="Waluta bazowa"
              value={baseCurrency}
              onChange={(e) => setBaseCurrency(Number(e.target.value))}
              required
              fullWidth
              disabled={createPocketMutation.isPending || currenciesLoading}
              helperText="Wybierz walutę, w której będą prezentowane wartości"
            >
              {currenciesLoading ? (
                <MenuItem disabled>
                  <CircularProgress size={20} />
                </MenuItem>
              ) : (
                currencies?.map((currency) => (
                  <MenuItem key={currency.id} value={currency.id}>
                    {currency.code}
                  </MenuItem>
                ))
              )}
            </TextField>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleClose} disabled={createPocketMutation.isPending}>
            Anuluj
          </Button>
          <Button
            type="submit"
            variant="contained"
            disabled={createPocketMutation.isPending || !name || !baseCurrency}
          >
            {createPocketMutation.isPending ? <CircularProgress size={24} /> : 'Dodaj'}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};

export default AddPocketDialog;
