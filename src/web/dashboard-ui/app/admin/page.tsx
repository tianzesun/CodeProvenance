'use client';

import { FormEvent, useEffect, useState } from 'react';
import { AlertTriangle, ShieldCheck, UserPlus, Users } from 'lucide-react';

import DashboardLayout from '@/components/DashboardLayout';
import { AuthRole, AuthUser, useAuth } from '@/components/AuthProvider';

function formatDate(value: string | null) {
  if (!value) {
    return 'Never';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);
}

function getErrorMessage(error: any): string {
  return error?.response?.data?.detail || 'Unable to complete that action right now.';
}

function validatePasswordInput(password: string): string | null {
  if (password.length < 8) {
    return 'Password must be at least 8 characters long.';
  }

  return null;
}

export default function AdminPage() {
  const { listUsers, createUser, user, loading: authLoading } = useAuth();
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [form, setForm] = useState({
    full_name: '',
    email: '',
    password: '',
    role: 'professor' as AuthRole,
    tenant_name: '',
  });

  const loadUsers = async () => {
    setLoading(true);
    setError('');
    try {
      setUsers(await listUsers());
    } catch (loadError) {
      setError(getErrorMessage(loadError));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (authLoading || !user || user.role !== 'admin') {
      return;
    }
    loadUsers();
  }, [authLoading, user]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');

    const passwordError = validatePasswordInput(form.password);
    if (passwordError) {
      setError(passwordError);
      return;
    }

    setSaving(true);

    try {
      await createUser(form);
      setForm({
        full_name: '',
        email: '',
        password: '',
        role: 'professor',
        tenant_name: '',
      });
      await loadUsers();
    } catch (createError) {
      setError(getErrorMessage(createError));
    } finally {
      setSaving(false);
    }
  };

  return (
    <DashboardLayout requiredRole="admin">
      <div className="px-4 py-4 lg:px-6 lg:py-6">
        <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
          <section className="theme-card-strong theme-section-line rounded-[30px] p-6 lg:p-8">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="inline-flex items-center gap-2 rounded-full border border-blue-600/10 bg-blue-600/[0.06] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-blue-600">
                  <Users size={14} />
                  Account Directory
                </div>
                <h1 className="mt-4 text-3xl font-semibold text-[var(--text-primary)]">User administration</h1>
                <p className="mt-2 max-w-2xl text-sm leading-7 text-[var(--text-secondary)]">
                  Create professor and admin accounts, review last sign-in activity, and keep the deployment owned by real users instead of shared credentials.
                </p>
              </div>
              <div className="rounded-3xl border border-[color:var(--border)] bg-[var(--surface-muted)] px-5 py-4">
                <div className="text-[11px] uppercase tracking-[0.2em] text-[var(--text-muted)]">Accounts</div>
                <div className="mt-2 text-3xl font-semibold text-[var(--text-primary)]">{users.length}</div>
              </div>
            </div>

            {error && (
              <div className="mt-6 flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <div className="mt-6 overflow-hidden rounded-[28px] border border-[color:var(--border)] bg-[var(--surface)]">
              <div className="grid grid-cols-[1.4fr_1fr_1fr_1.1fr] gap-4 border-b border-[color:var(--border)] px-5 py-3 text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                <div>User</div>
                <div>Role</div>
                <div>Workspace</div>
                <div>Last Login</div>
              </div>
              {loading ? (
                <div className="px-5 py-8 text-sm text-[var(--text-muted)]">Loading users...</div>
              ) : users.length === 0 ? (
                <div className="px-5 py-8 text-sm text-[var(--text-muted)]">No users found yet.</div>
              ) : (
                <div className="divide-y divide-[color:var(--border)]">
                  {users.map((user) => (
                    <div key={user.id} className="grid grid-cols-[1.4fr_1fr_1fr_1.1fr] gap-4 px-5 py-4 text-sm">
                      <div className="min-w-0">
                        <div className="truncate font-medium text-[var(--text-primary)]">{user.full_name}</div>
                        <div className="truncate text-[var(--text-muted)]">{user.email}</div>
                      </div>
                      <div>
                        <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${user.role === 'admin' ? 'bg-violet-100 text-violet-700' : 'bg-blue-100 text-blue-700'}`}>
                          {user.role === 'admin' ? 'Admin' : 'Professor'}
                        </span>
                      </div>
                      <div className="text-[var(--text-secondary)]">{user.tenant_name || 'No workspace'}</div>
                      <div className="text-[var(--text-secondary)]">{formatDate(user.last_login_at)}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>

          <section className="theme-card rounded-[30px] p-6 lg:p-8">
            <div className="inline-flex items-center gap-2 rounded-full border border-[color:var(--border)] bg-[var(--surface-muted)] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
              <UserPlus size={14} />
              Create Account
            </div>
            <h2 className="mt-4 text-2xl font-semibold text-[var(--text-primary)]">Add a new user</h2>
            <p className="mt-2 text-sm leading-7 text-[var(--text-secondary)]">
              Every new account gets its own workspace tenant by default so professor results stay separated.
            </p>

            <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-[var(--text-secondary)]">Full Name</label>
                <input
                  value={form.full_name}
                  onChange={(event) => setForm((current) => ({ ...current, full_name: event.target.value }))}
                  className="w-full rounded-2xl border border-[color:var(--border)] bg-[var(--surface)] px-4 py-3 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                  placeholder="Professor Grace Hopper"
                />
              </div>

              <div>
                <label className="mb-1.5 block text-sm font-medium text-[var(--text-secondary)]">Email</label>
                <input
                  type="email"
                  value={form.email}
                  onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
                  className="w-full rounded-2xl border border-[color:var(--border)] bg-[var(--surface)] px-4 py-3 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                  placeholder="name@university.edu"
                />
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-[var(--text-secondary)]">Role</label>
                  <select
                    value={form.role}
                    onChange={(event) => setForm((current) => ({ ...current, role: event.target.value as AuthRole }))}
                    className="w-full rounded-2xl border border-[color:var(--border)] bg-[var(--surface)] px-4 py-3 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                  >
                    <option value="professor">Professor</option>
                    <option value="admin">Admin</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-[var(--text-secondary)]">Workspace Name</label>
                  <input
                    value={form.tenant_name}
                    onChange={(event) => setForm((current) => ({ ...current, tenant_name: event.target.value }))}
                    className="w-full rounded-2xl border border-[color:var(--border)] bg-[var(--surface)] px-4 py-3 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                    placeholder="Optional custom workspace"
                  />
                </div>
              </div>

              <div>
                <label className="mb-1.5 block text-sm font-medium text-[var(--text-secondary)]">Temporary Password</label>
                <input
                  type="password"
                  value={form.password}
                  onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
                  className="w-full rounded-2xl border border-[color:var(--border)] bg-[var(--surface)] px-4 py-3 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                  placeholder="At least 8 characters"
                />
                <p className="mt-2 text-xs text-[var(--text-muted)]">
                  Use at least 8 characters for new accounts.
                </p>
              </div>

              <button
                type="submit"
                disabled={saving}
                className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <ShieldCheck size={16} />
                {saving ? 'Creating user...' : 'Create user'}
              </button>
            </form>
          </section>
        </div>
      </div>
    </DashboardLayout>
  );
}
