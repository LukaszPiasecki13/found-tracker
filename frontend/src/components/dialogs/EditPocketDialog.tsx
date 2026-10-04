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
import { useCurrencies, useUpdatePocket } from '../../hooks/usePockets';
import { useOperations } from '../../hooks/useOperations';
import type { Pocket, UpdatePocketRequest } from '../../types/api';

interface EditPocketDialogProps {
  pocket: Pocket;
  onClose: () => void;
  onSaved?: (pocket: Pocket) => void;
}

// Mounted only while open, so the form starts from the current pocket on every opening.
const EditPocketDialog: React.FC<EditPocketDialogProps> = ({ pocket, onClose, onSaved }) => {
  const [name, setName] = useState(pocket.name);
  const [baseCurrency, setBaseCurrency] = useState<number | ''>(pocket.base_currency.id);
  const { data: currencies, isLoading: currenciesLoading } = useCurrencies();
  const { data: operations } = useOperations(pocket.name);
  const updatePocketMutation = useUpdatePocket();

  // The stored amounts are in the base currency and are not converted, so it can only
  // change while the portfolio has no operations (the backend enforces the same rule).
  const currencyLocked = (operations?.length ?? 0) > 0;
  const trimmedName = name.trim();
  const isValid = trimmedName.length > 0 && trimmedName.length <= 100 && baseCurrency !== '';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!isValid) {
      return;
    }

    const changes: UpdatePocketRequest = {};
    if (trimmedName !== pocket.name) {
      changes.name = trimmedName;
    }
    if (baseCurrency !== pocket.base_currency.id) {
      changes.base_currency_id = baseCurrency;
    }
    if (Object.keys(changes).length === 0) {
      onClose();
      return;
    }

    try {
      const updated = await updatePocketMutation.mutateAsync({ id: pocket.id, data: changes });
      onSaved?.(updated);
      onClose();
    } catch {
      // Error is handled by the mutation
    }
  };

  return (
    <Dialog open onClose={onClose} maxWidth="sm" fullWidth>
      <form onSubmit={handleSubmit}>
        <DialogTitle>Edytuj portfel</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            <TextField
              label="Nazwa portfela"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              fullWidth
              autoFocus
              disabled={updatePocketMutation.isPending}
              inputProps={{ maxLength: 100 }}
            />

            <TextField
              select
              label="Waluta bazowa"
              value={baseCurrency}
              onChange={(e) => setBaseCurrency(Number(e.target.value))}
              required
              fullWidth
              disabled={updatePocketMutation.isPending || currenciesLoading || currencyLocked}
              helperText={
                currencyLocked
                  ? 'Walutę można zmienić tylko przed pierwszą operacją'
                  : 'Wybierz walutę, w której będą prezentowane wartości'
              }
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
          <Button onClick={onClose} disabled={updatePocketMutation.isPending}>
            Anuluj
          </Button>
          <Button
            type="submit"
            variant="contained"
            disabled={updatePocketMutation.isPending || !isValid}
          >
            {updatePocketMutation.isPending ? <CircularProgress size={24} /> : 'Zapisz'}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};

export default EditPocketDialog;
