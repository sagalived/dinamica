import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { sienge as api, kanbanApi, type AuthUser } from '../lib/api';

interface AuthContextData {
  sessionUser: AuthUser | null;
  authReady: boolean;
  isAdmin: boolean;
  isRestrictedUser: boolean;
  login: (user: AuthUser, token: string) => void;
  logout: () => void;
  checkAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextData | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [sessionUser, setSessionUser] = useState<AuthUser | null>(null);
  const [authReady, setAuthReady] = useState(false);

  const isAdmin = sessionUser?.role === 'developer' || sessionUser?.role === 'admin';
  const isRestrictedUser = sessionUser?.role === 'user';

  const checkAuth = useCallback(async () => {
    const token = localStorage.getItem('dinamica_token');
    const storedUser = localStorage.getItem('dinamica_user');
    
    if (token && storedUser) {
      try {
        api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
        kanbanApi.defaults.headers.common['Authorization'] = `Bearer ${token}`;
        
        const response = await api.get('/auth/me');
        if (response.data && response.data.user) {
          setSessionUser(response.data.user);
        } else {
          logout();
        }
      } catch (error) {
        console.error('Erro ao verificar sessão:', error);
        logout();
      }
    } else {
      logout();
    }
    setAuthReady(true);
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const login = useCallback((user: AuthUser, token: string) => {
    localStorage.setItem('dinamica_token', token);
    localStorage.setItem('dinamica_user', JSON.stringify(user));
    api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    kanbanApi.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    setSessionUser(user);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('dinamica_token');
    localStorage.removeItem('dinamica_user');
    delete api.defaults.headers.common['Authorization'];
    delete kanbanApi.defaults.headers.common['Authorization'];
    setSessionUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ sessionUser, authReady, isAdmin, isRestrictedUser, login, logout, checkAuth }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
