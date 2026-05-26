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

    const response = await api.get<{ local: Asset[]; yahoo: unknown[] }>('/assets/search-yahoo', {
      params: { q: query },
    });

    const localAssets = response.data.local || [];
    const yahooResults = response.data.yahoo || [];

    const yahooAssets: Asset[] = yahooResults.map((result) => {
      const r = result as Record<string, unknown>;
      const symbol = String(r.symbol ?? '');
      const name = String(r.name ?? symbol);
      const type = String(r.type ?? 'Stock');
      const currency = String(r.currency ?? 'USD');
      const exchange = String(r.exchange ?? '');
      const sector = String(r.sector ?? '');

      return {
        id: -1,
        ticker: symbol,
        name,
        asset_class: {
          id: -1,
          name: type,
        },
        currency: {
          id: -1,
          code: currency,
          exchange_rate: 1,
          base_currency_id: null,
        },
        current_price: 0,
        exchange,
        sector,
        updated_at: new Date().toISOString(),
        _fromYahoo: true,
      };
    });

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
