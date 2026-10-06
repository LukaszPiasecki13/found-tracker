import { useQuery } from '@tanstack/react-query';
import { analyticsService } from '../services/analyticsService';

export const useAccountVectors = (startDate: string, endDate: string, vectors?: string[]) => {
  return useQuery({
    queryKey: ['account-vectors', startDate, endDate, vectors],
    queryFn: () =>
      analyticsService.getAccountVectors({
        startDate,
        endDate,
        interval: '1d',
        vectors: vectors ? JSON.stringify(vectors) : undefined,
      }),
    enabled: !!startDate && !!endDate,
    staleTime: 1000 * 60 * 10, // 10 minutes - analytics data doesn't change often
    gcTime: 1000 * 60 * 30, // 30 minutes
  });
};
