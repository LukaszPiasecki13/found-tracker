import axios, { AxiosError } from 'axios';
import type { AxiosRequestConfig, InternalAxiosRequestConfig } from 'axios';
import type { ApiError } from '../types/api';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('access');
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

const clearSession = () => {
  localStorage.removeItem('access');
  localStorage.removeItem('refresh');
};

// One refresh at a time: parallel 401s wait for the same request instead of
// each spending (and racing on) the refresh token.
let pendingRefresh: Promise<string> | null = null;

export const refreshTokens = (): Promise<string> => {
  if (!pendingRefresh) {
    pendingRefresh = (async () => {
      const refreshToken = localStorage.getItem('refresh');
      if (!refreshToken) {
        throw new Error('No refresh token available');
      }
      const response = await axios.post<{ access: string; refresh?: string }>(
        `${import.meta.env.VITE_API_URL}/auth/token/refresh`,
        { refresh: refreshToken }
      );
      const { access, refresh } = response.data;
      localStorage.setItem('access', access);
      // The backend issues a new pair; keeping the new refresh token is what
      // lets an active session outlive the first refresh token.
      if (refresh) {
        localStorage.setItem('refresh', refresh);
      }
      return access;
    })().finally(() => {
      pendingRefresh = null;
    });
  }
  return pendingRefresh;
};

// Response interceptor to handle token refresh
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiError>) => {
    const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean };

    // A 401 from the credential endpoints themselves (wrong password, ...) is a normal
    // answer for the form, not an expired session: no refresh and no redirect,
    // which would reload the page and wipe the form and its error message.
    const isAuthRequest = ['/auth/login', '/auth/register', '/auth/token'].some((path) =>
      originalRequest?.url?.startsWith(path)
    );

    if (
      error.response?.status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !isAuthRequest
    ) {
      originalRequest._retry = true;

      try {
        const access = await refreshTokens();
        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${access}`;
        }
        return api(originalRequest);
      } catch (refreshError) {
        clearSession();
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

export default api;

// User-facing messages by the backend's stable error `code` (the `detail` text
// is only a fallback, per the error contract).
const ERROR_MESSAGES: Record<string, string> = {
  INVALID_CREDENTIALS: 'Nieprawidłowy e-mail lub hasło',
  EMAIL_ALREADY_REGISTERED: 'Ten adres e-mail jest już zarejestrowany',
  ADMIN_REQUIRED: 'Ta operacja wymaga uprawnień administratora',
  PORTFOLIO_NOT_FOUND: 'Nie znaleziono portfela',
  PORTFOLIO_ALREADY_EXISTS: 'Portfel o tej nazwie już istnieje',
  PORTFOLIO_CURRENCY_LOCKED: 'Walutę portfela można zmienić tylko przed pierwszą operacją',
  OPERATION_NOT_FOUND: 'Nie znaleziono operacji',
  INSUFFICIENT_CASH: 'Za mało środków na koncie portfela',
  INSUFFICIENT_QUANTITY: 'Nie masz tylu jednostek do sprzedaży',
  POSITION_NOT_FOUND: 'Brak otwartej pozycji dla tego waloru',
  CONCURRENT_CHANGE: 'Dane zmieniły się w międzyczasie, spróbuj ponownie',
  MARKET_DATA_UNAVAILABLE: 'Dostawca danych rynkowych jest chwilowo niedostępny',
  PRICE_DATA_MISSING: 'Brak cen historycznych dla jednego z walorów',
  INVALID_DATE_RANGE: 'Nieprawidłowy zakres dat (maksymalnie około 10 lat)',
  VALIDATION_ERROR: 'Nieprawidłowe dane w formularzu',
  RATE_LIMITED: 'Zbyt wiele prób, spróbuj ponownie za chwilę',
  IMPORT_PARSER_UNKNOWN: 'Nieznany parser importu',
  IMPORT_PARSE_FAILED: 'Nie udało się sparsować pliku',
  IMPORT_FILE_TOO_LARGE: 'Plik jest za duży (maksymalnie 10 MB)',
  IMPORT_UNRESOLVED_ROWS: 'Paczka zawiera wiersze do rozwiązania',
  IMPORT_BATCH_STATE_INVALID: 'Nieprawidłowy stan paczki importu',
  IMPORT_BATCH_HAS_EDITS: 'Paczka zawiera niezatwierdzone zmiany',
  IMPORT_ALREADY_UPLOADED: 'Ten plik został już wgrany',
  IMPORT_COMMIT_REJECTED: 'Import nie mógł być zatwierdzony',
  IMPORT_BATCH_NOT_FOUND: 'Nie znaleziono paczki importu',
};

// Helper function to extract a user-facing error message
export const getErrorMessage = (error: unknown): string => {
  if (axios.isAxiosError(error)) {
    const data = (error as AxiosError<ApiError>).response?.data;
    if (data?.code && ERROR_MESSAGES[data.code]) {
      return ERROR_MESSAGES[data.code];
    }
    if (typeof data?.detail === 'string') {
      return data.detail;
    }
    if (Array.isArray(data?.detail) && data.detail.length > 0) {
      return data.detail[0].msg;
    }
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'An unexpected error occurred';
};
