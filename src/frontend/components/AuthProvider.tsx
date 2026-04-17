'use client';

import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

import { apiClient, installAuthInterceptors } from '@/lib/apiClient';

export type AuthRole = 'admin' | 'professor';
export type AuthStatus = 'loading' | 'authenticated' | 'anonymous';

export interface AuthUser {
  id: string;
  email: string;
  full_name: string;
  role: AuthRole;
  tenant_id: string | null;
  tenant_name: string | null;
  is_active: boolean;
  suspended: boolean;
  last_login_at: string | null;
  created_at: string | null;
}

interface CreateUserInput {
  email: string;
  full_name: string;
  password: string;
  role: AuthRole;
  tenant_name?: string;
}

interface BootstrapAdminInput {
  email: string;
  full_name: string;
  password: string;
  tenant_name?: string;
}

interface AuthContextValue {
  user: AuthUser | null;
  status: AuthStatus;
  loading: boolean;
  bootstrapped: boolean;
  refreshSession: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  bootstrapAdmin: (payload: BootstrapAdminInput) => Promise<void>;
  logout: () => Promise<void>;
  listUsers: () => Promise<AuthUser[]>;
  createUser: (payload: CreateUserInput) => Promise<AuthUser>;
  handleSessionExpired: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [status, setStatus] = useState<AuthStatus>('loading');
  const [bootstrapped, setBootstrapped] = useState(false);

  const clearSession = useCallback(() => {
    setUser(null);
    setStatus('anonymous');
  }, []);

  const handleSessionExpired = useCallback(async () => {
    clearSession();
  }, [clearSession]);

  const refreshSession = useCallback(async () => {
    setStatus((current) => (bootstrapped ? current : 'loading'));

    try {
      const statusRes = await apiClient.get('/api/auth/status');
      const nextBootstrapped = Boolean(statusRes.data?.bootstrapped);

      if (!nextBootstrapped) {
        setBootstrapped(true);
        clearSession();
        return;
      }

      const meRes = await apiClient.get('/api/auth/me');
      const nextUser = meRes.data?.user ?? null;

      setBootstrapped(true);
      setUser(nextUser);
      setStatus(nextUser ? 'authenticated' : 'anonymous');
    } catch {
      setBootstrapped(true);
      clearSession();
    }
  }, [bootstrapped, clearSession]);

  useEffect(() => {
    installAuthInterceptors(async () => {
      await handleSessionExpired();
    });

    refreshSession();
  }, [handleSessionExpired, refreshSession]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await apiClient.post('/api/auth/login', { email, password });
    const nextUser = res.data?.user ?? null;

    setBootstrapped(true);
    setUser(nextUser);
    setStatus(nextUser ? 'authenticated' : 'anonymous');
  }, []);

  const bootstrapAdmin = useCallback(async (payload: BootstrapAdminInput) => {
    const res = await apiClient.post('/api/auth/bootstrap-admin', payload);
    const nextUser = res.data?.user ?? null;

    setBootstrapped(true);
    setUser(nextUser);
    setStatus(nextUser ? 'authenticated' : 'anonymous');
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiClient.post('/api/auth/logout');
    } catch (error) {
      console.warn('Logout API call failed:', error);
    } finally {
      clearSession();
    }
  }, [clearSession]);

  const listUsers = useCallback(async () => {
    const res = await apiClient.get('/api/admin/users');
    return res.data?.users || [];
  }, []);

  const createUser = useCallback(async (payload: CreateUserInput) => {
    const res = await apiClient.post('/api/admin/users', payload);
    return res.data?.user;
  }, []);

  const value = useMemo(
    () => ({
      user,
      status,
      loading: status === 'loading',
      bootstrapped,
      refreshSession,
      login,
      bootstrapAdmin,
      logout,
      listUsers,
      createUser,
      handleSessionExpired,
    }),
    [
      user,
      status,
      bootstrapped,
      refreshSession,
      login,
      bootstrapAdmin,
      logout,
      listUsers,
      createUser,
      handleSessionExpired,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    // During SSR or if provider is not mounted, return safe defaults
    if (typeof window === 'undefined') {
      return {
        user: null,
        status: 'loading' as const,
        loading: true,
        bootstrapped: false,
        refreshSession: async () => {},
        login: async () => {},
        bootstrapAdmin: async () => {},
        logout: async () => {},
        listUsers: async () => [],
        createUser: async () => ({} as any),
        handleSessionExpired: async () => {},
      };
    }
    throw new Error('useAuth must be used within AuthProvider');
  }

  return context;
}
