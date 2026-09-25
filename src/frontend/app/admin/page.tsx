'use client';

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  Download,
  FileText,
  GraduationCap,
  Loader2,
  Plus,
  Search,
  ShieldCheck,
  Upload,
  UserPlus,
  Users,
  UserCheck,
  UserX,
  X,
  Building2,
  Zap,
} from 'lucide-react';

import DashboardLayout from '@/components/DashboardLayout';
import { AuthRole, AuthUser, useAuth } from '@/components/AuthProvider';
import { apiClient } from '@/lib/apiClient';
import { buildTermOptions, courseTermLabel } from '@/lib/terms';
import { Modal } from '@/components/saas/SaaSPrimitives';

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

function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

interface AxiosErrorResponse {
  response?: {
    data?: {
      detail?: string;
      message?: string;
    };
  };
}

function getErrorMessage(error: unknown): string {
  const axiosError = error as AxiosErrorResponse;
  const detail = axiosError?.response?.data?.detail;
  if (typeof detail === 'string') {
    return detail;
  }
  return 'Unable to complete that action right now.';
}

function validatePasswordInput(password: string): string | null {
  if (password.length < 8) return 'Password must be at least 8 characters long.';
  return null;
}

// Engine labels mirror the upload flow's engine picker so the recommendation
// shown here reads the same as the analysis configuration.
const RECOMMENDED_ENGINE_LABELS: Record<string, string> = {
  token: 'Token',
  ast: 'AST',
  winnowing: 'Winnowing',
  gst: 'GST',
  semantic: 'Semantic',
  embedding: 'Embedding',
  cfg: 'Control Flow',
  execution_cfg: 'Execution CFG',
  tree_kernel: 'Tree Kernel',
  fingerprint: 'Fingerprint',
  ngram: 'N-gram',
  web: 'Web Matching',
  ai_detection: 'AI Detection',
};

function engineLabel(key: string): string {
  return RECOMMENDED_ENGINE_LABELS[key] ?? key.replace(/_/g, ' ');
}

// ─── Types ─────────────────────────────────────────────────────────────────────

type RoleFilter = 'all' | AuthRole;

interface CourseInstructor {
  id: string;
  full_name: string;
  email: string;
}

interface RecommendedAssignmentMode {
  assignment_type?: string | null;
  matched: boolean;
  mode_id: string | null;
  mode_name: string | null;
  engine_weights: Record<string, number>;
  top_engines: { key: string; weight: number }[];
  reason: string;
}

interface CourseAssignment {
  id: string;
  name: string;
  term?: string | null;
  version?: number;
  assignment_type?: string;
  recommended_mode?: RecommendedAssignmentMode | null;
  due_at?: string | null;
}

interface CourseWithInstructors {
  id: string;
  name: string;
  code?: string;
  term?: string | null;
  year?: number | null;
  department?: string | null;
  organization_name?: string;
  instructors: CourseInstructor[];
  assignment_count?: number;
  assignments?: CourseAssignment[];
}

type ImportRowStatus = 'created' | 'preview' | 'skipped' | 'error';

interface ImportRowResult {
  row: number;
  email: string;
  status: ImportRowStatus;
  detail: string;
  temporary_password?: string;
}

interface ImportReport {
  dry_run: boolean;
  created: number;
  previewed: number;
  skipped: number;
  failed: number;
  results: ImportRowResult[];
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

function AddUserCard({
  onAdd,
  buttonRef,
}: {
  onAdd: () => void;
  buttonRef?: React.RefObject<HTMLButtonElement | null>;
}) {
  return (
    <button
      ref={buttonRef}
      type="button"
      onClick={onAdd}
      aria-label="Add a new user"
      className="group flex w-full flex-col items-center justify-center gap-2 border-t border-slate-200 px-5 py-12 text-center transition hover:bg-blue-50/50 dark:border-slate-800 dark:hover:bg-slate-900/40"
    >
      <span className="flex h-16 w-16 items-center justify-center rounded-2xl border-2 border-dashed border-slate-300 text-slate-400 transition group-hover:border-blue-400 group-hover:bg-white group-hover:text-blue-600 dark:border-slate-700 dark:group-hover:border-blue-500 dark:group-hover:bg-slate-900">
        <Plus size={36} strokeWidth={2} aria-hidden="true" />
      </span>
      <span className="mt-1 text-sm font-semibold text-slate-600 group-hover:text-blue-700 dark:text-slate-300 dark:group-hover:text-blue-300">
        Add user
      </span>
      <span className="text-xs text-slate-400">Invite a professor or administrator</span>
    </button>
  );
}

function AddCourseCard({
  onAdd,
  buttonRef,
  variant = 'row',
}: {
  onAdd: () => void;
  buttonRef?: React.RefObject<HTMLButtonElement | null>;
  variant?: 'row' | 'grid';
}) {
  if (variant === 'grid') {
    return (
      <button
        ref={buttonRef}
        type="button"
        onClick={onAdd}
        aria-label="Add a new course"
        className="group flex min-h-[220px] flex-col items-center justify-center gap-2 rounded-3xl border-2 border-dashed border-slate-300 p-6 text-center transition hover:border-blue-400 hover:bg-blue-50/40 dark:border-slate-800 dark:hover:border-blue-500 dark:hover:bg-slate-900/40"
      >
        <span className="flex h-16 w-16 items-center justify-center rounded-2xl border-2 border-dashed border-slate-300 text-slate-400 transition group-hover:border-blue-400 group-hover:bg-white group-hover:text-blue-600 dark:border-slate-700 dark:group-hover:border-blue-500 dark:group-hover:bg-slate-900">
          <Plus size={36} strokeWidth={2} aria-hidden="true" />
        </span>
        <span className="mt-1 text-sm font-semibold text-slate-600 group-hover:text-blue-700 dark:text-slate-300 dark:group-hover:text-blue-300">
          Add course
        </span>
        <span className="text-xs text-slate-400">Create a new course in your organization</span>
      </button>
    );
  }

  return (
    <button
      ref={buttonRef}
      type="button"
      onClick={onAdd}
      aria-label="Add a new course"
      className="group flex w-full flex-col items-center justify-center gap-2 border-t border-slate-200 px-5 py-12 text-center transition hover:bg-blue-50/50 dark:border-slate-800 dark:hover:bg-slate-900/40"
    >
      <span className="flex h-16 w-16 items-center justify-center rounded-2xl border-2 border-dashed border-slate-300 text-slate-400 transition group-hover:border-blue-400 group-hover:bg-white group-hover:text-blue-600 dark:border-slate-700 dark:group-hover:border-blue-500 dark:group-hover:bg-slate-900">
        <Plus size={36} strokeWidth={2} aria-hidden="true" />
      </span>
      <span className="mt-1 text-sm font-semibold text-slate-600 group-hover:text-blue-700 dark:text-slate-300 dark:group-hover:text-blue-300">
        Add course
      </span>
      <span className="text-xs text-slate-400">Create a course to organise its assignments</span>
    </button>
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
      <div className="theme-page-container space-y-6">
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
  const courseButtonRef = useRef<HTMLButtonElement | null>(null);

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

  const [showImportPanel, setShowImportPanel] = useState(false);
  const [importContent, setImportContent] = useState('');
  const [importDefaultPassword, setImportDefaultPassword] = useState('');
  const [importDefaultTenant, setImportDefaultTenant] = useState('');
  const [importPreview, setImportPreview] = useState<ImportReport | null>(null);
  const [importBusy, setImportBusy] = useState(false);
  const [importError, setImportError] = useState('');
  const [exportingUsers, setExportingUsers] = useState(false);

  const [coursesWithInstructors, setCoursesWithInstructors] = useState<CourseWithInstructors[]>([]);
  const [loadingCourses, setLoadingCourses] = useState(true);
  const [selectedProfessorForCourse, setSelectedProfessorForCourse] = useState<Record<string, string>>({});
  const [assigningCourse, setAssigningCourse] = useState<string | null>(null);
  const [expandedCourseIds, setExpandedCourseIds] = useState<Set<string>>(new Set());
  const [activeTab, setActiveTab] = useState<'users' | 'courses'>('users');
  const [courseQuery, setCourseQuery] = useState('');
  const [courseTermFilter, setCourseTermFilter] = useState('all');

  const [form, setForm] = useState({
    full_name: '',
    email: '',
    password: '',
    role: 'professor' as AuthRole,
    tenant_name: '',
  });
  const [showCourseModal, setShowCourseModal] = useState(false);
  const [courseSaving, setCourseSaving] = useState(false);
  const [courseError, setCourseError] = useState('');
  const [courseForm, setCourseForm] = useState({
    name: '',
    code: '',
    term: 'Fall',
    year: String(new Date().getFullYear()),
    department: '',
    description: '',
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

  const totalCourses = coursesWithInstructors.length;
  const totalAssignments = coursesWithInstructors.reduce(
    (sum, c) => sum + (c.assignment_count ?? c.assignments?.length ?? 0),
    0
  );

  const termOptions = useMemo(
    () => buildTermOptions(coursesWithInstructors),
    [coursesWithInstructors]
  );

  // Reset the term filter when the selected term no longer exists
  // (e.g. its last course was deleted or renamed).
  useEffect(() => {
    if (courseTermFilter === 'all') return;
    if (!termOptions.some((option) => option.value === courseTermFilter)) {
      setCourseTermFilter('all');
    }
  }, [termOptions, courseTermFilter]);

  const filteredCourses = useMemo(() => {
    const query = courseQuery.trim().toLowerCase();
    return coursesWithInstructors.filter((course) => {
      const matchesTerm =
        courseTermFilter === 'all' || courseTermLabel(course) === courseTermFilter;
      if (!matchesTerm) return false;
      if (!query) return true;
      const haystack = [
        course.name,
        course.code ?? '',
        course.department ?? '',
        course.organization_name ?? '',
        courseTermLabel(course),
        ...(course.instructors?.map((i) => i.full_name) ?? []),
      ]
        .join(' ')
        .toLowerCase();
      return haystack.includes(query);
    });
  }, [coursesWithInstructors, courseQuery, courseTermFilter]);

  // ── Handlers ──────────────────────────────────────────────────────────────────

  const openCreatePanel = () => {
    setSuccessMessage('');
    setFormError('');
    setShowCreatePanel(true);
  };

  const openCourseModal = () => {
    setCourseError('');
    setCourseForm({
      name: '',
      code: '',
      term: 'Fall',
      year: String(new Date().getFullYear()),
      department: '',
      description: '',
    });
    setShowCourseModal(true);
  };

  const closeCourseModal = () => {
    if (courseSaving) return;
    setShowCourseModal(false);
    setTimeout(() => courseButtonRef.current?.focus(), 0);
  };

  const handleCreateCourse = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setCourseError('');
    if (!courseForm.name.trim()) {
      setCourseError('Course name is required.');
      return;
    }
    setCourseSaving(true);
    try {
      await apiClient.post('/api/courses', {
        name: courseForm.name.trim(),
        code: courseForm.code.trim() || null,
        term: courseForm.term.trim() || null,
        year: courseForm.year ? Number(courseForm.year) : null,
        department: courseForm.department.trim() || null,
        description: courseForm.description.trim() || null,
      });
      await loadCoursesWithInstructors();
      setShowCourseModal(false);
      setSuccessMessage('Course created successfully.');
      setTimeout(() => courseButtonRef.current?.focus(), 0);
    } catch (error) {
      setCourseError(getErrorMessage(error));
    } finally {
      setCourseSaving(false);
    }
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

  const openImportPanel = () => {
    setImportError('');
    setImportPreview(null);
    setShowImportPanel(true);
  };

  const closeImportPanel = () => {
    setShowImportPanel(false);
    setImportPreview(null);
    setImportError('');
  };

  const handleExportUsers = async (format: 'csv' | 'json') => {
    setExportingUsers(true);
    setPageError('');
    try {
      const res = await apiClient.get('/api/admin/users/export', {
        params: { format },
        responseType: 'blob',
      });
      const url = URL.createObjectURL(res.data as Blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `users.${format}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      setPageError(getErrorMessage(error));
    } finally {
      setExportingUsers(false);
    }
  };

  const handleImportFile = async (file: File | null) => {
    if (!file) return;
    try {
      setImportContent(await file.text());
      setImportPreview(null);
      setImportError('');
    } catch {
      setImportError('Could not read that file.');
    }
  };

  const runImport = async (dryRun: boolean) => {
    if (!importContent.trim()) {
      setImportError('Paste CSV or JSON content, or choose a file first.');
      return;
    }
    setImportBusy(true);
    setImportError('');
    try {
      const res = await apiClient.post('/api/admin/users/import', {
        content: importContent,
        dry_run: dryRun,
        default_password: importDefaultPassword,
        default_tenant_name: importDefaultTenant,
      });
      const report = res.data as ImportReport;
      setImportPreview(report);
      if (!dryRun) {
        await loadUsers();
        setSuccessMessage(
          `Imported ${report.created} user(s) — ${report.skipped} skipped, ${report.failed} failed.`
        );
      }
    } catch (error) {
      setImportError(getErrorMessage(error));
    } finally {
      setImportBusy(false);
    }
  };

  const canImport = Boolean(importPreview && importPreview.previewed > 0);

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

  const toggleCourseAssignments = (courseId: string) => {
    setExpandedCourseIds((prev) => {
      const next = new Set(prev);
      if (next.has(courseId)) {
        next.delete(courseId);
      } else {
        next.add(courseId);
      }
      return next;
    });
  };

  // ── Early returns ─────────────────────────────────────────────────────────────

  if (!bootstrapped || authLoading || status === 'loading') {
    return <AuthPageSkeleton />;
  }

  // ── Render ────────────────────────────────────────────────────────────────────

  return (
    <DashboardLayout requiredRole="admin">
      <div className="theme-page-container space-y-6">

        {/* ── Header ──────────────────────────────────────────────────────────── */}
        <section className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-blue-600/10 bg-blue-600/[0.06] px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.2em] text-blue-600 dark:border-blue-400/20 dark:bg-blue-400/10 dark:text-blue-400">
                <Users size={14} />
                Administration
              </div>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight text-slate-900 dark:text-white">
                Users &amp; courses
              </h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600 dark:text-slate-400">
                Manage accounts and roles, control course access, and see which
                assignments belong to each course — all in one place.
              </p>
            </div>

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
        <section className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
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

          <div className="rounded-[24px] border border-blue-100 bg-white p-5 shadow-sm dark:border-blue-900/40 dark:bg-slate-950">
            <div className="flex items-center justify-between">
              <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">
                Courses
              </div>
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-blue-50 dark:bg-blue-900/30">
                <GraduationCap size={14} className="text-blue-600 dark:text-blue-400" />
              </div>
            </div>
            <div className="mt-3 text-3xl font-semibold text-blue-700 tabular-nums dark:text-blue-300">
              {totalCourses}
            </div>
          </div>

          <div className="rounded-[24px] border border-violet-100 bg-white p-5 shadow-sm dark:border-violet-900/40 dark:bg-slate-950">
            <div className="flex items-center justify-between">
              <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">
                Assignments
              </div>
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-violet-50 dark:bg-violet-900/30">
                <FileText size={14} className="text-violet-600 dark:text-violet-400" />
              </div>
            </div>
            <div className="mt-3 text-3xl font-semibold text-violet-700 tabular-nums dark:text-violet-300">
              {totalAssignments}
            </div>
          </div>
        </section>

        {/* ── Section tabs ──────────────────────────────────────────────────────── */}
        <div className="grid grid-cols-2 gap-2 rounded-2xl border border-slate-200 bg-slate-50 p-1 dark:border-slate-800 dark:bg-slate-900">
          <button
            type="button"
            onClick={() => setActiveTab('users')}
            aria-pressed={activeTab === 'users'}
            className={`inline-flex h-10 items-center justify-center gap-2 rounded-xl px-4 text-sm font-semibold transition ${activeTab === 'users'
                ? 'bg-white text-slate-900 shadow-sm dark:bg-slate-800 dark:text-white'
                : 'text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800'}`}
          >
            <Users size={15} />
            Users
            <span className="ml-0.5 rounded-full bg-slate-200 px-1.5 text-[11px] font-bold tabular-nums text-slate-600 dark:bg-slate-800 dark:text-slate-300">
              {totalUsers}
            </span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('courses')}
            aria-pressed={activeTab === 'courses'}
            className={`inline-flex h-10 items-center justify-center gap-2 rounded-xl px-4 text-sm font-semibold transition ${activeTab === 'courses'
                ? 'bg-white text-slate-900 shadow-sm dark:bg-slate-800 dark:text-white'
                : 'text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800'}`}
          >
            <GraduationCap size={15} />
            Courses &amp; assignments
            <span className="ml-0.5 rounded-full bg-slate-200 px-1.5 text-[11px] font-bold tabular-nums text-slate-600 dark:bg-slate-800 dark:text-slate-300">
              {totalCourses}
            </span>
          </button>
        </div>

        {/* ── Users table ─────────────────────────────────────────────────────── */}
        {activeTab === 'users' && (
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

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => handleExportUsers('csv')}
                  disabled={exportingUsers}
                  className="inline-flex h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
                >
                  {exportingUsers ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
                  Export
                </button>
                <button
                  type="button"
                  onClick={openImportPanel}
                  className="inline-flex h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
                >
                  <Upload size={14} />
                  Import
                </button>
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
                No accounts match your current filters. Try a different search, or add a user below.
              </p>
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

          {!loadingUsers && (
            <AddUserCard onAdd={openCreatePanel} buttonRef={createButtonRef} />
          )}
        </section>
        )}

        {/* ── Course & Instructor Assignments ─────────────────────────────────── */}
        {activeTab === 'courses' && (
        <section className="overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
          <div className="flex flex-col gap-4 border-b border-slate-200 px-6 py-5 dark:border-slate-800 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-blue-600/10 bg-blue-600/[0.06] px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.2em] text-blue-600 dark:border-blue-400/20 dark:bg-blue-400/10 dark:text-blue-400">
                <GraduationCap size={14} />
                Courses
              </div>
              <h2 className="mt-3 text-xl font-semibold text-slate-900 dark:text-white">
                Courses &amp; assignments
              </h2>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                Manage course access and see which assignments belong to each course.
              </p>
            </div>

            <div className="flex flex-col gap-2 sm:items-end">
              <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
                <div className="relative w-full sm:w-[280px]">
                  <Search
                    size={15}
                    className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                  />
                  <input
                    type="search"
                    value={courseQuery}
                    onChange={(e) => setCourseQuery(e.target.value)}
                    placeholder="Search courses, codes, professors…"
                    aria-label="Search courses"
                    className="h-10 w-full rounded-xl border border-slate-200 bg-white pl-9 pr-4 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white dark:placeholder:text-slate-500"
                  />
                </div>
                {termOptions.length > 1 && (
                  <div className="relative w-full sm:w-[190px]">
                    <select
                      value={courseTermFilter}
                      onChange={(e) => setCourseTermFilter(e.target.value)}
                      aria-label="Filter courses by term"
                      className="h-10 w-full appearance-none rounded-xl border border-slate-200 bg-white px-3 pr-8 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white"
                    >
                      <option value="all">All terms</option>
                      {termOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.value} ({option.count})
                        </option>
                      ))}
                    </select>
                    <ChevronDown
                      size={13}
                      className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400"
                    />
                  </div>
                )}
              </div>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                {filteredCourses.length === totalCourses
                  ? `${totalCourses} course${totalCourses !== 1 ? 's' : ''} · ${totalAssignments} assignment${totalAssignments !== 1 ? 's' : ''}`
                  : `${filteredCourses.length} of ${totalCourses} courses`}
              </p>
            </div>
          </div>

          {loadingCourses ? (
            <div className="grid gap-4 p-5 md:grid-cols-2 xl:grid-cols-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="rounded-3xl border border-slate-200 p-5 dark:border-slate-800">
                  <div className="flex items-center justify-between">
                    <div className="h-4 w-20 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
                    <div className="h-4 w-16 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
                  </div>
                  <div className="mt-3 h-5 w-40 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
                  <div className="mt-4 h-9 w-full animate-pulse rounded-2xl bg-slate-200 dark:bg-slate-800" />
                  <div className="mt-3 h-9 w-full animate-pulse rounded-2xl bg-slate-200 dark:bg-slate-800" />
                </div>
              ))}
            </div>
          ) : totalCourses === 0 ? (
            <div className="p-5">
              <AddCourseCard onAdd={openCourseModal} buttonRef={courseButtonRef} variant="grid" />
            </div>
          ) : filteredCourses.length === 0 ? (
            <div className="px-6 py-16 text-center">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-slate-100 dark:bg-slate-900">
                <Search size={22} className="text-slate-500 dark:text-slate-400" />
              </div>
              <h3 className="mt-4 text-base font-semibold text-slate-900 dark:text-white">
                {courseQuery || courseTermFilter !== 'all'
                  ? 'No courses match your filters'
                  : 'No courses match your search'}
              </h3>
              <p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-slate-500 dark:text-slate-400">
                Try a different course name, code, term, department, organization, or professor.
              </p>
            </div>
          ) : (
            <div className="grid gap-4 p-5 md:grid-cols-2 xl:grid-cols-3">
              {filteredCourses.map((course) => {
                const professors = users.filter((u) => u.role === 'professor' || u.role === 'admin');
                const currentInstructorIds = course.instructors.map((i) => i.id);
                const availableProfessors = professors.filter((p) => !currentInstructorIds.includes(p.id));
                const isAssigning = assigningCourse === course.id;
                const assignmentCount = course.assignment_count ?? course.assignments?.length ?? 0;
                const isAssignmentsOpen = expandedCourseIds.has(course.id);

                return (
                  <article
                    key={course.id}
                    className="flex flex-col rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950"
                  >
                    {/* Course header */}
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          {course.code && (
                            <span className="rounded-md bg-slate-100 px-2 py-0.5 font-mono text-xs font-semibold text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                              {course.code}
                            </span>
                          )}
                        </div>
                        <h3 className="mt-2 text-base font-semibold leading-6 text-slate-900 dark:text-white">
                          {course.name}
                        </h3>
                      </div>
                    </div>

                    {/* Professors */}
                    <div className="mt-4 rounded-2xl bg-slate-50 p-3 dark:bg-slate-900/70">
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
                          Professors
                        </span>
                        <span className="rounded-full bg-white px-2 py-0.5 text-[11px] font-bold tabular-nums text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                          {course.instructors.length}
                        </span>
                      </div>

                      <div className="mt-2.5">
                        {course.instructors.length === 0 ? (
                          <p className="text-[11px] leading-5 text-slate-400 dark:text-slate-500">
                            No instructors assigned yet
                          </p>
                        ) : (
                          <div className="flex flex-wrap gap-2">
                            {course.instructors.map((inst) => (
                              <div
                                key={inst.id}
                                title={inst.email}
                                className="group inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white py-1 pl-1 pr-1.5 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300"
                              >
                                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-100 text-[10px] font-bold text-blue-700 dark:bg-blue-500/15 dark:text-blue-300">
                                  {initialsOf(inst.full_name)}
                                </span>
                                <span className="max-w-[9rem] truncate">{inst.full_name}</span>
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

                      {/* Assign a professor */}
                      {availableProfessors.length > 0 ? (
                        <div className="mt-3 flex items-center gap-2">
                          <div className="relative min-w-0 flex-1">
                            <select
                              value={selectedProfessorForCourse[course.id] || ''}
                              onChange={(e) =>
                                setSelectedProfessorForCourse((prev) => ({ ...prev, [course.id]: e.target.value }))
                              }
                              aria-label={`Choose a professor for ${course.name}`}
                              className="h-10 w-full appearance-none rounded-xl border border-slate-200 bg-white pl-3 pr-8 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-950 dark:text-white"
                            >
                              <option value="">Choose professor…</option>
                              {availableProfessors.map((p) => (
                                <option key={p.id} value={p.id}>
                                  {p.full_name}
                                </option>
                              ))}
                            </select>
                            <ChevronDown
                              size={13}
                              className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400"
                            />
                          </div>
                          <button
                            type="button"
                            disabled={!selectedProfessorForCourse[course.id] || isAssigning}
                            onClick={() => {
                              const uid = selectedProfessorForCourse[course.id];
                              if (uid) assignInstructor(course.id, uid);
                            }}
                            className="inline-flex h-10 shrink-0 items-center gap-1.5 rounded-xl bg-blue-600 px-4 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            {isAssigning ? <Loader2 size={13} className="animate-spin" /> : <UserPlus size={13} />}
                            Assign
                          </button>
                        </div>
                      ) : (
                        <p className="mt-3 text-xs leading-5 text-slate-400 dark:text-slate-500">
                          No other professor accounts available to assign.
                        </p>
                      )}
                    </div>

                    {/* Assignments */}
                    <div className="mt-auto pt-4">
                      <button
                        type="button"
                        onClick={() => toggleCourseAssignments(course.id)}
                        aria-expanded={isAssignmentsOpen}
                        className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-3 py-2.5 text-left transition hover:border-blue-300 hover:bg-blue-50/50 dark:border-slate-800 dark:hover:border-blue-500/40 dark:hover:bg-blue-500/5"
                      >
                        <span className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-600 dark:text-slate-300">
                          <FileText size={13} className="text-violet-500 dark:text-violet-400" />
                          Assignments
                          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-bold tabular-nums text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                            {assignmentCount}
                          </span>
                        </span>
                        <ChevronDown
                          size={15}
                          className={`text-slate-400 transition-transform ${isAssignmentsOpen ? 'rotate-180' : ''}`}
                        />
                      </button>

                      {isAssignmentsOpen && (
                        <div className="mt-3">
                          {course.assignments && course.assignments.length > 0 ? (
                            <ul className="space-y-2">
                              {course.assignments.map((assignment) => (
                                <li
                                  key={assignment.id}
                                  className="flex items-start gap-3 rounded-2xl border border-slate-100 bg-slate-50 px-3 py-2.5 dark:border-slate-800/70 dark:bg-slate-900/70"
                                >
                                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-white text-slate-500 shadow-sm dark:bg-slate-800 dark:text-slate-400">
                                    <FileText size={12} />
                                  </div>
                                  <div className="min-w-0 flex-1">
                                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                                      <span className="truncate text-sm font-medium text-slate-800 dark:text-slate-100">
                                        {assignment.name}
                                      </span>
                                      {assignment.assignment_type && (
                                        <span className="rounded-md bg-violet-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-violet-700 dark:bg-violet-500/15 dark:text-violet-300">
                                          {assignment.assignment_type.replace(/_/g, ' ')}
                                        </span>
                                      )}
                                    </div>
                                    {assignment.recommended_mode?.mode_id && (
                                      <p className="mt-1 flex flex-wrap items-center gap-x-1.5 gap-y-1 text-[11px] leading-4 text-slate-500 dark:text-slate-400">
                                        <Zap
                                          size={11}
                                          className="shrink-0 text-amber-500 dark:text-amber-400"
                                        />
                                        <span className="font-semibold text-slate-600 dark:text-slate-300">
                                          Suggested: {assignment.recommended_mode.mode_name}
                                        </span>
                                        {(assignment.recommended_mode.top_engines ?? []).length > 0 && (
                                          <span>
                                            ·{' '}
                                            {(assignment.recommended_mode.top_engines ?? [])
                                              .map((engine) => engineLabel(engine.key))
                                              .join(' · ')}
                                          </span>
                                        )}
                                      </p>
                                    )}
                                  </div>
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <div className="rounded-2xl bg-slate-50 px-4 py-6 text-center text-xs leading-5 text-slate-500 dark:bg-slate-900/70 dark:text-slate-400">
                              No assignments have been created for this course yet.
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </article>
                );
              })}
              <AddCourseCard onAdd={openCourseModal} buttonRef={courseButtonRef} variant="grid" />
            </div>
          )}
        </section>
        )}

      </div>

      <Modal
        open={showCourseModal}
        title="Create a new course"
        description="Add a course to your organization. You can assign instructors and create assignments after it is created."
        onClose={closeCourseModal}
      >
        <form onSubmit={handleCreateCourse} className="space-y-4">
          {courseError && (
            <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300">
              <AlertTriangle size={15} className="mt-0.5 shrink-0" />
              <span>{courseError}</span>
            </div>
          )}
          <Field label="Course name">
            <input
              required
              autoFocus
              value={courseForm.name}
              onChange={(e) => setCourseForm((c) => ({ ...c, name: e.target.value }))}
              placeholder="Introduction to Computer Science"
              className={inputClass}
            />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Course code" hint="Optional">
              <input
                value={courseForm.code}
                onChange={(e) => setCourseForm((c) => ({ ...c, code: e.target.value }))}
                placeholder="CS 101"
                className={inputClass}
              />
            </Field>
            <Field label="Department" hint="Optional">
              <input
                value={courseForm.department}
                onChange={(e) => setCourseForm((c) => ({ ...c, department: e.target.value }))}
                placeholder="Computer Science"
                className={inputClass}
              />
            </Field>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Term">
              <div className="relative">
                <select
                  value={courseForm.term}
                  onChange={(e) => setCourseForm((c) => ({ ...c, term: e.target.value }))}
                  className={selectClass}
                >
                  <option>Fall</option>
                  <option>Winter</option>
                  <option>Spring</option>
                  <option>Summer</option>
                </select>
                <ChevronDown size={14} className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-slate-400" />
              </div>
            </Field>
            <Field label="Year">
              <input
                type="number"
                min="1900"
                max="2200"
                value={courseForm.year}
                onChange={(e) => setCourseForm((c) => ({ ...c, year: e.target.value }))}
                className={inputClass}
              />
            </Field>
          </div>
          <Field label="Description" hint="Optional">
            <textarea
              rows={3}
              value={courseForm.description}
              onChange={(e) => setCourseForm((c) => ({ ...c, description: e.target.value }))}
              placeholder="A short description of this course"
              className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white"
            />
          </Field>
          <div className="flex justify-end gap-2 border-t border-slate-200 pt-4 dark:border-slate-800">
            <button
              type="button"
              onClick={closeCourseModal}
              disabled={courseSaving}
              className="inline-flex h-10 items-center rounded-xl px-4 text-sm font-medium text-slate-600 transition hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-900"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={courseSaving}
              className="inline-flex h-10 items-center gap-2 rounded-xl bg-slate-950 px-4 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:opacity-60 dark:bg-white dark:text-slate-950"
            >
              {courseSaving && <Loader2 size={15} className="animate-spin" />}
              {courseSaving ? 'Creating…' : 'Create course'}
            </button>
          </div>
        </form>
      </Modal>

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

      {/* ── Import users modal ────────────────────────────────────────────────── */}
      <Modal
        open={showImportPanel}
        title="Import users"
        description="Bulk-create accounts from a CSV or JSON file."
        onClose={closeImportPanel}
        footer={(
          <>
            <button
              type="button"
              onClick={closeImportPanel}
              className="inline-flex h-10 items-center justify-center rounded-xl border border-slate-200 px-4 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 dark:border-slate-800 dark:text-slate-200 dark:hover:bg-slate-900"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => runImport(true)}
              disabled={importBusy}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-slate-200 px-4 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-800 dark:text-slate-200 dark:hover:bg-slate-900"
            >
              {importBusy ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
              Preview
            </button>
            <button
              type="button"
              onClick={() => runImport(false)}
              disabled={importBusy || !canImport}
              className="theme-button-primary inline-flex h-10 items-center justify-center gap-2 rounded-xl px-4 text-sm font-semibold transition disabled:opacity-50"
            >
              {importBusy ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
              Import
            </button>
          </>
        )}
      >
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Default password" hint="Used for rows without their own password.">
              <input
                type="password"
                value={importDefaultPassword}
                onChange={(e) => setImportDefaultPassword(e.target.value)}
                placeholder="Leave blank to auto-generate"
                className={inputClass}
              />
            </Field>
            <Field label="Default workspace" hint="Share one workspace across every imported row.">
              <input
                type="text"
                value={importDefaultTenant}
                onChange={(e) => setImportDefaultTenant(e.target.value)}
                placeholder="Optional"
                className={inputClass}
              />
            </Field>
          </div>

          <Field label="Choose a file" hint="CSV columns: email, full_name, role, password, tenant_name.">
            <input
              type="file"
              accept=".csv,.json,text/csv,application/json"
              onChange={(e) => handleImportFile(e.target.files?.[0] ?? null)}
              className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-xl file:border-0 file:bg-slate-100 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-slate-700 hover:file:bg-slate-200 dark:text-slate-300 dark:file:bg-slate-800 dark:file:text-slate-200"
            />
          </Field>

          <Field label="Or paste content" hint="CSV, or JSON as a list or an object with a 'users' list.">
            <textarea
              value={importContent}
              onChange={(e) => { setImportContent(e.target.value); setImportPreview(null); }}
              rows={6}
              placeholder={'email,full_name,role\nada@example.edu,Ada Lovelace,professor'}
              className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 font-mono text-xs text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white"
            />
          </Field>

          {importError && (
            <div className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300">
              <AlertTriangle size={16} className="mt-0.5 shrink-0" />
              <span>{importError}</span>
            </div>
          )}

          {importPreview && (
            <div className="space-y-3 rounded-2xl border border-slate-200 p-4 dark:border-slate-800">
              <div className="flex flex-wrap gap-2 text-xs font-semibold">
                <span className="rounded-full bg-emerald-100 px-2.5 py-1 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300">
                  {importPreview.dry_run
                    ? `${importPreview.previewed} ready`
                    : `${importPreview.created} created`}
                </span>
                <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                  {importPreview.skipped} skipped
                </span>
                <span className="rounded-full bg-red-100 px-2.5 py-1 text-red-700 dark:bg-red-500/15 dark:text-red-300">
                  {importPreview.failed} failed
                </span>
              </div>

              <div className="max-h-56 space-y-1.5 overflow-y-auto">
                {importPreview.results.slice(0, 50).map((row) => (
                  <div
                    key={`${row.row}-${row.email}`}
                    className="flex items-start gap-2 rounded-xl bg-slate-50 px-3 py-2 text-xs dark:bg-slate-900/60"
                  >
                    <span className="mt-0.5 shrink-0 font-mono text-[11px] text-slate-400">
                      #{row.row}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium text-slate-700 dark:text-slate-200">
                        {row.email || '(no email)'}
                      </span>
                      <span
                        className={
                          row.status === 'error'
                            ? 'text-red-600 dark:text-red-400'
                            : row.status === 'skipped'
                              ? 'text-amber-600 dark:text-amber-400'
                              : 'text-slate-500 dark:text-slate-400'
                        }
                      >
                        {row.detail}
                      </span>
                      {row.temporary_password && (
                        <span className="mt-0.5 block font-mono text-[11px] text-slate-500 dark:text-slate-400">
                          Temp password: {row.temporary_password}
                        </span>
                      )}
                    </span>
                  </div>
                ))}
              </div>

              {importPreview.results.length > 50 && (
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Showing the first 50 of {importPreview.results.length} rows.
                </p>
              )}

              {importPreview.results.some((row) => row.temporary_password) && (
                <p className="text-xs text-amber-700 dark:text-amber-300">
                  Temporary passwords are shown once — copy them before closing this dialog.
                </p>
              )}
            </div>
          )}
        </div>
      </Modal>
    </DashboardLayout>
  );
}
