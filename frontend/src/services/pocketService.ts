import api from '../lib/api';
import type { Pocket, CreatePocketRequest, Currency } from '../types/api';

export const pocketService = {
  async getPockets(): Promise<Pocket[]> {
    const response = await api.get<Pocket[]>('/portfolios/pockets/');
    return response.data;
  },

  async getPocket(id: number): Promise<Pocket> {
    const response = await api.get<Pocket>(`/portfolios/pockets/${id}/`);
    return response.data;
  },

  async getPocketByName(name: string): Promise<Pocket> {
    const response = await api.get<Pocket[]>(`/portfolios/pockets/`, {
      params: { name },
    });
    return response.data[0];
  },

  async createPocket(data: CreatePocketRequest): Promise<Pocket> {
    const response = await api.post<Pocket>('/portfolios/pockets/', data);
    return response.data;
  },

  async updatePocket(id: number, data: Partial<CreatePocketRequest>): Promise<Pocket> {
    const response = await api.patch<Pocket>(`/portfolios/pockets/${id}/`, data);
    return response.data;
  },

  async deletePocket(id: number): Promise<void> {
    await api.delete(`/portfolios/pockets/${id}/`);
  },

  async getCurrencies(): Promise<Currency[]> {
    const response = await api.get<Currency[]>('/assets/currencies/');
    return response.data;
  },
};
