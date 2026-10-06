import api from '../lib/api';
import type { Position } from '../types/api';

export const positionService = {
  // Positions at the stored prices (no side effects on the server).
  async getStoredPositions(pocketName: string): Promise<Position[]> {
    const response = await api.get<Position[]>('/portfolios/positions', {
      params: { portfolio_name: pocketName },
    });
    return response.data;
  },

  // Asks the server to refresh rates and prices in the background. The answer is the
  // stored positions, so the caller reads the new prices from `getStoredPositions`.
  async requestRefresh(pocketName: string): Promise<void> {
    await api.post('/portfolios/positions/refresh', null, {
      params: { portfolio_name: pocketName },
    });
  },
};
