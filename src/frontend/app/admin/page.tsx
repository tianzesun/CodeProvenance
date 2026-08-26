'use client';

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  GraduationCap,
  Loader2,
  Plus,
  Search,
  ShieldCheck,
  UserPlus,
  Users,
  UserCheck,
  UserX,
  X,
  Building2,
} from 'lucide-react';

import DashboardLayout from '@/components/DashboardLayout';
import { AuthRole, AuthUser, useAuth } from '@/components/AuthProvider';
import { apiClient } from '@/lib/apiClient';

// ─── Helpers ──────────────────────────────────────────────────────────────────

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
    typeof (error as any).response === 'object' &&
    (error as any).response !== null &&
    'data' in (error as any).response &&
    typeof (error as any).response.data === 'object' &&
    (error as any).response.data !== null &&
    'detail' in (error as any).response.data &&
    typeof (error as any).response.data.detail === 'string'
  ) {
    return (error as any).response.data.detail;
  }
  return 'Unable to complete that action right now.';
}

function validatePasswordInput(password: string): string | null {
  if (password.length < 8) return 'Password must be at least 8 characters long.';
  return null;
}

// ─── Types ─────────────────────────────────────────────────────────────────────

type RoleFilter = 'all' | AuthRole;

interface CourseInstructor {
  id: string;
  full_name: string;
  email: string;
}

interface CourseWithInstructors {
  id: string;
  name: string;
  code?: string;
  organization_name?: string;
  instructors: CourseInstructor[];
}

// ─── Sub-components ────────────────────────────────────────────────────────────

function RoleBadge({ role }: { role: AuthRole }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${role === 'admin'
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
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${suspended
          ? 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300'
          : 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300'
        }`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${suspended ? 'bg-amber-500' : 'bg-emerald-500'
          }`}
      />
      {suspended ? 'Suspended' : 'Active'}
    </span>
  );
}

function UserRowSkeleton() {
  return (
    <tr>
      <td className="px-5 py-4">
        <div className="h-4 w-36 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
        <div className="mt-2 h-3 w-48 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
      </td>
      <td className="px-5 py-4">
        <div className="h-6 w-20 animate-pulse rounded-full bg-slate-200 dark:bg-slate-800" />
      </td>
      <td className="px-5 py-4">
        <div className="h-6 w-16 animate-pulse rounded-full bg-slate-200 dark:bg-slate-800" />
      </td>
      <td className="px-5 py-4">
        <div className="h-4 w-28 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
      </td>
      <td className="px-5 py-4">
        <div className="h-4 w-24 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
      </td>
      <td className="px-5 py-4">
        <div className="flex justify-end">
          <div className="h-9 w-24 animate-pulse rounded-xl bg-slate-200 dark:bg-slate-800" />
        </div>
      </td>
    </tr>
  );
}

function AuthPageSkeleton() {
  return (
    <DashboardLayout requiredRole="admin">
      <div className="px-4 py-6 sm:px-6 lg:px-8 lg:py-8 space-y-6">
        <div className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950">
          <div className="h-5 w-28 animate-pulse rounded-full bg-slate-200 dark:bg-slate-800" />
          <div className="mt-4 h-10 w-72 animate-pulse rounded-2xl bg-slate-200 dark:bg-slate-800" />
          <div className="mt-3 h-4 w-[28rem] max-w-full animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="rounded-[24px] border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950">
              <div className="h-4 w-24 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
              <div className="mt-4 h-9 w-16 animate-pulse rounded-xl bg-slate-200 dark:bg-slate-800" />
            </div>
          ))}
        </div>
        <div className="overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
          <div className="border-b border-slate-200 px-5 py-4 dark:border-slate-800">
            <div className="h-6 w-32 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
          </div>
          <table className="min-w-full">
            <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
              {Array.from({ length: 5 }).map((_, i) => <UserRowSkeleton key={i} />)}
            </tbody>
          </table>
        </div>
      </div>
    </DashboardLayout>
  );
}

// ─── Field component ───────────────────────────────────────────────────────────

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
        {label}
      </label>
      {children}
      {hint && <p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400">{hint}</p>}
    </div>
  );
}

const inputClass =
  'h-12 w-full rounded-2xl border border-slate-200 bg-white px-4 text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white dark:placeholder:text-slate-500';

const selectClass =
  'h-12 w-full rounded-2xl border border-slate-200 bg-white px-4 text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white appearance-none';

// ─── Main page ─────────────────────────────────────────────────────────────────

export default function AdminPage() {
  const { user, status, loading: authLoading, bootstrapped, listUsers, createUser } = useAuth();

  const createButtonRef = useRef<HTMLButtonElement | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);

  const [users, setUsers] = useState<AuthUser[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [pageError, setPageError] = useState('');
  const [formError, setFormError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  const [showCreatePanel, setShowCreatePanel] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState<RoleFilter>('all');

  const [coursesWithInstructors, setCoursesWithInstructors] = useState<CourseWithInstructors[]>([]);
  const [loadingCourses, setLoadingCourses] = useState(true);
  const [selectedProfessorForCourse, setSelectedProfessorForCourse] = useState<Record<string, string>>({});
  const [assigningCourse, setAssigningCourse] = useState<string | null>(null);

  const [form, setForm] = useState({
    full_name: '',
    email: '',
    password: '',
    role: 'professor' as AuthRole,
    tenant_name: '',
  });

  // ── Data loading ─────────────────────────────────────────────────────────────

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

  const loadCoursesWithInstructors = useCallback(async () => {
    setLoadingCourses(true);
    try {
      const res = await apiClient.get('/api/admin/courses-with-instructors');
      setCoursesWithInstructors(res.data?.courses || []);
    } catch (error) {
      console.error('Failed to load courses with instructors', error);
    } finally {
      setLoadingCourses(false);
    }
  }, []);

  useEffect(() => {
    if (!bootstrapped || authLoading || status === 'loading') return;
    if (!user || user.role !== 'admin') {
      setLoadingUsers(false);
      setLoadingCourses(false);
      return;
    }
    loadUsers();
    loadCoursesWithInstructors();
  }, [bootstrapped, authLoading, status, user, loadUsers, loadCoursesWithInstructors]);

  // ── Panel open/close ──────────────────────────────────────────────────────────

  const resetForm = () => {
    setForm({ full_name: '', email: '', password: '', role: 'professor', tenant_name: '' });
    setFormError('');
  };

  const closeCreatePanel = () => {
    setShowCreatePanel(false);
    resetForm();
    setTimeout(() => createButtonRef.current?.focus(), 0);
  };

  useEffect(() => {
    if (showCreatePanel) {
      document.body.style.overflow = 'hidden';
      setTimeout(() => closeButtonRef.current?.focus(), 0);
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = ''; };
  }, [showCreatePanel]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && showCreatePanel) closeCreatePanel();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showCreatePanel]);

  // ── Derived state ─────────────────────────────────────────────────────────────

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
  const activeUsers = users.filter((u) => !u.suspended).length;
  const suspendedUsers = users.filter((u) => u.suspended).length;

  // ── Handlers ──────────────────────────────────────────────────────────────────

  const openCreatePanel = () => {
    setSuccessMessage('');
    setFormError('');
    setShowCreatePanel(true);
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
    if (passwordError) { setFormError(passwordError); return; }

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

  const handleToggleSuspend = async (entry: AuthUser) => {
    setTogglingId(entry.id);
    setSuccessMessage('');
    setPageError('');
    try {
      // Call the appropriate endpoint — adjust to match your API
      await apiClient.patch(`/api/admin/users/${entry.id}`, {
        suspended: !entry.suspended,
      });
      await loadUsers();
      setSuccessMessage(
        entry.suspended
          ? `${entry.full_name} has been reactivated.`
          : `${entry.full_name} has been suspended.`
      );
    } catch (error) {
      setPageError(getErrorMessage(error));
    } finally {
      setTogglingId(null);
    }
  };

  const assignInstructor = async (courseId: string, userId: string) => {
    setAssigningCourse(courseId);
    try {
      await apiClient.post('/api/admin/course-instructors', {
        course_id: courseId,
        user_id: userId,
        role: 'instructor',
      });
      await loadCoursesWithInstructors();
      setSelectedProfessorForCourse((prev) => ({ ...prev, [courseId]: '' }));
    } catch (error) {
      setPageError(getErrorMessage(error));
    } finally {
      setAssigningCourse(null);
    }
  };

  const removeInstructor = async (courseId: string, userId: string, instructorName: string) => {
    if (!confirm(`Remove ${instructorName} from this course?`)) return;
    try {
      await apiClient.delete('/api/admin/course-instructors', {
        data: { course_id: courseId, user_id: userId },
      });
      await loadCoursesWithInstructors();
    } catch (error) {
      setPageError(getErrorMessage(error));
    }
  };

  // ── Early returns ─────────────────────────────────────────────────────────────

  if (!bootstrapped || authLoading || status === 'loading') {
    return <AuthPageSkeleton />;
  }

  // ── Render ────────────────────────────────────────────────────────────────────

  return (
    <DashboardLayout requiredRole="admin">
      <div className="px-4 py-6 sm:px-6 lg:px-8 lg:py-8 space-y-6">

        {/* ── Header ──────────────────────────────────────────────────────────── */}
        <section className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-blue-600/10 bg-blue-600/[0.06] px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.2em] text-blue-600 dark:border-blue-400/20 dark:bg-blue-400/10 dark:text-blue-400">
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

        {/* ── Alerts ──────────────────────────────────────────────────────────── */}
        {(successMessage || pageError) && (
          <div className="space-y-3">
            {successMessage && (
              <div className="flex items-start gap-3 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-300">
                <CheckCircle2 size={16} className="mt-0.5 shrink-0" />
                <span>{successMessage}</span>
                <button
                  type="button"
                  onClick={() => setSuccessMessage('')}
                  className="ml-auto shrink-0 opacity-60 hover:opacity-100 transition"
                  aria-label="Dismiss"
                >
                  <X size={14} />
                </button>
              </div>
            )}
            {pageError && (
              <div className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300">
                <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                <span>{pageError}</span>
                <button
                  type="button"
                  onClick={() => setPageError('')}
                  className="ml-auto shrink-0 opacity-60 hover:opacity-100 transition"
                  aria-label="Dismiss"
                >
                  <X size={14} />
                </button>
              </div>
            )}
          </div>
        )}

        {/* ── Stat cards ──────────────────────────────────────────────────────── */}
        <section className="grid gap-4 md:grid-cols-3">
          <div className="rounded-[24px] border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950">
            <div className="flex items-center justify-between">
              <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">
                Total users
              </div>
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-slate-100 dark:bg-slate-900">
                <Users size={14} className="text-slate-600 dark:text-slate-400" />
              </div>
            </div>
            <div className="mt-3 text-3xl font-semibold text-slate-900 tabular-nums dark:text-white">
              {totalUsers}
            </div>
          </div>

          <div className="rounded-[24px] border border-emerald-100 bg-white p-5 shadow-sm dark:border-emerald-900/40 dark:bg-slate-950">
            <div className="flex items-center justify-between">
              <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">
                Active
              </div>
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-emerald-50 dark:bg-emerald-900/30">
                <UserCheck size={14} className="text-emerald-600 dark:text-emerald-400" />
              </div>
            </div>
            <div className="mt-3 text-3xl font-semibold text-emerald-700 tabular-nums dark:text-emerald-300">
              {activeUsers}
            </div>
          </div>

          <div className="rounded-[24px] border border-amber-100 bg-white p-5 shadow-sm dark:border-amber-900/40 dark:bg-slate-950">
            <div className="flex items-center justify-between">
              <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">
                Suspended
              </div>
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-amber-50 dark:bg-amber-900/30">
                <UserX size={14} className="text-amber-600 dark:text-amber-400" />
              </div>
            </div>
            <div className="mt-3 text-3xl font-semibold text-amber-700 tabular-nums dark:text-amber-300">
              {suspendedUsers}
            </div>
          </div>
        </section>

        {/* ── Users table ─────────────────────────────────────────────────────── */}
        <section className="overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
          {/* Table header + filters */}
          <div className="flex flex-col gap-4 border-b border-slate-200 px-5 py-4 dark:border-slate-800 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Users</h2>
              <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
                {filteredUsers.length === totalUsers
                  ? `${totalUsers} account${totalUsers !== 1 ? 's' : ''}`
                  : `${filteredUsers.length} of ${totalUsers} accounts`}
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
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search by name, email, workspace…"
                  className="h-10 w-full rounded-xl border border-slate-200 bg-white pl-9 pr-4 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white dark:placeholder:text-slate-500"
                />
              </div>

              <div className="relative">
                <select
                  value={roleFilter}
                  onChange={(e) => setRoleFilter(e.target.value as RoleFilter)}
                  className="h-10 w-full appearance-none rounded-xl border border-slate-200 bg-white pl-4 pr-9 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white"
                >
                  <option value="all">All roles</option>
                  <option value="admin">Admin</option>
                  <option value="professor">Professor</option>
                </select>
                <ChevronDown size={14} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" />
              </div>
            </div>
          </div>

          {/* Desktop table */}
          {loadingUsers ? (
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
                  {Array.from({ length: 5 }).map((_, i) => <UserRowSkeleton key={i} />)}
                </tbody>
              </table>
            </div>
          ) : filteredUsers.length === 0 ? (
            <div className="px-5 py-16 text-center">
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
              {/* Desktop */}
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
                    {filteredUsers.map((entry) => {
                      const isToggling = togglingId === entry.id;
                      const isSelf = user?.id === entry.id;
                      return (
                        <tr key={entry.id} className="hover:bg-slate-50 dark:hover:bg-slate-900/50 transition-colors">
                          <td className="px-5 py-4">
                            <div className="font-medium text-slate-900 dark:text-white">{entry.full_name}</div>
                            <div className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">{entry.email}</div>
                          </td>
                          <td className="px-5 py-4"><RoleBadge role={entry.role} /></td>
                          <td className="px-5 py-4"><StatusBadge suspended={entry.suspended} /></td>
                          <td className="px-5 py-4 text-sm text-slate-600 dark:text-slate-400">
                            {formatDate(entry.last_login_at)}
                          </td>
                          <td className="px-5 py-4 text-sm text-slate-600 dark:text-slate-400">
                            {entry.tenant_name || (
                              <span className="text-slate-400 dark:text-slate-600">Default workspace</span>
                            )}
                          </td>
                          <td className="px-5 py-4">
                            <div className="flex justify-end">
                              {isSelf ? (
                                <span className="text-xs text-slate-400 dark:text-slate-600 italic">You</span>
                              ) : (
                                <button
                                  type="button"
                                  disabled={isToggling}
                                  onClick={() => handleToggleSuspend(entry)}
                                  className={`inline-flex h-9 items-center gap-2 rounded-xl border px-3 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${entry.suspended
                                      ? 'border-emerald-200 text-emerald-700 hover:bg-emerald-50 dark:border-emerald-900/50 dark:text-emerald-300 dark:hover:bg-emerald-900/20'
                                      : 'border-slate-200 text-slate-700 hover:bg-slate-100 dark:border-slate-800 dark:text-slate-300 dark:hover:bg-slate-900'
                                    }`}
                                >
                                  {isToggling ? (
                                    <Loader2 size={13} className="animate-spin" />
                                  ) : entry.suspended ? (
                                    <UserCheck size={13} />
                                  ) : (
                                    <UserX size={13} />
                                  )}
                                  {entry.suspended ? 'Activate' : 'Suspend'}
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Mobile cards */}
              <div className="grid gap-3 p-4 md:hidden">
                {filteredUsers.map((entry) => {
                  const isToggling = togglingId === entry.id;
                  const isSelf = user?.id === entry.id;
                  return (
                    <article
                      key={entry.id}
                      className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-950"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <h3 className="truncate text-base font-semibold text-slate-900 dark:text-white">
                            {entry.full_name}
                          </h3>
                          <p className="mt-0.5 truncate text-sm text-slate-500 dark:text-slate-400">
                            {entry.email}
                          </p>
                        </div>
                        <RoleBadge role={entry.role} />
                      </div>

                      <div className="mt-4 grid grid-cols-2 gap-3 rounded-2xl bg-slate-50 p-3 dark:bg-slate-900">
                        <div>
                          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">Status</div>
                          <div className="mt-2"><StatusBadge suspended={entry.suspended} /></div>
                        </div>
                        <div>
                          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">Last login</div>
                          <div className="mt-2 text-sm text-slate-700 dark:text-slate-300">{formatDate(entry.last_login_at)}</div>
                        </div>
                        <div className="col-span-2">
                          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">Workspace</div>
                          <div className="mt-2 text-sm text-slate-700 dark:text-slate-300">
                            {entry.tenant_name || 'Default workspace'}
                          </div>
                        </div>
                      </div>

                      {!isSelf && (
                        <button
                          type="button"
                          disabled={isToggling}
                          onClick={() => handleToggleSuspend(entry)}
                          className={`mt-3 inline-flex h-10 w-full items-center justify-center gap-2 rounded-2xl border px-4 text-sm font-medium transition disabled:opacity-50 ${entry.suspended
                              ? 'border-emerald-200 text-emerald-700 hover:bg-emerald-50 dark:border-emerald-900/50 dark:text-emerald-300 dark:hover:bg-emerald-900/20'
                              : 'border-slate-200 text-slate-700 hover:bg-slate-100 dark:border-slate-800 dark:text-slate-300 dark:hover:bg-slate-900'
                            }`}
                        >
                          {isToggling ? (
                            <Loader2 size={14} className="animate-spin" />
                          ) : entry.suspended ? (
                            <UserCheck size={14} />
                          ) : (
                            <UserX size={14} />
                          )}
                          {entry.suspended ? 'Activate user' : 'Suspend user'}
                        </button>
                      )}
                    </article>
                  );
                })}
              </div>
            </>
          )}
        </section>

        {/* ── Course & Instructor Assignments ─────────────────────────────────── */}
        <section className="overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
          <div className="flex items-start justify-between border-b border-slate-200 px-6 py-5 dark:border-slate-800">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-blue-600/10 bg-blue-600/[0.06] px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.2em] text-blue-600 dark:border-blue-400/20 dark:bg-blue-400/10 dark:text-blue-400">
                <GraduationCap size={14} />
                Instructor Access
              </div>
              <h2 className="mt-3 text-xl font-semibold text-slate-900 dark:text-white">
                Course &amp; Instructor Assignments
              </h2>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                Control which professors can view and upload to each course.
              </p>
            </div>
          </div>

          {loadingCourses ? (
            <div className="divide-y divide-slate-200 dark:divide-slate-800">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="px-6 py-5">
                  <div className="h-5 w-48 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
                  <div className="mt-2 h-4 w-32 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
                  <div className="mt-4 flex gap-2">
                    {Array.from({ length: 2 }).map((_, j) => (
                      <div key={j} className="h-7 w-24 animate-pulse rounded-full bg-slate-200 dark:bg-slate-800" />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : coursesWithInstructors.length === 0 ? (
            <div className="px-6 py-16 text-center">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-slate-100 dark:bg-slate-900">
                <Building2 size={22} className="text-slate-500 dark:text-slate-400" />
              </div>
              <h3 className="mt-4 text-base font-semibold text-slate-900 dark:text-white">No courses found</h3>
              <p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-slate-500 dark:text-slate-400">
                Create courses first before assigning instructors.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-slate-200 dark:divide-slate-800">
              {coursesWithInstructors.map((course) => {
                const professors = users.filter((u) => u.role === 'professor' || u.role === 'admin');
                const currentInstructorIds = course.instructors.map((i) => i.id);
                const availableProfessors = professors.filter((p) => !currentInstructorIds.includes(p.id));
                const isAssigning = assigningCourse === course.id;

                return (
                  <div key={course.id} className="px-6 py-5">
                    <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                      {/* Course info */}
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-semibold text-slate-900 dark:text-white">
                            {course.name}
                          </span>
                          {course.code && (
                            <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-mono font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                              {course.code}
                            </span>
                          )}
                        </div>
                        {course.organization_name && (
                          <div className="mt-0.5 flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
                            <Building2 size={11} />
                            {course.organization_name}
                          </div>
                        )}

                        {/* Current instructors */}
                        <div className="mt-3">
                          {course.instructors.length === 0 ? (
                            <div className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-amber-600 dark:bg-amber-900/20 dark:text-amber-400">
                              <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
                              No instructors assigned
                            </div>
                          ) : (
                            <div className="flex flex-wrap gap-2">
                              {course.instructors.map((inst) => (
                                <div
                                  key={inst.id}
                                  className="group inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 py-1 pl-3 pr-2 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
                                >
                                  <span>{inst.full_name}</span>
                                  <button
                                    type="button"
                                    onClick={() => removeInstructor(course.id, inst.id, inst.full_name)}
                                    className="flex h-5 w-5 items-center justify-center rounded-full text-slate-400 transition hover:bg-red-100 hover:text-red-600 dark:hover:bg-red-900/30 dark:hover:text-red-400"
                                    title={`Remove ${inst.full_name}`}
                                  >
                                    <X size={11} />
                                  </button>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Assign form */}
                      {availableProfessors.length > 0 && (
                        <div className="flex shrink-0 items-center gap-2">
                          <div className="relative">
                            <select
                              value={selectedProfessorForCourse[course.id] || ''}
                              onChange={(e) =>
                                setSelectedProfessorForCourse((prev) => ({ ...prev, [course.id]: e.target.value }))
                              }
                              className="h-10 appearance-none rounded-xl border border-slate-200 bg-white pl-3 pr-8 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white"
                            >
                              <option value="">Add professor…</option>
                              {availableProfessors.map((p) => (
                                <option key={p.id} value={p.id}>
                                  {p.full_name}
                                </option>
                              ))}
                            </select>
                            <ChevronDown size={13} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" />
                          </div>
                          <button
                            type="button"
                            disabled={!selectedProfessorForCourse[course.id] || isAssigning}
                            onClick={() => {
                              const uid = selectedProfessorForCourse[course.id];
                              if (uid) assignInstructor(course.id, uid);
                            }}
                            className="inline-flex h-10 items-center gap-2 rounded-xl bg-blue-600 px-4 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            {isAssigning ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
                            Assign
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

      </div>

      {/* ── Create user slide-over ─────────────────────────────────────────────── */}
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
            {/* Panel header */}
            <div className="sticky top-0 z-10 flex items-start justify-between border-b border-slate-200 bg-white/95 px-6 py-5 backdrop-blur dark:border-slate-800 dark:bg-slate-950/95">
              <div>
                <div className="inline-flex items-center gap-2 rounded-full border border-blue-600/10 bg-blue-600/[0.06] px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.2em] text-blue-600 dark:border-blue-400/20 dark:bg-blue-400/10 dark:text-blue-400">
                  <UserPlus size={14} />
                  Create account
                </div>
                <h2
                  id="create-user-title"
                  className="mt-3 text-2xl font-semibold tracking-tight text-slate-900 dark:text-white"
                >
                  Add a new user
                </h2>
                <p className="mt-1.5 text-sm leading-6 text-slate-500 dark:text-slate-400">
                  Create an admin or professor account with an optional workspace name.
                </p>
              </div>

              <button
                ref={closeButtonRef}
                type="button"
                onClick={closeCreatePanel}
                className="inline-flex h-10 w-10 items-center justify-center rounded-2xl text-slate-500 transition hover:bg-slate-100 hover:text-slate-700 dark:text-slate-400 dark:hover:bg-slate-900 dark:hover:text-white"
                aria-label="Close"
              >
                <X size={18} />
              </button>
            </div>

            {/* Form */}
            <form onSubmit={handleCreateUser} className="px-6 py-6">
              <div className="space-y-5">
                {formError && (
                  <div className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300">
                    <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                    <span>{formError}</span>
                  </div>
                )}

                <Field label="Full name">
                  <input
                    value={form.full_name}
                    onChange={(e) => setForm((c) => ({ ...c, full_name: e.target.value }))}
                    placeholder="Professor Grace Hopper"
                    className={inputClass}
                  />
                </Field>

                <Field label="Email address">
                  <input
                    type="email"
                    value={form.email}
                    onChange={(e) => setForm((c) => ({ ...c, email: e.target.value }))}
                    placeholder="name@university.edu"
                    className={inputClass}
                  />
                </Field>

                <div className="grid gap-4 md:grid-cols-2">
                  <Field label="Role">
                    <div className="relative">
                      <select
                        value={form.role}
                        onChange={(e) => setForm((c) => ({ ...c, role: e.target.value as AuthRole }))}
                        className={selectClass}
                      >
                        <option value="professor">Professor</option>
                        <option value="admin">Admin</option>
                      </select>
                      <ChevronDown size={14} className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-slate-400" />
                    </div>
                  </Field>

                  <Field label="Workspace name">
                    <input
                      value={form.tenant_name}
                      onChange={(e) => setForm((c) => ({ ...c, tenant_name: e.target.value }))}
                      placeholder="Optional"
                      className={inputClass}
                    />
                  </Field>
                </div>

                <Field
                  label="Temporary password"
                  hint="Minimum 8 characters. The user should change this on first login."
                >
                  <input
                    type="password"
                    value={form.password}
                    onChange={(e) => setForm((c) => ({ ...c, password: e.target.value }))}
                    placeholder="At least 8 characters"
                    className={inputClass}
                  />
                </Field>
              </div>

              <div className="mt-8 flex items-center justify-end gap-3 border-t border-slate-200 pt-5 dark:border-slate-800">
                <button
                  type="button"
                  onClick={closeCreatePanel}
                  className="inline-flex h-11 items-center justify-center rounded-2xl px-5 text-sm font-medium text-slate-600 transition hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-900"
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={saving}
                  className="inline-flex h-11 items-center justify-center gap-2 rounded-2xl bg-slate-950 px-6 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-white dark:text-slate-950 dark:hover:bg-slate-200"
                >
                  {saving ? <Loader2 size={16} className="animate-spin" /> : <ShieldCheck size={16} />}
                  {saving ? 'Creating…' : 'Create user'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}