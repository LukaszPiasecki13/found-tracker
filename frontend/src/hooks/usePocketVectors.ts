import { useQuery } from '@tanstack/react-query';
import { analyticsService } from '../services/analyticsService';

export const usePocketVectors = (
  pocketName: string,
  startDate: string,
  endDate: string,
  vectors?: string[],
  benchmarks?: string
) => {
  return useQuery({
    queryKey: ['pocket-vectors', pocketName, startDate, endDate, vectors, benchmarks],
    queryFn: () =>
      analyticsService.getPocketVectors({
        pocketName,
        startDate,
        endDate,
        interval: '1d',
        vectors: vectors ? JSON.stringify(vectors) : undefined,
        benchmarks,
      }),
    enabled: !!pocketName && !!startDate && !!endDate,
    staleTime: 1000 * 60 * 10, // 10 minutes - analytics data doesn't change often
    gcTime: 1000 * 60 * 30, // 30 minutes
  });
};
