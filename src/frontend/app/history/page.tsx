'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { Card, CardHeader, PageHeader, StatusBadge } from '@/components/saas/SaaSPrimitives';
import { apiClient } from '@/lib/apiClient';
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  Download,
  Inbox,
  Search,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

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
  persistence_warning?: string;
};

const STATUS_TABS: { key: JobStatus; label: string }[] = [
  { key: 'ALL', label: 'All' },
  { key: 'COMPLETED', label: 'Completed' },
  { key: 'PROCESSING', label: 'Processing' },
  { key: 'FAILED', label: 'Failed' },
];

const STATUS_ORDER: Record<string, number> = {
  completed: 0,
  processing: 1,
  analyzing: 2,
  failed: 3,
};

const PAGE_SIZES = [10, 25, 50];

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

export default function HistoryPage() {
  const [jobs, setJobs] = useState<JobItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [activeStatus, setActiveStatus] = useState<JobStatus>('ALL');
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('date');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  const [openDropdown, setOpenDropdown] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

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

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpenDropdown(null);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

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

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir(key === 'date' ? 'desc' : 'desc');
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
          eyebrow="History"
          title="Browse past plagiarism check history."
          description="View, search, and download reports from previous similarity analyses."
          action={
            <label className="flex w-full items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-500 shadow-sm transition focus-within:border-blue-300 focus-within:ring-4 focus-within:ring-blue-50 lg:w-80">
              <Search size={16} />
              <input
                type="search"
                value={search}
                onChange={(e) => handleSearch(e.target.value)}
                placeholder="Search by assignment, course, or ID"
                className="w-full bg-transparent text-slate-900 placeholder:text-slate-400 focus:outline-none"
                aria-label="Search history"
              />
            </label>
          }
        />

        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="mb-4 flex flex-wrap items-center gap-2">
          {STATUS_TABS.map((tab) => {
            const isActive = activeStatus === tab.key;
            const count = statusCounts[tab.key];
            const accent = isActive
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
            title="History"
            description="All similarity checks sorted by date."
            action={
              <div className="flex items-center gap-3 text-sm text-slate-500">
                <span>
                  Showing{' '}
                  <strong className="font-semibold text-slate-900">
                    {sorted.length === 0 ? 0 : pageStart + 1}–{pageStart + visible.length}
                  </strong>{' '}
                  of <strong className="font-semibold text-slate-900">{sorted.length}</strong>{' '}
                  {sorted.length === 1 ? 'check' : 'checks'}
                  {search || activeStatus !== 'ALL' ? (
                    <span className="text-slate-400"> (filtered)</span>
                  ) : null}
                </span>
              </div>
            }
          />
          <div className="overflow-x-auto">
            {loading ? (
              <div className="px-5 py-8 text-sm text-slate-500">Loading history...</div>
            ) : sorted.length === 0 ? (
              <div className="flex flex-col items-center px-5 py-12 text-center">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-100 text-slate-400">
                  <Inbox size={20} />
                </div>
                <p className="mt-3 text-sm font-medium text-slate-700">No checks found</p>
                <p className="mt-1 text-sm text-slate-500">
                  {jobs.length === 0
                    ? 'Run a plagiarism check to see results here.'
                    : 'No checks match the current filters or search.'}
                </p>
              </div>
            ) : (
              <table className="w-full min-w-[900px]">
                <thead className="bg-slate-50">
                  <tr>
                    {renderSortableTh('date', 'Date')}
                    {renderSortableTh('name', 'Name')}
                    {renderSortableTh('submissions', 'Submissions')}
                    {renderSortableTh('highRisk', 'High-Risk')}
                    <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Status
                    </th>
                    <th className="px-5 py-3 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {visible.map((job) => (
                    <tr key={job.id} className="transition hover:bg-slate-50">
                      <td className="px-5 py-4 text-xs text-slate-500">
                        {formatDate(job.createdAt)}
                      </td>
                      <td className="px-5 py-4">
                        <div className="text-sm font-semibold text-slate-950">
                          {job.assignmentName}
                        </div>
                        <div className="mt-1 text-xs text-slate-500">{job.courseName}</div>
                      </td>
                      <td className="px-5 py-4 text-sm font-medium text-slate-700">
                        {job.totalSubmissions}
                      </td>
                      <td className="px-5 py-4">
                        {job.highSimilarityCount > 0 ? (
                          <span className="inline-flex items-center rounded-full bg-red-50 px-2.5 py-1 text-xs font-semibold text-red-700 ring-1 ring-red-100">
                            {job.highSimilarityCount}
                          </span>
                        ) : (
                          <span className="text-sm text-slate-400">0</span>
                        )}
                      </td>
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-2">
                          <StatusBadge status={job.status} />
                          {job.persistenceWarning && (
                            <span title={job.persistenceWarning}>
                              <AlertTriangle size={14} className="text-amber-500" />
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-5 py-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <a
                            href={`/results/${job.id}`}
                            className="text-sm font-semibold text-blue-600 hover:text-blue-700"
                          >
                            View
                          </a>
                          <div className="relative" ref={openDropdown === job.id ? dropdownRef : undefined}>
                            <button
                              type="button"
                              onClick={() =>
                                setOpenDropdown((prev) =>
                                  prev === job.id ? null : job.id
                                )
                              }
                              className="inline-flex items-center justify-center rounded-md border border-slate-200 p-1.5 text-slate-500 transition hover:bg-slate-50 hover:text-slate-700"
                              aria-label="Download options"
                            >
                              <Download size={14} />
                            </button>
                            {openDropdown === job.id && (
                              <div className="absolute right-0 z-20 mt-1 w-52 rounded-lg border border-slate-200 bg-white py-1 shadow-lg">
                                <a
                                  href={`/report/${job.id}/download`}
                                  className="flex items-center gap-2 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
                                  onClick={() => setOpenDropdown(null)}
                                >
                                  <Download size={13} />
                                  HTML Report
                                </a>
                                <a
                                  href={`/report/${job.id}/download-json`}
                                  className="flex items-center gap-2 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
                                  onClick={() => setOpenDropdown(null)}
                                >
                                  <Download size={13} />
                                  JSON Data
                                </a>
                                <a
                                  href={`/report/${job.id}/committee`}
                                  className="flex items-center gap-2 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  onClick={() => setOpenDropdown(null)}
                                >
                                  <Download size={13} />
                                  Committee Report
                                </a>
                                <a
                                  href={`/report/${job.id}/download-pdf`}
                                  className="flex items-center gap-2 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
                                  onClick={() => setOpenDropdown(null)}
                                >
                                  <Download size={13} />
                                  PDF Report
                                </a>
                                <a
                                  href={`/report/${job.id}/download-csv`}
                                  className="flex items-center gap-2 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
                                  onClick={() => setOpenDropdown(null)}
                                >
                                  <Download size={13} />
                                  CSV Data
                                </a>
                              </div>
                            )}
                          </div>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

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
