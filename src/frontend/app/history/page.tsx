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
  FileSearch,
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
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { CSSProperties, ElementType } from 'react';
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
  const letters = name.replace(/[^a-zA-Z0-9 ]/g, ' ').trim().split(/\s+/).slice(0, 2);
  if (letters.length === 0 || !letters[0]) return '??';
  return letters.map((part) => part[0]?.toUpperCase() ?? '').join('');
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
      <span className={`h-1.5 w-1.5 rounded-full ${meta.dot}`} />
      {meta.label}
    </span>
  );
}

function ReviewChip({ status }: { status: string }) {
  const meta = REVIEW_STYLES[status] || REVIEW_STYLES.unreviewed;
  const { Icon } = meta;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${meta.className}`}
    >
      <Icon size={11} />
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

  useEffect(() => {
    setMounted(true);
  }, []);

  const close = useCallback(() => setOpen(false), []);

  useEffect(() => {
    if (!open) return;
    function handleOutside(event: MouseEvent) {
      const target = event.target as Node;
      // The menu is portalled to <body>, so it is not inside containerRef —
      // without this check it unmounts on mousedown, before the link's click
      // event fires, and the download never starts.
      if (containerRef.current?.contains(target) || menuRef.current?.contains(target)) return;
      setOpen(false);
    }
    function handleKey(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false);
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
    document.addEventListener('mousedown', handleOutside);
    document.addEventListener('keydown', handleKey);
    window.addEventListener('resize', reanchor);
    window.addEventListener('scroll', reanchor, { capture: true, passive: true });
    return () => {
      document.removeEventListener('mousedown', handleOutside);
      document.removeEventListener('keydown', handleKey);
      window.removeEventListener('resize', reanchor);
      window.removeEventListener('scroll', reanchor, { capture: true });
    };
  }, [open]);

  const items: {
    label: string;
    href: string;
    Icon: ElementType;
    accent?: boolean;
    divider?: boolean;
  }[] = [
    { label: 'HTML report', href: `/report/${job.id}/download`, Icon: FileText },
    { label: 'PDF report', href: `/report/${job.id}/download-pdf`, Icon: FileDown },
    { label: 'Committee report', href: `/report/${job.id}/committee`, Icon: ScrollText },
    { label: 'JSON data', href: `/report/${job.id}/download-json`, Icon: FileCode2 },
    { label: 'CSV data', href: `/report/${job.id}/download-csv`, Icon: FileSpreadsheet },
    {
      label: 'Integrity assessment (HTML)',
      href: `/api/reports/integrity-assessment/${job.id}?format=html`,
      Icon: Shield,
      accent: true,
      divider: true,
    },
    {
      label: 'Integrity assessment (PDF)',
      href: `/api/reports/integrity-assessment/${job.id}?format=pdf`,
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
        style={menuStyle}
        className="overflow-y-auto rounded-xl border border-slate-200 bg-white py-1 shadow-xl dark:border-slate-800 dark:bg-slate-950"
      >
        <div className="px-4 py-2 text-[10px] font-bold uppercase tracking-[0.14em] text-slate-400 dark:text-slate-500">
          Export &amp; reports
        </div>
        {items.map((item) => (
          <div key={item.label}>
            {item.divider && (
              <div className="my-1 border-t border-slate-200 dark:border-slate-800" />
            )}
            <a
              href={item.href}
              target="_blank"
              rel="noopener noreferrer"
              onClick={close}
              className={`flex items-center gap-2.5 px-4 py-2 text-sm transition hover:bg-slate-50 dark:hover:bg-slate-900 ${
                item.accent
                  ? 'font-semibold text-blue-700 dark:text-blue-300'
                  : 'text-slate-700 dark:text-slate-300'
              }`}
            >
              <item.Icon
                size={14}
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
        aria-label="Export options"
        aria-expanded={open}
        className={`inline-flex items-center justify-center rounded-lg border border-slate-200 p-2 text-slate-500 transition hover:bg-slate-50 hover:text-slate-700 dark:border-slate-800 dark:text-slate-400 dark:hover:bg-slate-900 dark:hover:text-slate-200 ${
          open ? 'bg-slate-50 text-slate-700 dark:bg-slate-900 dark:text-slate-200' : ''
        }`}
      >
        <MoreHorizontal size={16} />
      </button>

      {mounted && createPortal(menu, document.body)}
    </div>
  );
}

/** Primary "open" action, shared by the desktop row and the mobile card. */
function OpenLink({ job }: { job: JobItem }) {
  return (
    <Link
      href={`/results/${job.id}`}
      className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:border-blue-300 hover:text-blue-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-blue-500/40 dark:hover:text-blue-300"
    >
      Open
      <FileSearch size={13} />
    </Link>
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
              href={`/results/${job.id}`}
              className="block truncate text-sm font-semibold text-[var(--text-primary)]"
            >
              {job.assignmentName}
            </Link>
            <div className="mt-0.5 truncate text-xs text-[var(--text-muted)]">{job.courseName}</div>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <OpenLink job={job} />
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
        {job.persistenceWarning && (
          <span title={job.persistenceWarning}>
            <AlertTriangle size={14} className="text-amber-500" />
          </span>
        )}
      </div>

      <div className="mt-3 flex items-center justify-between gap-3 text-xs text-[var(--text-muted)]">
        <span className="inline-flex items-center gap-1.5" title={formatAbsolute(job.createdAt)}>
          <Clock size={12} />
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
  const [sortKey, setSortKey] = useState<SortKey>('date');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  const fetchJobs = useCallback(async () => {
    try {
      const response = await apiClient.get('/api/jobs');
      const jobsData = (response.data?.jobs || []) as RawJob[];

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
      console.error('Failed to fetch jobs:', err);
      setError(
        err instanceof Error ? err.message : 'Failed to load history. Please try again.'
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(fetchJobs, 30000);
    return () => clearInterval(interval);
  }, [fetchJobs]);

  const refreshNow = useCallback(async () => {
    setRefreshing(true);
    try {
      await fetchJobs();
    } finally {
      setRefreshing(false);
    }
  }, [fetchJobs]);

  const statusCounts = useMemo(() => {
    const counts: Record<JobStatus, number> = {
      ALL: jobs.length,
      COMPLETED: 0,
      PROCESSING: 0,
      FAILED: 0,
    };
    for (const j of jobs) {
      if (j.status === 'completed') counts.COMPLETED += 1;
      else if (j.status === 'processing' || j.status === 'analyzing') counts.PROCESSING += 1;
      else if (j.status === 'failed') counts.FAILED += 1;
    }
    return counts;
  }, [jobs]);

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    return jobs.filter((j) => {
      if (activeStatus !== 'ALL') {
        if (activeStatus === 'PROCESSING') {
          if (j.status !== 'processing' && j.status !== 'analyzing') return false;
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
          cmp =
            new Date(a.createdAt || 0).getTime() - new Date(b.createdAt || 0).getTime();
          break;
        case 'name':
          cmp = String(a.assignmentName || '').localeCompare(
            String(b.assignmentName || '')
          );
          break;
        case 'submissions':
          cmp = (a.totalSubmissions || 0) - (b.totalSubmissions || 0);
          break;
        case 'highRisk':
          cmp = (a.highSimilarityCount || 0) - (b.highSimilarityCount || 0);
          break;
      }
      return cmp * dir;
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
      setSortDir('desc');
    }
    setPage(1);
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
    if (sortKey !== column) return <ArrowUpDown size={13} className="text-slate-400 dark:text-slate-500" />;
    return sortDir === 'asc' ? (
      <ArrowUp size={13} className="text-blue-600 dark:text-blue-400" />
    ) : (
      <ArrowDown size={13} className="text-blue-600 dark:text-blue-400" />
    );
  };

  const renderSortableTh = (
    column: SortKey,
    label: string,
    align: 'left' | 'right' = 'left',
    width?: string
  ) => (
    <th
      className={`px-4 py-3 ${align === 'right' ? 'text-right' : 'text-left'}`}
      style={width ? { width } : undefined}
      aria-sort={sortKey === column ? (sortDir === 'asc' ? 'ascending' : 'descending') : undefined}
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
        {error && <ErrorState message={error} onRetry={fetchJobs} />}

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
              <span className="text-sm text-[var(--text-muted)]">
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
                title="Refresh now (also refreshes every 30 seconds)"
                aria-label="Refresh history"
                className="theme-icon-button"
              >
                <RefreshCw size={15} className={refreshing ? 'animate-spin' : ''} />
              </button>
            </div>
          </div>

          <label className="mt-3 flex w-full items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-[var(--text-muted)] shadow-sm transition focus-within:border-blue-400 focus-within:ring-4 focus-within:ring-blue-500/10 dark:border-slate-800 dark:bg-slate-900 dark:focus-within:border-blue-500 dark:focus-within:ring-blue-500/20 sm:max-w-md">
            <Search size={16} />
            <input
              type="search"
              value={search}
              onChange={(e) => handleSearch(e.target.value)}
              placeholder="Search assignment, course, or ID"
              className="w-full bg-transparent text-[var(--text-primary)] placeholder:text-slate-400 focus:outline-none dark:placeholder:text-slate-500"
              aria-label="Search history"
            />
          </label>
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
                <table className="w-full min-w-[880px] table-fixed">
                  <TableHeader>
                    <tr>
                      {renderSortableTh('date', 'Date', 'left', '100px')}
                      {renderSortableTh('name', 'Check')}
                      {renderSortableTh('submissions', 'Submissions', 'right', '110px')}
                      {renderSortableTh('highRisk', 'High-risk', 'right', '95px')}
                      <th className="whitespace-nowrap px-4 py-3 text-left" style={{ width: '130px' }}>
                        Review
                      </th>
                      <th className="whitespace-nowrap px-4 py-3 text-left" style={{ width: '125px' }}>
                        Status
                      </th>
                      <th className="whitespace-nowrap px-4 py-3 text-right" style={{ width: '118px' }}>
                        Actions
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
                                href={`/results/${job.id}`}
                                className="block break-words text-sm font-semibold leading-5 text-[var(--text-primary)] hover:text-blue-600 dark:hover:text-blue-400"
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
                            {job.persistenceWarning && (
                              <span title={job.persistenceWarning}>
                                <AlertTriangle size={14} className="text-amber-500" />
                              </span>
                            )}
                          </div>
                        </td>

                        <td className="px-4 py-4 align-top">
                          <div className="flex items-center justify-end gap-2">
                            <OpenLink job={job} />
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
                <span>Rows per page</span>
                <select
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

              <div className="flex items-center gap-1">
                <button
                  type="button"
                  disabled={safePage <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  aria-label="Previous page"
                  className="theme-icon-button"
                >
                  <ChevronLeft size={15} />
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
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  aria-label="Next page"
                  className="theme-icon-button"
                >
                  <ChevronRight size={15} />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}

function formatDate(value?: string): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  const now = new Date();
  const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));
  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays}d ago`;
  return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(date);
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
