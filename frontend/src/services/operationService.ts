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
    if (!query || query.length < 2) {
      return [];
    }

    const response = await api.get<{ local: Asset[], yahoo: any[] }>('/assets/assets/search_yahoo/', {
      params: { q: query },
    });

    // Combine local results with Yahoo results
    // For Yahoo results that don't exist in DB, we'll create temporary Asset objects
    const localAssets = response.data.local || [];
    const yahooResults = response.data.yahoo || [];

    // Convert Yahoo results to Asset-like objects
    const yahooAssets: Asset[] = yahooResults.map((result) => ({
      id: -1, // Temporary ID to indicate it's from Yahoo
      ticker: result.symbol,
      name: result.name || result.symbol,
      asset_class: {
        id: -1,
        name: result.type || 'Stock',
      },
      currency: {
        id: -1,
        code: result.currency || 'USD',
        exchange_rate: 1,
        base_currency: null,
      },
      current_price: 0,
      exchange: result.exchange || '',
      sector: result.sector || '',
      updated_at: new Date().toISOString(),
      _fromYahoo: true, // Flag to indicate this needs to be created
    } as any));

    return [...localAssets, ...yahooAssets];
  },

  async createAssetFromYahoo(ticker: string, assetClassId?: number, currencyId?: number): Promise<Asset> {
    const response = await api.post<Asset>('/assets/assets/create_from_yahoo/', {
      ticker,
      asset_class_id: assetClassId,
      currency_id: currencyId,
    });
    return response.data;
  },
};
