import React, { useState, useEffect } from 'react';
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
  Chip,
  Alert,
} from '@mui/material';
import dayjs from 'dayjs';
import { useCreateOperation } from '../../hooks/useOperations';
import { usePocket } from '../../hooks/usePockets';
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
  const [fxRate, setFxRate] = useState('1');
  const [operationDate, setOperationDate] = useState(dayjs().format('YYYY-MM-DD'));
  const [notes, setNotes] = useState('');

  const { data: pocket } = usePocket(pocketId);
  const createOperationMutation = useCreateOperation();

  const selectedPosition = positions.find((p) => p.id === selectedPositionId);

  // Check if currencies are different and update FX rate
  useEffect(() => {
    if (selectedPosition && pocket) {
      const assetCurrency = selectedPosition.asset.currency.code;
      const pocketCurrency = pocket.base_currency_detail.code;
      
      if (assetCurrency !== pocketCurrency) {
        const rate = selectedPosition.asset.currency.exchange_rate || 1;
        setFxRate(rate.toString());
      } else {
        setFxRate('1');
      }
    }
  }, [selectedPosition, pocket]);

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
        fx_rate: parseFloat(fxRate),
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
    setFxRate('1');
    setNotes('');
    setOperationDate(dayjs().format('YYYY-MM-DD'));
    onClose();
  };

  const needsCurrencyConversion = selectedPosition && pocket && 
    selectedPosition.asset.currency.code !== pocket.base_currency_detail.code;

  const totalAmount = quantity && price 
    ? parseFloat(quantity) * parseFloat(price) * parseFloat(fxRate) - parseFloat(fee || '0') 
    : 0;

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

            {/* Currency information and conversion */}
            {selectedPosition && pocket && (
              <Box sx={{ p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
                <Typography variant="subtitle2" gutterBottom>
                  Informacje o walutach
                </Typography>
                <Box display="flex" gap={2} alignItems="center" mb={1}>
                  <Chip 
                    label={`Aktywo: ${selectedPosition.asset.currency.code}`} 
                    size="small" 
                    color="primary"
                  />
                  <Chip 
                    label={`Portfel: ${pocket.base_currency_detail.code}`} 
                    size="small" 
                    color="secondary"
                  />
                </Box>
                
                {needsCurrencyConversion && (
                  <>
                    <Alert severity="info" sx={{ mb: 2 }}>
                      Wymagana konwersja walut: {selectedPosition.asset.currency.code} → {pocket.base_currency_detail.code}
                    </Alert>
                    <TextField
                      label={`Kurs wymiany (1 ${selectedPosition.asset.currency.code} = ? ${pocket.base_currency_detail.code})`}
                      type="number"
                      value={fxRate}
                      onChange={(e) => setFxRate(e.target.value)}
                      required
                      fullWidth
                      disabled={createOperationMutation.isPending}
                      inputProps={{ step: '0.0001', min: '0' }}
                      helperText="Podaj aktualny kurs wymiany waluty aktywa do waluty portfela"
                    />
                  </>
                )}
                
                {!needsCurrencyConversion && (
                  <Typography variant="body2" color="text.secondary">
                    Obie waluty są takie same - konwersja nie jest wymagana
                  </Typography>
                )}
              </Box>
            )}

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

            {totalAmount > 0 && pocket && selectedPosition && (
              <Box sx={{ p: 2, bgcolor: 'warning.light', borderRadius: 1, border: 1, borderColor: 'warning.main' }}>
                <Typography variant="subtitle2" gutterBottom color="warning.dark">
                  Podsumowanie transakcji
                </Typography>
                
                {needsCurrencyConversion && (
                  <>
                    <Box display="flex" justifyContent="space-between" mb={1}>
                      <Typography variant="body2">
                        Wartość w {selectedPosition.asset.currency.code}:
                      </Typography>
                      <Typography variant="body2" fontWeight="bold">
                        {(parseFloat(quantity || '0') * parseFloat(price || '0')).toFixed(2)} {selectedPosition.asset.currency.code}
                      </Typography>
                    </Box>
                    <Box display="flex" justifyContent="space-between" mb={1}>
                      <Typography variant="body2">
                        Kurs wymiany:
                      </Typography>
                      <Typography variant="body2" fontWeight="bold">
                        {parseFloat(fxRate).toFixed(4)}
                      </Typography>
                    </Box>
                    <Box display="flex" justifyContent="space-between" mb={1}>
                      <Typography variant="body2">
                        Po konwersji:
                      </Typography>
                      <Typography variant="body2" fontWeight="bold">
                        {(parseFloat(quantity || '0') * parseFloat(price || '0') * parseFloat(fxRate)).toFixed(2)} {pocket.base_currency_detail.code}
                      </Typography>
                    </Box>
                    <Box display="flex" justifyContent="space-between" mb={1}>
                      <Typography variant="body2">
                        - Prowizja:
                      </Typography>
                      <Typography variant="body2" fontWeight="bold">
                        {parseFloat(fee || '0').toFixed(2)} {pocket.base_currency_detail.code}
                      </Typography>
                    </Box>
                  </>
                )}
                
                {!needsCurrencyConversion && (
                  <>
                    <Box display="flex" justifyContent="space-between" mb={1}>
                      <Typography variant="body2">
                        Wartość sprzedaży:
                      </Typography>
                      <Typography variant="body2" fontWeight="bold">
                        {(parseFloat(quantity || '0') * parseFloat(price || '0')).toFixed(2)} {pocket.base_currency_detail.code}
                      </Typography>
                    </Box>
                    <Box display="flex" justifyContent="space-between" mb={1}>
                      <Typography variant="body2">
                        - Prowizja:
                      </Typography>
                      <Typography variant="body2" fontWeight="bold">
                        {parseFloat(fee || '0').toFixed(2)} {pocket.base_currency_detail.code}
                      </Typography>
                    </Box>
                  </>
                )}
                
                <Box sx={{ borderTop: 1, borderColor: 'warning.dark', pt: 1, mt: 1 }}>
                  <Box display="flex" justifyContent="space-between">
                    <Typography variant="body1" fontWeight="bold">
                      Kwota do otrzymania:
                    </Typography>
                    <Typography variant="h6" fontWeight="bold" color="warning.dark">
                      {totalAmount.toFixed(2)} {pocket.base_currency_detail.code}
                    </Typography>
                  </Box>
                </Box>
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
