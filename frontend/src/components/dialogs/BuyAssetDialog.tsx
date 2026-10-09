import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  MenuItem,
  Box,
  CircularProgress,
  Autocomplete,
  Chip,
  Typography,
  Alert,
  Divider,
} from '@mui/material';
import dayjs from 'dayjs';
import { useAssetClasses, useCreateOperation, useSearchAssets } from '../../hooks/useOperations';
import { useCreateBondAndBuy, useSearchBondSeries } from '../../hooks/useBonds';
import { useFxRate } from '../../hooks/useFxRate';
import { useCurrencies, usePocket } from '../../hooks/usePockets';
import { operationService } from '../../services/operationService';
import type { Asset, BondCapitalization, BondReferenceType, BondSymbol } from '../../types/api';

interface BuyAssetDialogProps {
  open: boolean;
  onClose: () => void;
  pocketId: number;
}

type AssetKind = 'security' | 'bond';

const BOND_SYMBOLS: BondSymbol[] = ['OTS', 'ROR', 'DOR', 'TOS', 'COI', 'EDO', 'ROS', 'ROD'];
const CAPITALIZATIONS: { value: BondCapitalization; label: string }[] = [
  { value: 'none', label: 'Brak (odsetki wypłacane na gotówkę)' },
  { value: 'monthly', label: 'Miesięczna' },
  { value: 'annual', label: 'Roczna' },
];
const REFERENCE_TYPES: { value: BondReferenceType; label: string }[] = [
  { value: 'fixed', label: 'Stała stopa' },
  { value: 'nbp_reference', label: 'Stopa referencyjna NBP' },
  { value: 'cpi', label: 'Inflacja (CPI)' },
];

const BuyAssetDialog: React.FC<BuyAssetDialogProps> = ({ open, onClose, pocketId }) => {
  const [assetKind, setAssetKind] = useState<AssetKind>('security');

  // --- security (stock/ETF) path ---
  const [assetSearch, setAssetSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null);
  const [isCreatingAsset, setIsCreatingAsset] = useState(false);

  // --- bond path ---
  const [seriesCode, setSeriesCode] = useState('');
  const [bondTicker, setBondTicker] = useState('');
  const [bondName, setBondName] = useState('');
  const [bondCurrencyId, setBondCurrencyId] = useState<number | ''>('');
  const [bondAssetClassId, setBondAssetClassId] = useState<number | ''>('');
  const [bondSymbol, setBondSymbol] = useState<BondSymbol | ''>('');
  const [nominalValue, setNominalValue] = useState('100.00');
  const [issueDate, setIssueDate] = useState('');
  const [maturityDate, setMaturityDate] = useState('');
  const [capitalization, setCapitalization] = useState<BondCapitalization | ''>('');
  const [firstPeriodRate, setFirstPeriodRate] = useState('');
  const [referenceType, setReferenceType] = useState<BondReferenceType | ''>('');
  const [margin, setMargin] = useState('');
  const [redemptionFee, setRedemptionFee] = useState('');
  // Collapsed into a one-line summary once a search prefills the terms, so
  // the common case (search, confirm, buy) doesn't look like a big form.
  const [showBondDetails, setShowBondDetails] = useState(true);

  // --- shared purchase fields ---
  const [quantity, setQuantity] = useState('');
  const [price, setPrice] = useState('');
  const [fee, setFee] = useState('0');
  const [fxRate, setFxRate] = useState('1');
  const [operationDate, setOperationDate] = useState(dayjs().format('YYYY-MM-DD'));
  const [notes, setNotes] = useState('');

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(assetSearch);
    }, 500); // 500ms delay

    return () => clearTimeout(timer);
  }, [assetSearch]);

  const { data: pocket } = usePocket(pocketId);

  const { data: searchResults, isLoading: searchLoading } = useSearchAssets(debouncedSearch);
  const createOperationMutation = useCreateOperation();

  const { data: currencies, isLoading: currenciesLoading } = useCurrencies();
  const { data: assetClasses, isLoading: assetClassesLoading } = useAssetClasses();
  const searchBondMutation = useSearchBondSeries();
  const createBondMutation = useCreateBondAndBuy();

  // Retail bonds are always PLN; default to it instead of forcing a choice
  // for the near-universal case.
  useEffect(() => {
    if (assetKind !== 'bond' || bondCurrencyId || !currencies?.length) return;
    const pln = currencies.find((c) => c.code === 'PLN');
    setBondCurrencyId((pln ?? currencies[0]).id);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only run once currencies arrive
  }, [assetKind, currencies]);

  // Pick the obvious "bond" category if one exists; otherwise leave the
  // choice to the user rather than guessing wrong.
  useEffect(() => {
    if (assetKind !== 'bond' || bondAssetClassId || !assetClasses?.length) return;
    const bondClass = assetClasses.find((c) => /obligac|bond/i.test(c.name));
    if (bondClass) setBondAssetClassId(bondClass.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only run once classes arrive
  }, [assetKind, assetClasses]);

  // Prefill the rate with the real cross rate (asset currency -> portfolio currency); when it
  // is unknown the field stays editable and the user types the rate themselves.
  const bondCurrencyCode = currencies?.find((c) => c.id === bondCurrencyId)?.code;
  const assetCurrencyCode =
    assetKind === 'bond' ? bondCurrencyCode : selectedAsset?.currency.code;
  const pocketCurrencyCode = pocket?.base_currency.code;
  const needsRate = !!assetCurrencyCode && !!pocketCurrencyCode && assetCurrencyCode !== pocketCurrencyCode;
  const {
    data: fxQuote,
    isError: isFxRateUnavailable,
    isLoading: isFxRateLoading,
  } = useFxRate(
    needsRate ? assetCurrencyCode : undefined,
    needsRate ? pocketCurrencyCode : undefined
  );

  useEffect(() => {
    if (!needsRate) {
      setFxRate('1');
    } else if (fxQuote) {
      setFxRate(fxQuote.rate.toString());
    } else {
      // No quote (loading or unknown): never keep the previous asset's rate or a silent 1;
      // the empty required field forces a deliberate manual entry.
      setFxRate('');
    }
  }, [needsRate, fxQuote]);

  const handleSearchBondSeries = () => {
    if (!seriesCode) return;
    searchBondMutation.mutate(seriesCode, {
      onSuccess: (terms) => {
        setBondSymbol(terms.bond_symbol);
        setNominalValue(terms.nominal_value.toString());
        setIssueDate(terms.issue_date);
        setMaturityDate(terms.maturity_date);
        setCapitalization(terms.capitalization);
        setFirstPeriodRate(terms.first_period_rate?.toString() ?? '');
        setReferenceType(terms.reference_type ?? '');
        setMargin(terms.margin?.toString() ?? '');
        setRedemptionFee(terms.redemption_fee.toString());
        setPrice(terms.nominal_value.toString());
        if (!bondTicker) setBondTicker(terms.series_code);
        if (!bondName) setBondName(`Obligacja ${terms.bond_symbol} ${terms.series_code}`);
        setShowBondDetails(false);
      },
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (assetKind === 'bond') {
      if (
        !bondTicker ||
        !bondName ||
        !bondCurrencyId ||
        !bondAssetClassId ||
        !bondSymbol ||
        !issueDate ||
        !maturityDate ||
        !capitalization ||
        !redemptionFee ||
        !quantity ||
        !price
      ) {
        return;
      }

      try {
        await createBondMutation.mutateAsync({
          ticker: bondTicker,
          name: bondName,
          assetClassId: bondAssetClassId as number,
          currencyId: bondCurrencyId as number,
          terms: {
            bond_symbol: bondSymbol,
            series_code: seriesCode || bondTicker,
            nominal_value: parseFloat(nominalValue),
            issue_date: issueDate,
            maturity_date: maturityDate,
            capitalization,
            first_period_rate: firstPeriodRate ? parseFloat(firstPeriodRate) : null,
            reference_type: referenceType || null,
            margin: margin ? parseFloat(margin) : null,
            redemption_fee: parseFloat(redemptionFee),
          },
          operation: {
            portfolio_id: pocketId,
            operation_type: 'buy',
            quantity: parseFloat(quantity),
            price: parseFloat(price),
            amount: parseFloat(quantity) * parseFloat(price) + parseFloat(fee || '0'),
            fee: parseFloat(fee || '0'),
            fx_rate: parseFloat(fxRate || '1'),
            operation_date: operationDate,
            notes,
          },
        });
        handleClose();
      } catch {
        // Error handled by the mutation
      }
      return;
    }

    if (!selectedAsset || !quantity || !price) return;

    try {
      let assetId = selectedAsset.id;

      // If asset is from Yahoo (id = -1), create it first
      if (selectedAsset.id === -1 || (selectedAsset as unknown as Record<string, unknown>)['_fromYahoo'] === true) {
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
        portfolio_id: pocketId,
        asset_id: assetId,
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
    } catch {
      // Error handled by mutation
    }
  };

  const handleClose = () => {
    setAssetKind('security');
    setSelectedAsset(null);
    setAssetSearch('');
    setDebouncedSearch('');
    setSeriesCode('');
    setBondTicker('');
    setBondName('');
    setBondCurrencyId('');
    setBondAssetClassId('');
    setBondSymbol('');
    setNominalValue('100.00');
    setIssueDate('');
    setMaturityDate('');
    setCapitalization('');
    setFirstPeriodRate('');
    setReferenceType('');
    setMargin('');
    setRedemptionFee('');
    setShowBondDetails(true);
    setQuantity('');
    setPrice('');
    setFee('0');
    setFxRate('1');
    setNotes('');
    setOperationDate(dayjs().format('YYYY-MM-DD'));
    onClose();
  };

  const isFromYahoo = (asset: Asset) => {
    return asset.id === -1 || (asset as unknown as Record<string, unknown>)['_fromYahoo'] === true;
  };

  const needsCurrencyConversion = !!assetCurrencyCode && !!pocketCurrencyCode && assetCurrencyCode !== pocketCurrencyCode;

  const totalAmount = quantity && price
    ? parseFloat(quantity) * parseFloat(price) * parseFloat(fxRate || '0') + parseFloat(fee || '0')
    : 0;
  const isProcessing = createOperationMutation.isPending || isCreatingAsset || createBondMutation.isPending;

  const isSecurityValid = assetKind === 'security' && !!selectedAsset && !!quantity && !!price;
  const isBondValid =
    assetKind === 'bond' &&
    !!bondTicker &&
    !!bondName &&
    !!bondCurrencyId &&
    !!bondAssetClassId &&
    !!bondSymbol &&
    !!issueDate &&
    !!maturityDate &&
    !!capitalization &&
    !!redemptionFee &&
    !!quantity &&
    !!price;

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
      <form onSubmit={handleSubmit}>
        <DialogTitle>Kup aktywo</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            <TextField
              select
              label="Rodzaj"
              value={assetKind}
              onChange={(e) => setAssetKind(e.target.value as AssetKind)}
              fullWidth
              disabled={isProcessing}
            >
              <MenuItem value="security">Akcja / ETF</MenuItem>
              <MenuItem value="bond">Obligacja skarbowa</MenuItem>
            </TextField>

            {assetKind === 'security' && (
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
                renderOption={(props, option) => {
                  const { key, ...optionProps } = props as typeof props & { key: string };
                  return (
                    <li key={key} {...optionProps}>
                      <Box display="flex" alignItems="center" gap={1} width="100%">
                        <span>
                          {option.ticker} - {option.name}
                        </span>
                        {isFromYahoo(option) && (
                          <Chip label="Yahoo Finance" size="small" color="primary" variant="outlined" />
                        )}
                      </Box>
                    </li>
                  );
                }}
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
            )}

            {assetKind === 'bond' && (
              <>
                <Box display="flex" gap={2}>
                  <TextField
                    label="Seria (np. EDO1036)"
                    value={seriesCode}
                    onChange={(e) => setSeriesCode(e.target.value.toUpperCase())}
                    fullWidth
                    disabled={isProcessing}
                    helperText="Wpisz kod serii i wyszukaj, albo wypełnij pola poniżej ręcznie"
                  />
                  <Button
                    variant="outlined"
                    onClick={handleSearchBondSeries}
                    disabled={!seriesCode || searchBondMutation.isPending || isProcessing}
                    sx={{ whiteSpace: 'nowrap' }}
                  >
                    {searchBondMutation.isPending ? <CircularProgress size={20} /> : 'Szukaj'}
                  </Button>
                </Box>

                {searchBondMutation.isError && (
                  <Alert severity="warning">
                    Nie znaleziono serii w źródle danych — wypełnij parametry ręcznie poniżej.
                  </Alert>
                )}
                {searchBondMutation.isSuccess && (
                  <Alert severity="success">
                    Dane serii wypełnione automatycznie — sprawdź przed zapisem.
                  </Alert>
                )}

                <Box display="flex" gap={2}>
                  <TextField
                    label="Ticker"
                    value={bondTicker}
                    onChange={(e) => setBondTicker(e.target.value)}
                    required
                    fullWidth
                    disabled={isProcessing}
                  />
                  <TextField
                    label="Nazwa"
                    value={bondName}
                    onChange={(e) => setBondName(e.target.value)}
                    required
                    fullWidth
                    disabled={isProcessing}
                  />
                </Box>

                <Box display="flex" gap={2}>
                  <TextField
                    select
                    label="Waluta"
                    value={bondCurrencyId}
                    onChange={(e) => setBondCurrencyId(Number(e.target.value))}
                    required
                    fullWidth
                    disabled={isProcessing || currenciesLoading}
                  >
                    {currencies?.map((currency) => (
                      <MenuItem key={currency.id} value={currency.id}>
                        {currency.code}
                      </MenuItem>
                    ))}
                  </TextField>
                  <TextField
                    select
                    label="Kategoria waloru"
                    value={bondAssetClassId}
                    onChange={(e) => setBondAssetClassId(Number(e.target.value))}
                    required
                    fullWidth
                    disabled={isProcessing || assetClassesLoading}
                    helperText={
                      assetClasses?.length === 0 ? 'Brak kategorii — dodaj ją najpierw' : undefined
                    }
                  >
                    {assetClasses?.map((assetClass) => (
                      <MenuItem key={assetClass.id} value={assetClass.id}>
                        {assetClass.name}
                      </MenuItem>
                    ))}
                  </TextField>
                </Box>

                <Divider />
                <Box display="flex" justifyContent="space-between" alignItems="center">
                  <Typography variant="subtitle2">Warunki obligacji</Typography>
                  {!showBondDetails && (
                    <Button size="small" onClick={() => setShowBondDetails(true)} disabled={isProcessing}>
                      Edytuj szczegóły
                    </Button>
                  )}
                </Box>

                {!showBondDetails ? (
                  <Box sx={{ p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
                    <Typography variant="body2">
                      <strong>{bondSymbol}</strong> {seriesCode} — nominał {nominalValue}, wykup{' '}
                      {maturityDate}, stopa {firstPeriodRate || '—'}%
                      {margin && ` + ${margin} p.p.`}, opłata za wcześniejszy wykup {redemptionFee}
                    </Typography>
                  </Box>
                ) : (
                  <>
                    <Box display="flex" gap={2}>
                      <TextField
                        select
                        label="Typ obligacji"
                        value={bondSymbol}
                        onChange={(e) => setBondSymbol(e.target.value as BondSymbol)}
                        required
                        fullWidth
                        disabled={isProcessing}
                      >
                        {BOND_SYMBOLS.map((symbol) => (
                          <MenuItem key={symbol} value={symbol}>
                            {symbol}
                          </MenuItem>
                        ))}
                      </TextField>
                      <TextField
                        label="Nominał"
                        type="number"
                        value={nominalValue}
                        onChange={(e) => setNominalValue(e.target.value)}
                        required
                        fullWidth
                        disabled={isProcessing}
                        inputProps={{ step: '0.01', min: '0' }}
                      />
                    </Box>

                    <Box display="flex" gap={2}>
                      <TextField
                        label="Data emisji"
                        type="date"
                        value={issueDate}
                        onChange={(e) => setIssueDate(e.target.value)}
                        required
                        fullWidth
                        disabled={isProcessing}
                        InputLabelProps={{ shrink: true }}
                      />
                      <TextField
                        label="Data wykupu"
                        type="date"
                        value={maturityDate}
                        onChange={(e) => setMaturityDate(e.target.value)}
                        required
                        fullWidth
                        disabled={isProcessing}
                        InputLabelProps={{ shrink: true }}
                      />
                    </Box>

                    <Box display="flex" gap={2}>
                      <TextField
                        select
                        label="Kapitalizacja"
                        value={capitalization}
                        onChange={(e) => setCapitalization(e.target.value as BondCapitalization)}
                        required
                        fullWidth
                        disabled={isProcessing}
                      >
                        {CAPITALIZATIONS.map((option) => (
                          <MenuItem key={option.value} value={option.value}>
                            {option.label}
                          </MenuItem>
                        ))}
                      </TextField>
                      <TextField
                        select
                        label="Rodzaj oprocentowania"
                        value={referenceType}
                        onChange={(e) => setReferenceType(e.target.value as BondReferenceType)}
                        fullWidth
                        disabled={isProcessing}
                      >
                        {REFERENCE_TYPES.map((option) => (
                          <MenuItem key={option.value} value={option.value}>
                            {option.label}
                          </MenuItem>
                        ))}
                      </TextField>
                    </Box>

                    <Box display="flex" gap={2}>
                      <TextField
                        label="Stopa I okresu (%)"
                        type="number"
                        value={firstPeriodRate}
                        onChange={(e) => setFirstPeriodRate(e.target.value)}
                        fullWidth
                        disabled={isProcessing}
                        inputProps={{ step: '0.01' }}
                      />
                      <TextField
                        label="Marża (p.p.)"
                        type="number"
                        value={margin}
                        onChange={(e) => setMargin(e.target.value)}
                        fullWidth
                        disabled={isProcessing}
                        inputProps={{ step: '0.01' }}
                        helperText="Tylko dla stopy referencyjnej/CPI"
                      />
                      <TextField
                        label="Opłata za wcześniejszy wykup"
                        type="number"
                        value={redemptionFee}
                        onChange={(e) => setRedemptionFee(e.target.value)}
                        required
                        fullWidth
                        disabled={isProcessing}
                        inputProps={{ step: '0.01', min: '0' }}
                      />
                    </Box>
                  </>
                )}
                <Divider />
              </>
            )}

            <Box display="flex" gap={2}>
              <TextField
                label={assetKind === 'bond' ? 'Liczba obligacji' : 'Ilość'}
                type="number"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                required
                fullWidth
                disabled={isProcessing}
                inputProps={{ step: assetKind === 'bond' ? '1' : '0.0001', min: '0' }}
              />

              <TextField
                label={assetKind === 'bond' ? 'Cena za obligację' : 'Cena za jednostkę'}
                type="number"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                required
                fullWidth
                disabled={isProcessing}
                inputProps={{ step: '0.01', min: '0' }}
                helperText={assetKind === 'bond' ? 'Obligacje detaliczne kupowane są po nominale' : undefined}
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
            {((assetKind === 'security' && selectedAsset) || (assetKind === 'bond' && bondCurrencyCode)) && pocket && (
              <Box sx={{ p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
                <Typography variant="subtitle2" gutterBottom>
                  Informacje o walutach
                </Typography>
                <Box display="flex" gap={2} alignItems="center" mb={1}>
                  <Chip
                    label={`Aktywo: ${assetCurrencyCode}`}
                    size="small"
                    color="primary"
                  />
                  <Chip
                    label={`Portfel: ${pocket.base_currency.code}`}
                    size="small"
                    color="secondary"
                  />
                </Box>

                {needsCurrencyConversion && (
                  <>
                    <Alert severity="info" sx={{ mb: 2 }}>
                      Wymagana konwersja walut: {assetCurrencyCode} → {pocket.base_currency.code}
                    </Alert>
                    <TextField
                      label={`Kurs wymiany (1 ${assetCurrencyCode} = ? ${pocket.base_currency.code})`}
                      type="number"
                      value={fxRate}
                      onChange={(e) => setFxRate(e.target.value)}
                      required
                      fullWidth
                      disabled={isProcessing}
                      inputProps={{ step: '0.0001', min: '0' }}
                      helperText={
                        isFxRateUnavailable
                          ? 'Brak kursu w systemie — wpisz go ręcznie'
                          : 'Podaj aktualny kurs wymiany waluty aktywa do waluty portfela'
                      }
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

            {totalAmount > 0 && pocket && (
              <Box sx={{ p: 2, bgcolor: 'success.light', borderRadius: 1, border: 1, borderColor: 'success.main' }}>
                <Typography variant="subtitle2" gutterBottom color="success.dark">
                  Podsumowanie transakcji
                </Typography>

                {needsCurrencyConversion && (
                  <>
                    <Box display="flex" justifyContent="space-between" mb={1}>
                      <Typography variant="body2">
                        Wartość w {assetCurrencyCode}:
                      </Typography>
                      <Typography variant="body2" fontWeight="bold">
                        {(parseFloat(quantity || '0') * parseFloat(price || '0')).toFixed(2)} {assetCurrencyCode}
                      </Typography>
                    </Box>
                    <Box display="flex" justifyContent="space-between" mb={1}>
                      <Typography variant="body2">
                        Kurs wymiany:
                      </Typography>
                      <Typography variant="body2" fontWeight="bold">
                        {parseFloat(fxRate || '0').toFixed(4)}
                      </Typography>
                    </Box>
                    <Box display="flex" justifyContent="space-between" mb={1}>
                      <Typography variant="body2">
                        Po konwersji:
                      </Typography>
                      <Typography variant="body2" fontWeight="bold">
                        {(parseFloat(quantity || '0') * parseFloat(price || '0') * parseFloat(fxRate || '0')).toFixed(2)} {pocket.base_currency.code}
                      </Typography>
                    </Box>
                    <Box display="flex" justifyContent="space-between" mb={1}>
                      <Typography variant="body2">
                        + Prowizja:
                      </Typography>
                      <Typography variant="body2" fontWeight="bold">
                        {parseFloat(fee || '0').toFixed(2)} {pocket.base_currency.code}
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
                        {(parseFloat(quantity || '0') * parseFloat(price || '0')).toFixed(2)} {pocket.base_currency.code}
                      </Typography>
                    </Box>
                    <Box display="flex" justifyContent="space-between" mb={1}>
                      <Typography variant="body2">
                        + Prowizja:
                      </Typography>
                      <Typography variant="body2" fontWeight="bold">
                        {parseFloat(fee || '0').toFixed(2)} {pocket.base_currency.code}
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
                      {totalAmount.toFixed(2)} {pocket.base_currency.code}
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
            disabled={isProcessing || isFxRateLoading || !(isSecurityValid || isBondValid)}
          >
            {isProcessing ? <CircularProgress size={24} /> : 'Kup'}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};

export default BuyAssetDialog;
