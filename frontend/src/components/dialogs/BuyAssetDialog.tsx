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
  Autocomplete,
  MenuItem,
} from '@mui/material';
import dayjs from 'dayjs';
import { useCreateOperation, useAssetClasses, useSearchAssets } from '../../hooks/useOperations';
import type { Asset, AssetClass } from '../../types/api';

interface BuyAssetDialogProps {
  open: boolean;
  onClose: () => void;
  pocketId: number;
}

const BuyAssetDialog: React.FC<BuyAssetDialogProps> = ({ open, onClose, pocketId }) => {
  const [assetSearch, setAssetSearch] = useState('');
  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null);
  const [quantity, setQuantity] = useState('');
  const [price, setPrice] = useState('');
  const [fee, setFee] = useState('0');
  const [operationDate, setOperationDate] = useState(dayjs().format('YYYY-MM-DD'));
  const [notes, setNotes] = useState('');

  const { data: assetClasses } = useAssetClasses();
  const { data: searchResults, isLoading: searchLoading } = useSearchAssets(assetSearch);
  const createOperationMutation = useCreateOperation();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!selectedAsset || !quantity || !price) return;

    try {
      await createOperationMutation.mutateAsync({
        pocket: pocketId,
        asset: selectedAsset.id,
        operation_type: 'buy',
        quantity: parseFloat(quantity),
        price: parseFloat(price),
        amount: parseFloat(quantity) * parseFloat(price) + parseFloat(fee),
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
    setSelectedAsset(null);
    setAssetSearch('');
    setQuantity('');
    setPrice('');
    setFee('0');
    setNotes('');
    setOperationDate(dayjs().format('YYYY-MM-DD'));
    onClose();
  };

  const totalAmount = quantity && price ? parseFloat(quantity) * parseFloat(price) + parseFloat(fee || '0') : 0;

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
      <form onSubmit={handleSubmit}>
        <DialogTitle>Kup aktywo</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            <Autocomplete
              options={searchResults || []}
              getOptionLabel={(option) => `${option.ticker} - ${option.name}`}
              value={selectedAsset}
              onChange={(_, newValue) => setSelectedAsset(newValue)}
              inputValue={assetSearch}
              onInputChange={(_, newInputValue) => setAssetSearch(newInputValue)}
              loading={searchLoading}
              renderInput={(params) => (
                <TextField
                  {...params}
                  label="Szukaj aktywa (ticker lub nazwa)"
                  required
                  disabled={createOperationMutation.isPending}
                  InputProps={{
                    ...params.InputProps,
                    endAdornment: (
                      <>
                        {searchLoading ? <CircularProgress size={20} /> : null}
                        {params.InputProps.endAdornment}
                      </>
                    ),
                  }}
                />
              )}
            />

            <Box display="flex" gap={2}>
              <TextField
                label="Ilość"
                type="number"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                required
                fullWidth
                disabled={createOperationMutation.isPending}
                inputProps={{ step: '0.0001', min: '0' }}
              />

              <TextField
                label="Cena za jednostkę"
                type="number"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                required
                fullWidth
                disabled={createOperationMutation.isPending}
                inputProps={{ step: '0.01', min: '0' }}
              />
            </Box>

            <TextField
              label="Prowizja"
              type="number"
              value={fee}
              onChange={(e) => setFee(e.target.value)}
              fullWidth
              disabled={createOperationMutation.isPending}
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
                  label="Łączny koszt"
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
            disabled={createOperationMutation.isPending || !selectedAsset || !quantity || !price}
          >
            {createOperationMutation.isPending ? <CircularProgress size={24} /> : 'Kup'}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};

export default BuyAssetDialog;
