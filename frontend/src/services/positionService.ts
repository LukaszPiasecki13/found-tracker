import api from '../lib/api';
import type { Position } from '../types/api';

export const positionService = {
  async getPositions(pocketName: string): Promise<Position[]> {
    const response = await api.get<Position[]>('/portfolios/positions/', {
      params: { pocket_name: pocketName },
    });
    return response.data;
  },

  async getPosition(id: number): Promise<Position> {
    const response = await api.get<Position>(`/portfolios/positions/${id}/`);
    return response.data;
  },
};
