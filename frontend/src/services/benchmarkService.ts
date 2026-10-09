/**
 * Benchmark service — deprecated.
 *
 * Benchmark data is now fetched as part of the `analyticsService.getPocketVectors()`
 * response, using the `benchmarks` query parameter. The backend returns benchmark
 * indices (sp500, nasdaq, wig20) as normalized vectors (base 1.0 at start, converted
 * to portfolio currency).
 *
 * This file is kept for reference only; it is no longer used (DEC-08, ADR-0008).
 */

/**
 * @deprecated Use analyticsService.getPocketVectors({ benchmarks: JSON.stringify([...]) })
 * instead. Benchmark data is returned in the response under the "benchmarks" key.
 */
export const benchmarkService = {
  async getSP500Data(): Promise<null> {
    // Replaced by analyticsService portfolio vectors
    return null;
  },
};
