import type { OperationType } from '../types/api';

const OPERATION_TYPE_LABELS: Record<OperationType, string> = {
  buy: 'Kupno',
  sell: 'Sprzedaż',
  deposit: 'Wpłata',
  withdrawal: 'Wypłata',
  dividend: 'Dywidenda',
  interest: 'Odsetki',
  fee: 'Opłata',
  split: 'Split',
};

export const getOperationTypeLabel = (type: string): string =>
  OPERATION_TYPE_LABELS[type as OperationType] ?? type;
