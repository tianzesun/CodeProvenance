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
  // Authentication is verified against the backend HttpOnly session cookie on
  // every startup. localStorage is NEVER treated as proof of identity: a stale
  // or forged `integritydesk_auth_user` must not grant dashboard access, so
  // identity starts unset and is only populated from /api/auth/me.
  const [user, setUser] = useState<AuthUser | null>(null);
  const [status, setStatus] = useState<AuthStatus>('loading');
  const [bootstrapped, setBootstrapped] = useState(() => {
    // Optimistic UI hint only (controls login-page wording). Whether the
    // workspace is initialized is always re-checked server-side on startup.
    if (typeof window !== 'undefined') {
      return localStorage.getItem('integritydesk_bootstrapped') === 'true';
    }
    return false;
  });

  const clearSession = useCallback(() => {
    setUser(null);
    setStatus('anonymous');
    if (typeof window !== 'undefined') {
      localStorage.removeItem('integritydesk_auth_user');
    }
  }, []);

  const handleSessionExpired = useCallback(async () => {
    clearSession();
  }, [clearSession]);

  const refreshSession = useCallback(async () => {
    // Always validate against the backend. localStorage user data is never a
    // substitute for the server-issued HttpOnly cookie.
    try {
      const statusRes = await apiClient.get('/api/auth/status');
      const nextBootstrapped = Boolean(statusRes.data?.bootstrapped);

      if (!nextBootstrapped) {
        setBootstrapped(false);
        clearSession();
        return;
      }

      setBootstrapped(true);

      const meRes = await apiClient.get('/api/auth/me');
      const currentUser = meRes.data?.user ?? null;

      setUser(currentUser);
      setStatus(currentUser ? 'authenticated' : 'anonymous');

      if (currentUser) {
        localStorage.setItem('integritydesk_auth_user', JSON.stringify(currentUser));
      }
    } catch {
      // Backend could not confirm a valid session cookie, so treat the user
      // as anonymous instead of trusting cached localStorage identity.
      clearSession();
    }
  }, [clearSession]);

  useEffect(() => {
    installAuthInterceptors(async () => {
      await handleSessionExpired();
    });

    // Always validate the session on startup. The previous code skipped this
    // whenever `bootstrapped` was already true from localStorage, which let a
    // stale/forged stored user render the dashboard without a valid cookie and
    // then bounce every refresh/click to login once the first API call 401'd.
    refreshSession();
  }, [handleSessionExpired, refreshSession]);

// Periodic session validation (every 5 minutes)
  useEffect(() => {
    if (!user || status !== 'authenticated') return;

    const interval = setInterval(async () => {
      try {
        await apiClient.get('/api/auth/me');
      } catch {
        // If session validation fails, clear the session
        clearSession();
      }
    }, 5 * 60 * 1000); // 5 minutes

    return () => clearInterval(interval);
  }, [user, status, clearSession]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await apiClient.post('/api/auth/login', { email, password });
    const nextUser = res.data?.user ?? null;

    setBootstrapped(true);
    setUser(nextUser);
    setStatus(nextUser ? 'authenticated' : 'anonymous');

    // Persist user in localStorage
    if (nextUser && typeof window !== 'undefined') {
      localStorage.setItem('integritydesk_auth_user', JSON.stringify(nextUser));
    }
  }, []);

  const bootstrapAdmin = useCallback(async (payload: BootstrapAdminInput) => {
    const res = await apiClient.post('/api/auth/bootstrap-admin', payload);
    const nextUser = res.data?.user ?? null;

    setBootstrapped(true);
    setUser(nextUser);
    setStatus(nextUser ? 'authenticated' : 'anonymous');

    // Persist user in localStorage
    if (nextUser && typeof window !== 'undefined') {
      localStorage.setItem('integritydesk_auth_user', JSON.stringify(nextUser));
    }
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
