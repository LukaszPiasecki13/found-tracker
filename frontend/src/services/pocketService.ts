import api from '../lib/api';
import type { Pocket, CreatePocketRequest, UpdatePocketRequest, Currency } from '../types/api';

export const pocketService = {
  async getPockets(): Promise<Pocket[]> {
    const response = await api.get<Pocket[]>('/portfolios/');
    return response.data;
  },

  async getPocket(id: number): Promise<Pocket> {
    const response = await api.get<Pocket>(`/portfolios/${id}`);
    return response.data;
  },

  async getPocketByName(name: string): Promise<Pocket> {
    const response = await api.get<Pocket[]>('/portfolios/', {
      params: { name },
    });
    
    if (!response.data || response.data.length === 0) {
      throw new Error(`Pocket with name "${name}" not found`);
    }
    
    return response.data[0];
  },

  async createPocket(data: CreatePocketRequest): Promise<Pocket> {
    const response = await api.post<Pocket>('/portfolios/', data);
    return response.data;
  },

  async updatePocket(id: number, data: UpdatePocketRequest): Promise<Pocket> {
    const response = await api.patch<Pocket>(`/portfolios/${id}`, data);
    return response.data;
  },

  async deletePocket(id: number): Promise<void> {
    await api.delete(`/portfolios/${id}`);
  },

  async getCurrencies(): Promise<Currency[]> {
    const response = await api.get<Currency[]>('/assets/currencies');
    return response.data;
  },
};
