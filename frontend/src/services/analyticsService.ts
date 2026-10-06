import api from '../lib/api';
import type { CurrencySplitResponse, PocketVectorsResponse } from '../types/api';

interface PocketVectorsParams {
  pocketName: string;
  startDate?: string;
  endDate?: string;
  interval?: string;
  vectors?: string;
}

interface AccountVectorsParams {
  startDate?: string;
  endDate?: string;
  interval?: string;
  vectors?: string;
}

export const analyticsService = {
  async getPocketVectors(params: PocketVectorsParams): Promise<PocketVectorsResponse> {
    const response = await api.get<PocketVectorsResponse>('/portfolios/portfolio-vectors', {
      params: {
        portfolioName: params.pocketName,
        startDate: params.startDate,
        endDate: params.endDate,
        interval: params.interval,
        vectors: params.vectors,
      },
    });
    return response.data;
  },

  async getAccountVectors(params: AccountVectorsParams): Promise<PocketVectorsResponse> {
    const response = await api.get<PocketVectorsResponse>('/portfolios/account-vectors', {
      params: {
        startDate: params.startDate,
        endDate: params.endDate,
        interval: params.interval,
        vectors: params.vectors,
      },
    });
    return response.data;
  },

  async getCurrencySplit(portfolioName?: string): Promise<CurrencySplitResponse> {
    const response = await api.get<CurrencySplitResponse>('/portfolios/currency-split', {
      params: { portfolioName },
    });
    return response.data;
  },
};
