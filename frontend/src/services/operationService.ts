import api from '../lib/api';
import type { Operation, CreateOperationRequest, AssetClass, Asset } from '../types/api';

export const operationService = {
  async getOperations(pocketName?: string): Promise<Operation[]> {
    const response = await api.get<Operation[]>('/portfolios/operations/', {
      params: pocketName ? { pocket_name: pocketName } : undefined,
    });
    return response.data;
  },

  async getOperation(id: number): Promise<Operation> {
    const response = await api.get<Operation>(`/portfolios/operations/${id}/`);
    return response.data;
  },

  async createOperation(data: CreateOperationRequest): Promise<Operation> {
    const response = await api.post<Operation>('/portfolios/operations/', data);
    return response.data;
  },

  async updateOperation(id: number, data: Partial<CreateOperationRequest>): Promise<Operation> {
    const response = await api.patch<Operation>(`/portfolios/operations/${id}/`, data);
    return response.data;
  },

  async deleteOperation(id: number): Promise<void> {
    await api.delete(`/portfolios/operations/${id}/`);
  },

  async getAssetClasses(): Promise<AssetClass[]> {
    const response = await api.get<AssetClass[]>('/assets/asset-classes/');
    return response.data;
  },

  async searchAssets(query: string): Promise<Asset[]> {
    const response = await api.get<Asset[]>('/assets/assets/', {
      params: { search: query },
    });
    return response.data;
  },
};
