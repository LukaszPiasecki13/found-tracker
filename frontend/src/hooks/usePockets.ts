import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSnackbar } from 'notistack';
import { pocketService } from '../services/pocketService';
import type { Pocket, CreatePocketRequest, Currency } from '../types/api';
import { getErrorMessage } from '../lib/api';

export const usePockets = () => {
  return useQuery({
    queryKey: ['pockets'],
    queryFn: pocketService.getPockets,
  });
};

export const usePocket = (id: number) => {
  return useQuery({
    queryKey: ['pockets', id],
    queryFn: () => pocketService.getPocket(id),
    enabled: !!id,
  });
};

export const usePocketByName = (name: string) => {
  return useQuery({
    queryKey: ['pockets', 'by-name', name],
    queryFn: () => pocketService.getPocketByName(name),
    enabled: !!name,
  });
};

export const useCreatePocket = () => {
  const queryClient = useQueryClient();
  const { enqueueSnackbar } = useSnackbar();

  return useMutation({
    mutationFn: (data: CreatePocketRequest) => pocketService.createPocket(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pockets'] });
      enqueueSnackbar('Portfel utworzony pomyślnie', { variant: 'success' });
    },
    onError: (error) => {
      const message = getErrorMessage(error);
      enqueueSnackbar(message, { variant: 'error' });
    },
  });
};

export const useUpdatePocket = () => {
  const queryClient = useQueryClient();
  const { enqueueSnackbar } = useSnackbar();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<CreatePocketRequest> }) =>
      pocketService.updatePocket(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pockets'] });
      enqueueSnackbar('Portfel zaktualizowany pomyślnie', { variant: 'success' });
    },
    onError: (error) => {
      const message = getErrorMessage(error);
      enqueueSnackbar(message, { variant: 'error' });
    },
  });
};

export const useDeletePocket = () => {
  const queryClient = useQueryClient();
  const { enqueueSnackbar } = useSnackbar();

  return useMutation({
    mutationFn: (id: number) => pocketService.deletePocket(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pockets'] });
      enqueueSnackbar('Portfel usunięty pomyślnie', { variant: 'success' });
    },
    onError: (error) => {
      const message = getErrorMessage(error);
      enqueueSnackbar(message, { variant: 'error' });
    },
  });
};

export const useCurrencies = () => {
  return useQuery({
    queryKey: ['currencies'],
    queryFn: pocketService.getCurrencies,
    staleTime: 1000 * 60 * 30, // 30 minutes - currencies don't change often
  });
};
