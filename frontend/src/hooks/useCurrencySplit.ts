import { useQuery } from '@tanstack/react-query';
import { analyticsService } from '../services/analyticsService';

// Without a portfolio name: all the user's portfolios, in the account currency.
export const useCurrencySplit = (portfolioName?: string) => {
  return useQuery({
    queryKey: ['currency-split', portfolioName ?? null],
    queryFn: () => analyticsService.getCurrencySplit(portfolioName),
    staleTime: 1000 * 60 * 5,
    gcTime: 1000 * 60 * 30,
  });
};
