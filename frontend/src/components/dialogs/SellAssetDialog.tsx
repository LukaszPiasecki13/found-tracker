import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  CircularProgress,
  MenuItem,
  Typography,
} from '@mui/material';
import dayjs from 'dayjs';
import { useCreateOperation } from '../../hooks/useOperations';
import type { Position } from '../../types/api';

interface SellAssetDialogProps {
  open: boolean;
  onClose: () => void;
  pocketId: number;
  positions: Position[];
}

const SellAssetDialog: React.FC<SellAssetDialogProps> = ({ open, onClose, pocketId, positions }) => {
  const [selectedPositionId, setSelectedPositionId] = useState<number | ''>('');
  const [quantity, setQuantity] = useState('');
  const [price, setPrice] = useState('');
  const [fee, setFee] = useState('0');
  const [operationDate, setOperationDate] = useState(dayjs().format('YYYY-MM-DD'));
  const [notes, setNotes] = useState('');

  const createOperationMutation = useCreateOperation();

  const selectedPosition = positions.find((p) => p.id === selectedPositionId);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!selectedPosition || !quantity || !price) return;

    const quantityNum = parseFloat(quantity);
    if (quantityNum > selectedPosition.quantity) {
      alert('Nie możesz sprzedać więcej niż posiadasz');
      return;
    }

    try {
      await createOperationMutation.mutateAsync({
        pocket: pocketId,
        asset: selectedPosition.asset.id,
        operation_type: 'sell',
        quantity: quantityNum,
        price: parseFloat(price),
        amount: quantityNum * parseFloat(price) - parseFloat(fee),
        fee: parseFloat(fee),
        operation_date: operationDate,
        notes,
      });
      handleClose();
    } catch (error) {
      // Error handled by mutation
    }
  };

  const handleClose = () => {
    setSelectedPositionId('');
    setQuantity('');
    setPrice('');
    setFee('0');
    setNotes('');
    setOperationDate(dayjs().format('YYYY-MM-DD'));
    onClose();
  };

  const totalAmount = quantity && price ? parseFloat(quantity) * parseFloat(price) - parseFloat(fee || '0') : 0;

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
      <form onSubmit={handleSubmit}>
        <DialogTitle>Sprzedaj aktywo</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            <TextField
              select
              label="Wybierz pozycję"
              value={selectedPositionId}
              onChange={(e) => setSelectedPositionId(Number(e.target.value))}
              required
              fullWidth
              disabled={createOperationMutation.isPending}
            >
              {positions.map((position) => (
                <MenuItem key={position.id} value={position.id}>
                  {position.asset.ticker} - {position.asset.name} (dostępne: {position.quantity})
                </MenuItem>
              ))}
            </TextField>

            {selectedPosition && (
              <Box sx={{ p: 2, bgcolor: 'info.light', borderRadius: 1 }}>
                <Typography variant="body2">
                  Posiadana ilość: <strong>{selectedPosition.quantity}</strong>
                </Typography>
                <Typography variant="body2">
                  Średnia cena zakupu: <strong>{selectedPosition.average_buy_price.toFixed(2)}</strong>
                </Typography>
                <Typography variant="body2">
                  Aktualna cena: <strong>{selectedPosition. asset.current_price.toFixed(2)}</strong>
                </Typography>
              </Box>
            )}

            <Box display="flex" gap={2}>
              <TextField
                label="Ilość"
                type="number"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                required
                fullWidth
                disabled={createOperationMutation.isPending || !selectedPosition}
                inputProps={{
                  step: '0.0001',
                  min: '0',
                  max: selectedPosition?.quantity || undefined,
                }}
                helperText={selectedPosition ? `Maksymalnie: ${selectedPosition.quantity}` : ''}
              />

              <TextField
                label="Cena za jednostkę"
                type="number"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                required
                fullWidth
                disabled={createOperationMutation.isPending || !selectedPosition}
                inputProps={{ step: '0.01', min: '0' }}
              />
            </Box>

            <TextField
              label="Prowizja"
              type="number"
              value={fee}
              onChange={(e) => setFee(e.target.value)}
              fullWidth
              disabled={createOperationMutation.isPending || !selectedPosition}
              inputProps={{ step: '0.01', min: '0' }}
            />

            <TextField
              label="Data operacji"
              type="date"
              value={operationDate}
              onChange={(e) => setOperationDate(e.target.value)}
              required
              fullWidth
              disabled={createOperationMutation.isPending}
              InputLabelProps={{ shrink: true }}
            />

            <TextField
              label="Notatki"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              multiline
              rows={2}
              fullWidth
              disabled={createOperationMutation.isPending}
            />

            {totalAmount > 0 && (
              <Box sx={{ p: 2, bgcolor: 'background.paper', borderRadius: 1, border: 1, borderColor: 'divider' }}>
                <TextField
                  label="Kwota do otrzymania"
                  value={totalAmount.toFixed(2)}
                  disabled
                  fullWidth
                  InputProps={{ readOnly: true }}
                />
              </Box>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleClose} disabled={createOperationMutation.isPending}>
            Anuluj
          </Button>
          <Button
            type="submit"
            variant="contained"
            color="warning"
            disabled={createOperationMutation.isPending || !selectedPosition || !quantity || !price}
          >
            {createOperationMutation.isPending ? <CircularProgress size={24} /> : 'Sprzedaj'}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};

export default SellAssetDialog;
