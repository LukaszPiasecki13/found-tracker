import api from '../lib/api';
import type {
  Asset,
  BondSeriesSearchResult,
  BondTerms,
  CreateAssetRequest,
  CreateBondTermsRequest,
} from '../types/api';

export const bondService = {
  async searchBondSeries(seriesCode: string): Promise<BondSeriesSearchResult> {
    const response = await api.get<BondSeriesSearchResult>(
      `/assets/bond-series/${encodeURIComponent(seriesCode)}`
    );
    return response.data;
  },

  async createAsset(data: CreateAssetRequest): Promise<Asset> {
    const response = await api.post<Asset>('/assets/', data);
    return response.data;
  },

  async registerBondTerms(assetId: number, data: CreateBondTermsRequest): Promise<BondTerms> {
    const response = await api.post<BondTerms>(`/assets/${assetId}/bond-terms`, data);
    return response.data;
  },
};
