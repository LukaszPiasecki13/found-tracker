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
  positions_value?: number;
  total_value?: number;
  total_fees?: number;
  total_profit_loss?: number;
  total_return_pct?: number;
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
  market_value?: number;
  unrealized_pnl?: number;
  return_pct?: number;
  portfolio_weight_pct?: number;
}

export type OperationType = 'buy' | 'sell' | 'deposit' | 'withdrawal' | 'dividend';

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
  free_cash_vector: number[];
  pocket_value_vector: number[];
  portfolio_value_vector?: number[];
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

// Error Response
export interface ApiError {
  detail?: string;
  [key: string]: any;
}
