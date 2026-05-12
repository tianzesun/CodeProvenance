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
  const [user, setUser] = useState<AuthUser | null>(() => {
    // Try to restore user from localStorage on initial load
    if (typeof window !== 'undefined') {
      try {
        const stored = localStorage.getItem('integritydesk_auth_user');
        if (stored) {
          const parsed = JSON.parse(stored);
          // Basic validation of stored user data
          if (parsed && typeof parsed === 'object' && parsed.id && parsed.email) {
            return parsed;
          } else {
            // Invalid data, remove it
            localStorage.removeItem('integritydesk_auth_user');
          }
        }
      } catch {
        // If parsing fails, clean up
        localStorage.removeItem('integritydesk_auth_user');
      }
    }
    return null;
  });
  const [status, setStatus] = useState<AuthStatus>(() => {
    // Set initial status based on stored user
    if (typeof window !== 'undefined') {
      try {
        const stored = localStorage.getItem('integritydesk_auth_user');
        if (stored) {
          const parsed = JSON.parse(stored);
          // Basic validation of stored user data
          if (parsed && typeof parsed === 'object' && parsed.id && parsed.email) {
            return 'authenticated';
          } else {
            localStorage.removeItem('integritydesk_auth_user');
          }
        }
      } catch {
        localStorage.removeItem('integritydesk_auth_user');
      }
    }
    return 'loading';
  });
  const [bootstrapped, setBootstrapped] = useState(() => {
    // Initialize bootstrapped to true if we have stored user data
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('integritydesk_auth_user');
      if (stored) {
        try {
          const parsed = JSON.parse(stored);
          if (parsed && typeof parsed === 'object' && parsed.id && parsed.email) {
            return true; // Assume system is bootstrapped if we have valid user data
          }
        } catch {
          // Invalid data
        }
      }
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
    // If we already have user data from localStorage, just verify the system is bootstrapped
    const hasStoredUser = typeof window !== 'undefined' && localStorage.getItem('integritydesk_auth_user');

    try {
      const statusRes = await apiClient.get('/api/auth/status');
      const nextBootstrapped = Boolean(statusRes.data?.bootstrapped);

      if (!nextBootstrapped) {
        setBootstrapped(true);
        clearSession();
        return;
      }

      setBootstrapped(true);

      // If we have stored user data, try to verify it's still valid
      if (hasStoredUser && user) {
        try {
          const meRes = await apiClient.get('/api/auth/me');
          const currentUser = meRes.data?.user ?? null;

          // Update user data if it changed
          if (currentUser && JSON.stringify(currentUser) !== JSON.stringify(user)) {
            setUser(currentUser);
            localStorage.setItem('integritydesk_auth_user', JSON.stringify(currentUser));
          }
        } catch {
          // If verification fails, clear the session
          clearSession();
        }
      } else {
        // No stored user, try to get current user
        const meRes = await apiClient.get('/api/auth/me');
        const nextUser = meRes.data?.user ?? null;

        setUser(nextUser);
        setStatus(nextUser ? 'authenticated' : 'anonymous');

        if (nextUser) {
          localStorage.setItem('integritydesk_auth_user', JSON.stringify(nextUser));
        }
      }
    } catch {
      setBootstrapped(true);
      // Don't clear session if we have stored user data - it might just be a network issue
      if (!hasStoredUser) {
        clearSession();
      }
    }
  }, [user, clearSession]);

  useEffect(() => {
    installAuthInterceptors(async () => {
      await handleSessionExpired();
    });

    // Only check bootstrap status once, not on every navigation
    if (!bootstrapped) {
      apiClient.get('/api/auth/status').then((statusRes) => {
        const nextBootstrapped = Boolean(statusRes.data?.bootstrapped);
        setBootstrapped(nextBootstrapped);

        if (!nextBootstrapped) {
          clearSession();
          return;
        }

        // If we have stored user data and system is bootstrapped, we're good
        const hasStoredUser = typeof window !== 'undefined' && localStorage.getItem('integritydesk_auth_user');
        if (!hasStoredUser) {
          // No stored user, try to refresh session
          refreshSession();
        }
      }).catch(() => {
        // If we can't check status, assume system is bootstrapped to avoid loops
        setBootstrapped(true);
        const hasStoredUser = typeof window !== 'undefined' && localStorage.getItem('integritydesk_auth_user');
        if (!hasStoredUser) {
          clearSession();
        }
      });
    }
  }, [bootstrapped, handleSessionExpired, refreshSession, clearSession]);

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
