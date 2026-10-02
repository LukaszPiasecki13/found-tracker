import api from '../lib/api';
import type { FxRate } from '../types/api';

export const fxRateService = {
  async getRate(fromCurrency: string, toCurrency: string): Promise<FxRate> {
    const response = await api.get<FxRate>('/portfolios/fx-rate', {
      params: { from_currency: fromCurrency, to_currency: toCurrency },
    });
    return response.data;
  },
};
