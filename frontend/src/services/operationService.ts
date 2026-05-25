import api from '../lib/api';
import type { Operation, CreateOperationRequest, AssetClass, Asset } from '../types/api';

export const operationService = {
  async getOperations(pocketName?: string): Promise<Operation[]> {
    const response = await api.get<Operation[]>('/portfolios/operations', {
      params: pocketName ? { portfolio_name: pocketName } : undefined,
    });
    return response.data;
  },

  async createOperation(data: CreateOperationRequest): Promise<Operation> {
    const response = await api.post<Operation>('/portfolios/operations', data);
    return response.data;
  },

  async deleteOperation(id: number): Promise<void> {
    await api.delete(`/portfolios/operations/${id}`);
  },

  async getAssetClasses(): Promise<AssetClass[]> {
    const response = await api.get<AssetClass[]>('/assets/asset-classes');
    return response.data;
  },

  async searchAssets(query: string): Promise<Asset[]> {
    if (!query || query.length < 2) {
      return [];
    }

    const response = await api.get<{ local: Asset[], yahoo: any[] }>('/assets/search-yahoo', {
      params: { q: query },
    });

    const localAssets = response.data.local || [];
    const yahooResults = response.data.yahoo || [];

    const yahooAssets: Asset[] = yahooResults.map((result) => ({
      id: -1,
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
        base_currency_id: null,
      },
      current_price: 0,
      exchange: result.exchange || '',
      sector: result.sector || '',
      updated_at: new Date().toISOString(),
      _fromYahoo: true,
    } as any));

    return [...localAssets, ...yahooAssets];
  },

  async createAssetFromYahoo(ticker: string, assetClassId?: number, currencyId?: number): Promise<Asset> {
    const response = await api.post<Asset>('/assets/create-from-yahoo', {
      ticker,
      asset_class_id: assetClassId,
      currency_id: currencyId,
    });
    return response.data;
  },
};
