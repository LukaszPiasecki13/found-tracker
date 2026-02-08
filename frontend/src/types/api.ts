// API Response Types
export interface Currency {
  id: number;
  code: string;
  exchange_rate: number;
  base_currency: number | null;
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
  status: 'regular' | 'admin';
  main_currency: string;
}

export interface Pocket {
  id: number;
  owner: number;
  name: string;
  base_currency: Currency;
  cash_balance: number;
  total_deposited: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  total_fees?: number;
  total_profit_loss?: number;
  total_return_pct?: number;
}

export interface Position {
  id: number;
  pocket: number;
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
  cost_basis_in_pocket_currency?: number;
  market_value?: number;
  unrealized_pnl?: number;
  profit?: number;
  return_pct?: number;
  pocket_weight_pct?: number;
}

export type OperationType = 'buy' | 'sell' | 'deposit' | 'withdrawal' | 'dividend';

export interface Operation {
  id: number;
  pocket: number;
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
  date_vector: string[];
  asset_vectors: Record<string, number[]>;
  asset_class_vectors: Record<string, number[]>;
  net_deposits_vector: number[];
  transaction_cost_vector: number[];
  profit_vector: number[];
  free_cash_vector: number[];
  pocket_value_vector: number[];
}

// Auth Types
export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access: string;
  refresh: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  main_currency: string;
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
  base_currency: number;
}

export interface CreateOperationRequest {
  pocket: number;
  asset?: number;
  operation_type: OperationType;
  quantity?: number;
  price?: number;
  amount: number;
  fee?: number;
  fx_rate?: number;
  notes?: string;
  operation_date: string;
}

// Error Response
export interface ApiError {
  detail?: string;
  [key: string]: any;
}
