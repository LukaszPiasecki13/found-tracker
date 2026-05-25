import api from '../lib/api';
import type { PocketVectorsResponse } from '../types/api';

interface PocketVectorsParams {
  pocketName: string;
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
};
