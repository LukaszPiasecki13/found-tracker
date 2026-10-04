import api from '../lib/api';
import type {
  ImportBatchSummary,
  ImportBatch,
  ImportPreview,
} from '../types/api';

export const importService = {
  async getImports(portfolioId: number): Promise<ImportBatchSummary[]> {
    const response = await api.get<ImportBatchSummary[]>(
      `/portfolios/${portfolioId}/imports`
    );
    return response.data;
  },

  async getImportBatch(portfolioId: number, batchId: number): Promise<ImportBatch> {
    const response = await api.get<ImportBatch>(
      `/portfolios/${portfolioId}/imports/${batchId}`
    );
    return response.data;
  },

  async previewImport(
    portfolioId: number,
    file: File
  ): Promise<ImportPreview> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await api.post<ImportPreview>(
      `/portfolios/${portfolioId}/imports/preview`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  },

  async commitImport(
    portfolioId: number,
    file: File
  ): Promise<ImportBatch> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await api.post<ImportBatch>(
      `/portfolios/${portfolioId}/imports`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  },

  async revertImportBatch(
    portfolioId: number,
    batchId: number
  ): Promise<ImportBatch> {
    const response = await api.post<ImportBatch>(
      `/portfolios/${portfolioId}/imports/${batchId}/revert`
    );
    return response.data;
  },
};
