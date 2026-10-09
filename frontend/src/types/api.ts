// API Response Types
export interface Currency {
  id: number;
  code: string;
  exchange_rate: number;
  base_currency_id: number | null;
}

export interface AssetClass {
  id: number;
  name: string;
}

export interface Asset {
  id: number;
  ticker: string;
  name: string;
  asset_class: AssetClass;
  currency: Currency;
  current_price: number;
  exchange: string;
  sector: string | null;
  updated_at: string;
}

// The eight current Polish retail treasury bond series.
export type BondSymbol = 'OTS' | 'ROR' | 'DOR' | 'TOS' | 'COI' | 'EDO' | 'ROS' | 'ROD';
export type BondCapitalization = 'none' | 'monthly' | 'annual';
export type BondReferenceType = 'fixed' | 'nbp_reference' | 'cpi';

// What `GET /assets/bond-series/{series_code}` returns: prefill data from the
// provider, not yet registered against any asset.
export interface BondSeriesSearchResult {
  bond_symbol: BondSymbol;
  series_code: string;
  nominal_value: number;
  issue_date: string;
  maturity_date: string;
  capitalization: BondCapitalization;
  first_period_rate: number | null;
  reference_type: BondReferenceType | null;
  margin: number | null;
  redemption_fee: number;
}

export interface CreateBondTermsRequest {
  bond_symbol: BondSymbol;
  series_code: string;
  nominal_value: number;
  issue_date: string;
  maturity_date: string;
  capitalization: BondCapitalization;
  first_period_rate: number | null;
  reference_type: BondReferenceType | null;
  margin: number | null;
  redemption_fee: number;
}

export interface BondTerms extends CreateBondTermsRequest {
  asset_id: number;
  source: string;
}

export interface CreateAssetRequest {
  ticker: string;
  name: string;
  asset_class_id: number;
  currency_id: number;
  asset_type: 'stock' | 'etf' | 'bond';
}

export interface UserProfile {
  id: number;
  email: string;
  is_active: boolean;
}

export interface Pocket {
  id: number;
  owner_id: number;
  name: string;
  base_currency: Currency;
  cash_balance: number;
  total_deposited: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  // Null when a position has no currency rate (see rate_missing).
  positions_value?: number | null;
  total_value?: number | null;
  total_fees?: number;
  total_profit_loss?: number | null;
  // Cumulative time-weighted return (%) since the first operation; null when it cannot be told.
  total_return_pct?: number | null;
  return_method?: string | null;
  rate_missing?: boolean;
}

export interface Position {
  id: number;
  portfolio_id: number;
  asset_id: number;
  asset: Asset;
  quantity: number;
  average_buy_price: number;
  average_fx_rate: number;
  total_fees: number;
  total_dividends: number;
  opened_at: string;
  updated_at: string;
  // Calculated fields
  cost_basis?: number;
  cost_basis_in_portfolio_currency?: number;
  // Null when no rate turns the asset's currency into the portfolio's.
  market_value?: number | null;
  unrealized_pnl?: number | null;
  return_pct?: number | null;
  portfolio_weight_pct?: number | null;
  rate_missing?: boolean;
  // Asset-currency view: needs no rate, so it is set even when rate_missing (DEC-6).
  market_value_asset_currency?: number | null;
  unrealized_pnl_asset_currency?: number | null;
  price_change_pct?: number | null;
  // PLN profit split (DEC-4); null when rate_missing.
  fx_rate_applied?: number | null;
  price_effect?: number | null;
  fx_effect?: number | null;
}

export type OperationType =
  | 'buy'
  | 'sell'
  | 'deposit'
  | 'withdrawal'
  | 'dividend'
  | 'interest'
  | 'fee'
  | 'split';

export interface Operation {
  id: number;
  portfolio_id: number;
  asset_id: number | null;
  asset: Asset | null;
  operation_type: OperationType;
  quantity: number | null;
  price: number | null;
  amount: number;
  fee: number;
  fx_rate: number;
  notes: string;
  operation_date: string;
  created_at: string;
}

export interface PocketVectorsResponse {
  date: string[];
  assets: Record<string, number[]>;
  asset_classes: Record<string, number[]>;
  net_deposits_vector: number[];
  transaction_cost_vector: number[];
  profit_vector: number[];
  dividend_income_vector?: number[];
  free_cash_vector: number[];
  pocket_value_vector: number[];
  portfolio_value_vector?: number[];
  // Null where a value is not defined (XIRR before the first flow, or no solution).
  twr_index_vector?: number[];
  drawdown_vector?: number[];
  xirr_vector?: (number | null)[];
}

export interface CurrencySplitItem {
  currency: string;
  value: number;
}

export interface CurrencySplitResponse {
  currency: string;
  items: CurrencySplitItem[];
  unpriced: number;
}

// Auth Types
export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access: string;
  refresh: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
}

export interface TokenRefreshRequest {
  refresh: string;
}

export interface TokenRefreshResponse {
  access: string;
}

// Request Types
export interface CreatePocketRequest {
  name: string;
  base_currency_id: number;
}

export interface CreateOperationRequest {
  portfolio_id: number;
  asset_id?: number;
  operation_type: OperationType;
  quantity?: number;
  price?: number;
  amount: number;
  fee?: number;
  fx_rate?: number;
  notes?: string;
  operation_date: string;
  ticker?: string;
  asset_class?: string;
}

// Partial update (PATCH): only the fields that changed are sent.
export interface UpdatePocketRequest {
  name?: string;
  base_currency_id?: number;
}

export interface UpdateOperationRequest {
  quantity?: number;
  price?: number;
  amount?: number;
  fee?: number;
  fx_rate?: number;
  notes?: string | null;
  operation_date?: string;
}

// Error Response
export interface ValidationDetail {
  type: string;
  loc: (string | number)[];
  msg: string;
}

// Error body: `code` is the stable identifier, `detail` a message or, for 422,
// the list of invalid fields.
export interface ApiError {
  detail?: string | ValidationDetail[];
  code?: string;
}

export interface FxRate {
  from_currency: string;
  to_currency: string;
  rate: number;
  via: 'identity' | 'direct' | 'inverse' | 'cross';
}

// Import Types
export type ImportRowStatus = 'ok' | 'duplicate' | 'unrecognized' | 'error' | 'skip';
export type ImportBatchStatus = 'committed' | 'reverted';

export interface ImportRowPayload {
  operation_type?: string;
  operation_date?: string;
  amount?: string;
  quantity?: string;
  price?: string;
  fee?: string;
  ticker?: string | null;
  exchange_hint?: string | null;
  notes?: string;
  external_ref?: string;
  asset_class?: string | null;
}

export interface ImportRow {
  id: number | null;
  row_number: number;
  row_status: ImportRowStatus;
  message: string | null;
  payload: ImportRowPayload;
  asset_id: number | null;
  operation_id: number | null;
}

export interface ReconciliationDifference {
  field: string;
  expected: number | null;
  actual: number | null;
}

export interface ReconciliationReport {
  matched: boolean;
  differences: ReconciliationDifference[];
  closed_profit_reported: number | null;
  ledger_error: string | null;
}

export interface ImportPreview {
  parser_id: string;
  filename: string;
  sha256: string;
  existing_batch_id: number | null;
  rows: ImportRow[];
  reconciliation: ReconciliationReport | null;
}

export interface ImportBatchSummary {
  id: number;
  portfolio_id: number;
  parser_id: string;
  filename: string;
  sha256: string;
  status: ImportBatchStatus;
  created_at: string;
}

export interface ImportBatch extends ImportBatchSummary {
  rows: ImportRow[];
  reconciliation: ReconciliationReport | null;
}
