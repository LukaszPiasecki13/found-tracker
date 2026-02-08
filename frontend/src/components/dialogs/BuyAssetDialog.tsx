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
  Chip,
  Typography,
  Alert,
} from '@mui/material';
import dayjs from 'dayjs';
import { useCreateOperation, useAssetClasses, useSearchAssets } from '../../hooks/useOperations';
import { usePocket } from '../../hooks/usePockets';
import { operationService } from '../../services/operationService';
import type { Asset, AssetClass } from '../../types/api';

interface BuyAssetDialogProps {
  open: boolean;
  onClose: () => void;
  pocketId: number;
}

const BuyAssetDialog: React.FC<BuyAssetDialogProps> = ({ open, onClose, pocketId }) => {
  const [assetSearch, setAssetSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null);
  const [quantity, setQuantity] = useState('');
  const [price, setPrice] = useState('');
  const [fee, setFee] = useState('0');
  const [fxRate, setFxRate] = useState('1');
  const [operationDate, setOperationDate] = useState(dayjs().format('YYYY-MM-DD'));
  const [notes, setNotes] = useState('');
  const [isCreatingAsset, setIsCreatingAsset] = useState(false);

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(assetSearch);
    }, 500); // 500ms delay

    return () => clearTimeout(timer);
  }, [assetSearch]);

  const { data: pocket } = usePocket(pocketId);
  const { data: assetClasses } = useAssetClasses();
  const { data: searchResults, isLoading: searchLoading } = useSearchAssets(debouncedSearch);
  const createOperationMutation = useCreateOperation();

  // Check if currencies are different and update FX rate
  useEffect(() => {
    if (selectedAsset && pocket) {
      const assetCurrency = selectedAsset.currency.code;
      const pocketCurrency = pocket.base_currency_detail.code;
      
      if (assetCurrency !== pocketCurrency) {
        // Get exchange rate from asset currency
        // If asset has exchange_rate, use it, otherwise default to 1
        const rate = selectedAsset.currency.exchange_rate || 1;
        setFxRate(rate.toString());
      } else {
        setFxRate('1');
      }
    }
  }, [selectedAsset, pocket]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!selectedAsset || !quantity || !price) return;

    try {
      let assetId = selectedAsset.id;

      // If asset is from Yahoo (id = -1), create it first
      if (selectedAsset.id === -1 || (selectedAsset as any)._fromYahoo) {
        setIsCreatingAsset(true);
        try {
          const newAsset = await operationService.createAssetFromYahoo(
            selectedAsset.ticker,
            selectedAsset.asset_class?.id > 0 ? selectedAsset.asset_class.id : undefined,
            selectedAsset.currency?.id > 0 ? selectedAsset.currency.id : undefined
          );
          assetId = newAsset.id;
        } catch (error) {
          console.error('Failed to create asset:', error);
          throw error;
        } finally {
          setIsCreatingAsset(false);
        }
      }

      await createOperationMutation.mutateAsync({
        pocket: pocketId,
        asset: assetId,
        operation_type: 'buy',
        quantity: parseFloat(quantity),
        price: parseFloat(price),
        amount: parseFloat(quantity) * parseFloat(price) + parseFloat(fee),
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
    setSelectedAsset(null);
    setAssetSearch('');
    setDebouncedSearch('');
    setQuantity('');
    setPrice('');
    setFxRate('1');
    setNotes('');
    setOperationDate(dayjs().format('YYYY-MM-DD'));
    onClose();
  };

  const isFromYahoo = (asset: Asset) => {
    return asset.id === -1 || (asset as any)._fromYahoo;
  };

  const needsCurrencyConversion = selectedAsset && pocket && 
    selectedAsset.currency.code !== pocket.base_currency_detail.code;

  const totalAmount = quantity && price 
    ? parseFloat(quantity) * parseFloat(price) * parseFloat(fxRate) + parseFloat(fee || '0') 
    : 0;
  const isProcessing = createOperationMutation.isPending || isCreatingAsset;

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
              onChange={(_, newValue) => {
                setSelectedAsset(newValue);
                // Keep the search input as just the ticker when an option is selected
                if (newValue) {
                  setAssetSearch(newValue.ticker);
                }
              }}
              inputValue={assetSearch}
              onInputChange={(_, newInputValue, reason) => {
                // Only update search if user is typing, not selecting
                if (reason === 'input') {
                  setAssetSearch(newInputValue);
                }
              }}
              loading={searchLoading}
              renderOption={(props, option) => (
                <li {...props}>
                  <Box display="flex" alignItems="center" gap={1} width="100%">
                    <span>
                      {option.ticker} - {option.name}
                    </span>
                    {isFromYahoo(option) && (
                      <Chip label="Yahoo Finance" size="small" color="primary" variant="outlined" />
                    )}
                  </Box>
                </li>
              )}
              renderInput={(params) => (
                <TextField
                  {...params}
                  label="Szukaj aktywa (ticker lub nazwa)"
                  required
                  disabled={isProcessing}
                  helperText="Wpisz co najmniej 2 znaki aby wyszukać aktywa"
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
                disabled={isProcessing}
                inputProps={{ step: '0.0001', min: '0' }}
              />

              <TextField
                label="Cena za jednostkę"
                type="number"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                required
                fullWidth
                disabled={isProcessing}
                inputProps={{ step: '0.01', min: '0' }}
              />
            </Box>

            <TextField
              label="Prowizja"
              type="number"
              value={fee}
              onChange={(e) => setFee(e.target.value)}
              fullWidth
              disabled={isProcessing}
              inputProps={{ step: '0.01', min: '0' }}
            />

            {/* Currency information and conversion */}
            {selectedAsset && pocket && (
              <Box sx={{ p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
                <Typography variant="subtitle2" gutterBottom>
                  Informacje o walutach
                </Typography>
                <Box display="flex" gap={2} alignItems="center" mb={1}>
                  <Chip 
                    label={`Aktywo: ${selectedAsset.currency.code}`} 
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
                      Wymagana konwersja walut: {selectedAsset.currency.code} → {pocket.base_currency_detail.code}
                    </Alert>
                    <TextField
                      label={`Kurs wymiany (1 ${selectedAsset.currency.code} = ? ${pocket.base_currency_detail.code})`}
                      type="number"
                      value={fxRate}
                      onChange={(e) => setFxRate(e.target.value)}
                      required
                      fullWidth
                      disabled={isProcessing}
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
              disabled={isProcessing}
              InputLabelProps={{ shrink: true }}
            />

            <TextField
              label="Notatki"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              multiline
              rows={2}
              fullWidth
              disabled={isProcessing}
            />

            {totalAmount > 0 && pocket && selectedAsset && (
              <Box sx={{ p: 2, bgcolor: 'success.light', borderRadius: 1, border: 1, borderColor: 'success.main' }}>
                <Typography variant="subtitle2" gutterBottom color="success.dark">
                  Podsumowanie transakcji
                </Typography>
                
                {needsCurrencyConversion && (
                  <>
                    <Box display="flex" justifyContent="space-between" mb={1}>
                      <Typography variant="body2">
                        Wartość w {selectedAsset.currency.code}:
                      </Typography>
                      <Typography variant="body2" fontWeight="bold">
                        {(parseFloat(quantity || '0') * parseFloat(price || '0')).toFixed(2)} {selectedAsset.currency.code}
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
                        + Prowizja:
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
                        Wartość aktywów:
                      </Typography>
                      <Typography variant="body2" fontWeight="bold">
                        {(parseFloat(quantity || '0') * parseFloat(price || '0')).toFixed(2)} {pocket.base_currency_detail.code}
                      </Typography>
                    </Box>
                    <Box display="flex" justifyContent="space-between" mb={1}>
                      <Typography variant="body2">
                        + Prowizja:
                      </Typography>
                      <Typography variant="body2" fontWeight="bold">
                        {parseFloat(fee || '0').toFixed(2)} {pocket.base_currency_detail.code}
                      </Typography>
                    </Box>
                  </>
                )}
                
                <Box sx={{ borderTop: 1, borderColor: 'success.dark', pt: 1, mt: 1 }}>
                  <Box display="flex" justifyContent="space-between">
                    <Typography variant="body1" fontWeight="bold">
                      Łączny koszt:
                    </Typography>
                    <Typography variant="h6" fontWeight="bold" color="success.dark">
                      {totalAmount.toFixed(2)} {pocket.base_currency_detail.code}
                    </Typography>
                  </Box>
                </Box>
              </Box>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleClose} disabled={isProcessing}>
            Anuluj
          </Button>
          <Button
            type="submit"
            variant="contained"
            disabled={isProcessing || !selectedAsset || !quantity || !price}
          >
            {isProcessing ? <CircularProgress size={24} /> : 'Kup'}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};

export default BuyAssetDialog;
