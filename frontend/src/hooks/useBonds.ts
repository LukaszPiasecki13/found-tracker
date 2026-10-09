import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useSnackbar } from 'notistack';
import { bondService } from '../services/bondService';
import { operationService } from '../services/operationService';
import type { CreateBondTermsRequest, CreateOperationRequest } from '../types/api';
import { getErrorMessage } from '../lib/api';

export const useSearchBondSeries = () => {
  const { enqueueSnackbar } = useSnackbar();

  return useMutation({
    mutationFn: (seriesCode: string) => bondService.searchBondSeries(seriesCode),
    onError: (error) => {
      enqueueSnackbar(getErrorMessage(error), { variant: 'error' });
    },
  });
};

interface CreateBondAndBuyRequest {
  ticker: string;
  name: string;
  assetClassId: number;
  currencyId: number;
  terms: CreateBondTermsRequest;
  operation: Omit<CreateOperationRequest, 'asset_id'>;
}

/** Creates the Asset (`asset_type="bond"`), registers its terms, then books
 * the purchase as a BUY operation - three calls in sequence, matching how
 * `BuyAssetDialog` creates-then-buys a Yahoo asset. */
export const useCreateBondAndBuy = () => {
  const queryClient = useQueryClient();
  const { enqueueSnackbar } = useSnackbar();

  return useMutation({
    mutationFn: async (data: CreateBondAndBuyRequest) => {
      const asset = await bondService.createAsset({
        ticker: data.ticker,
        name: data.name,
        asset_class_id: data.assetClassId,
        currency_id: data.currencyId,
        asset_type: 'bond',
      });
      await bondService.registerBondTerms(asset.id, data.terms);
      return operationService.createOperation({ ...data.operation, asset_id: asset.id });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['operations'] });
      queryClient.invalidateQueries({ queryKey: ['positions'] });
      queryClient.invalidateQueries({ queryKey: ['pockets'] });
      enqueueSnackbar('Obligacja dodana do portfela', { variant: 'success' });
    },
    onError: (error) => {
      enqueueSnackbar(getErrorMessage(error), { variant: 'error' });
    },
  });
};
