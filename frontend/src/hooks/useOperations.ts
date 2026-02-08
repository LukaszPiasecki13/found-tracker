import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSnackbar } from 'notistack';
import { operationService } from '../services/operationService';
import type { Operation, CreateOperationRequest, AssetClass, Asset } from '../types/api';
import { getErrorMessage } from '../lib/api';

export const useOperations = (pocketName?: string) => {
  return useQuery({
    queryKey: pocketName ? ['operations', pocketName] : ['operations'],
    queryFn: () => operationService.getOperations(pocketName),
  });
};

export const useOperation = (id: number) => {
  return useQuery({
    queryKey: ['operations', id],
    queryFn: () => operationService.getOperation(id),
    enabled: !!id,
  });
};

export const useCreateOperation = () => {
  const queryClient = useQueryClient();
  const { enqueueSnackbar } = useSnackbar();

  return useMutation({
    mutationFn: (data: CreateOperationRequest) => operationService.createOperation(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['operations'] });
      queryClient.invalidateQueries({ queryKey: ['positions'] });
      queryClient.invalidateQueries({ queryKey: ['pockets'] });
      enqueueSnackbar('Operacja wykonana pomyślnie', { variant: 'success' });
    },
    onError: (error) => {
      const message = getErrorMessage(error);
      enqueueSnackbar(message, { variant: 'error' });
    },
  });
};

export const useUpdateOperation = () => {
  const queryClient = useQueryClient();
  const { enqueueSnackbar } = useSnackbar();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<CreateOperationRequest> }) =>
      operationService.updateOperation(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['operations'] });
      queryClient.invalidateQueries({ queryKey: ['positions'] });
      queryClient.invalidateQueries({ queryKey: ['pockets'] });
      enqueueSnackbar('Operacja zaktualizowana pomyślnie', { variant: 'success' });
    },
    onError: (error) => {
      const message = getErrorMessage(error);
      enqueueSnackbar(message, { variant: 'error' });
    },
  });
};

export const useDeleteOperation = () => {
  const queryClient = useQueryClient();
  const { enqueueSnackbar } = useSnackbar();

  return useMutation({
    mutationFn: (id: number) => operationService.deleteOperation(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['operations'] });
      queryClient.invalidateQueries({ queryKey: ['positions'] });
      queryClient.invalidateQueries({ queryKey: ['pockets'] });
      enqueueSnackbar('Operacja usunięta pomyślnie', { variant: 'success' });
    },
    onError: (error) => {
      const message = getErrorMessage(error);
      enqueueSnackbar(message, { variant: 'error' });
    },
  });
};

export const useAssetClasses = () => {
  return useQuery({
    queryKey: ['asset-classes'],
    queryFn: operationService.getAssetClasses,
    staleTime: 1000 * 60 * 30, // 30 minutes
  });
};

export const useSearchAssets = (query: string) => {
  return useQuery({
    queryKey: ['assets', 'search', query],
    queryFn: () => operationService.searchAssets(query),
    enabled: query.length >= 2, // Only search when query is at least 2 characters
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
};
