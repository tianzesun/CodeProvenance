'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { Card, CardHeader, PageHeader, RiskBadge, StatusBadge } from '@/components/saas/SaaSPrimitives';
import { apiClient } from '@/lib/apiClient';
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  Inbox,
  Search,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';

type CaseStatus = 'OPEN' | 'UNDER_REVIEW' | 'ESCALATED' | 'CLOSED';

type CaseItem = {
  id: string;
  title: string;
  status: string;
  priority: string;
  course?: string;
  assignment?: string;
  students?: string;
  risk?: number;
  reviewer?: string;
  updatedAt?: string;
};

type SortKey = 'risk' | 'status' | 'course' | 'updated';

type RawCase = {
  id: string;
  title: string;
  status?: string;
  priority?: string;
  course?: string;
  students_display?: string;
  risk_score?: number;
  updated_at?: string;
  created_at?: string;
  assignment?: { title?: string; course_name?: string };
  investigator?: { name?: string };
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

const PAGE_SIZES = [10, 25, 50];

function matchesSearch(caseItem: CaseItem, query: string): boolean {
  if (!query) return true;
  const needle = query.toLowerCase();
  return [
    caseItem.title,
    caseItem.course,
    caseItem.assignment,
    caseItem.students,
    caseItem.reviewer,
    caseItem.status,
    caseItem.priority,
    caseItem.id,
  ]
    .filter(Boolean)
    .some((value) => String(value).toLowerCase().includes(needle));
}

export default function CasesQueuePage() {
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter / sort / pagination state
  const [activeStatus, setActiveStatus] = useState<CaseStatus | 'ALL'>('ALL');
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('risk');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  useEffect(() => {
    const fetchCases = async () => {
      try {
        const response = await apiClient.get('/api/cases', { params: { limit: 1000 } });
        const casesData = (response.data || []) as RawCase[];

        // Transform API response to match UI expectations
        const transformedCases = casesData.map((c) => ({
          id: c.id,
          title: c.title,
          status: c.status || 'OPEN',
          priority: c.priority || 'MEDIUM',
          course: c.assignment?.course_name || c.course || 'Unknown Course',
          assignment: c.assignment?.title || c.title,
          students: c.students_display || 'Multiple students',
          risk: c.risk_score || 75,
          reviewer: c.investigator?.name || 'Unassigned',
          updatedAt: c.updated_at || c.created_at,
        }));
        setCases(transformedCases);
      } catch (err) {
        console.error('Failed to fetch cases:', err);
        setError(
          err instanceof Error ? err.message : 'Failed to load cases. Please try again.'
        );
      } finally {
        setLoading(false);
      }
    };

    fetchCases();
  }, []);

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
      const status = (c.status || 'OPEN').toUpperCase() as CaseStatus;
      if (status in counts) counts[status] += 1;
    }
    return counts;
  }, [cases]);

  // Apply status filter + live search
  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    return cases.filter((c) => {
      if (activeStatus !== 'ALL' && c.status !== activeStatus) return false;
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
          cmp = (STATUS_ORDER[a.status] ?? 99) - (STATUS_ORDER[b.status] ?? 99);
          break;
        case 'course':
          cmp = String(a.course || '').localeCompare(String(b.course || ''));
          break;
        case 'updated':
          cmp =
            new Date(a.updatedAt || 0).getTime() - new Date(b.updatedAt || 0).getTime();
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

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir(key === 'status' ? 'asc' : 'desc');
    }
    setPage(1);
  };

  const handleSearch = useCallback((value: string) => {
    setSearch(value);
    setPage(1);
  }, []);

  const handleStatusTab = (key: CaseStatus | 'ALL') => {
    setActiveStatus(key);
    setPage(1);
  };

  const renderSortIcon = (column: SortKey) => {
    if (sortKey !== column) return <ArrowUpDown size={13} className="text-slate-400" />;
    return sortDir === 'asc' ? (
      <ArrowUp size={13} className="text-blue-600" />
    ) : (
      <ArrowDown size={13} className="text-blue-600" />
    );
  };

  const renderSortableTh = (
    column: SortKey,
    label: string,
    className = ''
  ) => (
    <th className={`px-5 py-3 text-left ${className}`}>
      <button
        type="button"
        onClick={() => handleSort(column)}
        className={`inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide transition ${
          sortKey === column ? 'text-slate-900' : 'text-slate-500 hover:text-slate-700'
        }`}
      >
        {label}
        {renderSortIcon(column)}
      </button>
    </th>
  );

  return (
    <DashboardLayout>
      <div className="max-w-none px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <PageHeader
          eyebrow="Cases"
          title="An inbox for academic integrity review."
          description="Teaching teams can assign, review, dismiss, and export cases without digging through raw tool output."
          action={
            <label className="flex w-full items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-500 shadow-sm transition focus-within:border-blue-300 focus-within:ring-4 focus-within:ring-blue-50 lg:w-80">
              <Search size={16} />
              <input
                type="search"
                value={search}
                onChange={(e) => handleSearch(e.target.value)}
                placeholder="Search cases, students, courses"
                className="w-full bg-transparent text-slate-900 placeholder:text-slate-400 focus:outline-none"
                aria-label="Search cases"
              />
            </label>
          }
        />

        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Status tabs */}
        <div className="mb-4 flex flex-wrap items-center gap-2">
          {STATUS_TABS.map((tab) => {
            const isActive = activeStatus === tab.key;
            const count = statusCounts[tab.key];
            const isOpenTab = tab.key === 'OPEN' || tab.key === 'ALL';
            const accent =
              isOpenTab && count > 0
                ? 'border-red-200 bg-red-50 text-red-700 hover:bg-red-100'
                : isActive
                  ? 'border-slate-900 bg-slate-900 text-white hover:bg-slate-800'
                  : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50';
            return (
              <button
                key={tab.key}
                type="button"
                onClick={() => handleStatusTab(tab.key)}
                className={`inline-flex items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-xs font-semibold transition ${accent} ${
                  isActive ? '' : 'shadow-sm'
                }`}
              >
                {tab.label}
                <span
                  className={`rounded-full px-1.5 py-0.5 text-[10px] font-bold ${
                    isActive ? 'bg-white/20' : 'bg-slate-100 text-slate-500'
                  }`}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        <Card>
          <CardHeader
            title="Queue"
            description="Sorted by risk and unreviewed status."
            action={
              <div className="flex items-center gap-3 text-sm text-slate-500">
                <span>
                  Showing{' '}
                  <strong className="font-semibold text-slate-900">
                    {sorted.length === 0 ? 0 : pageStart + 1}–{pageStart + visible.length}
                  </strong>{' '}
                  of <strong className="font-semibold text-slate-900">{sorted.length}</strong>{' '}
                  {sorted.length === 1 ? 'case' : 'cases'}
                  {search || activeStatus !== 'ALL' ? (
                    <span className="text-slate-400"> (filtered)</span>
                  ) : null}
                </span>
              </div>
            }
          />
          <div className="overflow-x-auto">
            {loading ? (
              <div className="px-5 py-8 text-sm text-slate-500">Loading cases...</div>
            ) : sorted.length === 0 ? (
              <div className="flex flex-col items-center px-5 py-12 text-center">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-100 text-slate-400">
                  <Inbox size={20} />
                </div>
                <p className="mt-3 text-sm font-medium text-slate-700">No cases found</p>
                <p className="mt-1 text-sm text-slate-500">
                  {cases.length === 0
                    ? 'Run an AI detection or similarity analysis to create cases.'
                    : 'No cases match the current filters or search.'}
                </p>
              </div>
            ) : (
              <table className="w-full min-w-[900px]">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Status
                    </th>
                    {renderSortableTh('course', 'Course')}
                    <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Pair
                    </th>
                    {renderSortableTh('risk', 'Risk')}
                    <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Assigned reviewer
                    </th>
                    {renderSortableTh('updated', 'Updated', 'text-right')}
                    <th className="px-5 py-3 text-right" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {visible.map((item) => (
                    <tr key={item.id} className="transition hover:bg-slate-50">
                      <td className="px-5 py-4">
                        <StatusBadge status={item.status} />
                      </td>
                      <td className="px-5 py-4">
                        <div className="text-sm font-semibold text-slate-950">{item.course}</div>
                        <div className="mt-1 text-xs text-slate-500">{item.assignment}</div>
                      </td>
                      <td className="px-5 py-4">
                        <div className="text-sm font-semibold text-slate-950">{item.students}</div>
                        <div className="mt-1 text-xs text-slate-500">{item.title}</div>
                      </td>
                      <td className="px-5 py-4">
                        <RiskBadge value={item.risk || 50} />
                      </td>
                      <td className="px-5 py-4 text-sm text-slate-600">{item.reviewer}</td>
                      <td className="px-5 py-4 text-right text-xs text-slate-500">
                        {formatDate(item.updatedAt)}
                      </td>
                      <td className="px-5 py-4 text-right">
                        <a
                          href={`/cases/${item.id}`}
                          className="text-sm font-semibold text-blue-600 hover:text-blue-700"
                        >
                          Open
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Pagination footer */}
          {!loading && sorted.length > 0 && (
            <div className="flex flex-col gap-3 border-t border-slate-200 px-5 py-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <span>Rows per page</span>
                <select
                  value={pageSize}
                  onChange={(e) => {
                    setPageSize(Number(e.target.value));
                    setPage(1);
                  }}
                  className="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700 focus:border-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-50"
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
                  className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-slate-200 text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
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
                      className={`inline-flex h-8 w-8 items-center justify-center rounded-md text-xs font-semibold transition ${
                        safePage === num
                          ? 'bg-slate-900 text-white'
                          : 'border border-slate-200 text-slate-600 hover:bg-slate-50'
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
                  className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-slate-200 text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <ChevronRight size={15} />
                </button>
              </div>
            </div>
          )}
        </Card>
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