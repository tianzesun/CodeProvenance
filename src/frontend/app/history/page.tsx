'use client';

import DashboardLayout from '@/components/DashboardLayout';
import {
  EmptyState,
  ErrorState,
  FilterChip,
  LoadingState,
  PageHeader,
  TableBody,
  TableHeader,
  TableRow,
} from '@/components/saas/SaaSPrimitives';
import { apiClient } from '@/lib/apiClient';
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  Ban,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  Eye,
  FileCode2,
  FileDown,
  FileSpreadsheet,
  FileText,
  MoreHorizontal,
  RefreshCw,
  ScrollText,
  Search,
  Shield,
  ShieldCheck,
  Upload,
} from 'lucide-react';
import Link from 'next/link';
import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react';
import type { CSSProperties, ElementType, KeyboardEvent as ReactKeyboardEvent } from 'react';
import { createPortal } from 'react-dom';

type JobStatus = 'COMPLETED' | 'PROCESSING' | 'FAILED' | 'ALL';

type JobItem = {
  id: string;
  name: string;
  status: string;
  assignmentName: string;
  courseName: string;
  createdAt: string;
  totalSubmissions: number;
  highSimilarityCount: number;
  reviewStatus: string;
  persistenceWarning?: string;
};

type SortKey = 'date' | 'name' | 'submissions' | 'highRisk';

type RawJob = {
  id: string;
  name?: string;
  status?: string;
  assignment_name?: string;
  course_name?: string;
  created_at?: string;
  total_submissions?: number;
  high_similarity_count?: number;
  review_status?: string;
  persistence_warning?: string;
};

const STATUS_TABS: { key: JobStatus; label: string }[] = [
  { key: 'ALL', label: 'All' },
  { key: 'COMPLETED', label: 'Completed' },
  { key: 'PROCESSING', label: 'Processing' },
  { key: 'FAILED', label: 'Failed' },
];

const PAGE_SIZES = [10, 25, 50];
const SORT_KEYS: SortKey[] = ['date', 'name', 'submissions', 'highRisk'];
const DEFAULT_SORT_KEY: SortKey = 'date';
const DEFAULT_SORT_DIR = 'desc';
const DEFAULT_PAGE_SIZE = 25;
const POLL_ACTIVE_MS = 8000;
const POLL_IDLE_MS = 30000;

/** Sort choices for small screens, where the sortable table headers are not shown. */
const SORT_OPTIONS: { value: string; label: string }[] = [
  { value: 'date:desc', label: 'Newest first' },
  { value: 'date:asc', label: 'Oldest first' },
  { value: 'name:asc', label: 'Name A–Z' },
  { value: 'name:desc', label: 'Name Z–A' },
  { value: 'submissions:desc', label: 'Most submissions' },
  { value: 'submissions:asc', label: 'Fewest submissions' },
  { value: 'highRisk:desc', label: 'Most high-risk' },
  { value: 'highRisk:asc', label: 'Fewest high-risk' },
];

const REFERENCE_HEADERS = ['x-correlation-id', 'x-request-id'];

/** Generic, status-keyed text; a correlation id is appended when the backend sends one. */
function describeLoadError(error: unknown): string {
  const response = (error as { response?: { status?: unknown; headers?: unknown } } | null)?.response;
  const status = typeof response?.status === 'number' ? response.status : undefined;
  const headers = (response?.headers ?? {}) as Record<string, unknown>;
  const reference = REFERENCE_HEADERS.map((name) => headers[name]).find(
    (value): value is string => typeof value === 'string' && value.length > 0
  );

  let message: string;
  if (status === 401) {
    message = 'Your session has expired. Please sign in again.';
  } else if (status === 403) {
    message = 'You don’t have permission to view this history.';
  } else {
    message = 'Failed to load history. Please try again.';
  }

  return reference ? `${message} (Reference: ${reference})` : message;
}

/** Checks that are still waiting or running. "pending" and "queued" had no tab or colour. */
function isActiveStatus(status: string): boolean {
  return status === 'processing' || status === 'analyzing' || status === 'pending' || status === 'queued';
}

function toTime(value?: string): number {
  const time = new Date(value || 0).getTime();
  return Number.isNaN(time) ? 0 : time;
}

/** Status → chip styling. Kept local so job states get real colours instead of the generic badge. */
const STATUS_STYLES: Record<string, { label: string; className: string; dot: string }> = {
  completed: {
    label: 'Completed',
    className: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400',
    dot: 'bg-emerald-500',
  },
  processing: {
    label: 'Processing',
    className: 'border-blue-500/20 bg-blue-500/10 text-blue-700 dark:text-blue-400',
    dot: 'bg-blue-500 animate-pulse',
  },
  analyzing: {
    label: 'Analyzing',
    className: 'border-blue-500/20 bg-blue-500/10 text-blue-700 dark:text-blue-400',
    dot: 'bg-blue-500 animate-pulse',
  },
  pending: {
    label: 'Queued',
    className: 'border-slate-500/15 bg-slate-500/[0.07] text-slate-600 dark:text-slate-300',
    dot: 'bg-slate-400 animate-pulse',
  },
  queued: {
    label: 'Queued',
    className: 'border-slate-500/15 bg-slate-500/[0.07] text-slate-600 dark:text-slate-300',
    dot: 'bg-slate-400 animate-pulse',
  },
  failed: {
    label: 'Failed',
    className: 'border-red-500/20 bg-red-500/10 text-red-700 dark:text-red-400',
    dot: 'bg-red-500',
  },
};

/** Review state → chip styling, including the icon shown next to the label. */
const REVIEW_STYLES: Record<string, { label: string; className: string; Icon: ElementType }> = {
  confirmed: {
    label: 'Confirmed',
    className: 'border-red-500/20 bg-red-500/10 text-red-700 dark:text-red-400',
    Icon: CheckCircle2,
  },
  escalated: {
    label: 'Escalated',
    className: 'border-violet-500/20 bg-violet-500/10 text-violet-700 dark:text-violet-400',
    Icon: ArrowUp,
  },
  needs_review: {
    label: 'Needs review',
    className: 'border-amber-500/20 bg-amber-500/10 text-amber-700 dark:text-amber-400',
    Icon: Eye,
  },
  dismissed: {
    label: 'Dismissed',
    className: 'border-slate-500/20 bg-slate-500/10 text-slate-600 dark:text-slate-300',
    Icon: Ban,
  },
  unreviewed: {
    label: 'Unreviewed',
    className: 'border-slate-500/15 bg-slate-500/[0.07] text-slate-500 dark:text-slate-400',
    Icon: Clock,
  },
};

/** Tinted initials tile so rows are easy to tell apart at a glance. */
const TILE_TONES = [
  'bg-blue-500/10 text-blue-600 dark:text-blue-400',
  'bg-violet-500/10 text-violet-600 dark:text-violet-400',
  'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
  'bg-amber-500/10 text-amber-600 dark:text-amber-400',
  'bg-cyan-500/10 text-cyan-600 dark:text-cyan-400',
  'bg-rose-500/10 text-rose-600 dark:text-rose-400',
];

function tileTone(seed: string): string {
  let hash = 0;
  for (let i = 0; i < seed.length; i++) hash = (hash * 31 + seed.charCodeAt(i)) >>> 0;
  return TILE_TONES[hash % TILE_TONES.length];
}

function initials(name: string): string {
  // Unicode-aware: the old [a-zA-Z0-9] filter turned a name in another script into "??".
  const letters = name.replace(/[^\p{L}\p{N} ]/gu, ' ').trim().split(/\s+/).slice(0, 2);
  if (letters.length === 0 || !letters[0]) return '??';
  return letters.map((part) => Array.from(part)[0]?.toUpperCase() ?? '').join('');
}

function matchesSearch(job: JobItem, query: string): boolean {
  if (!query) return true;
  const needle = query.toLowerCase();
  return [job.assignmentName, job.courseName, job.id, job.name]
    .filter(Boolean)
    .some((value) => String(value).toLowerCase().includes(needle));
}

function normalizeStatus(status?: string): string {
  return String(status || '').toLowerCase();
}

function StatusChip({ status }: { status: string }) {
  const key = normalizeStatus(status);
  const meta =
    STATUS_STYLES[key] ||
    ({
      label: key ? key.charAt(0).toUpperCase() + key.slice(1) : 'Unknown',
      className: 'border-slate-500/15 bg-slate-500/[0.07] text-slate-600 dark:text-slate-300',
      dot: 'bg-slate-400',
    } as const);

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${meta.className}`}
    >
      <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${meta.dot}`} />
      {meta.label}
    </span>
  );
}

function ReviewChip({ status }: { status: string }) {
  const meta = Object.prototype.hasOwnProperty.call(REVIEW_STYLES, status)
    ? REVIEW_STYLES[status]
    : REVIEW_STYLES.unreviewed;
  const { Icon } = meta;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${meta.className}`}
    >
      <Icon size={11} aria-hidden="true" />
      {meta.label}
    </span>
  );
}

/**
 * Export dropdown. The menu is portalled to <body> with fixed positioning
 * because the table lives in a horizontally scrollable, overflow-hidden card —
 * an absolutely positioned menu inside it would be clipped on the last row.
 */
function ExportMenu({ job }: { job: JobItem }) {
  const [open, setOpen] = useState(false);
  const [anchor, setAnchor] = useState<DOMRect | null>(null);
  const [mounted, setMounted] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuId = useId();

  useEffect(() => {
    setMounted(true);
  }, []);

  const close = useCallback(() => setOpen(false), []);

  useEffect(() => {
    if (!open) return;
    function handleOutside(event: PointerEvent) {
      const target = event.target as Node;
      // The menu is portalled to <body>, so it is not inside containerRef —
      // without this check it unmounts on pointerdown, before the link's click
      // event fires, and the download never starts.
      if (containerRef.current?.contains(target) || menuRef.current?.contains(target)) return;
      setOpen(false);
    }
    function handleKey(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setOpen(false);
        // Hand focus back to the button that opened the menu.
        buttonRef.current?.focus();
      }
    }
    // The menu is anchored to viewport coordinates, so scrolling has to move it
    // with its button rather than drop it — Lenis fires scroll events for tiny
    // trackpad deltas, which made a close-on-scroll menu vanish on touch.
    function reanchor() {
      const rect = buttonRef.current?.getBoundingClientRect();
      if (!rect || rect.bottom < 0 || rect.top > window.innerHeight) {
        setOpen(false);
        return;
      }
      setAnchor(rect);
    }
    document.addEventListener('pointerdown', handleOutside);
    document.addEventListener('keydown', handleKey);
    window.addEventListener('resize', reanchor);
    window.addEventListener('scroll', reanchor, { capture: true, passive: true });
    return () => {
      document.removeEventListener('pointerdown', handleOutside);
      document.removeEventListener('keydown', handleKey);
      window.removeEventListener('resize', reanchor);
      window.removeEventListener('scroll', reanchor, { capture: true });
    };
  }, [open]);

  // Move focus into the menu when it opens, so it can be used from the keyboard.
  useEffect(() => {
    if (!open || !anchor) return;
    const frame = window.requestAnimationFrame(() => {
      menuRef.current?.querySelector<HTMLElement>('[role="menuitem"]')?.focus();
    });
    return () => window.cancelAnimationFrame(frame);
  }, [open, anchor === null]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleMenuKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    const entries = Array.from(
      menuRef.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? []
    );
    if (entries.length === 0) return;
    const index = entries.indexOf(document.activeElement as HTMLElement);

    if (event.key === 'ArrowDown') {
      event.preventDefault();
      entries[(index + 1) % entries.length].focus();
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      entries[(index - 1 + entries.length) % entries.length].focus();
    } else if (event.key === 'Home') {
      event.preventDefault();
      entries[0].focus();
    } else if (event.key === 'End') {
      event.preventDefault();
      entries[entries.length - 1].focus();
    } else if (event.key === 'Tab') {
      // The menu is portalled to the end of <body>, so Tab can't continue from the row.
      setOpen(false);
    }
  };

  // Reports only exist for a finished check; for a running or failed one these links went to 404s.
  if (job.status !== 'completed') {
    return (
      <button
        type="button"
        disabled
        aria-label="Export options (available once the check completes)"
        title="Reports are available once the check completes"
        className="inline-flex cursor-not-allowed items-center justify-center rounded-lg border border-slate-200 p-2 text-slate-400 opacity-50 dark:border-slate-800 dark:text-slate-500"
      >
        <MoreHorizontal size={16} aria-hidden="true" />
      </button>
    );
  }

  const id = encodeURIComponent(job.id);
  const items: {
    label: string;
    href: string;
    Icon: ElementType;
    accent?: boolean;
    divider?: boolean;
  }[] = [
    { label: 'HTML report', href: `/report/${id}/download`, Icon: FileText },
    { label: 'PDF report', href: `/report/${id}/download-pdf`, Icon: FileDown },
    { label: 'Committee report', href: `/report/${id}/committee`, Icon: ScrollText },
    { label: 'JSON data', href: `/report/${id}/download-json`, Icon: FileCode2 },
    { label: 'CSV data', href: `/report/${id}/download-csv`, Icon: FileSpreadsheet },
    {
      label: 'Integrity assessment (HTML)',
      href: `/api/reports/integrity-assessment/${id}?format=html`,
      Icon: Shield,
      accent: true,
      divider: true,
    },
    {
      label: 'Integrity assessment (PDF)',
      href: `/api/reports/integrity-assessment/${id}?format=pdf`,
      Icon: ShieldCheck,
      accent: true,
    },
  ];

  const MENU_WIDTH = 256;
  const GAP = 8;
  const MIN_HEIGHT = 220;

  let menuStyle: CSSProperties | undefined;
  if (anchor && mounted) {
    const left = Math.min(
      Math.max(GAP, anchor.right - MENU_WIDTH),
      Math.max(GAP, window.innerWidth - MENU_WIDTH - GAP)
    );
    const spaceBelow = window.innerHeight - anchor.bottom - GAP;
    // main.dashboard-main carries z-10, so the portaled menu needs an explicit
    // z-index of its own or it renders underneath the page content.
    menuStyle =
      spaceBelow >= MIN_HEIGHT
        ? {
            position: 'fixed',
            top: anchor.bottom + GAP,
            left,
            width: MENU_WIDTH,
            maxHeight: spaceBelow,
            zIndex: 1000,
          }
        : {
            position: 'fixed',
            bottom: window.innerHeight - anchor.top + GAP,
            left,
            width: MENU_WIDTH,
            maxHeight: Math.max(160, anchor.top - GAP * 2),
            zIndex: 1000,
          };
  }

  const menu =
    open && anchor && mounted ? (
      <div
        ref={menuRef}
        id={menuId}
        role="menu"
        aria-label={`Export ${job.assignmentName}`}
        onKeyDown={handleMenuKeyDown}
        style={menuStyle}
        className="overflow-y-auto rounded-xl border border-slate-200 bg-white py-1 shadow-xl dark:border-slate-800 dark:bg-slate-950"
      >
        <div
          role="presentation"
          className="px-4 py-2 text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400"
        >
          Export &amp; reports
        </div>
        {items.map((item) => (
          <div key={item.label} role="none">
            {item.divider && (
              <div role="separator" className="my-1 border-t border-slate-200 dark:border-slate-800" />
            )}
            <a
              href={item.href}
              role="menuitem"
              target="_blank"
              rel="noopener noreferrer"
              onClick={close}
              className={`flex items-center gap-2.5 px-4 py-2 text-sm outline-none transition hover:bg-slate-50 focus-visible:bg-slate-100 dark:hover:bg-slate-900 dark:focus-visible:bg-slate-800 ${
                item.accent
                  ? 'font-semibold text-blue-700 dark:text-blue-300'
                  : 'text-slate-700 dark:text-slate-300'
              }`}
            >
              <item.Icon
                size={14}
                aria-hidden="true"
                className={item.accent ? 'text-blue-600 dark:text-blue-400' : 'text-slate-400'}
              />
              <span className="truncate">{item.label}</span>
            </a>
          </div>
        ))}
      </div>
    ) : null;

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        ref={buttonRef}
        onClick={() => {
          const rect = buttonRef.current?.getBoundingClientRect();
          if (rect) setAnchor(rect);
          setOpen((value) => !value);
        }}
        onKeyDown={(event) => {
          if (event.key === 'ArrowDown' && !open) {
            event.preventDefault();
            const rect = buttonRef.current?.getBoundingClientRect();
            if (rect) setAnchor(rect);
            setOpen(true);
          }
        }}
        aria-label={`Export options for ${job.assignmentName}`}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        className={`inline-flex items-center justify-center rounded-lg border border-slate-200 p-2 text-slate-500 transition hover:bg-slate-50 hover:text-slate-700 dark:border-slate-800 dark:text-slate-400 dark:hover:bg-slate-900 dark:hover:text-slate-200 ${
          open ? 'bg-slate-50 text-slate-700 dark:bg-slate-900 dark:text-slate-200' : ''
        }`}
      >
        <MoreHorizontal size={16} aria-hidden="true" />
      </button>

      {mounted && createPortal(menu, document.body)}
    </div>
  );
}

/** Primary "open" action, shared by the desktop row and the mobile card. */
function PersistenceWarning({ text }: { text: string }) {
  return (
    <span title={text} role="img" aria-label={`Warning: ${text}`}>
      <AlertTriangle size={14} className="text-amber-500" aria-hidden="true" />
    </span>
  );
}

/** Compact row used on small screens, mirroring the desktop table's information. */
function HistoryCard({ job }: { job: JobItem }) {
  return (
    <div className="p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <span
            className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-xs font-bold ${tileTone(
              job.assignmentName + job.courseName
            )}`}
          >
            {initials(job.assignmentName)}
          </span>
          <div className="min-w-0">
            <Link
              href={`/results/${encodeURIComponent(job.id)}`}
              className="block truncate text-sm font-semibold text-[var(--text-primary)]"
            >
              {job.assignmentName}
            </Link>
            <div className="mt-0.5 truncate text-xs text-[var(--text-muted)]">{job.courseName}</div>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <ExportMenu job={job} />
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <StatusChip status={job.status} />
        <ReviewChip status={job.reviewStatus} />
        {job.highSimilarityCount > 0 && (
          <span className="inline-flex items-center rounded-full border border-red-500/20 bg-red-500/10 px-2.5 py-1 text-xs font-semibold text-red-700 dark:text-red-400">
            {job.highSimilarityCount} high-risk
          </span>
        )}
        {job.persistenceWarning && <PersistenceWarning text={job.persistenceWarning} />}
      </div>

      {job.persistenceWarning && (
        // No hover on touch screens, so the text is shown rather than left in a tooltip.
        <p className="mt-2 text-xs text-amber-700 dark:text-amber-400">{job.persistenceWarning}</p>
      )}

      <div className="mt-3 flex items-center justify-between gap-3 text-xs text-[var(--text-muted)]">
        <span className="inline-flex items-center gap-1.5" title={formatAbsolute(job.createdAt)}>
          <Clock size={12} aria-hidden="true" />
          {formatDate(job.createdAt)} · {formatClock(job.createdAt)}
        </span>
        <span>
          {job.totalSubmissions} submission{job.totalSubmissions === 1 ? '' : 's'}
        </span>
      </div>
    </div>
  );
}

export default function HistoryPage() {
  const [jobs, setJobs] = useState<JobItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [activeStatus, setActiveStatus] = useState<JobStatus>('ALL');
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>(DEFAULT_SORT_KEY);
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>(DEFAULT_SORT_DIR);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [viewRestored, setViewRestored] = useState(false);
  const requestIdRef = useRef(0);

  // Only the newest request may update state, and a failed refresh keeps the rows already on screen.
  const fetchJobs = useCallback(async (signal?: AbortSignal) => {
    const requestId = ++requestIdRef.current;
    try {
      const response = await apiClient.get('/api/jobs', { signal });
      if (requestId !== requestIdRef.current) return;

      const data = response.data;
      const jobsData: RawJob[] = Array.isArray(data) ? data : Array.isArray(data?.jobs) ? data.jobs : [];

      const transformed = jobsData.map((j) => ({
        id: j.id,
        name: j.name || j.assignment_name || 'Unnamed Job',
        status: normalizeStatus(j.status),
        assignmentName: j.assignment_name || j.name || 'Unnamed Assignment',
        courseName: j.course_name || 'Unknown Course',
        createdAt: j.created_at || '',
        totalSubmissions: Number(j.total_submissions) || 0,
        highSimilarityCount: Number(j.high_similarity_count) || 0,
        reviewStatus: j.review_status || 'unreviewed',
        persistenceWarning: j.persistence_warning || undefined,
      }));

      setJobs(transformed);
      setError(null);
    } catch (err) {
      if (signal?.aborted || requestId !== requestIdRef.current) return;
      setError(describeLoadError(err));
    } finally {
      if (requestId === requestIdRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetchJobs(controller.signal);
    return () => controller.abort();
  }, [fetchJobs]);

  // Poll faster while something is running and pause while the tab is hidden. It used to call
  // the API every 30 seconds regardless.
  const hasActiveJobs = jobs.some((j) => isActiveStatus(j.status));

  useEffect(() => {
    const refreshIfVisible = () => {
      if (document.visibilityState === 'visible') fetchJobs();
    };
    const interval = setInterval(refreshIfVisible, hasActiveJobs ? POLL_ACTIVE_MS : POLL_IDLE_MS);
    document.addEventListener('visibilitychange', refreshIfVisible);
    return () => {
      clearInterval(interval);
      document.removeEventListener('visibilitychange', refreshIfVisible);
    };
  }, [fetchJobs, hasActiveJobs]);

  const refreshNow = useCallback(async () => {
    if (refreshing) return;
    setRefreshing(true);
    try {
      await fetchJobs();
    } finally {
      setRefreshing(false);
    }
  }, [fetchJobs, refreshing]);

  // Restore status, sort and page from the URL (not the search text, which can contain names), so
  // opening a check and pressing Back returns to the same view.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const status = params.get('status');
    if (status && STATUS_TABS.some((tab) => tab.key === status)) setActiveStatus(status as JobStatus);
    const sort = params.get('sort');
    if (sort && SORT_KEYS.includes(sort as SortKey)) setSortKey(sort as SortKey);
    const dir = params.get('dir');
    if (dir === 'asc' || dir === 'desc') setSortDir(dir);
    const size = Number(params.get('size'));
    if (PAGE_SIZES.includes(size)) setPageSize(size);
    const pageParam = Number(params.get('page'));
    if (Number.isInteger(pageParam) && pageParam >= 1) setPage(pageParam);
    setViewRestored(true);
  }, []);

  useEffect(() => {
    if (!viewRestored) return;
    const params = new URLSearchParams(window.location.search);
    const sync = (key: string, value: string | number, fallback: string | number) => {
      if (value === fallback) params.delete(key);
      else params.set(key, String(value));
    };
    sync('status', activeStatus, 'ALL');
    sync('sort', sortKey, DEFAULT_SORT_KEY);
    sync('dir', sortDir, DEFAULT_SORT_DIR);
    sync('size', pageSize, DEFAULT_PAGE_SIZE);
    sync('page', page, 1);
    const query = params.toString();
    const next = `${window.location.pathname}${query ? `?${query}` : ''}`;
    if (next !== `${window.location.pathname}${window.location.search}`) {
      window.history.replaceState(window.history.state, '', next);
    }
  }, [viewRestored, activeStatus, sortKey, sortDir, pageSize, page]);

  const statusCounts = useMemo(() => {
    const counts: Record<JobStatus, number> = {
      ALL: jobs.length,
      COMPLETED: 0,
      PROCESSING: 0,
      FAILED: 0,
    };
    for (const j of jobs) {
      if (j.status === 'completed') counts.COMPLETED += 1;
      else if (isActiveStatus(j.status)) counts.PROCESSING += 1;
      else if (j.status === 'failed') counts.FAILED += 1;
    }
    return counts;
  }, [jobs]);

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    return jobs.filter((j) => {
      if (activeStatus !== 'ALL') {
        if (activeStatus === 'PROCESSING') {
          if (!isActiveStatus(j.status)) return false;
        } else if (j.status !== activeStatus.toLowerCase()) {
          return false;
        }
      }
      if (query && !matchesSearch(j, query)) return false;
      return true;
    });
  }, [jobs, activeStatus, search]);

  const sorted = useMemo(() => {
    const dir = sortDir === 'asc' ? 1 : -1;
    const list = [...filtered];

    list.sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case 'date':
          cmp = toTime(a.createdAt) - toTime(b.createdAt);
          break;
        case 'name':
          cmp = String(a.assignmentName || '').localeCompare(String(b.assignmentName || ''), undefined, {
            numeric: true,
            sensitivity: 'base',
          });
          break;
        case 'submissions':
          cmp = (a.totalSubmissions || 0) - (b.totalSubmissions || 0);
          break;
        case 'highRisk':
          cmp = (a.highSimilarityCount || 0) - (b.highSimilarityCount || 0);
          break;
      }
      if (cmp !== 0) return cmp * dir;
      // Ties (many checks share a submission count or risk) fall back to newest-first, then id.
      const byDate = toTime(b.createdAt) - toTime(a.createdAt);
      return byDate !== 0 ? byDate : a.id.localeCompare(b.id);
    });
    return list;
  }, [filtered, sortKey, sortDir]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const safePage = Math.min(page, totalPages);
  const pageStart = (safePage - 1) * pageSize;
  const visible = sorted.slice(pageStart, pageStart + pageSize);
  const hasActiveFilters = Boolean(search.trim()) || activeStatus !== 'ALL';

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      // A name sorts A–Z first; the numeric and date columns start with the biggest/newest.
      setSortDir(key === 'name' ? 'asc' : 'desc');
    }
    setPage(1);
  };

  const handleSortSelect = (value: string) => {
    const [key, dir] = value.split(':');
    if (SORT_KEYS.includes(key as SortKey) && (dir === 'asc' || dir === 'desc')) {
      setSortKey(key as SortKey);
      setSortDir(dir);
      setPage(1);
    }
  };

  const handleSearch = useCallback((value: string) => {
    setSearch(value);
    setPage(1);
  }, []);

  const handleStatusTab = (key: JobStatus) => {
    setActiveStatus(key);
    setPage(1);
  };

  const clearFilters = () => {
    setSearch('');
    setActiveStatus('ALL');
    setPage(1);
  };

  const renderSortIcon = (column: SortKey) => {
    if (sortKey !== column) return <ArrowUpDown size={13} aria-hidden="true" className="text-slate-400 dark:text-slate-500" />;
    return sortDir === 'asc' ? (
      <ArrowUp size={13} aria-hidden="true" className="text-blue-600 dark:text-blue-400" />
    ) : (
      <ArrowDown size={13} aria-hidden="true" className="text-blue-600 dark:text-blue-400" />
    );
  };

  const renderSortableTh = (
    column: SortKey,
    label: string,
    align: 'left' | 'right' = 'left',
    width?: string
  ) => (
    <th
      scope="col"
      className={`px-4 py-3 ${align === 'right' ? 'text-right' : 'text-left'}`}
      style={width ? { width } : undefined}
      aria-sort={sortKey === column ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
    >
      <button
        type="button"
        onClick={() => handleSort(column)}
        className={`inline-flex items-center gap-1.5 whitespace-nowrap text-[11px] font-bold uppercase tracking-[0.08em] transition ${
          sortKey === column
            ? 'text-[var(--text-primary)]'
            : 'text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'
        }`}
      >
        {label}
        {renderSortIcon(column)}
      </button>
    </th>
  );

  return (
    <DashboardLayout>
      <div className="theme-page-container space-y-6">
        {error && <ErrorState message={error} onRetry={() => fetchJobs()} />}

        <PageHeader
          eyebrow="History"
          title="Plagiarism check history"
          description="Every similarity check with its review state, high-risk count, and one-click exports."
          eyebrowStyle="badge"
          action={
            <Link
              href="/upload"
              className="theme-button-primary inline-flex items-center gap-2 rounded-xl px-5 py-3 text-sm font-semibold transition hover:-translate-y-0.5"
            >
              <Upload size={16} />
              New check
            </Link>
          }
        />

        {/* Toolbar: filters + count on the first row, search on the second so
            neither line wraps unpredictably at intermediate widths. */}
        <div className="theme-card-strong rounded-[24px] px-5 py-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2">
              {STATUS_TABS.map((tab) => (
                <FilterChip
                  key={tab.key}
                  active={activeStatus === tab.key}
                  label={tab.label}
                  count={statusCounts[tab.key]}
                  onClick={() => handleStatusTab(tab.key)}
                  tone={tab.key === 'FAILED' ? 'negative' : tab.key === 'PROCESSING' ? 'warning' : 'neutral'}
                />
              ))}
              {hasActiveFilters && (
                <button
                  type="button"
                  onClick={clearFilters}
                  className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1.5 text-xs font-semibold text-[var(--text-muted)] transition hover:text-[var(--text-primary)]"
                >
                  Clear filters
                </button>
              )}
            </div>

            <div className="flex items-center gap-3">
              <span className="text-sm text-[var(--text-muted)]" aria-live="polite">
                Showing{' '}
                <strong className="font-semibold text-[var(--text-primary)]">
                  {sorted.length === 0 ? 0 : pageStart + 1}–{pageStart + visible.length}
                </strong>{' '}
                of{' '}
                <strong className="font-semibold text-[var(--text-primary)]">{sorted.length}</strong>{' '}
                {sorted.length === 1 ? 'check' : 'checks'}
              </span>

              <button
                type="button"
                onClick={refreshNow}
                disabled={refreshing}
                title="Refresh now (the list also updates automatically)"
                aria-label="Refresh history"
                className="theme-icon-button disabled:opacity-60"
              >
                <RefreshCw size={15} aria-hidden="true" className={refreshing ? 'animate-spin' : ''} />
              </button>
            </div>
          </div>

          <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center">
          <label className="flex w-full items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-[var(--text-muted)] shadow-sm transition focus-within:border-blue-400 focus-within:ring-4 focus-within:ring-blue-500/10 dark:border-slate-800 dark:bg-slate-900 dark:focus-within:border-blue-500 dark:focus-within:ring-blue-500/20 sm:max-w-md">
            <Search size={16} aria-hidden="true" />
            <input
              type="search"
              name="history-search"
              autoComplete="off"
              value={search}
              onChange={(e) => handleSearch(e.target.value)}
              placeholder="Search assignment, course, or ID"
              className="w-full bg-transparent text-[var(--text-primary)] placeholder:text-slate-400 focus:outline-none dark:placeholder:text-slate-500"
              aria-label="Search history"
            />
          </label>

          {/* The sortable table headers are only shown on wide screens; this is the small-screen equivalent. */}
          <select
            value={`${sortKey}:${sortDir}`}
            onChange={(e) => handleSortSelect(e.target.value)}
            aria-label="Sort history"
            className="theme-compact-field h-10 w-full sm:w-auto xl:hidden"
          >
            {SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          </div>
        </div>

        {/* Results */}
        <div className="theme-card-strong overflow-hidden rounded-[24px] shadow-sm">
          {loading ? (
            <div className="p-5">
              <LoadingState label="Loading history…" />
            </div>
          ) : sorted.length === 0 ? (
            <div className="p-5">
              {jobs.length === 0 ? (
                <EmptyState
                  title="No checks yet"
                  description="Run a plagiarism check to see it here with its review state and exports."
                  href="/upload"
                  action="Run a check"
                />
              ) : (
                <div className="theme-card-muted rounded-[20px] px-5 py-10 text-center">
                  <div className="theme-section-title text-base">No checks match your filters</div>
                  <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[var(--text-muted)]">
                    Nothing matches {search.trim() ? `“${search.trim()}”` : 'the current status filter'}
                    {activeStatus !== 'ALL' ? ` in ${STATUS_TABS.find((t) => t.key === activeStatus)?.label}` : ''}.
                  </p>
                  <button
                    type="button"
                    onClick={clearFilters}
                    className="mt-5 inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-blue-300 hover:text-blue-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
                  >
                    Clear filters
                  </button>
                </div>
              )}
            </div>
          ) : (
            <>
              {/* Desktop table */}
              <div className="hidden overflow-x-auto xl:block">
                <table className="w-full min-w-[820px] table-fixed">
                  <caption className="sr-only">Plagiarism check history</caption>
                  <TableHeader>
                    <tr>
                      {renderSortableTh('date', 'Date', 'left', '100px')}
                      {renderSortableTh('name', 'Check', 'left', '190px')}
                      {renderSortableTh('submissions', 'Submissions', 'right', '100px')}
                      {renderSortableTh('highRisk', 'High-risk', 'right', '90px')}
                      <th scope="col" className="whitespace-nowrap px-4 py-3 text-left" style={{ width: '120px' }}>
                        Review
                      </th>
                      {/* Status carries a chip plus an optional persistence warning, so it
                          needs more room than the other badge column. */}
                      <th scope="col" className="whitespace-nowrap px-4 py-3 text-left" style={{ width: '160px' }}>
                        Status
                      </th>
                      {/* Export is an icon-only menu, so the column just holds the button. */}
                      <th scope="col" className="whitespace-nowrap px-4 py-3 text-right" style={{ width: '56px' }}>
                        <span className="sr-only">Actions</span>
                      </th>
                    </tr>
                  </TableHeader>
                  <TableBody>
                    {visible.map((job) => (
                      <TableRow key={job.id}>
                        <td className="px-4 py-4 align-top">
                          <div
                            className="text-sm font-semibold text-[var(--text-primary)]"
                            title={formatAbsolute(job.createdAt)}
                          >
                            {formatDate(job.createdAt)}
                          </div>
                          <div className="mt-0.5 text-xs text-[var(--text-muted)]">
                            {formatClock(job.createdAt)}
                          </div>
                        </td>

                        <td className="px-4 py-4 align-top">
                          <div className="flex items-center gap-3">
                            <span
                              className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-xs font-bold ${tileTone(
                                job.assignmentName + job.courseName
                              )}`}
                            >
                              {initials(job.assignmentName)}
                            </span>
                            <div className="min-w-0">
                              <Link
                                href={`/results/${encodeURIComponent(job.id)}`}
                                className="block truncate text-sm font-semibold leading-5 text-[var(--text-primary)] hover:text-blue-600 dark:hover:text-blue-400"
                                title={job.assignmentName}
                              >
                                {job.assignmentName}
                              </Link>
                              <div className="mt-0.5 flex items-center gap-2 text-xs text-[var(--text-muted)]">
                                <span className="truncate">{job.courseName}</span>
                                <span className="hidden shrink-0 font-mono opacity-70 xl:inline">
                                  {job.id.slice(0, 8)}
                                </span>
                              </div>
                            </div>
                          </div>
                        </td>

                        <td className="px-4 py-4 text-right align-top">
                          <div className="text-sm font-semibold text-[var(--text-primary)]">
                            {job.totalSubmissions}
                          </div>
                        </td>

                        <td className="px-4 py-4 text-right align-top">
                          {job.highSimilarityCount > 0 ? (
                            <span
                              className="inline-flex items-center rounded-full border border-red-500/20 bg-red-500/10 px-2.5 py-1 text-xs font-bold text-red-700 dark:text-red-400"
                              title={`${job.highSimilarityCount} pair(s) above the high-similarity threshold`}
                            >
                              {job.highSimilarityCount}
                            </span>
                          ) : (
                            <span className="text-sm text-slate-400 dark:text-slate-600">—</span>
                          )}
                        </td>

                        <td className="px-4 py-4 align-top">
                          <ReviewChip status={job.reviewStatus} />
                        </td>

                        <td className="px-4 py-4 align-top">
                          <div className="flex items-center gap-2">
                            <StatusChip status={job.status} />
                            {job.persistenceWarning && <PersistenceWarning text={job.persistenceWarning} />}
                          </div>
                        </td>

                        <td className="px-4 py-4 align-top">
                          {/* The assignment name above is already the link to the review
                              workspace, so this column holds only the export menu. */}
                          <div className="flex items-center justify-end">
                            <ExportMenu job={job} />
                          </div>
                        </td>
                      </TableRow>
                    ))}
                  </TableBody>
                </table>
              </div>

              {/* Mobile cards */}
              <div className="divide-y divide-[color:var(--border)] xl:hidden">
                {visible.map((job) => (
                  <HistoryCard key={job.id} job={job} />
                ))}
              </div>
            </>
          )}

          {!loading && sorted.length > 0 && (
            <div className="flex flex-col gap-3 border-t border-[color:var(--border)] px-5 py-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
                <label htmlFor="history-page-size">Rows per page</label>
                <select
                  id="history-page-size"
                  value={pageSize}
                  onChange={(e) => {
                    setPageSize(Number(e.target.value));
                    setPage(1);
                  }}
                  className="theme-compact-field h-8 w-auto"
                >
                  {PAGE_SIZES.map((size) => (
                    <option key={size} value={size}>
                      {size}
                    </option>
                  ))}
                </select>
              </div>

              <nav aria-label="Pagination" className="flex items-center gap-1">
                <button
                  type="button"
                  disabled={safePage <= 1}
                  // Based on the visible page: after the list shrank, the stored page could exceed it
                  // and "Previous" appeared to do nothing.
                  onClick={() => setPage(Math.max(1, safePage - 1))}
                  aria-label="Previous page"
                  className="theme-icon-button"
                >
                  <ChevronLeft size={15} aria-hidden="true" />
                </button>
                {pageNumbers(safePage, totalPages).map((num, i) =>
                  num === '…' ? (
                    <span key={`gap-${i}`} className="px-1 text-xs text-slate-400">
                      …
                    </span>
                  ) : (
                    <button
                      key={num}
                      type="button"
                      onClick={() => setPage(Number(num))}
                      aria-label={`Page ${num}`}
                      aria-current={safePage === num ? 'page' : undefined}
                      className={`inline-flex h-8 w-8 items-center justify-center rounded-lg text-xs font-semibold transition ${
                        safePage === num
                          ? 'bg-blue-600 text-white shadow-sm shadow-blue-500/25'
                          : 'border border-slate-200 text-slate-600 hover:bg-slate-50 dark:border-slate-800 dark:text-slate-300 dark:hover:bg-slate-900'
                      }`}
                    >
                      {num}
                    </button>
                  )
                )}
                <button
                  type="button"
                  disabled={safePage >= totalPages}
                  onClick={() => setPage(Math.min(totalPages, safePage + 1))}
                  aria-label="Next page"
                  className="theme-icon-button"
                >
                  <ChevronRight size={15} aria-hidden="true" />
                </button>
              </nav>
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}

function startOfDay(date: Date): number {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
}

/**
 * Calendar-day based, and the year is shown once a check is from a different year. History spans
 * years, so "Mar 4" alone was ambiguous; a future timestamp (clock skew) used to read "-1d ago".
 */
function formatDate(value?: string): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  const now = new Date();
  const diffDays = Math.round((startOfDay(now) - startOfDay(date)) / (1000 * 60 * 60 * 24));
  if (diffDays <= 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays}d ago`;
  const options: Intl.DateTimeFormatOptions =
    date.getFullYear() === now.getFullYear()
      ? { month: 'short', day: 'numeric' }
      : { month: 'short', day: 'numeric', year: 'numeric' };
  return new Intl.DateTimeFormat('en-US', options).format(date);
}

/** Time of day shown under the relative date so two checks on the same day stay apart. */
function formatClock(value?: string): string {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: '2-digit' }).format(date);
}

/** Full timestamp for tooltips. */
function formatAbsolute(value?: string): string {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('en-US', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

function pageNumbers(current: number, total: number): (number | '…')[] {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }
  const pages: (number | '…')[] = [1];
  const start = Math.max(2, current - 1);
  const end = Math.min(total - 1, current + 1);
  if (start > 2) pages.push('…');
  for (let i = start; i <= end; i++) pages.push(i);
  if (end < total - 1) pages.push('…');
  pages.push(total);
  return pages;
}
