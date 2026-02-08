import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSnackbar } from 'notistack';
import { positionService } from '../services/positionService';
import type { Position } from '../types/api';
import { getErrorMessage } from '../lib/api';

export const usePositions = (pocketName: string) => {
  return useQuery({
    queryKey: ['positions', pocketName],
    queryFn: () => positionService.getPositions(pocketName),
    enabled: !!pocketName,
  });
};

export const usePosition = (id: number) => {
  return useQuery({
    queryKey: ['positions', id],
    queryFn: () => positionService.getPosition(id),
    enabled: !!id,
  });
};
