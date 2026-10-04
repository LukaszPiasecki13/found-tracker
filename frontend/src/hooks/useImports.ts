import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSnackbar } from 'notistack';
import { importService } from '../services/importService';
import { getErrorMessage } from '../lib/api';

export const useImports = (portfolioId: number | undefined) => {
  return useQuery({
    queryKey: ['imports', portfolioId],
    queryFn: () => importService.getImports(portfolioId as number),
    enabled: !!portfolioId,
  });
};

export const useImportBatch = (
  portfolioId: number | undefined,
  batchId: number | undefined
) => {
  return useQuery({
    queryKey: ['import-batch', portfolioId, batchId],
    queryFn: () =>
      importService.getImportBatch(
        portfolioId as number,
        batchId as number
      ),
    enabled: !!portfolioId && !!batchId,
  });
};

export const usePreviewImport = () => {
  return useMutation({
    mutationFn: ({
      portfolioId,
      file,
    }: {
      portfolioId: number;
      file: File;
    }) => importService.previewImport(portfolioId, file),
  });
};

export const useCommitImport = () => {
  const queryClient = useQueryClient();
  const { enqueueSnackbar } = useSnackbar();

  return useMutation({
    mutationFn: ({
      portfolioId,
      file,
    }: {
      portfolioId: number;
      file: File;
    }) => importService.commitImport(portfolioId, file),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ['imports', variables.portfolioId],
      });
      queryClient.invalidateQueries({ queryKey: ['operations'] });
      queryClient.invalidateQueries({ queryKey: ['positions'] });
      queryClient.invalidateQueries({ queryKey: ['pockets'] });
      queryClient.invalidateQueries({
        queryKey: ['pocket-vectors'],
      });
      enqueueSnackbar('Import zatwierdzony pomyślnie', {
        variant: 'success',
      });
    },
    onError: (error) => {
      const message = getErrorMessage(error);
      enqueueSnackbar(message, { variant: 'error' });
    },
  });
};

export const useRevertImportBatch = () => {
  const queryClient = useQueryClient();
  const { enqueueSnackbar } = useSnackbar();

  return useMutation({
    mutationFn: ({
      portfolioId,
      batchId,
    }: {
      portfolioId: number;
      batchId: number;
    }) => importService.revertImportBatch(portfolioId, batchId),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ['imports', variables.portfolioId],
      });
      // The reverted batch no longer exists: drop it instead of refetching.
      queryClient.removeQueries({
        queryKey: ['import-batch', variables.portfolioId, variables.batchId],
      });
      queryClient.invalidateQueries({ queryKey: ['operations'] });
      queryClient.invalidateQueries({ queryKey: ['positions'] });
      queryClient.invalidateQueries({ queryKey: ['pockets'] });
      queryClient.invalidateQueries({
        queryKey: ['pocket-vectors'],
      });
      enqueueSnackbar('Import cofnięty pomyślnie', {
        variant: 'success',
      });
    },
    onError: (error) => {
      const message = getErrorMessage(error);
      enqueueSnackbar(message, { variant: 'error' });
    },
  });
};
