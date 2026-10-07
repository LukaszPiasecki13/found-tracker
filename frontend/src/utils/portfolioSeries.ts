/**
 * Pure utility functions for portfolio chart data transformation.
 * No React, no side effects - purely functional data operations.
 */

/**
 * Filter a series of stacks (assets, asset_classes) to keep only those
 * with a maximum value > 0 across the entire range.
 * Removes stacks that are zero throughout.
 *
 * @param series - Record mapping stack names to value arrays
 * @returns Array of keys (stack names) that have at least one non-zero value
 */
export function dropZeroSeries(series: Record<string, number[]>): string[] {
  return Object.entries(series)
    .filter(([, values]) => Math.max(...values) > 0)
    .map(([key]) => key);
}

/**
 * Build pie chart slices from portfolio positions and free cash.
 * Each position becomes a slice, plus optional "Cash" slice from free cash.
 *
 * @param positions - Position data { [key: string]: number } mapping asset/class names to values
 * @param lastFreeCash - Last value from free_cash_vector (portfolio cash balance)
 * @returns Array of slices with name and value, where sum equals portfolio value
 */
export function pieSlices(
  positions: Record<string, number>,
  lastFreeCash: number
): Array<{ name: string; value: number }> {
  const slices: Array<{ name: string; value: number }> = [];

  // Add positions with a positive value; zero and negative values are skipped
  for (const [name, value] of Object.entries(positions)) {
    if (value > 0) {
      slices.push({ name, value });
    }
  }

  // Add cash slice if it's positive
  if (lastFreeCash > 0) {
    slices.push({ name: "Gotówka", value: lastFreeCash });
  }

  return slices;
}

/**
 * Calculate return percentage from profit and deposits.
 * Points where deposits <= 0 return null (drawn as gaps in the chart).
 *
 * @param profit - Array of profit values
 * @param deposits - Array of net deposit values
 * @returns Array of return percentages (null where deposits <= 0)
 */
export function returnPercent(
  profit: number[],
  deposits: number[]
): (number | null)[] {
  if (profit.length !== deposits.length) {
    throw new Error("profit and deposits arrays must have same length");
  }

  return profit.map((p, idx) => {
    const d = deposits[idx];
    if (d <= 0) return null; // Gap in the chart for non-positive deposits
    return (p / d) * 100;
  });
}
