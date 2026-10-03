'use client';

import DashboardLayout from '@/components/DashboardLayout';
import {
  CardHeader,
  FilterChip,
  PageHeader,
  RiskBadge,
  StatusBadge,
} from '@/components/saas/SaaSPrimitives';
import { apiClient } from '@/lib/apiClient';
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  Inbox,
  Search,
} from 'lucide-react';
import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';

type CaseStatus = 'OPEN' | 'UNDER_REVIEW' | 'ESCALATED' | 'CLOSED';
type SortKey = 'risk' | 'status' | 'course' | 'updated';
type SortDir = 'asc' | 'desc';

type CaseItem = {
  id: string;
  title: string;
  /** Raw value from the API, passed to StatusBadge as before. */
  status: string;
  /** Upper-cased copy used for counts, filtering and sorting. */
  statusKey: string;
  priority: string;
  course?: string;
  assignment?: string;
  risk?: number;
  reviewer?: string;
  updatedAt?: string;
};

type RawCase = {
  id: string;
  title: string;
  status?: string;
  priority?: string;
  course?: string;
  updated_at?: string;
  created_at?: string;
  assignment?: { title?: string; course_name?: string };
  investigator?: { name?: string };
};

// NOTE: this is a stand-in, not a measured score. The list endpoint doesn't
// return a similarity/risk value, so "Risk" is derived from case priority.
const PRIORITY_RISK: Record<string, number> = {
  URGENT: 97,
  HIGH: 92,
  MEDIUM: 72,
  LOW: 40,
};

const STATUS_TABS: { key: CaseStatus | 'ALL'; label: string }[] = [
  { key: 'ALL', label: 'All' },
  { key: 'OPEN', label: 'Open' },
  { key: 'UNDER_REVIEW', label: 'Under Review' },
  { key: 'ESCALATED', label: 'Escalated' },
  { key: 'CLOSED', label: 'Closed' },
];

const STATUS_ORDER: Record<string, number> = {
  OPEN: 0,
  UNDER_REVIEW: 1,
  ESCALATED: 2,
  CLOSED: 3,
};

const SORT_KEYS: SortKey[] = ['risk', 'status', 'course', 'updated'];
const SORT_LABELS: Record<SortKey, string> = {
  risk: 'risk',
  status: 'status',
  course: 'course',
  updated: 'last updated',
};

const PAGE_SIZES = [10, 25, 50];
const CASE_LIMIT = 1000;

const DEFAULT_SORT_KEY: SortKey = 'risk';
const DEFAULT_SORT_DIR: SortDir = 'desc';
const DEFAULT_PAGE_SIZE = 25;

// ─── Helpers ───────────────────────────────────────────────────────────────────

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
    message = 'You don’t have permission to view cases.';
  } else {
    message = 'Failed to load cases. Please try again.';
  }

  return reference ? `${message} (Reference: ${reference})` : message;
}

function toTime(value?: string): number {
  const time = new Date(value || 0).getTime();
  return Number.isNaN(time) ? 0 : time;
}

function matchesSearch(caseItem: CaseItem, query: string): boolean {
  if (!query) return true;
  const needle = query.toLowerCase();
  return [
    caseItem.title,
    caseItem.course,
    caseItem.assignment,
    caseItem.reviewer,
    caseItem.status,
    caseItem.priority,
    caseItem.id,
  ]
    .filter(Boolean)
    .some((value) => String(value).toLowerCase().includes(needle));
}

function startOfDay(date: Date): number {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
}

/** Calendar-day based; a future timestamp (clock skew) shows "Today" rather than "-1d ago". */
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

function formatFullDate(value?: string): string | undefined {
  if (!value) return undefined;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return undefined;
  return new Intl.DateTimeFormat('en-US', { dateStyle: 'medium', timeStyle: 'short' }).format(date);
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

function CaseRowSkeleton() {
  return (
    <tr>
      <td className="px-5 py-4">
        <div className="h-6 w-20 animate-pulse rounded-full bg-slate-200 dark:bg-slate-800" />
      </td>
      <td className="px-5 py-4">
        <div className="h-4 w-36 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
        <div className="mt-2 h-3 w-48 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
      </td>
      <td className="px-5 py-4">
        <div className="h-4 w-40 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
      </td>
      <td className="px-5 py-4">
        <div className="h-6 w-16 animate-pulse rounded-full bg-slate-200 dark:bg-slate-800" />
      </td>
      <td className="px-5 py-4">
        <div className="h-4 w-28 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
      </td>
      <td className="px-5 py-4">
        <div className="h-4 w-20 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
      </td>
      <td className="px-5 py-4">
        <div className="flex justify-end">
          <div className="h-9 w-24 animate-pulse rounded-xl bg-slate-200 dark:bg-slate-800" />
        </div>
      </td>
    </tr>
  );
}

// ─── Page ──────────────────────────────────────────────────────────────────────

export default function CasesQueuePage() {
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [truncated, setTruncated] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  // Filter / sort / pagination state
  const [activeStatus, setActiveStatus] = useState<CaseStatus | 'ALL'>('ALL');
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>(DEFAULT_SORT_KEY);
  const [sortDir, setSortDir] = useState<SortDir>(DEFAULT_SORT_DIR);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [viewRestored, setViewRestored] = useState(false);

  useEffect(() => {
    const controller = new AbortController();

    const fetchCases = async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await apiClient.get('/api/cases', {
          params: { limit: CASE_LIMIT },
          signal: controller.signal,
        });
        const data = response.data;
        const casesData: RawCase[] = Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : [];

        // Transform API response to match UI expectations
        const transformedCases: CaseItem[] = casesData.map((c) => {
          const status = c.status || 'OPEN';
          const priority = c.priority || 'MEDIUM';
          return {
            id: c.id,
            title: c.title,
            status,
            statusKey: status.toUpperCase(),
            priority,
            course: c.assignment?.course_name || c.course || 'Unknown Course',
            assignment: c.assignment?.title || c.title,
            risk: PRIORITY_RISK[priority.toUpperCase()] ?? 72,
            reviewer: c.investigator?.name || 'Unassigned',
            updatedAt: c.updated_at || c.created_at,
          };
        });

        setCases(transformedCases);
        // The request is capped and not paged, so a full page means there may be more.
        setTruncated(casesData.length >= CASE_LIMIT);
      } catch (err) {
        if (controller.signal.aborted) return;
        setError(describeLoadError(err));
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    };

    fetchCases();
    return () => controller.abort();
  }, [reloadKey]);

  // Restore the view (not the search text, which can contain names) from the URL once,
  // so opening a case and pressing Back lands on the same tab, sort and page.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);

    const status = params.get('status');
    if (status && STATUS_TABS.some((tab) => tab.key === status)) {
      setActiveStatus(status as CaseStatus | 'ALL');
    }
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

  // Status tab counts from the full data set
  const statusCounts = useMemo(() => {
    const counts: Record<CaseStatus | 'ALL', number> = {
      ALL: cases.length,
      OPEN: 0,
      UNDER_REVIEW: 0,
      ESCALATED: 0,
      CLOSED: 0,
    };
    for (const c of cases) {
      if (c.statusKey in counts) counts[c.statusKey as CaseStatus] += 1;
    }
    return counts;
  }, [cases]);

  // Apply status filter + live search
  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    return cases.filter((c) => {
      // statusKey, so the filter agrees with the tab counts even if the API's casing varies.
      if (activeStatus !== 'ALL' && c.statusKey !== activeStatus) return false;
      if (query && !matchesSearch(c, query)) return false;
      return true;
    });
  }, [cases, activeStatus, search]);

  // Sort the filtered list
  const sorted = useMemo(() => {
    const dir = sortDir === 'asc' ? 1 : -1;
    const list = [...filtered];

    list.sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case 'risk':
          cmp = (a.risk || 0) - (b.risk || 0);
          break;
        case 'status':
          cmp = (STATUS_ORDER[a.statusKey] ?? 99) - (STATUS_ORDER[b.statusKey] ?? 99);
          break;
        case 'course':
          cmp = String(a.course || '').localeCompare(String(b.course || ''), undefined, {
            numeric: true,
            sensitivity: 'base',
          });
          break;
        case 'updated':
          cmp = toTime(a.updatedAt) - toTime(b.updatedAt);
          break;
      }
      if (cmp !== 0) return cmp * dir;

      // Risk and status have only a few distinct values; break ties newest-first
      // (then by id) so the order is stable instead of whatever the API returned.
      const byUpdated = toTime(b.updatedAt) - toTime(a.updatedAt);
      return byUpdated !== 0 ? byUpdated : a.id.localeCompare(b.id);
    });
    return list;
  }, [filtered, sortKey, sortDir]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const safePage = Math.min(page, totalPages);
  const pageStart = (safePage - 1) * pageSize;
  const visible = sorted.slice(pageStart, pageStart + pageSize);

  // If the list shrinks (e.g. after a reload) pull the stored page back into range.
  useEffect(() => {
    if (!loading && page > totalPages) setPage(totalPages);
  }, [loading, page, totalPages]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir(key === 'status' ? 'asc' : 'desc');
    }
    setPage(1);
  };

  const handleSearch = (value: string) => {
    setSearch(value);
    setPage(1);
  };

  const handleStatusTab = (key: CaseStatus | 'ALL') => {
    setActiveStatus(key);
    setPage(1);
  };

  const renderSortIcon = (column: SortKey) => {
    if (sortKey !== column) return <ArrowUpDown size={13} className="text-slate-400 dark:text-slate-500" aria-hidden="true" />;
    return sortDir === 'asc' ? (
      <ArrowUp size={13} className="text-blue-600 dark:text-blue-400" aria-hidden="true" />
    ) : (
      <ArrowDown size={13} className="text-blue-600 dark:text-blue-400" aria-hidden="true" />
    );
  };

  const renderSortableTh = (
    column: SortKey,
    label: string,
    className = ''
  ) => (
    <th
      scope="col"
      className={`px-5 py-3 text-left ${className}`}
      aria-sort={sortKey === column ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
    >
      <button
        type="button"
        onClick={() => handleSort(column)}
        className={`inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.16em] transition ${
          sortKey === column
            ? 'text-slate-900 dark:text-white'
            : 'text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'
        }`}
      >
        {label}
        {renderSortIcon(column)}
      </button>
    </th>
  );

  const tableHeader = (
    <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500 dark:bg-slate-900/80 dark:text-slate-400">
      <tr>
        {/* Status was the only sortable-by-design column without a sort control. */}
        {renderSortableTh('status', 'Status')}
        {renderSortableTh('course', 'Course')}
        <th scope="col" className="px-5 py-3 text-left">
          Pair
        </th>
        {renderSortableTh('risk', 'Risk')}
        <th scope="col" className="px-5 py-3 text-left">
          Assigned reviewer
        </th>
        {renderSortableTh('updated', 'Updated', 'text-right')}
        <th scope="col" className="px-5 py-3 text-right">
          <span className="sr-only">Actions</span>
        </th>
      </tr>
    </thead>
  );

  const isFiltered = Boolean(search) || activeStatus !== 'ALL';

  return (
    <DashboardLayout>
      <div className="theme-page-container space-y-6">
        <PageHeader
          eyebrow="Cases"
          eyebrowStyle="badge"
          title="An inbox for academic integrity review."
          description="Teaching teams can assign, review, dismiss, and export cases without digging through raw tool output."
          action={
            <label className="flex h-10 w-full items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-500 shadow-sm transition focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 lg:w-80">
              <Search size={16} className="text-slate-400" aria-hidden="true" />
              <input
                type="search"
                name="case-search"
                value={search}
                onChange={(e) => handleSearch(e.target.value)}
                placeholder="Search cases, courses, reviewers"
                autoComplete="off"
                spellCheck={false}
                className="w-full bg-transparent text-slate-900 placeholder:text-slate-400 focus:outline-none dark:text-white dark:placeholder:text-slate-500"
                aria-label="Search cases"
              />
            </label>
          }
        />

        {error && (
          <div
            role="alert"
            className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300"
          >
            <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
            <span className="flex-1">{error}</span>
            <button
              type="button"
              onClick={() => setReloadKey((key) => key + 1)}
              className="inline-flex h-9 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
            >
              Try again
            </button>
          </div>
        )}

        {truncated && !error && (
          <div
            role="status"
            className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-300"
          >
            <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
            <span>
              Only the first {CASE_LIMIT.toLocaleString('en-US')} cases are loaded, so the queue and the counts below
              may be incomplete.
            </span>
          </div>
        )}

        {/* Status tabs */}
        <div className="flex flex-wrap items-center gap-2">
          {STATUS_TABS.map((tab) => (
            <FilterChip
              key={tab.key}
              active={activeStatus === tab.key}
              label={tab.label}
              count={statusCounts[tab.key]}
              tone={(tab.key === 'OPEN' || tab.key === 'ALL') && statusCounts[tab.key] > 0 ? 'negative' : 'neutral'}
              onClick={() => handleStatusTab(tab.key)}
            />
          ))}
        </div>

        <section className="overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
          <div className="px-6 pt-6 lg:px-7 lg:pt-7">
            <CardHeader
              title="Queue"
              description={`Sorted by ${SORT_LABELS[sortKey]}, ${sortDir === 'asc' ? 'ascending' : 'descending'}.`}
              action={
                <div className="flex items-center gap-3 text-sm text-slate-500 dark:text-slate-400">
                  <span aria-live="polite">
                    Showing{' '}
                    <strong className="font-semibold text-slate-900 dark:text-white">
                      {sorted.length === 0 ? 0 : pageStart + 1}–{pageStart + visible.length}
                    </strong>{' '}
                    of <strong className="font-semibold text-slate-900 dark:text-white">{sorted.length}</strong>{' '}
                    {sorted.length === 1 ? 'case' : 'cases'}
                    {isFiltered ? <span className="text-slate-400 dark:text-slate-500"> (filtered)</span> : null}
                  </span>
                </div>
              }
            />
          </div>
          <div className="overflow-x-auto">
            {loading ? (
              <table className="w-full min-w-[900px] text-left">
                <caption className="sr-only">Case queue</caption>
                {tableHeader}
                <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                  {Array.from({ length: 5 }).map((_, i) => <CaseRowSkeleton key={i} />)}
                </tbody>
              </table>
            ) : error && cases.length === 0 ? (
              // A failed load must not look like "no cases yet".
              <div className="px-5 py-12 lg:px-7">
                <div
                  role="alert"
                  className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300"
                >
                  <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
                  <span className="flex-1">{error}</span>
                  <button
                    type="button"
                    onClick={() => setReloadKey((key) => key + 1)}
                    className="inline-flex h-9 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
                  >
                    Try again
                  </button>
                </div>
              </div>
            ) : sorted.length === 0 ? (
              <div className="px-5 py-16 text-center">
                <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-slate-100 text-slate-500 dark:bg-slate-900 dark:text-slate-400">
                  <Inbox size={22} aria-hidden="true" />
                </div>
                <h3 className="mt-4 text-base font-semibold text-slate-900 dark:text-white">No cases found</h3>
                <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500 dark:text-slate-400">
                  {cases.length === 0
                    ? 'Run an AI detection or similarity analysis to create cases.'
                    : 'No cases match the current filters or search.'}
                </p>
              </div>
            ) : (
              <table className="w-full min-w-[900px] text-left">
                <caption className="sr-only">Case queue</caption>
                {tableHeader}
                <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                  {visible.map((item) => (
                    <tr key={item.id} className="transition-colors hover:bg-slate-50 dark:hover:bg-slate-900/50">
                      <td className="px-5 py-4">
                        <StatusBadge status={item.status} />
                      </td>
                      <td className="px-5 py-4">
                        <div className="truncate font-medium text-slate-900 dark:text-white">{item.course}</div>
                        <div className="mt-0.5 truncate text-sm text-slate-500 dark:text-slate-400">{item.assignment}</div>
                      </td>
                      <td className="px-5 py-4">
                        <div className="truncate font-medium text-slate-900 dark:text-white">{item.title}</div>
                      </td>
                      <td className="px-5 py-4">
                        <RiskBadge value={item.risk || 50} />
                      </td>
                      <td className="px-5 py-4 text-sm text-slate-600 dark:text-slate-400">{item.reviewer}</td>
                      <td className="px-5 py-4 text-right text-xs text-slate-500 dark:text-slate-400">
                        <span title={formatFullDate(item.updatedAt)}>{formatDate(item.updatedAt)}</span>
                      </td>
                      <td className="px-5 py-4 text-right">
                        {/* Link keeps client-side navigation; a plain <a> reloaded the whole app. */}
                        <Link
                          href={`/cases/${encodeURIComponent(item.id)}`}
                          aria-label={`Open case ${item.title}`}
                          className="text-sm font-semibold text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
                        >
                          Open
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Pagination footer */}
          {!loading && sorted.length > 0 && (
            <div className="flex flex-col gap-3 border-t border-slate-200 px-6 py-3.5 dark:border-slate-800 sm:flex-row sm:items-center sm:justify-between lg:px-7">
              <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                <label htmlFor="cases-page-size">Rows per page</label>
                <select
                  id="cases-page-size"
                  value={pageSize}
                  onChange={(e) => {
                    setPageSize(Number(e.target.value));
                    setPage(1);
                  }}
                  className="h-8 w-auto rounded-lg border border-slate-200 bg-white px-2 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white"
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
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  aria-label="Previous page"
                  className="theme-icon-button"
                >
                  <ChevronLeft size={15} aria-hidden="true" />
                </button>
                {pageNumbers(safePage, totalPages).map((num, i) =>
                  num === '…' ? (
                    <span key={`gap-${i}`} className="px-1 text-xs text-slate-400 dark:text-slate-500" aria-hidden="true">
                      …
                    </span>
                  ) : (
                    <button
                      key={num}
                      type="button"
                      onClick={() => setPage(Number(num))}
                      aria-label={`Page ${num}`}
                      aria-current={safePage === num ? 'page' : undefined}
                      className={`inline-flex h-8 w-8 items-center justify-center rounded-md text-xs font-semibold transition ${
                        safePage === num
                          ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-950'
                          : 'border border-slate-200 text-slate-600 hover:bg-slate-50 dark:border-slate-800 dark:text-slate-300 dark:hover:bg-slate-800'
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
                  <ChevronRight size={15} aria-hidden="true" />
                </button>
              </nav>
            </div>
          )}
        </section>
      </div>
    </DashboardLayout>
  );
}
