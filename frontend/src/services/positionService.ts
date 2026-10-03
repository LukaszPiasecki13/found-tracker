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

  // Refreshes prices and rates from the market-data provider first; when that
  // fails (provider down), the stored values are still shown.
  async getPositions(pocketName: string): Promise<Position[]> {
    try {
      const response = await api.post<Position[]>(
        '/portfolios/positions/refresh',
        null,
        { params: { portfolio_name: pocketName } }
      );
      return response.data;
    } catch {
      return positionService.getStoredPositions(pocketName);
    }
  },
};
