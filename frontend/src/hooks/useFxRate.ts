import { useQuery } from '@tanstack/react-query';
import { fxRateService } from '../services/fxRateService';

/** Rate turning one unit of `fromCurrency` into `toCurrency`; idle until both are known. */
export const useFxRate = (fromCurrency: string | undefined, toCurrency: string | undefined) => {
  return useQuery({
    queryKey: ['fx-rate', fromCurrency, toCurrency],
    queryFn: () => fxRateService.getRate(fromCurrency as string, toCurrency as string), // enabled guards both
    enabled: !!fromCurrency && !!toCurrency,
    retry: false, // RATE_MISSING (404) is a final answer, not a transient failure
    staleTime: 1000 * 60 * 5,
  });
};
