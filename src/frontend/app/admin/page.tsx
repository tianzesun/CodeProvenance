'use client';

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  Calendar,
  CheckCircle2,
  ChevronDown,
  Download,
  FileText,
  GraduationCap,
  Loader2,
  Pencil,
  Plus,
  Search,
  ShieldCheck,
  Trash2,
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

/** Turn a timestamp into a friendly relative label ("3 days ago"). */
function relativeTime(value: string | null): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;

  const minutes = Math.round((Date.now() - date.getTime()) / 60000);
  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? '' : 's'} ago`;

  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`;

  const days = Math.round(hours / 24);
  if (days < 30) return `${days} day${days === 1 ? '' : 's'} ago`;

  const months = Math.round(days / 30);
  if (months < 12) return `${months} month${months === 1 ? '' : 's'} ago`;

  const years = Math.round(months / 12);
  return `${years} year${years === 1 ? '' : 's'} ago`;
}

/** Background/text classes for an avatar by role. */
const AVATAR_TONES: Record<AuthRole, string> = {
  admin: 'bg-violet-100 text-violet-700 dark:bg-violet-500/20 dark:text-violet-300',
  professor: 'bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-300',
};

/** Initials avatar used across the users table and course cards. */
function Avatar({
  name,
  role = 'professor',
  size = 36,
  title,
}: {
  name: string;
  role?: AuthRole;
  size?: number;
  title?: string;
}) {
  return (
    <span
      title={title ?? name}
      style={{ width: size, height: size, fontSize: Math.round(size * 0.36) }}
      className={`inline-flex shrink-0 select-none items-center justify-center rounded-full font-bold leading-none ${AVATAR_TONES[role]}`}
    >
      {initialsOf(name)}
    </span>
  );
}

/** Tone palettes for KPI cards. */
const STAT_TONES: Record<string, { border: string; icon: string; value: string }> = {
  slate: {
    border: 'border-slate-200 dark:border-slate-800',
    icon: 'bg-slate-100 text-slate-600 dark:bg-slate-900 dark:text-slate-400',
    value: 'text-slate-900 dark:text-white',
  },
  emerald: {
    border: 'border-emerald-100 dark:border-emerald-900/40',
    icon: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400',
    value: 'text-emerald-700 dark:text-emerald-300',
  },
  amber: {
    border: 'border-amber-100 dark:border-amber-900/40',
    icon: 'bg-amber-50 text-amber-600 dark:bg-amber-900/30 dark:text-amber-400',
    value: 'text-amber-700 dark:text-amber-300',
  },
  blue: {
    border: 'border-blue-100 dark:border-blue-900/40',
    icon: 'bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400',
    value: 'text-blue-700 dark:text-blue-300',
  },
  violet: {
    border: 'border-violet-100 dark:border-violet-900/40',
    icon: 'bg-violet-50 text-violet-600 dark:bg-violet-900/30 dark:text-violet-400',
    value: 'text-violet-700 dark:text-violet-300',
  },
  sky: {
    border: 'border-sky-100 dark:border-sky-900/40',
    icon: 'bg-sky-50 text-sky-600 dark:bg-sky-900/30 dark:text-sky-400',
    value: 'text-sky-700 dark:text-sky-300',
  },
};

/**
 * One KPI in the header strip. Clicking it opens the tab the number describes,
 * so the card doubles as navigation.
 */
function StatCard({
  label,
  value,
  hint,
  icon,
  tone,
  onClick,
  active,
}: {
  label: string;
  value: number | string;
  hint: string;
  icon: React.ReactNode;
  tone: keyof typeof STAT_TONES;
  onClick: () => void;
  active: boolean;
}) {
  const palette = STAT_TONES[tone] ?? STAT_TONES.slate;
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`group relative overflow-hidden rounded-[24px] border bg-white p-5 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-md dark:bg-slate-950 ${palette.border} ${
        active ? 'ring-2 ring-blue-500/40' : 'ring-0'
      }`}
    >
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">
          {label}
        </span>
        <span className={`flex h-8 w-8 items-center justify-center rounded-xl transition group-hover:scale-110 ${palette.icon}`}>
          {icon}
        </span>
      </div>
      <div className={`mt-3 text-3xl font-semibold tabular-nums ${palette.value}`}>{value}</div>
      <div className="mt-1 truncate text-xs text-slate-500 dark:text-slate-400">{hint}</div>
    </button>
  );
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
  term_id?: string | null;
  department?: string | null;
  description?: string | null;
  organization_name?: string;
  instructors: CourseInstructor[];
  assignment_count?: number;
  assignments?: CourseAssignment[];
}

type ImportRowStatus = 'created' | 'preview' | 'skipped' | 'error';

/** Assignments reported by the admin payload, falling back to the loaded list. */
function courseAssignmentCount(course: CourseWithInstructors): number {
  return course.assignment_count ?? course.assignments?.length ?? 0;
}

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

/** One entry of the organization's term registry (see GET /api/terms). */
interface AdminTerm {
  id: string;
  name: string;
  year: number;
  /** Server-rendered "Fall 2026" display label. */
  label: string;
  description?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  course_count: number;
  created_at: string;
}

/** Season names offered by the registry's term-name dropdown. */
const TERM_NAMES: readonly string[] = ['Fall', 'Winter', 'Spring', 'Summer'];

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
        className="group relative flex min-h-[240px] w-full flex-col items-center justify-center rounded-3xl bg-white dark:bg-slate-900 transition hover:bg-blue-50/30 dark:hover:bg-slate-800/50"
      >
        {/* Card border */}
        <div className="absolute inset-0 rounded-3xl border-2 border-slate-200 dark:border-slate-700 group-hover:border-blue-400 group-hover:dark:border-blue-500 transition-colors" />

        {/* Icon container */}
        <div className="relative z-10 flex h-24 w-24 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-500/10 dark:to-indigo-500/10 group-hover:from-blue-100 group-hover:to-indigo-100 dark:group-hover:from-blue-500/20 dark:group-hover:to-indigo-500/20 transition-colors shadow-sm group-hover:shadow-md">
          <Plus size={48} className="text-blue-500 dark:text-blue-400 transition-transform group-hover:scale-110 group-hover:text-blue-600 dark:group-hover:text-blue-300" />
        </div>

        {/* Text content */}
        <div className="relative z-10 mt-6 flex flex-col items-center gap-2 px-6">
          <span className="text-lg font-semibold text-slate-700 dark:text-slate-200 transition-colors group-hover:text-blue-700 dark:group-hover:text-blue-300">
            Add Course
          </span>
          <span className="text-xs text-slate-500 dark:text-slate-400 text-center max-w-[220px]">
            Create a new course to organize assignments
          </span>
        </div>

        {/* Subtle glow effect on hover */}
        <div className="absolute inset-0 rounded-3xl bg-blue-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
      </button>
    );
  }

  return (
    <button
      ref={buttonRef}
      type="button"
      onClick={onAdd}
      aria-label="Add a new course"
      className="group relative flex w-full flex-col items-center justify-center rounded-xl bg-white dark:bg-slate-900 px-5 py-10 transition hover:bg-blue-50/30 dark:hover:bg-slate-800/50"
    >
      {/* Card border */}
      <div className="absolute inset-0 rounded-xl border-2 border-slate-200 dark:border-slate-700 group-hover:border-blue-400 group-hover:dark:border-blue-500 transition-colors" />

      {/* Icon container */}
      <div className="relative z-10 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-500/10 dark:to-indigo-500/10 group-hover:from-blue-100 group-hover:to-indigo-100 dark:group-hover:from-blue-500/20 dark:group-hover:to-indigo-500/20 transition-colors shadow-sm group-hover:shadow-md">
        <Plus size={36} className="text-blue-500 dark:text-blue-400 transition-transform group-hover:scale-110 group-hover:text-blue-600 dark:group-hover:text-blue-300" />
      </div>

      {/* Text content */}
      <div className="relative z-10 mt-3 flex flex-col items-center gap-1">
        <span className="text-sm font-semibold text-slate-700 dark:text-slate-200 transition-colors group-hover:text-blue-700 dark:group-hover:text-blue-300">
          Add Course
        </span>
        <span className="text-xs text-slate-500 dark:text-slate-400">
          Create a course to organize its assignments
        </span>
      </div>

      {/* Subtle glow effect on hover */}
      <div className="absolute inset-0 rounded-xl bg-blue-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
    </button>
  );
}

function AddTermCard({
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
      aria-label="Add a new academic term"
      className="group relative flex min-h-[200px] w-full flex-col items-center justify-center rounded-3xl bg-white dark:bg-slate-900 transition hover:bg-blue-50/30 dark:hover:bg-slate-800/50"
    >
      {/* Card border */}
      <div className="absolute inset-0 rounded-3xl border-2 border-slate-200 dark:border-slate-700 group-hover:border-blue-400 group-hover:dark:border-blue-500 transition-colors" />

      {/* Icon container */}
      <div className="relative z-10 flex h-20 w-20 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-500/10 dark:to-indigo-500/10 group-hover:from-blue-100 group-hover:to-indigo-100 dark:group-hover:from-blue-500/20 dark:group-hover:to-indigo-500/20 transition-colors shadow-sm group-hover:shadow-md">
        <Plus size={40} className="text-blue-500 dark:text-blue-400 transition-transform group-hover:scale-110 group-hover:text-blue-600 dark:group-hover:text-blue-300" />
      </div>

      {/* Text content */}
      <div className="relative z-10 mt-6 flex flex-col items-center gap-2 px-6">
        <span className="text-lg font-semibold text-slate-700 dark:text-slate-200 transition-colors group-hover:text-blue-700 dark:group-hover:text-blue-300">
          Add Term
        </span>
        <span className="text-xs text-slate-500 dark:text-slate-400 text-center max-w-[200px]">
          Create a new academic term (Fall 2026, etc.)
        </span>
      </div>

      {/* Subtle glow effect on hover */}
      <div className="absolute inset-0 rounded-3xl bg-blue-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
    </button>
  );
}

/** Season accent palette so every term card has its own identity at a glance. */
interface TermAccent {
  /** Status chip colors. */
  chip: string;
  /** Small status dot. */
  dot: string;
  /** Top edge gradient. */
  bar: string;
  /** Soft wash behind the card header. */
  wash: string;
  /** Season label text colors. */
  text: string;
}

const TERM_ACCENTS: Record<string, TermAccent> = {
  fall: {
    chip: 'bg-amber-100 text-amber-700 ring-amber-200 dark:bg-amber-500/15 dark:text-amber-300 dark:ring-amber-500/25',
    dot: 'bg-amber-500',
    bar: 'bg-gradient-to-r from-amber-500 via-orange-500 to-rose-500',
    wash: 'bg-gradient-to-br from-amber-500/12 via-transparent to-transparent',
    text: 'text-amber-600 dark:text-amber-300',
  },
  winter: {
    chip: 'bg-sky-100 text-sky-700 ring-sky-200 dark:bg-sky-500/15 dark:text-sky-300 dark:ring-sky-500/25',
    dot: 'bg-sky-500',
    bar: 'bg-gradient-to-r from-sky-500 via-cyan-500 to-blue-500',
    wash: 'bg-gradient-to-br from-sky-500/12 via-transparent to-transparent',
    text: 'text-sky-600 dark:text-sky-300',
  },
  spring: {
    chip: 'bg-emerald-100 text-emerald-700 ring-emerald-200 dark:bg-emerald-500/15 dark:text-emerald-300 dark:ring-emerald-500/25',
    dot: 'bg-emerald-500',
    bar: 'bg-gradient-to-r from-emerald-500 via-teal-500 to-green-500',
    wash: 'bg-gradient-to-br from-emerald-500/12 via-transparent to-transparent',
    text: 'text-emerald-600 dark:text-emerald-300',
  },
  summer: {
    chip: 'bg-violet-100 text-violet-700 ring-violet-200 dark:bg-violet-500/15 dark:text-violet-300 dark:ring-violet-500/25',
    dot: 'bg-violet-500',
    bar: 'bg-gradient-to-r from-violet-500 via-fuchsia-500 to-purple-500',
    wash: 'bg-gradient-to-br from-violet-500/12 via-transparent to-transparent',
    text: 'text-violet-600 dark:text-violet-300',
  },
};

/** Neutral accent for term names that are not one of the four seasons. */
const DEFAULT_TERM_ACCENT: TermAccent = {
  chip: 'bg-blue-100 text-blue-700 ring-blue-200 dark:bg-blue-500/15 dark:text-blue-300 dark:ring-blue-500/25',
  dot: 'bg-blue-500',
  bar: 'bg-gradient-to-r from-blue-500 via-indigo-500 to-slate-500',
  wash: 'bg-gradient-to-br from-blue-500/12 via-transparent to-transparent',
  text: 'text-blue-600 dark:text-blue-300',
};

/** Accent palette shared by course cards, keyed off a stable string hash. */
interface CourseAccent {
  bar: string;
  wash: string;
  text: string;
}

const COURSE_ACCENTS: CourseAccent[] = [
  {
    bar: 'bg-gradient-to-r from-blue-500 via-indigo-500 to-slate-400',
    wash: 'bg-gradient-to-br from-blue-500/12 via-transparent to-transparent',
    text: 'text-blue-600 dark:text-blue-300',
  },
  {
    bar: 'bg-gradient-to-r from-violet-500 via-fuchsia-500 to-purple-400',
    wash: 'bg-gradient-to-br from-violet-500/12 via-transparent to-transparent',
    text: 'text-violet-600 dark:text-violet-300',
  },
  {
    bar: 'bg-gradient-to-r from-emerald-500 via-teal-500 to-green-400',
    wash: 'bg-gradient-to-br from-emerald-500/12 via-transparent to-transparent',
    text: 'text-emerald-600 dark:text-emerald-300',
  },
  {
    bar: 'bg-gradient-to-r from-amber-500 via-orange-500 to-rose-400',
    wash: 'bg-gradient-to-br from-amber-500/12 via-transparent to-transparent',
    text: 'text-amber-600 dark:text-amber-300',
  },
  {
    bar: 'bg-gradient-to-r from-sky-500 via-cyan-500 to-blue-400',
    wash: 'bg-gradient-to-br from-sky-500/12 via-transparent to-transparent',
    text: 'text-sky-600 dark:text-sky-300',
  },
  {
    bar: 'bg-gradient-to-r from-rose-500 via-pink-500 to-fuchsia-400',
    wash: 'bg-gradient-to-br from-rose-500/12 via-transparent to-transparent',
    text: 'text-rose-600 dark:text-rose-300',
  },
];

/**
 * Pick a stable accent for a course from its department (or code/name), so
 * departments read as a group without anyone having to configure colours.
 */
function courseAccent(seed: string): CourseAccent {
  let hash = 0;
  for (const character of seed.trim().toLowerCase()) {
    hash = (hash * 31 + character.charCodeAt(0)) >>> 0;
  }
  return COURSE_ACCENTS[hash % COURSE_ACCENTS.length];
}

/**
 * Approximate season windows (``[monthIndex, day]`` pairs) used only when a
 * term has no stored dates, so status and progress can still be shown.
 */
const SEASON_WINDOWS: Record<string, [[number, number], [number, number]]> = {
  winter: [[0, 5], [3, 30]],
  spring: [[2, 20], [5, 10]],
  summer: [[4, 20], [7, 15]],
  fall: [[7, 15], [11, 20]],
};

/** Resolve the accent palette for a term by season name. */
function termAccent(name: string): TermAccent {
  return TERM_ACCENTS[name.trim().toLowerCase()] ?? DEFAULT_TERM_ACCENT;
}

/** Parse a ``YYYY-MM-DD`` string into a local date, or ``null`` when unset. */
function parseTermDate(value?: string | null): Date | null {
  if (!value) return null;
  const [year, month, day] = value.slice(0, 10).split('-').map(Number);
  if (!year || !month || !day) return null;
  const parsed = new Date(year, month - 1, day);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

/** Build an estimated window from a season name and year (month is 0-based). */
function approximateTermWindow(name: string, year: number): { start: Date; end: Date } | null {
  const window = SEASON_WINDOWS[name.trim().toLowerCase()];
  if (!window || !year) return null;
  const [[startMonth, startDay], [endMonth, endDay]] = window;
  const start = new Date(year, startMonth, startDay);
  const end = new Date(year, endMonth, endDay);
  return end > start ? { start, end } : null;
}

/** Status of a term relative to today, plus the window it was derived from. */
interface TermStatus {
  label: string;
  /** True when the term stores no dates and the window is season-estimated. */
  estimated: boolean;
  start: Date | null;
  end: Date | null;
  /** Percent through the window, ``null`` when no window could be derived. */
  progress: number | null;
}

/** Compute a term's status, timeline window and progress percentage. */
function termStatus(term: AdminTerm, now: Date): TermStatus {
  const storedStart = parseTermDate(term.start_date);
  const storedEnd = parseTermDate(term.end_date);
  const hasBothDates = Boolean(storedStart && storedEnd);
  const hasAnyDate = Boolean(storedStart || storedEnd);

  if (hasBothDates && storedStart && storedEnd) {
    const span = storedEnd.getTime() - storedStart.getTime();
    const raw = span > 0 ? ((now.getTime() - storedStart.getTime()) / span) * 100 : 100;
    const label = now < storedStart ? 'Upcoming' : now > storedEnd ? 'Completed' : 'In session';
    return {
      label,
      estimated: false,
      start: storedStart,
      end: storedEnd,
      progress: Math.min(100, Math.max(0, raw)),
    };
  }

  // Partial or missing dates: estimate the window from the season so the card
  // can still say whether the term is running, but only show the timeline when
  // the term stores no dates at all (a partial range is surfaced as-is).
  const estimatedWindow = approximateTermWindow(term.name, term.year);
  if (!estimatedWindow) {
    return { label: 'Dates not set', estimated: true, start: null, end: null, progress: null };
  }

  const span = estimatedWindow.end.getTime() - estimatedWindow.start.getTime();
  const raw = span > 0 ? ((now.getTime() - estimatedWindow.start.getTime()) / span) * 100 : 100;
  const label =
    now < estimatedWindow.start ? 'Upcoming' : now > estimatedWindow.end ? 'Completed' : 'In session';

  return {
    label,
    estimated: true,
    start: hasAnyDate ? null : estimatedWindow.start,
    end: hasAnyDate ? null : estimatedWindow.end,
    progress: Math.min(100, Math.max(0, raw)),
  };
}

/** Format a date for the term timeline (e.g. "Aug 15, 2026"). */
function formatTermDate(date: Date): string {
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(date);
}

/** Number of weeks spanned by a term window, for the "N weeks" timeline hint. */
function termWeeks(start: Date | null, end: Date | null): number {
  if (!start || !end) return 0;
  return (end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24 * 7);
}

/**
 * One academic term card: status, date timeline with progress, headline
 * counts and the courses it covers.
 */
function TermCard({
  term,
  courses,
  onEdit,
  onDelete,
  deleting,
  onOpenCourses,
}: {
  term: AdminTerm;
  courses: CourseWithInstructors[];
  onEdit: (term: AdminTerm) => void;
  onDelete: (term: AdminTerm) => void;
  deleting: boolean;
  onOpenCourses: (label: string) => void;
}) {
  const accent = termAccent(term.name);
  const status = termStatus(term, new Date());
  const label = term.label || `${term.name} ${term.year}`;

  const hasBothDates = Boolean(
    parseTermDate(term.start_date) && parseTermDate(term.end_date),
  );
  const singleDate = hasBothDates
    ? null
    : parseTermDate(term.start_date) ?? parseTermDate(term.end_date);
  const singleDateIsStart = Boolean(term.start_date);

  const professorCount = new Set(
    courses.flatMap((course) => course.instructors.map((instructor) => instructor.id)),
  ).size;
  const assignmentCount = courses.reduce(
    (sum, course) => sum + courseAssignmentCount(course),
    0,
  );
  const courseCount = term.course_count ?? courses.length;

  const stats = [
    { value: courseCount, label: courseCount === 1 ? 'Course' : 'Courses' },
    { value: professorCount, label: professorCount === 1 ? 'Professor' : 'Professors' },
    { value: assignmentCount, label: assignmentCount === 1 ? 'Assignment' : 'Assignments' },
  ];

  const previewCourses = courses.slice(0, 3);
  const remainingCourses = Math.max(0, courses.length - previewCourses.length);

  const statusTone =
    status.label === 'In session'
      ? 'bg-emerald-100 text-emerald-700 ring-emerald-200 dark:bg-emerald-500/15 dark:text-emerald-300 dark:ring-emerald-500/25'
      : status.label === 'Upcoming'
        ? 'bg-blue-100 text-blue-700 ring-blue-200 dark:bg-blue-500/15 dark:text-blue-300 dark:ring-blue-500/25'
        : status.label === 'Completed'
          ? 'bg-slate-100 text-slate-600 ring-slate-200 dark:bg-slate-500/15 dark:text-slate-300 dark:ring-slate-500/25'
          : 'bg-slate-100 text-slate-500 ring-slate-200 dark:bg-slate-500/15 dark:text-slate-400 dark:ring-slate-500/25';

  return (
    <article className="relative flex h-full flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm transition hover:-translate-y-0.5 hover:shadow-md dark:border-slate-800 dark:bg-slate-950">
      {/* Season accent */}
      <div className={`h-1.5 w-full ${accent.bar}`} aria-hidden />
      <div className={`pointer-events-none absolute inset-x-0 top-0 h-32 ${accent.wash}`} aria-hidden />

      <div className="relative flex flex-1 flex-col gap-4 p-5">
        {/* Status + actions */}
        <div className="flex items-start justify-between gap-3">
          <span
            title={
              status.estimated && status.label !== 'Dates not set'
                ? 'No dates set — status estimated from the season.'
                : undefined
            }
            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${statusTone}`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                status.label === 'In session'
                  ? 'animate-pulse bg-emerald-500'
                  : status.label === 'Upcoming'
                    ? 'bg-blue-500'
                    : 'bg-slate-400'
              }`}
            />
            {status.label}
            {status.estimated && status.label !== 'Dates not set' && (
              <span className="font-normal opacity-70">· est.</span>
            )}
          </span>

          <div className="flex shrink-0 items-center gap-1">
            <button
              type="button"
              onClick={() => onEdit(term)}
              aria-label={`Edit ${label}`}
              className="rounded-md p-2 text-slate-400 transition hover:bg-white/80 hover:text-slate-700 dark:hover:bg-slate-800 dark:hover:text-slate-200"
            >
              <Pencil size={15} />
            </button>
            <button
              type="button"
              onClick={() => onDelete(term)}
              disabled={deleting}
              aria-label={`Remove ${label} from registry`}
              className="rounded-md p-2 text-slate-400 transition hover:bg-red-50 hover:text-red-600 disabled:opacity-50 dark:hover:bg-red-900/30 dark:hover:text-red-400"
            >
              {deleting ? <Loader2 size={15} className="animate-spin" /> : <Trash2 size={15} />}
            </button>
          </div>
        </div>

        {/* Title */}
        <div className="min-w-0">
          <p className={`flex items-center gap-2 text-[11px] font-bold uppercase tracking-[0.2em] ${accent.text}`}>
            <span className={`h-2 w-2 rounded-full ${accent.dot}`} aria-hidden />
            {term.name}
          </p>
          <h3 className="mt-1.5 truncate text-xl font-semibold tracking-tight text-slate-900 dark:text-white">
            {label}
          </h3>
          {term.description && (
            <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500 dark:text-slate-400">
              {term.description}
            </p>
          )}
        </div>

        {/* Timeline */}
        <div
          title={
            status.estimated && status.start && status.end
              ? 'No dates stored for this term — this window is estimated from the season.'
              : undefined
          }
          className="rounded-2xl border border-slate-200/80 bg-white/70 p-3 dark:border-slate-800 dark:bg-slate-900/50"
        >
          {status.start && status.end ? (
            <>
              <div className="flex items-baseline justify-between gap-3 text-xs text-slate-500 dark:text-slate-400">
                <span
                  className={`font-medium text-slate-600 dark:text-slate-300 ${
                    status.estimated ? 'border-b border-dashed border-slate-300 dark:border-slate-600' : ''
                  }`}
                >
                  {formatTermDate(status.start)}
                </span>
                <span aria-hidden>→</span>
                <span
                  className={`font-medium text-slate-600 dark:text-slate-300 ${
                    status.estimated ? 'border-b border-dashed border-slate-300 dark:border-slate-600' : ''
                  }`}
                >
                  {formatTermDate(status.end)}
                </span>
              </div>
              <div className="mt-2.5 h-2 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
                <div
                  className={`h-full rounded-full transition-all ${accent.bar}`}
                  style={{ width: `${status.progress ?? 0}%` }}
                />
              </div>
              <div className="mt-1.5 flex items-center justify-between gap-2 text-[11px] text-slate-400 dark:text-slate-500">
                <span>{Math.round(status.progress ?? 0)}% through the term</span>
                {status.estimated ? (
                  <button
                    type="button"
                    onClick={() => onEdit(term)}
                    className="font-semibold text-blue-600 transition hover:text-blue-700 dark:text-blue-300 dark:hover:text-blue-200"
                  >
                    Set dates
                  </button>
                ) : (
                  <span>{Math.max(1, Math.round(termWeeks(status.start, status.end)))} weeks</span>
                )}
              </div>
            </>
          ) : (
            <div className="flex items-center justify-between gap-2 text-xs">
              <span className="text-slate-500 dark:text-slate-400">
                {singleDate
                  ? `${singleDateIsStart ? 'Starts' : 'Ends'} ${formatTermDate(singleDate)}`
                  : 'No date range set'}
              </span>
              <button
                type="button"
                onClick={() => onEdit(term)}
                className="font-semibold text-blue-600 transition hover:text-blue-700 dark:text-blue-300 dark:hover:text-blue-200"
              >
                {singleDate ? 'Complete dates' : 'Add dates'}
              </button>
            </div>
          )}
        </div>

        {/* Headline counts */}
        <div className="grid grid-cols-3 divide-x divide-slate-200 rounded-2xl bg-slate-50 py-3 dark:divide-slate-800 dark:bg-slate-900/70">
          {stats.map((stat) => (
            <div key={stat.label} className="flex flex-col items-center gap-0.5 px-1">
              <span className="text-xl font-bold tabular-nums leading-6 text-slate-900 dark:text-white">
                {stat.value}
              </span>
              <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400">
                {stat.label}
              </span>
            </div>
          ))}
        </div>

        {/* Courses in this term */}
        <div className="flex flex-col gap-2">
          {previewCourses.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {previewCourses.map((course) => (
                <span
                  key={course.id}
                  title={course.name}
                  className="max-w-[11rem] truncate rounded-lg border border-slate-200 bg-white px-2 py-1 font-mono text-[11px] font-semibold text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
                >
                  {course.code || course.name}
                </span>
              ))}
              {remainingCourses > 0 && (
                <span className="rounded-lg bg-slate-100 px-2 py-1 text-[11px] font-semibold text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                  +{remainingCourses}
                </span>
              )}
            </div>
          ) : (
            <p className="text-xs text-slate-400 dark:text-slate-500">
              No courses linked to this term yet.
            </p>
          )}
        </div>

        {courseCount > 0 && (
          <button
            type="button"
            onClick={() => onOpenCourses(label)}
            className="mt-auto flex w-full items-center justify-center gap-1.5 rounded-xl border border-slate-200 bg-white py-2.5 text-xs font-semibold text-slate-600 transition hover:border-blue-300 hover:text-blue-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-blue-500/40 dark:hover:text-blue-300"
          >
            Open {courseCount} course{courseCount !== 1 ? 's' : ''}
            <ChevronDown size={13} className="-rotate-90" />
          </button>
        )}
      </div>
    </article>
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
  required,
  children,
}: {
  label: string;
  hint?: string;
  /** Marks a mandatory field with a red asterisk next to its label. */
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
        {label}
        {required && (
          <span aria-hidden="true" className="ml-0.5 text-red-500 dark:text-red-400">
            *
          </span>
        )}
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
  const termButtonRef = useRef<HTMLButtonElement | null>(null);

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
  // term assignment per course: courseId → selected term_id in dropdown
  const [selectedTermForCourse, setSelectedTermForCourse] = useState<Record<string, string>>({});
  const [assigningTermForCourse, setAssigningTermForCourse] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'users' | 'courses' | 'terms'>('users');
  const [courseQuery, setCourseQuery] = useState('');
  const [courseTermFilter, setCourseTermFilter] = useState('all');

  const [terms, setTerms] = useState<AdminTerm[]>([]);
  const [loadingTerms, setLoadingTerms] = useState(true);
  const [showTermModal, setShowTermModal] = useState(false);
  const [termSaving, setTermSaving] = useState(false);
  const [termError, setTermError] = useState('');
  const [editingTermId, setEditingTermId] = useState<string | null>(null);
  const [deletingTermId, setDeletingTermId] = useState<string | null>(null);
  const [termToDelete, setTermToDelete] = useState<AdminTerm | null>(null);
  const [termForm, setTermForm] = useState({
    name: 'Fall',
    year: String(new Date().getFullYear()),
    start_date: '',
    end_date: '',
    description: '',
  });

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
  // Course create vs edit, plus the pending delete confirmation.
  const [editingCourseId, setEditingCourseId] = useState<string | null>(null);
  const [courseToDelete, setCourseToDelete] = useState<CourseWithInstructors | null>(null);
  const [courseDeleting, setCourseDeleting] = useState(false);
  const [courseForm, setCourseForm] = useState({
    name: '',
    code: '',
    term: 'Fall',
    year: String(new Date().getFullYear()),
    department: '',
    description: '',
    term_id: '',
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

  const loadTerms = useCallback(async () => {
    setLoadingTerms(true);
    try {
      const res = await apiClient.get('/api/terms');
      setTerms(Array.isArray(res.data) ? res.data : []);
    } catch (error) {
      console.error('Failed to load terms', error);
    } finally {
      setLoadingTerms(false);
    }
  }, []);

  useEffect(() => {
    if (!bootstrapped || authLoading || status === 'loading') return;
    if (!user || user.role !== 'admin') {
      setLoadingUsers(false);
      setLoadingCourses(false);
      setLoadingTerms(false);
      return;
    }
    loadUsers();
    loadCoursesWithInstructors();
    loadTerms();
  }, [bootstrapped, authLoading, status, user, loadUsers, loadCoursesWithInstructors, loadTerms]);

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

  // Secondary figures shown under each KPI so the strip answers "how is the
  // organization doing?" instead of just showing raw counts.
  const adminCount = users.filter((u) => u.role === 'admin').length;
  const professorCount = totalUsers - adminCount;
  const coursesWithStaff = coursesWithInstructors.filter((c) => c.instructors.length > 0).length;
  const activePercent = totalUsers > 0 ? Math.round((activeUsers / totalUsers) * 100) : 0;
  const assignmentsPerCourse = totalCourses > 0 ? totalAssignments / totalCourses : 0;
  const inSessionTerm = terms.find((term) => termStatus(term, new Date()).label === 'In session');

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
    setEditingCourseId(null);
    setCourseForm({
      name: '',
      code: '',
      term: 'Fall',
      year: String(new Date().getFullYear()),
      department: '',
      description: '',
      term_id: '',
    });
    setShowCourseModal(true);
  };

  /**
   * Prefill the course modal for an edit. ``term_id`` is carried through so a
   * registry link survives the PUT — omitting it would unlink the term, because
   * the endpoint mirrors term/year from the registry whenever one is present.
   */
  const openEditCourse = (course: CourseWithInstructors) => {
    setCourseError('');
    setEditingCourseId(course.id);
    setCourseForm({
      name: course.name,
      code: course.code ?? '',
      term: course.term || 'Fall',
      year: course.year ? String(course.year) : String(new Date().getFullYear()),
      department: course.department ?? '',
      description: course.description ?? '',
      term_id: course.term_id ?? '',
    });
    setShowCourseModal(true);
  };

  const closeCourseModal = () => {
    if (courseSaving) return;
    setShowCourseModal(false);
    setEditingCourseId(null);
    setTimeout(() => courseButtonRef.current?.focus(), 0);
  };

  const handleSaveCourse = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setCourseError('');
    if (!courseForm.name.trim()) {
      setCourseError('Course name is required.');
      return;
    }
    const wasEditing = Boolean(editingCourseId);
    setCourseSaving(true);
    try {
      const payload = {
        name: courseForm.name.trim(),
        code: courseForm.code.trim() || null,
        term: courseForm.term.trim() || null,
        year: courseForm.year ? Number(courseForm.year) : null,
        department: courseForm.department.trim() || null,
        description: courseForm.description.trim() || null,
        term_id: courseForm.term_id || null,
      };
      if (editingCourseId) {
        await apiClient.put(`/api/courses/${editingCourseId}`, payload);
      } else {
        await apiClient.post('/api/courses', payload);
      }
      await loadCoursesWithInstructors();
      setShowCourseModal(false);
      setEditingCourseId(null);
      setSuccessMessage(wasEditing ? 'Course updated successfully.' : 'Course created successfully.');
      setTimeout(() => courseButtonRef.current?.focus(), 0);
    } catch (error) {
      setCourseError(getErrorMessage(error));
    } finally {
      setCourseSaving(false);
    }
  };

  // ── Course deletion ───────────────────────────────────────────────────────────

  const confirmDeleteCourse = async () => {
    if (!courseToDelete) return;
    setCourseDeleting(true);
    setPageError('');
    try {
      await apiClient.delete(`/api/courses/${courseToDelete.id}`);
      setCourseToDelete(null);
      await loadCoursesWithInstructors();
      setSuccessMessage(`“${courseToDelete.name}” deleted.`);
    } catch (error) {
      // Courses that still own assignments come back as 409 with an
      // actionable message — surface it instead of a generic failure.
      setCourseToDelete(null);
      setPageError(getErrorMessage(error));
    } finally {
      setCourseDeleting(false);
    }
  };

  // ── Term handlers ────────────────────────────────────────────────────────────

  const openTermModal = () => {
    setTermError('');
    setEditingTermId(null);
    setTermForm({
      name: 'Fall',
      year: String(new Date().getFullYear()),
      start_date: '',
      end_date: '',
      description: '',
    });
    setShowTermModal(true);
  };

  const openEditTerm = (term: AdminTerm) => {
    setTermError('');
    setEditingTermId(term.id);
    setTermForm({
      name: term.name,
      year: String(term.year),
      start_date: term.start_date ?? '',
      end_date: term.end_date ?? '',
      description: term.description ?? '',
    });
    setShowTermModal(true);
  };

  const closeTermModal = () => {
    if (termSaving) return;
    setShowTermModal(false);
    setTimeout(() => termButtonRef.current?.focus(), 0);
  };

  const handleSaveTerm = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setTermError('');
    const name = termForm.name.trim();
    const year = Number(termForm.year);
    if (!name) {
      setTermError('Term name is required.');
      return;
    }
    if (!Number.isInteger(year) || year < 1900 || year > 2200) {
      setTermError('Year must be a number between 1900 and 2200.');
      return;
    }
    if (termForm.start_date && termForm.end_date && termForm.start_date > termForm.end_date) {
      setTermError('Start date must be on or before end date.');
      return;
    }
    setTermSaving(true);
    try {
      const payload = {
        name,
        year,
        start_date: termForm.start_date || null,
        end_date: termForm.end_date || null,
        description: termForm.description.trim() || null,
      };
      if (editingTermId) {
        await apiClient.put(`/api/terms/${editingTermId}`, payload);
        setSuccessMessage('Term updated successfully.');
      } else {
        // POST is idempotent: when the (name, year) pair is already registered the
        // API returns that row instead of creating a duplicate, so say so.
        const knownIds = new Set(terms.map((t) => t.id));
        const res = await apiClient.post('/api/terms', payload);
        const saved = res?.data as AdminTerm | undefined;
        setSuccessMessage(
          saved?.id && knownIds.has(saved.id)
            ? `${saved.label || `${name} ${year}`} was already in the registry.`
            : 'Term created successfully.',
        );
      }
      await Promise.all([loadTerms(), loadCoursesWithInstructors()]);
      setShowTermModal(false);
      setTimeout(() => termButtonRef.current?.focus(), 0);
    } catch (error) {
      setTermError(getErrorMessage(error));
    } finally {
      setTermSaving(false);
    }
  };

  const handleDeleteTerm = (term: AdminTerm) => {
    setTermToDelete(term);
  };

  const confirmDeleteTerm = async () => {
    if (!termToDelete) return;
    const term = termToDelete;
    const label = term.label || `${term.name} ${term.year}`;
    setTermToDelete(null);
    setDeletingTermId(term.id);
    setPageError('');
    try {
      await apiClient.delete(`/api/terms/${term.id}`);
      await Promise.all([loadTerms(), loadCoursesWithInstructors()]);
      setSuccessMessage(`Term ${label} removed.`);
    } catch (error) {
      setPageError(getErrorMessage(error));
    } finally {
      setDeletingTermId(null);
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

  const assignCourseTerm = async (courseId: string, termId: string) => {
    // Find the course to preserve required fields for the PUT body
    const course = coursesWithInstructors.find((c) => c.id === courseId);
    if (!course) return;
    setAssigningTermForCourse(courseId);
    try {
      await apiClient.put(`/api/courses/${courseId}`, {
        name: course.name,
        code: course.code ?? null,
        department: course.department ?? null,
        description: course.description ?? null,
        term_id: termId || null,   // empty string → unlink
      });
      await loadCoursesWithInstructors();
      setSelectedTermForCourse((prev) => ({ ...prev, [courseId]: '' }));
      setSuccessMessage('Term assignment updated.');
    } catch (error) {
      setPageError(getErrorMessage(error));
    } finally {
      setAssigningTermForCourse(null);
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
        <section className="relative overflow-hidden rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950">
          <div
            className="pointer-events-none absolute inset-0 bg-gradient-to-br from-blue-500/[0.07] via-transparent to-violet-500/[0.06]"
            aria-hidden
          />
          <div className="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
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

            {/* Quick action for the tab you are on */}
            <div className="flex flex-wrap items-center gap-2">
              {activeTab === 'users' && (
                <button
                  type="button"
                  onClick={openCreatePanel}
                  className="inline-flex h-10 items-center gap-2 rounded-xl bg-blue-600 px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50"
                >
                  <UserPlus size={15} />
                  Add user
                </button>
              )}

              {activeTab === 'courses' && (
                <button
                  type="button"
                  onClick={openCourseModal}
                  className="inline-flex h-10 items-center gap-2 rounded-xl bg-blue-600 px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50"
                >
                  <Plus size={15} />
                  Add course
                </button>
              )}

              {activeTab === 'terms' && (
                <button
                  type="button"
                  onClick={openTermModal}
                  className="inline-flex h-10 items-center gap-2 rounded-xl bg-blue-600 px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50"
                >
                  <Plus size={15} />
                  Add term
                </button>
              )}
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
        <section className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          <StatCard
            label="Total users"
            value={totalUsers}
            hint={`${adminCount} admin${adminCount === 1 ? '' : 's'} · ${professorCount} professor${professorCount === 1 ? '' : 's'}`}
            icon={<Users size={14} />}
            tone="slate"
            active={activeTab === 'users'}
            onClick={() => setActiveTab('users')}
          />
          <StatCard
            label="Active"
            value={activeUsers}
            hint={totalUsers > 0 ? `${activePercent}% of accounts active` : 'No accounts yet'}
            icon={<UserCheck size={14} />}
            tone="emerald"
            active={false}
            onClick={() => {
              setRoleFilter('all');
              setSearchQuery('');
              setActiveTab('users');
            }}
          />
          <StatCard
            label="Suspended"
            value={suspendedUsers}
            hint={suspendedUsers === 0 ? 'All accounts in good standing' : 'Disabled from signing in'}
            icon={<UserX size={14} />}
            tone="amber"
            active={false}
            onClick={() => setActiveTab('users')}
          />
          <StatCard
            label="Courses"
            value={totalCourses}
            hint={coursesWithStaff === totalCourses ? 'All staffed with professors' : `${coursesWithStaff} of ${totalCourses} staffed`}
            icon={<GraduationCap size={14} />}
            tone="blue"
            active={activeTab === 'courses'}
            onClick={() => setActiveTab('courses')}
          />
          <StatCard
            label="Assignments"
            value={totalAssignments}
            hint={totalCourses > 0 ? `${assignmentsPerCourse.toFixed(1)} per course on average` : 'No courses yet'}
            icon={<FileText size={14} />}
            tone="violet"
            active={false}
            onClick={() => setActiveTab('courses')}
          />
          <StatCard
            label="Terms"
            value={terms.length}
            hint={inSessionTerm ? `${inSessionTerm.label} is in session` : 'No term currently running'}
            icon={<Calendar size={14} />}
            tone="sky"
            active={activeTab === 'terms'}
            onClick={() => setActiveTab('terms')}
          />
        </section>

        {/* ── Section tabs ──────────────────────────────────────────────────────── */}
        <div className="grid grid-cols-3 gap-2 rounded-2xl border border-slate-200 bg-slate-50 p-1 dark:border-slate-800 dark:bg-slate-900">
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
          <button
            type="button"
            onClick={() => setActiveTab('terms')}
            aria-pressed={activeTab === 'terms'}
            className={`inline-flex h-10 items-center justify-center gap-2 rounded-xl px-4 text-sm font-semibold transition ${activeTab === 'terms'
              ? 'bg-white text-slate-900 shadow-sm dark:bg-slate-800 dark:text-white'
              : 'text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800'}`}
          >
            <Calendar size={15} />
            Terms
            <span className="ml-0.5 rounded-full bg-slate-200 px-1.5 text-[11px] font-bold tabular-nums text-slate-600 dark:bg-slate-800 dark:text-slate-300">
              {terms.length}
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
                    ? `${totalUsers} account${totalUsers !== 1 ? 's' : ''} · ${adminCount} admin${adminCount !== 1 ? 's' : ''} · ${professorCount} professor${professorCount !== 1 ? 's' : ''}`
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
                          <tr key={entry.id} className="transition-colors hover:bg-slate-50 dark:hover:bg-slate-900/50">
                            <td className="px-5 py-4">
                              <div className="flex items-center gap-3">
                                <Avatar name={entry.full_name} role={entry.role} title={entry.email} />
                                <div className="min-w-0">
                                  <div className="flex items-center gap-2">
                                    <span className="truncate font-medium text-slate-900 dark:text-white">
                                      {entry.full_name}
                                    </span>
                                    {isSelf && (
                                      <span className="shrink-0 rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                                        You
                                      </span>
                                    )}
                                  </div>
                                  <div className="mt-0.5 truncate text-sm text-slate-500 dark:text-slate-400">
                                    {entry.email}
                                  </div>
                                </div>
                              </div>
                            </td>
                            <td className="px-5 py-4"><RoleBadge role={entry.role} /></td>
                            <td className="px-5 py-4"><StatusBadge suspended={entry.suspended} /></td>
                            <td className="px-5 py-4 text-sm text-slate-600 dark:text-slate-400">
                              {entry.last_login_at ? (
                                <span title={`Last sign-in: ${formatDate(entry.last_login_at)}`}>
                                  <span className="block font-medium text-slate-700 dark:text-slate-300">
                                    {relativeTime(entry.last_login_at) ?? 'Never'}
                                  </span>
                                  <span className="mt-0.5 block text-xs text-slate-400 dark:text-slate-500">
                                    {formatDate(entry.last_login_at)}
                                  </span>
                                </span>
                              ) : (
                                <span className="text-slate-400 dark:text-slate-500">Never signed in</span>
                              )}
                            </td>
                            <td className="px-5 py-4 text-sm text-slate-600 dark:text-slate-400">
                              <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                                <Building2 size={12} />
                                {entry.tenant_name || 'Default workspace'}
                              </span>
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
                          <div className="flex min-w-0 items-center gap-3">
                            <Avatar name={entry.full_name} role={entry.role} size={40} title={entry.email} />
                            <div className="min-w-0">
                              <div className="flex items-center gap-2">
                                <h3 className="truncate text-base font-semibold text-slate-900 dark:text-white">
                                  {entry.full_name}
                                </h3>
                                {isSelf && (
                                  <span className="shrink-0 rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                                    You
                                  </span>
                                )}
                              </div>
                              <p className="mt-0.5 truncate text-sm text-slate-500 dark:text-slate-400">
                                {entry.email}
                              </p>
                            </div>
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
                            <div className="mt-2 text-sm text-slate-700 dark:text-slate-300">
                              {relativeTime(entry.last_login_at) ?? 'Never signed in'}
                            </div>
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
                  Create, edit, and delete courses, assign professors and terms, and review the
                  assignments each course owns.
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
                  const assignmentCount = courseAssignmentCount(course);
                  const isAssignmentsOpen = expandedCourseIds.has(course.id);
                  const accent = courseAccent(course.department || course.code || course.name);
                  const linkedTerm = course.term
                    ? `${course.term}${course.year ? ` ${course.year}` : ''}`
                    : 'No term';

                  return (
                    <article
                      key={course.id}
                      className="relative flex h-full flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm transition hover:-translate-y-0.5 hover:shadow-md dark:border-slate-800 dark:bg-slate-950"
                    >
                      {/* Course accent */}
                      <div className={`h-1.5 w-full ${accent.bar}`} aria-hidden />
                      <div className={`pointer-events-none absolute inset-x-0 top-0 h-28 ${accent.wash}`} aria-hidden />

                      <div className="relative flex flex-1 flex-col gap-4 p-5">
                        {/* Course header */}
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            {course.code && (
                              <span className="rounded-md bg-white/80 px-2 py-0.5 font-mono text-xs font-semibold text-slate-600 ring-1 ring-slate-200 dark:bg-slate-900/80 dark:text-slate-300 dark:ring-slate-700">
                                {course.code}
                              </span>
                            )}
                            {course.department && (
                              <span className={`text-[11px] font-bold uppercase tracking-[0.16em] ${accent.text}`}>
                                {course.department}
                              </span>
                            )}
                          </div>
                          <div className="mt-2 flex items-start justify-between gap-3">
                            <h3 className="min-w-0 text-lg font-semibold leading-6 tracking-tight text-slate-900 dark:text-white">
                              {course.name}
                            </h3>
                            {/* Course maintenance lives here: professors keep
                                assignments, admins keep the course itself. */}
                            <div className="flex shrink-0 items-center gap-1">
                              <button
                                type="button"
                                onClick={() => openEditCourse(course)}
                                aria-label={`Edit ${course.name}`}
                                className="rounded-lg p-2 text-slate-400 transition hover:bg-blue-50 hover:text-blue-600 dark:hover:bg-blue-500/10 dark:hover:text-blue-300"
                              >
                                <Pencil size={15} />
                              </button>
                              <button
                                type="button"
                                onClick={() => setCourseToDelete(course)}
                                aria-label={`Delete ${course.name}`}
                                className="rounded-lg p-2 text-slate-400 transition hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-500/10 dark:hover:text-red-400"
                              >
                                <Trash2 size={15} />
                              </button>
                            </div>
                          </div>
                          <p className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-500 dark:text-slate-400">
                            <span className={`font-semibold ${accent.text}`}>{linkedTerm}</span>
                            <span aria-hidden className="text-slate-300 dark:text-slate-600">·</span>
                            <span>
                              {course.instructors.length} professor{course.instructors.length === 1 ? '' : 's'}
                            </span>
                            <span aria-hidden className="text-slate-300 dark:text-slate-600">·</span>
                            <span>
                              {assignmentCount} assignment{assignmentCount === 1 ? '' : 's'}
                            </span>
                          </p>
                        </div>

                        {/* Term assignment. The term value is stated once in the
                            summary line above, so this block only owns the
                            control — repeating it as a pill made every card
                            read the same term twice. */}
                        <div className="rounded-2xl border border-slate-200/80 bg-white/70 p-3.5 dark:border-slate-800 dark:bg-slate-900/50">
                          <span className="block text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
                            Term
                          </span>
                        {terms.length === 0 ? (
                          <p className="mt-2 text-xs text-slate-400 dark:text-slate-500">
                            No terms in the registry yet. Add one in the Terms tab.
                          </p>
                        ) : (
                          <div className="mt-2.5 flex items-center gap-2">
                            <div className="relative min-w-0 flex-1">
                              <select
                                value={selectedTermForCourse[course.id] ?? ''}
                                onChange={(e) =>
                                  setSelectedTermForCourse((prev) => ({ ...prev, [course.id]: e.target.value }))
                                }
                                aria-label={`Assign term to ${course.name}`}
                                className="h-9 w-full appearance-none rounded-xl border border-slate-200 bg-white pl-3 pr-8 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-950 dark:text-white"
                              >
                                <option value="">
                                  {course.term_id
                                    ? '— Remove term link —'
                                    : course.term
                                      ? 'Assign a registry term…'
                                      : 'Assign a term…'}
                                </option>
                                {terms.map((t) => (
                                  <option key={t.id} value={t.id}>
                                    {t.label || `${t.name} ${t.year}`}
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
                              disabled={
                                selectedTermForCourse[course.id] === undefined ||
                                selectedTermForCourse[course.id] === '' ||
                                assigningTermForCourse === course.id
                              }
                              onClick={() =>
                                assignCourseTerm(course.id, selectedTermForCourse[course.id] ?? '')
                              }
                              className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-xl bg-blue-600 px-3.5 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              {assigningTermForCourse === course.id ? (
                                <Loader2 size={13} className="animate-spin" />
                              ) : (
                                <Calendar size={13} />
                              )}
                              Save
                            </button>
                          </div>
                        )}
                      </div>

                      {/* Professors. The headcount lives in the summary line, so
                          the header stays a plain label and the chips carry the
                          names. */}
                      <div className="rounded-2xl border border-slate-200/80 bg-white/70 p-3.5 dark:border-slate-800 dark:bg-slate-900/50">
                        <span className="block text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
                          Professors
                        </span>

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
                                  <Avatar name={inst.full_name} size={24} title={inst.email} />
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
                                className="h-9 w-full appearance-none rounded-xl border border-slate-200 bg-white pl-3 pr-8 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-950 dark:text-white"
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
                              className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-xl bg-blue-600 px-3.5 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
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
                      <div className="mt-auto">
                        <button
                          type="button"
                          onClick={() => toggleCourseAssignments(course.id)}
                          aria-expanded={isAssignmentsOpen}
                          className="flex w-full items-center justify-between rounded-2xl border border-slate-200/80 bg-white/70 px-3.5 py-3 text-left transition hover:border-blue-300 hover:bg-blue-50/50 dark:border-slate-800 dark:bg-slate-900/50 dark:hover:border-blue-500/40 dark:hover:bg-blue-500/5"
                        >
                          <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
                            Assignments
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
                      </div>
                    </article>
                  );
                })}
                <AddCourseCard onAdd={openCourseModal} buttonRef={courseButtonRef} variant="grid" />
              </div>
            )}
          </section>
        )}

        {/* ── Academic terms ─────────────────────────────────────────────────── */}
        {activeTab === 'terms' && (
          <section className="overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
            <div className="flex flex-col gap-4 border-b border-slate-200 px-6 py-5 dark:border-slate-800 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <div className="inline-flex items-center gap-2 rounded-full border border-blue-600/10 bg-blue-600/[0.06] px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.2em] text-blue-600 dark:border-blue-400/20 dark:bg-blue-400/10 dark:text-blue-400">
                  <Calendar size={14} />
                  Terms
                </div>
                <h2 className="mt-3 text-xl font-semibold text-slate-900 dark:text-white">
                  Academic terms
                </h2>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                  Create the terms courses are scheduled in. Renaming a term relabels the
                  courses that use it; removing one only unlinks it from them.
                </p>
              </div>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                {terms.length} term{terms.length !== 1 ? 's' : ''} ·{' '}
                {terms.reduce((total, term) => total + (term.course_count ?? 0), 0)} courses
              </p>
            </div>

            {loadingTerms ? (
              <div className="grid gap-4 p-5 md:grid-cols-2 xl:grid-cols-3">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="rounded-3xl border border-slate-200 p-5 dark:border-slate-800">
                    <div className="h-4 w-24 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
                    <div className="mt-3 h-5 w-32 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
                    <div className="mt-4 h-9 w-full animate-pulse rounded-2xl bg-slate-200 dark:bg-slate-800" />
                  </div>
                ))}
              </div>
            ) : terms.length === 0 ? (
              <div className="p-5">
                <AddTermCard onAdd={openTermModal} buttonRef={termButtonRef} />
              </div>
            ) : (
              <div className="grid gap-4 p-5 md:grid-cols-2 xl:grid-cols-3">
                {terms.map((term) => {
                  const termCourses = coursesWithInstructors.filter(
                    (course) =>
                      course.term_id === term.id ||
                      (!course.term_id && courseTermLabel(course) === term.label),
                  );
                  return (
                    <TermCard
                      key={term.id}
                      term={term}
                      courses={termCourses}
                      deleting={deletingTermId === term.id}
                      onEdit={openEditTerm}
                      onDelete={handleDeleteTerm}
                      onOpenCourses={(label) => {
                        setCourseTermFilter(label);
                        setActiveTab('courses');
                      }}
                    />
                  );
                })}
                <AddTermCard onAdd={openTermModal} buttonRef={termButtonRef} />
              </div>
            )}
          </section>
        )}

      </div>

      <Modal
        open={showCourseModal}
        title={editingCourseId ? 'Edit course' : 'Create a new course'}
        description={
          editingCourseId
            ? 'Update the course details. Instructors, term links, and assignments are managed on the course card.'
            : 'Add a course to your organization. You can assign instructors and create assignments after it is created.'
        }
        onClose={closeCourseModal}
      >
        <form onSubmit={handleSaveCourse} className="space-y-4">
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
            <Field
              label="Term"
              hint={editingCourseId && courseForm.term_id ? 'Set by the registry term' : undefined}
            >
              <div className="relative">
                <select
                  value={courseForm.term}
                  onChange={(e) => setCourseForm((c) => ({ ...c, term: e.target.value }))}
                  disabled={Boolean(courseForm.term_id)}
                  className={selectClass}
                >
                  {/* A registry-linked course takes its season from the term, so
                      the text field is read-only; a legacy season outside the
                      four options still has to stay selectable. */}
                  {courseForm.term && !TERM_NAMES.includes(courseForm.term) && (
                    <option>{courseForm.term}</option>
                  )}
                  <option>Fall</option>
                  <option>Winter</option>
                  <option>Spring</option>
                  <option>Summer</option>
                </select>
                <ChevronDown size={14} className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-slate-400" />
              </div>
            </Field>
            <Field
              label="Year"
              hint={editingCourseId && courseForm.term_id ? 'Set by the registry term' : undefined}
            >
              <input
                type="number"
                min="1900"
                max="2200"
                value={courseForm.year}
                onChange={(e) => setCourseForm((c) => ({ ...c, year: e.target.value }))}
                disabled={Boolean(courseForm.term_id)}
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
              {courseSaving
                ? editingCourseId ? 'Saving…' : 'Creating…'
                : editingCourseId ? 'Save changes' : 'Create course'}
            </button>
          </div>
        </form>
      </Modal>

      <Modal
        open={showTermModal}
        title={editingTermId ? 'Edit term' : 'Add a term'}
        description={
          editingTermId
            ? 'Rename the term or adjust its dates. Courses scheduled in it are relabelled to match.'
            : 'Add an academic term so courses can be scheduled into it.'
        }
        onClose={closeTermModal}
      >
        <form onSubmit={handleSaveTerm} className="space-y-4">
          {termError && (
            <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300">
              <AlertTriangle size={15} className="mt-0.5 shrink-0" />
              <span>{termError}</span>
            </div>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Term name" required>
              <div className="relative">
                <select
                  required
                  autoFocus
                  value={termForm.name}
                  onChange={(e) => setTermForm((t) => ({ ...t, name: e.target.value }))}
                  className={selectClass}
                >
                  {/* A legacy row can carry a name outside the season list; keep it
                      selectable so editing one does not silently rename it. */}
                  {termForm.name && !TERM_NAMES.includes(termForm.name) && (
                    <option>{termForm.name}</option>
                  )}
                  {TERM_NAMES.map((season) => (
                    <option key={season}>{season}</option>
                  ))}
                </select>
                <ChevronDown
                  size={14}
                  className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-slate-400"
                />
              </div>
            </Field>
            <Field label="Year" required>
              <input
                type="number"
                min="1900"
                max="2200"
                required
                value={termForm.year}
                onChange={(e) => setTermForm((t) => ({ ...t, year: e.target.value }))}
                className={inputClass}
              />
            </Field>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Start date">
              <input
                type="date"
                value={termForm.start_date}
                onChange={(e) => setTermForm((t) => ({ ...t, start_date: e.target.value }))}
                className={inputClass}
              />
            </Field>
            <Field label="End date">
              <input
                type="date"
                value={termForm.end_date}
                onChange={(e) => setTermForm((t) => ({ ...t, end_date: e.target.value }))}
                className={inputClass}
              />
            </Field>
          </div>
          <Field label="Notes">
            <textarea
              rows={2}
              value={termForm.description}
              onChange={(e) => setTermForm((t) => ({ ...t, description: e.target.value }))}
              placeholder="Registration window, grading deadline, anything the team should know"
              className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white"
            />
          </Field>
          <div className="flex justify-end gap-2 border-t border-slate-200 pt-4 dark:border-slate-800">
            <button
              type="button"
              onClick={closeTermModal}
              disabled={termSaving}
              className="inline-flex h-10 items-center rounded-xl px-4 text-sm font-medium text-slate-600 transition hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-900"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={termSaving}
              className="inline-flex h-10 items-center gap-2 rounded-xl bg-slate-950 px-4 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:opacity-60 dark:bg-white dark:text-slate-950"
            >
              {termSaving && <Loader2 size={15} className="animate-spin" />}
              {termSaving
                ? 'Saving…'
                : editingTermId
                  ? 'Save changes'
                  : 'Create term'}
            </button>
          </div>
        </form>
      </Modal>

      {/* ── Delete term confirmation modal ───────────────────────────────────── */}
      {termToDelete && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 backdrop-blur-sm p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="delete-term-title"
          onClick={() => setTermToDelete(null)}
        >
          <div
            className="w-full max-w-md rounded-3xl bg-white shadow-2xl dark:bg-slate-950 ring-1 ring-slate-200 dark:ring-slate-800"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-start gap-4 px-6 pt-6 pb-4">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-red-100 dark:bg-red-500/15">
                <Trash2 size={20} className="text-red-600 dark:text-red-400" />
              </div>
              <div className="flex-1 min-w-0">
                <h3
                  id="delete-term-title"
                  className="text-base font-semibold text-slate-900 dark:text-white"
                >
                  Remove term from registry?
                </h3>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                  <strong className="font-semibold text-slate-700 dark:text-slate-300">
                    {termToDelete.label || `${termToDelete.name} ${termToDelete.year}`}
                  </strong>{' '}
                  will be removed from the registry.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setTermToDelete(null)}
                className="rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800"
                aria-label="Cancel"
              >
                <X size={16} />
              </button>
            </div>

            {/* Warning when courses are linked */}
            {termToDelete.course_count > 0 && (
              <div className="mx-6 mb-2 flex items-start gap-2.5 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 dark:border-amber-500/20 dark:bg-amber-500/10">
                <AlertTriangle size={15} className="mt-0.5 shrink-0 text-amber-600 dark:text-amber-400" />
                <p className="text-sm text-amber-800 dark:text-amber-300">
                  <strong>{termToDelete.course_count} course{termToDelete.course_count !== 1 ? 's' : ''}</strong>{' '}
                  {termToDelete.course_count !== 1 ? 'are' : 'is'} linked to this term. Each course will
                  keep its term label but will no longer be linked to the registry entry.
                </p>
              </div>
            )}

            {/* Info note */}
            <p className="px-6 pb-4 text-xs text-slate-400 dark:text-slate-500">
              This only removes the registry entry — no courses, assignments, or submission data will be deleted.
            </p>

            {/* Actions */}
            <div className="flex items-center justify-end gap-3 border-t border-slate-100 px-6 py-4 dark:border-slate-800">
              <button
                type="button"
                onClick={() => setTermToDelete(null)}
                className="h-10 rounded-xl border border-slate-200 px-4 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={confirmDeleteTerm}
                className="h-10 inline-flex items-center gap-2 rounded-xl bg-red-600 px-4 text-sm font-semibold text-white transition hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
              >
                <Trash2 size={14} />
                Remove term
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Delete course confirmation modal ───────────────────────────────────── */}
      {courseToDelete && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 backdrop-blur-sm p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="delete-course-title"
          onClick={() => {
            if (!courseDeleting) setCourseToDelete(null);
          }}
        >
          <div
            className="w-full max-w-md rounded-3xl bg-white shadow-2xl dark:bg-slate-950 ring-1 ring-slate-200 dark:ring-slate-800"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-start gap-4 px-6 pt-6 pb-4">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-red-100 dark:bg-red-500/15">
                <Trash2 size={20} className="text-red-600 dark:text-red-400" />
              </div>
              <div className="flex-1 min-w-0">
                <h3
                  id="delete-course-title"
                  className="text-base font-semibold text-slate-900 dark:text-white"
                >
                  Delete course?
                </h3>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                  <strong className="font-semibold text-slate-700 dark:text-slate-300">
                    {courseToDelete.name}
                  </strong>{' '}
                  and its {courseAssignmentCount(courseToDelete)} assignment
                  {courseAssignmentCount(courseToDelete) === 1 ? '' : 's'} will be permanently
                  deleted.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setCourseToDelete(null)}
                disabled={courseDeleting}
                className="rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800"
                aria-label="Cancel"
              >
                <X size={16} />
              </button>
            </div>

            {/* Evidence that is kept is evidence that blocks the delete */}
            {courseAssignmentCount(courseToDelete) > 0 && (
              <div className="mx-6 mb-2 flex items-start gap-2.5 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 dark:border-amber-500/20 dark:bg-amber-500/10">
                <AlertTriangle size={15} className="mt-0.5 shrink-0 text-amber-600 dark:text-amber-400" />
                <p className="text-sm text-amber-800 dark:text-amber-300">
                  Check history and integrity cases are <strong>kept</strong>, not deleted. If any
                  of these assignments has them attached, the deletion is refused instead.
                </p>
              </div>
            )}

            {/* Info note */}
            <p className="px-6 pb-4 text-xs text-slate-400 dark:text-slate-500">
              Enrollments and instructor links for this course are removed with it. This cannot be
              undone.
            </p>

            {/* Actions */}
            <div className="flex items-center justify-end gap-3 border-t border-slate-100 px-6 py-4 dark:border-slate-800">
              <button
                type="button"
                onClick={() => setCourseToDelete(null)}
                disabled={courseDeleting}
                className="h-10 rounded-xl border border-slate-200 px-4 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-60 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={confirmDeleteCourse}
                disabled={courseDeleting}
                className="h-10 inline-flex items-center gap-2 rounded-xl bg-red-600 px-4 text-sm font-semibold text-white transition hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 disabled:opacity-70"
              >
                {courseDeleting ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <Trash2 size={14} />
                )}
                {courseDeleting ? 'Deleting…' : 'Delete course'}
              </button>
            </div>
          </div>
        </div>
      )}

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
