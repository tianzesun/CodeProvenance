'use client';

import axios from 'axios';
import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from 'react';

export type AuthRole = 'admin' | 'professor';

export interface AuthUser {
  id: string;
  email: string;
  full_name: string;
  role: AuthRole;
  tenant_id: string | null;
  tenant_name: string | null;
  is_active: boolean;
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

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  bootstrapped: boolean;
  refreshSession: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  bootstrapAdmin: (payload: {
    email: string;
    full_name: string;
    password: string;
    tenant_name?: string;
  }) => Promise<void>;
  logout: () => Promise<void>;
  listUsers: () => Promise<AuthUser[]>;
  createUser: (payload: CreateUserInput) => Promise<AuthUser>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [bootstrapped, setBootstrapped] = useState(true);

  const refreshSession = async () => {
    setLoading(true);
    try {
      axios.defaults.withCredentials = true;
      const statusRes = await axios.get('/api/auth/status');
      const nextBootstrapped = Boolean(statusRes.data?.bootstrapped);
      setBootstrapped(nextBootstrapped);

      if (!nextBootstrapped) {
        setUser(null);
        return;
      }

      const meRes = await axios.get('/api/auth/me');
      setUser(meRes.data?.user || null);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshSession();
  }, []);

  const login = async (email: string, password: string) => {
    const res = await axios.post('/api/auth/login', { email, password });
    setBootstrapped(true);
    setUser(res.data?.user || null);
  };

  const bootstrapAdmin = async (payload: {
    email: string;
    full_name: string;
    password: string;
    tenant_name?: string;
  }) => {
    const res = await axios.post('/api/auth/bootstrap-admin', payload);
    setBootstrapped(true);
    setUser(res.data?.user || null);
  };

  const logout = async () => {
    await axios.post('/api/auth/logout');
    setUser(null);
  };

  const listUsers = async () => {
    const res = await axios.get('/api/admin/users');
    return res.data?.users || [];
  };

  const createUser = async (payload: CreateUserInput) => {
    const res = await axios.post('/api/admin/users', payload);
    return res.data?.user;
  };

  const value = useMemo(
    () => ({
      user,
      loading,
      bootstrapped,
      refreshSession,
      login,
      bootstrapAdmin,
      logout,
      listUsers,
      createUser,
    }),
    [user, loading, bootstrapped],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used inside AuthProvider');
  }
  return context;
}
