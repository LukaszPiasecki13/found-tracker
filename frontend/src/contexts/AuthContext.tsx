import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { authService } from '../services/authService';
import type { UserProfile, LoginRequest, RegisterRequest } from '../types/api';
import { getErrorMessage } from '../lib/api';
import { useSnackbar } from 'notistack';

interface AuthContextType {
  user: UserProfile | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: LoginRequest) => Promise<void>;
  register: (userData: RegisterRequest) => Promise<void>;
  logout: () => void;
  refreshUserData: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const { enqueueSnackbar } = useSnackbar();
  const navigate = useNavigate();

  // Check if user is already logged in on mount
  useEffect(() => {
    const initAuth = async () => {
      const token = localStorage.getItem('access');
      if (token) {
        try {
          const userData = await authService.getCurrentUser();
          setUser(userData);
        } catch (error) {
          console.error('Failed to fetch user data:', error);
          localStorage.removeItem('access');
          localStorage.removeItem('refresh');
        }
      }
      setIsLoading(false);
    };

    initAuth();
  }, []);

  // Auto-refresh token before expiry
  useEffect(() => {
    if (!user) return;

    const refreshInterval = setInterval(async () => {
      const refreshToken = localStorage.getItem('refresh');
      if (refreshToken) {
        try {
          const { access } = await authService.refreshToken(refreshToken);
          localStorage.setItem('access', access);
        } catch (error) {
          console.error('Token refresh failed:', error);
          logout();
        }
      }
    }, 1000 * 60 * 14); // Refresh every 14 minutes (tokens usually expire in 15 mins)

    return () => clearInterval(refreshInterval);
  }, [user]);

  const login = async (credentials: { username: string; password: string }) => {
    try {
      const { access, refresh } = await authService.login(credentials);
      localStorage.setItem('access', access);
      localStorage.setItem('refresh', refresh);

      const userData = await authService.getCurrentUser();
      setUser(userData);
      enqueueSnackbar('Zalogowano pomyślnie', { variant: 'success' });
      navigate('/');
    } catch (error: any) {
      // Try to extract backend error details for field errors
      if (error && typeof error === 'object' && error.details) {
        // pass error up for field error display
        throw error;
      }
      const message = getErrorMessage(error);
      enqueueSnackbar(message, { variant: 'error' });
      throw error;
    }
  };

  const register = async (userData: RegisterRequest) => {
    try {
      await authService.register(userData);
      enqueueSnackbar('Konto utworzone pomyślnie. Możesz się teraz zalogować.', { variant: 'success' });
      navigate('/login');
    } catch (error) {
      const message = getErrorMessage(error);
      enqueueSnackbar(message, { variant: 'error' });
      throw error;
    }
  };

  const logout = () => {
    authService.logout();
    setUser(null);
    enqueueSnackbar('Wylogowano pomyślnie', { variant: 'info' });
    navigate('/login');
  };

  const refreshUserData = async () => {
    try {
      const userData = await authService.getCurrentUser();
      setUser(userData);
    } catch (error) {
      console.error('Failed to refresh user data:', error);
    }
  };

  const value: AuthContextType = {
    user,
    isAuthenticated: !!user,
    isLoading,
    login,
    register,
    logout,
    refreshUserData,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
