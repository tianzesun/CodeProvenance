'use client';

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Loader2,
  Plus,
  Search,
  ShieldCheck,
  UserPlus,
  Users,
  UserCheck,
  UserX,
  X,
} from 'lucide-react';

import DashboardLayout from '@/components/DashboardLayout';
import { AuthRole, AuthUser, useAuth } from '@/components/AuthProvider';

function formatDate(value: string | null) {
  if (!value) return 'Never';

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);
}

function getErrorMessage(error: unknown): string {
  if (
    typeof error === 'object' &&
    error !== null &&
    'response' in error &&
    typeof error.response === 'object' &&
    error.response !== null &&
    'data' in error.response &&
    typeof error.response.data === 'object' &&
    error.response.data !== null &&
    'detail' in error.response.data &&
    typeof error.response.data.detail === 'string'
  ) {
    return error.response.data.detail;
  }

  return 'Unable to complete that action right now.';
}

function validatePasswordInput(password: string): string | null {
  if (password.length < 8) return 'Password must be at least 8 characters long.';
  return null;
}

type RoleFilter = 'all' | AuthRole;

function RoleBadge({ role }: { role: AuthRole }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${
        role === 'admin'
          ? 'bg-violet-100 text-violet-700 dark:bg-violet-500/15 dark:text-violet-300'
          : 'bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300'
      }`}
    >
      {role === 'admin' ? 'Admin' : 'Professor'}
    </span>
  );
}

function StatusBadge({ suspended }: { suspended?: boolean }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${
        suspended
          ? 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300'
          : 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300'
      }`}
    >
      {suspended ? 'Suspended' : 'Active'}
    </span>
  );
}

function UserRowSkeleton() {
  return (
    <div className="grid grid-cols-12 items-center gap-4 px-5 py-4">
      <div className="col-span-4 h-10 animate-pulse rounded-2xl bg-slate-200 dark:bg-slate-800" />
      <div className="col-span-2 h-6 animate-pulse rounded-full bg-slate-200 dark:bg-slate-800" />
      <div className="col-span-2 h-6 animate-pulse rounded-full bg-slate-200 dark:bg-slate-800" />
      <div className="col-span-2 h-5 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
      <div className="col-span-2 h-9 animate-pulse rounded-xl bg-slate-200 dark:bg-slate-800" />
    </div>
  );
}

function AuthPageSkeleton() {
  return (
    <DashboardLayout requiredRole="admin">
      <div className="mx-auto max-w-7xl px-4 py-6 lg:px-6 lg:py-8">
        <div className="mb-6 rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950">
          <div className="h-5 w-28 animate-pulse rounded-full bg-slate-200 dark:bg-slate-800" />
          <div className="mt-4 h-10 w-72 animate-pulse rounded-2xl bg-slate-200 dark:bg-slate-800" />
          <div className="mt-3 h-4 w-[28rem] max-w-full animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
        </div>

        <div className="mb-6 grid gap-4 md:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <div
              key={index}
              className="rounded-[24px] border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950"
            >
              <div className="h-4 w-24 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
              <div className="mt-4 h-9 w-16 animate-pulse rounded-xl bg-slate-200 dark:bg-slate-800" />
            </div>
          ))}
        </div>

        <div className="overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
          <div className="border-b border-slate-200 px-5 py-4 dark:border-slate-800">
            <div className="h-6 w-32 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
            <div className="mt-2 h-4 w-64 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
          </div>
          <div className="divide-y divide-slate-200 dark:divide-slate-800">
            {Array.from({ length: 5 }).map((_, index) => (
              <UserRowSkeleton key={index} />
            ))}
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

export default function AdminPage() {
  const {
    user,
    status,
    loading: authLoading,
    bootstrapped,
    listUsers,
    createUser,
  } = useAuth();

  const createButtonRef = useRef<HTMLButtonElement | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);

  const [users, setUsers] = useState<AuthUser[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [saving, setSaving] = useState(false);

  const [pageError, setPageError] = useState('');
  const [formError, setFormError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  const [showCreatePanel, setShowCreatePanel] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState<RoleFilter>('all');

  const [form, setForm] = useState({
    full_name: '',
    email: '',
    password: '',
    role: 'professor' as AuthRole,
    tenant_name: '',
  });

  const loadUsers = useCallback(async () => {
    setLoadingUsers(true);
    setPageError('');

    try {
      const result = await listUsers();
      setUsers(result);
    } catch (error) {
      setPageError(getErrorMessage(error));
    } finally {
      setLoadingUsers(false);
    }
  }, [listUsers]);

  useEffect(() => {
    if (!bootstrapped || authLoading || status === 'loading') {
      return;
    }

    if (!user || user.role !== 'admin') {
      setLoadingUsers(false);
      return;
    }

    loadUsers();
  }, [bootstrapped, authLoading, status, user, loadUsers]);

  useEffect(() => {
    if (showCreatePanel) {
      document.body.style.overflow = 'hidden';
      setTimeout(() => closeButtonRef.current?.focus(), 0);
    } else {
      document.body.style.overflow = '';
    }

    return () => {
      document.body.style.overflow = '';
    };
  }, [showCreatePanel]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && showCreatePanel) {
        closeCreatePanel();
      }
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [showCreatePanel]);

  const filteredUsers = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();

    return users.filter((entry) => {
      const matchesRole = roleFilter === 'all' || entry.role === roleFilter;
      const matchesQuery =
        !query ||
        entry.full_name.toLowerCase().includes(query) ||
        entry.email.toLowerCase().includes(query) ||
        (entry.tenant_name || '').toLowerCase().includes(query);

      return matchesRole && matchesQuery;
    });
  }, [users, roleFilter, searchQuery]);

  const totalUsers = users.length;
  const activeUsers = users.filter((entry) => !entry.suspended).length;
  const suspendedUsers = users.filter((entry) => entry.suspended).length;

  const resetForm = () => {
    setForm({
      full_name: '',
      email: '',
      password: '',
      role: 'professor',
      tenant_name: '',
    });
    setFormError('');
  };

  const openCreatePanel = () => {
    setSuccessMessage('');
    setFormError('');
    setShowCreatePanel(true);
  };

  const closeCreatePanel = () => {
    setShowCreatePanel(false);
    resetForm();
    setTimeout(() => createButtonRef.current?.focus(), 0);
  };

  const handleCreateUser = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    setFormError('');
    setSuccessMessage('');

    if (!form.full_name.trim() || !form.email.trim()) {
      setFormError('Full name and email are required.');
      return;
    }

    const passwordError = validatePasswordInput(form.password);
    if (passwordError) {
      setFormError(passwordError);
      return;
    }

    setSaving(true);

    try {
      await createUser({
        full_name: form.full_name.trim(),
        email: form.email.trim(),
        password: form.password,
        role: form.role,
        tenant_name: form.tenant_name.trim(),
      });

      await loadUsers();
      closeCreatePanel();
      setSuccessMessage('User created successfully.');
    } catch (error) {
      setFormError(getErrorMessage(error));
    } finally {
      setSaving(false);
    }
  };

  if (!bootstrapped || authLoading || status === 'loading') {
    return <AuthPageSkeleton />;
  }

  return (
    <DashboardLayout requiredRole="admin">
      <div className="mx-auto max-w-7xl px-4 py-6 lg:px-6 lg:py-8">
        <section className="mb-6 rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
                <Users size={14} />
                Account Directory
              </div>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight text-slate-900 dark:text-white">
                User administration
              </h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600 dark:text-slate-400">
                Review all accounts, check access status, and create new users from one place.
              </p>
            </div>

            <button
              ref={createButtonRef}
              type="button"
              onClick={openCreatePanel}
              className="inline-flex h-11 items-center justify-center gap-2 rounded-2xl bg-slate-950 px-5 text-sm font-semibold text-white transition hover:bg-slate-800 dark:bg-white dark:text-slate-950 dark:hover:bg-slate-200"
            >
              <Plus size={16} />
              New user
            </button>
          </div>
        </section>

        {(successMessage || pageError) && (
          <div className="mb-6 space-y-3">
            {successMessage && (
              <div className="flex items-start gap-3 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-300">
                <CheckCircle2 size={16} className="mt-0.5 shrink-0" />
                <span>{successMessage}</span>
              </div>
            )}

            {pageError && (
              <div className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300">
                <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                <span>{pageError}</span>
              </div>
            )}
          </div>
        )}

        <section className="mb-6 grid gap-4 md:grid-cols-3">
          <div className="rounded-[24px] border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950">
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">
              Total users
            </div>
            <div className="mt-3 text-3xl font-semibold text-slate-900 tabular-nums dark:text-white">
              {totalUsers}
            </div>
          </div>

          <div className="rounded-[24px] border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950">
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">
              Active
            </div>
            <div className="mt-3 text-3xl font-semibold text-emerald-700 tabular-nums dark:text-emerald-300">
              {activeUsers}
            </div>
          </div>

          <div className="rounded-[24px] border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950">
            <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">
              Suspended
            </div>
            <div className="mt-3 text-3xl font-semibold text-amber-700 tabular-nums dark:text-amber-300">
              {suspendedUsers}
            </div>
          </div>
        </section>

        <section className="overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
          <div className="flex flex-col gap-4 border-b border-slate-200 px-5 py-4 dark:border-slate-800 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Users</h2>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                Search by name, email, or workspace.
              </p>
            </div>

            <div className="flex flex-col gap-3 sm:flex-row">
              <div className="relative min-w-[240px]">
                <Search
                  size={16}
                  className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                />
                <input
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  placeholder="Search users"
                  className="h-11 w-full rounded-2xl border border-slate-200 bg-white pl-10 pr-4 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white dark:placeholder:text-slate-500"
                />
              </div>

              <select
                value={roleFilter}
                onChange={(event) => setRoleFilter(event.target.value as RoleFilter)}
                className="h-11 rounded-2xl border border-slate-200 bg-white px-4 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white"
              >
                <option value="all">All roles</option>
                <option value="admin">Admin</option>
                <option value="professor">Professor</option>
              </select>
            </div>
          </div>

          {loadingUsers ? (
            <>
              <div className="hidden md:block">
                <div className="grid grid-cols-12 gap-4 border-b border-slate-200 px-5 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500 dark:border-slate-800 dark:text-slate-400">
                  <div className="col-span-4">User</div>
                  <div className="col-span-2">Role</div>
                  <div className="col-span-2">Status</div>
                  <div className="col-span-2">Last login</div>
                  <div className="col-span-2 text-right">Actions</div>
                </div>
                <div className="divide-y divide-slate-200 dark:divide-slate-800">
                  {Array.from({ length: 5 }).map((_, index) => (
                    <UserRowSkeleton key={index} />
                  ))}
                </div>
              </div>

              <div className="grid gap-4 p-4 md:hidden">
                {Array.from({ length: 3 }).map((_, index) => (
                  <div
                    key={index}
                    className="rounded-3xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-950"
                  >
                    <div className="h-5 w-1/2 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
                    <div className="mt-3 h-4 w-2/3 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
                    <div className="mt-4 h-20 animate-pulse rounded-2xl bg-slate-200 dark:bg-slate-800" />
                  </div>
                ))}
              </div>
            </>
          ) : filteredUsers.length === 0 ? (
            <div className="px-5 py-14 text-center">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-slate-100 text-slate-500 dark:bg-slate-900 dark:text-slate-400">
                <Users size={22} />
              </div>
              <h3 className="mt-4 text-base font-semibold text-slate-900 dark:text-white">
                No users found
              </h3>
              <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500 dark:text-slate-400">
                No accounts match your current filters. Try a different search, or create a new user.
              </p>
              <button
                type="button"
                onClick={openCreatePanel}
                className="mt-5 inline-flex h-11 items-center justify-center gap-2 rounded-2xl bg-slate-950 px-5 text-sm font-semibold text-white transition hover:bg-slate-800 dark:bg-white dark:text-slate-950 dark:hover:bg-slate-200"
              >
                <UserPlus size={16} />
                Create user
              </button>
            </div>
          ) : (
            <>
              <div className="hidden md:block overflow-x-auto">
                <table className="min-w-full text-left">
                  <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500 dark:bg-slate-900/80 dark:text-slate-400">
                    <tr>
                      <th className="px-5 py-3">User</th>
                      <th className="px-5 py-3">Role</th>
                      <th className="px-5 py-3">Status</th>
                      <th className="px-5 py-3">Last login</th>
                      <th className="px-5 py-3">Workspace</th>
                      <th className="px-5 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                    {filteredUsers.map((entry) => (
                      <tr
                        key={entry.id}
                        className="hover:bg-slate-50 dark:hover:bg-slate-900/60"
                      >
                        <td className="px-5 py-4">
                          <div className="font-medium text-slate-900 dark:text-white">
                            {entry.full_name}
                          </div>
                          <div className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                            {entry.email}
                          </div>
                        </td>

                        <td className="px-5 py-4">
                          <RoleBadge role={entry.role} />
                        </td>

                        <td className="px-5 py-4">
                          <StatusBadge suspended={entry.suspended} />
                        </td>

                        <td className="px-5 py-4 text-sm text-slate-600 dark:text-slate-400">
                          {formatDate(entry.last_login_at)}
                        </td>

                        <td className="px-5 py-4 text-sm text-slate-600 dark:text-slate-400">
                          {entry.tenant_name || 'Default workspace'}
                        </td>

                        <td className="px-5 py-4">
                          <div className="flex justify-end">
                            <button
                              type="button"
                              className="inline-flex h-9 items-center gap-2 rounded-xl border border-slate-200 px-3 text-sm font-medium text-slate-700 transition hover:bg-slate-100 dark:border-slate-800 dark:text-slate-200 dark:hover:bg-slate-900"
                            >
                              {entry.suspended ? <UserCheck size={14} /> : <UserX size={14} />}
                              {entry.suspended ? 'Activate' : 'Suspend'}
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="grid gap-4 p-4 md:hidden">
                {filteredUsers.map((entry) => (
                  <article
                    key={entry.id}
                    className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-950"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <h3 className="truncate text-base font-semibold text-slate-900 dark:text-white">
                          {entry.full_name}
                        </h3>
                        <p className="mt-1 truncate text-sm text-slate-500 dark:text-slate-400">
                          {entry.email}
                        </p>
                      </div>
                      <RoleBadge role={entry.role} />
                    </div>

                    <div className="mt-4 grid grid-cols-2 gap-3 rounded-2xl bg-slate-50 p-3 dark:bg-slate-900">
                      <div>
                        <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
                          Status
                        </div>
                        <div className="mt-2">
                          <StatusBadge suspended={entry.suspended} />
                        </div>
                      </div>

                      <div>
                        <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
                          Last login
                        </div>
                        <div className="mt-2 text-sm text-slate-700 dark:text-slate-300">
                          {formatDate(entry.last_login_at)}
                        </div>
                      </div>

                      <div className="col-span-2">
                        <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
                          Workspace
                        </div>
                        <div className="mt-2 text-sm text-slate-700 dark:text-slate-300">
                          {entry.tenant_name || 'Default workspace'}
                        </div>
                      </div>
                    </div>

                    <div className="mt-4">
                      <button
                        type="button"
                        className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-2xl border border-slate-200 px-4 text-sm font-medium text-slate-700 transition hover:bg-slate-100 dark:border-slate-800 dark:text-slate-200 dark:hover:bg-slate-900"
                      >
                        {entry.suspended ? <UserCheck size={14} /> : <UserX size={14} />}
                        {entry.suspended ? 'Activate user' : 'Suspend user'}
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            </>
          )}
        </section>
      </div>

      {showCreatePanel && (
        <div
          className="fixed inset-0 z-50 flex justify-end bg-slate-950/40 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-labelledby="create-user-title"
        >
          <button
            type="button"
            aria-label="Close panel"
            className="hidden h-full flex-1 cursor-default md:block"
            onClick={closeCreatePanel}
          />

          <div className="h-full w-full max-w-xl overflow-y-auto border-l border-slate-200 bg-white shadow-2xl dark:border-slate-800 dark:bg-slate-950">
            <div className="sticky top-0 z-10 flex items-start justify-between border-b border-slate-200 bg-white/95 px-6 py-5 backdrop-blur dark:border-slate-800 dark:bg-slate-950/95">
              <div>
                <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
                  <UserPlus size={14} />
                  Create account
                </div>
                <h2
                  id="create-user-title"
                  className="mt-3 text-2xl font-semibold tracking-tight text-slate-900 dark:text-white"
                >
                  Add a new user
                </h2>
                <p className="mt-2 text-sm leading-6 text-slate-500 dark:text-slate-400">
                  Create an admin or professor account with an optional workspace name.
                </p>
              </div>

              <button
                ref={closeButtonRef}
                type="button"
                onClick={closeCreatePanel}
                className="inline-flex h-10 w-10 items-center justify-center rounded-2xl text-slate-500 transition hover:bg-slate-100 hover:text-slate-700 dark:text-slate-400 dark:hover:bg-slate-900 dark:hover:text-white"
                aria-label="Close create user panel"
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleCreateUser} className="space-y-5 px-6 py-6">
              {formError && (
                <div className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300">
                  <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                  <span>{formError}</span>
                </div>
              )}

              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
                  Full name
                </label>
                <input
                  value={form.full_name}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, full_name: event.target.value }))
                  }
                  placeholder="Professor Grace Hopper"
                  className="h-12 w-full rounded-2xl border border-slate-200 bg-white px-4 text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white dark:placeholder:text-slate-500"
                />
              </div>

              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
                  Email
                </label>
                <input
                  type="email"
                  value={form.email}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, email: event.target.value }))
                  }
                  placeholder="name@university.edu"
                  className="h-12 w-full rounded-2xl border border-slate-200 bg-white px-4 text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white dark:placeholder:text-slate-500"
                />
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
                    Role
                  </label>
                  <select
                    value={form.role}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        role: event.target.value as AuthRole,
                      }))
                    }
                    className="h-12 w-full rounded-2xl border border-slate-200 bg-white px-4 text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white"
                  >
                    <option value="professor">Professor</option>
                    <option value="admin">Admin</option>
                  </select>
                </div>

                <div>
                  <label className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
                    Workspace name
                  </label>
                  <input
                    value={form.tenant_name}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, tenant_name: event.target.value }))
                    }
                    placeholder="Optional workspace"
                    className="h-12 w-full rounded-2xl border border-slate-200 bg-white px-4 text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white dark:placeholder:text-slate-500"
                  />
                </div>
              </div>

              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
                  Temporary password
                </label>
                <input
                  type="password"
                  value={form.password}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, password: event.target.value }))
                  }
                  placeholder="At least 8 characters"
                  className="h-12 w-full rounded-2xl border border-slate-200 bg-white px-4 text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white dark:placeholder:text-slate-500"
                />
                <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                  Use a temporary password with at least 8 characters.
                </p>
              </div>

              <div className="sticky bottom-0 flex items-center justify-end gap-3 border-t border-slate-200 bg-white/95 pt-5 backdrop-blur dark:border-slate-800 dark:bg-slate-950/95">
                <button
                  type="button"
                  onClick={closeCreatePanel}
                  className="inline-flex h-11 items-center justify-center rounded-2xl px-4 text-sm font-medium text-slate-600 transition hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-900"
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={saving}
                  className="inline-flex h-11 items-center justify-center gap-2 rounded-2xl bg-slate-950 px-5 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-white dark:text-slate-950 dark:hover:bg-slate-200"
                >
                  {saving ? <Loader2 size={16} className="animate-spin" /> : <ShieldCheck size={16} />}
                  {saving ? 'Creating user...' : 'Create user'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
