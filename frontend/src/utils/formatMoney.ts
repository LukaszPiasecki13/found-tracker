export const NO_VALUE = '—';

/** Money with its currency. `code` shows the ISO code (100,00 EUR), `symbol` the
 *  locale symbol (100,00 zł). Asset-currency amounts use `code` (DEC-1). */
export function formatMoney(
  value: number | null | undefined,
  currencyCode: string,
  display: 'symbol' | 'code' = 'symbol',
): string {
  if (value == null) return NO_VALUE;
  return new Intl.NumberFormat('pl-PL', {
    style: 'currency',
    currency: currencyCode,
    currencyDisplay: display,
    minimumFractionDigits: 2,
  }).format(value);
}

export function formatPercent(value: number | null | undefined): string {
  if (value == null) return NO_VALUE;
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
}
