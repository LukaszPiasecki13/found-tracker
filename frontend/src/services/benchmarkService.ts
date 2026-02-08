/**
 * Benchmark service fetches S&P 500 data from the backend analytics endpoint.
 * We use a special "benchmark" pocket name convention or direct yfinance proxy.
 * 
 * Since backend PocketMetrics uses yfinance, we can create a lightweight
 * endpoint or fetch directly. For now, we provide a static normalization utility.
 */

interface BenchmarkDataPoint {
  date: string;
  value: number;
}

/**
 * Normalize a value array to percentage change relative to start (start = 100)
 */
export const normalizeToPercent = (values: number[]): number[] => {
  if (values.length === 0) return [];
  const start = values[0] || 1;
  return values.map((v) => (v / start) * 100);
};

/**
 * Placeholder for future S&P 500 API integration.
 * Could use Alpha Vantage, Yahoo Finance proxy, or backend endpoint.
 * 
 * For now, returns null so the UI can handle the absence gracefully.
 */
export const benchmarkService = {
  async getSP500Data(
    _startDate: string,
    _endDate: string
  ): Promise<BenchmarkDataPoint[] | null> {
    // TODO: Integrate with external API for S&P 500 data
    // Options:
    // 1. Backend endpoint that uses yfinance to fetch ^GSPC
    // 2. Alpha Vantage free API
    // 3. Financial Modeling Prep API
    return null;
  },
};
