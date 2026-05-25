import api from '../lib/api';
import type {
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  TokenRefreshRequest,
  TokenRefreshResponse,
  UserProfile,
} from '../types/api';

export const authService = {
  async login(credentials: { email: string; password: string }): Promise<LoginResponse> {
    const response = await api.post<LoginResponse>('/auth/login', {
      email: credentials.email,
      password: credentials.password,
    });
    return response.data;
  },

  async register(userData: RegisterRequest): Promise<UserProfile> {
    const response = await api.post<UserProfile>('/auth/register', userData);
    return response.data;
  },

  async refreshToken(refreshToken: string): Promise<TokenRefreshResponse> {
    const response = await api.post<TokenRefreshResponse>('/auth/token/refresh', {
      refresh: refreshToken,
    } as TokenRefreshRequest);
    return response.data;
  },

  async getCurrentUser(): Promise<UserProfile> {
    const response = await api.get<UserProfile>('/auth/me');
    return response.data;
  },

  logout(): void {
    localStorage.removeItem('access');
    localStorage.removeItem('refresh');
  },
};
