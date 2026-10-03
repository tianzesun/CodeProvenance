'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { Modal, PageHeader } from '@/components/saas/SaaSPrimitives';
import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import Link from 'next/link';
import { apiClient } from '@/lib/apiClient';
import {
  Network,
  ShieldCheck,
  Download,
  RefreshCw,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Info,
  Search,
} from 'lucide-react';

// ─── Types ─────────────────────────────────────────────────────────────────────

interface Cluster {
  cluster_id: number;
  members: string[];
  center: string;
  /** 0–1 */
  avg_similarity: number;
  /** 0–1 */
  max_similarity: number;
  suspicious_pairs: number;
  evidence_strength: string;
  size: number;
}

type SortOrder = 'strength' | 'size' | 'similarity' | 'reported';

// ─── Constants ─────────────────────────────────────────────────────────────────

const STRENGTH_RANK: Record<string, number> = { strong: 0, moderate: 1, weak: 2 };
const PAGE_STEP = 25;
const REFERENCE_HEADERS = ['x-correlation-id', 'x-request-id'];

// ─── Helpers ───────────────────────────────────────────────────────────────────

/** Generic, status-keyed text; a correlation id is appended when the backend sends one. */
function describeError(error: unknown): string {
  const response = (error as { response?: { status?: unknown; headers?: unknown } } | null)?.response;
  const status = typeof response?.status === 'number' ? response.status : undefined;
  const headers = (response?.headers ?? {}) as Record<string, unknown>;
  const reference = REFERENCE_HEADERS.map((name) => headers[name]).find(
    (value): value is string => typeof value === 'string' && value.length > 0
  );

  let message = 'Failed to load the similarity clusters. Please try again.';
  if (status === 401) message = 'Your session has expired. Please sign in again.';
  else if (status === 403) message = 'You don’t have permission to view this data.';

  return reference ? `${message} (Reference: ${reference})` : message;
}

const toNumber = (value: unknown): number => {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
};
const clamp01 = (value: unknown): number => Math.max(0, Math.min(1, toNumber(value)));
const percent = (value: number, digits = 0): string => `${(value * 100).toFixed(digits)}%`;

/** The response was stored as-is, so a missing list or number crashed `.slice` / `.reduce` or showed "NaN". */
function normalizeClusters(data: unknown): Cluster[] {
  const raw = data as { clusters?: unknown } | null;
  const list = Array.isArray(data) ? data : Array.isArray(raw?.clusters) ? (raw?.clusters as unknown[]) : [];
  return list
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object')
    .map((item, index) => {
      const members = Array.isArray(item.members) ? item.members.map(String) : [];
      const idNumber = Number(item.cluster_id);
      return {
        cluster_id: Number.isFinite(idNumber) ? idNumber : index,
        members,
        center: String(item.center ?? ''),
        avg_similarity: clamp01(item.avg_similarity),
        max_similarity: clamp01(item.max_similarity),
        suspicious_pairs: Math.max(0, Math.round(toNumber(item.suspicious_pairs))),
        evidence_strength: String(item.evidence_strength ?? 'unknown').toLowerCase(),
        size: Math.max(0, Math.round(toNumber(item.size))) || members.length,
      };
    });
}

/**
 * Last two path segments (folder/file). The list used to show only the file name, so a class where
 * every submission is "main.py" showed five identical chips.
 */
function memberLabel(path: string): string {
  const parts = path.split(/[\\/]/).filter(Boolean);
  return parts.slice(-2).join('/') || path;
}

function humanize(value: string): string {
  const text = value.replace(/_/g, ' ').trim();
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : 'Unknown';
}

// "Weak" evidence used to be green, which reads as "cleared". Weak evidence is just weaker evidence.
function strengthClass(strength: string): string {
  if (strength === 'strong') {
    return 'border-red-200 bg-red-50 text-red-700 dark:border-red-500/25 dark:bg-red-500/15 dark:text-red-300';
  }
  if (strength === 'moderate') {
    return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/25 dark:bg-amber-500/15 dark:text-amber-300';
  }
  return 'border-slate-200 bg-slate-100 text-slate-600 dark:border-slate-800 dark:bg-slate-800 dark:text-slate-300';
}

function csvCell(value: string | number): string {
  let text = String(value);
  if (typeof value === 'string' && /^[=+\-@\t\r]/.test(text)) text = `'${text}`;
  return `"${text.replace(/"/g, '""')}"`;
}

function triggerDownload(filename: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function formatTime(value: Date): string {
  return new Intl.DateTimeFormat('en-US', { dateStyle: 'medium', timeStyle: 'short' }).format(value);
}

function SummaryCard({ value, label }: { value: string; label: string }) {
  return (
    <div className="rounded-[24px] border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950">
      <div className="text-2xl font-semibold text-slate-900 dark:text-white">{value}</div>
      <div className="text-sm text-slate-500 dark:text-slate-400">{label}</div>
    </div>
  );
}

// ─── Page ──────────────────────────────────────────────────────────────────────

export default function ClusterDetectionPage() {
  const [clusters, setClusters] = useState<Cluster[]>([]);
  // Starts true: with `false` the "No groups detected" message flashed before the request began.
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [loadedAt, setLoadedAt] = useState<Date | null>(null);
  const [selectedCluster, setSelectedCluster] = useState<Cluster | null>(null);

  const [query, setQuery] = useState('');
  const [strengthFilter, setStrengthFilter] = useState('all');
  const [order, setOrder] = useState<SortOrder>('strength');
  const [visibleCount, setVisibleCount] = useState(PAGE_STEP);
  const requestIdRef = useRef(0);

  const loadClusters = useCallback(async (signal?: AbortSignal) => {
    const requestId = ++requestIdRef.current;
    setLoading(true);
    setError('');
    try {
      const response = await apiClient.get('/api/cluster-detection/clusters', { signal });
      if (requestId !== requestIdRef.current) return;
      setClusters(normalizeClusters(response.data));
      setLoadedAt(new Date());
    } catch (err) {
      if (signal?.aborted || requestId !== requestIdRef.current) return;
      // A failed refresh keeps the last clusters on screen rather than showing "none found".
      setError(describeError(err));
    } finally {
      if (requestId === requestIdRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    loadClusters(controller.signal);
    return () => controller.abort();
  }, [loadClusters]);

  const hasData = loadedAt !== null;

  const strengths = useMemo(() => Array.from(new Set(clusters.map((c) => c.evidence_strength))).sort(), [clusters]);

  const visibleClusters = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = clusters.filter((c) => {
      if (strengthFilter !== 'all' && c.evidence_strength !== strengthFilter) return false;
      if (q && !c.members.some((m) => m.toLowerCase().includes(q))) return false;
      return true;
    });
    if (order === 'strength') {
      return [...list].sort(
        (a, b) =>
          (STRENGTH_RANK[a.evidence_strength] ?? 3) - (STRENGTH_RANK[b.evidence_strength] ?? 3) ||
          b.max_similarity - a.max_similarity
      );
    }
    if (order === 'size') return [...list].sort((a, b) => b.size - a.size || b.max_similarity - a.max_similarity);
    if (order === 'similarity') return [...list].sort((a, b) => b.avg_similarity - a.avg_similarity);
    return list;
  }, [clusters, query, strengthFilter, order]);

  const stats = useMemo(() => {
    // A submission in two clusters used to be counted twice, and these are submissions (file paths), not students.
    const submissions = new Set<string>();
    clusters.forEach((c) => c.members.forEach((m) => submissions.add(m)));
    const pairs = clusters.reduce((sum, c) => sum + c.suspicious_pairs, 0);
    const avg = clusters.length ? clusters.reduce((sum, c) => sum + c.avg_similarity, 0) / clusters.length : 0;
    return { clusters: clusters.length, submissions: submissions.size, pairs, avg };
  }, [clusters]);

  const stat = (value: string) => (loading && !hasData ? '…' : error && !hasData ? '—' : value);

  const exportCsv = () => {
    const header = ['Group', 'Submissions', 'Evidence strength', 'Avg similarity %', 'Max similarity %', 'Suspicious pairs', 'Most central submission', 'Members'];
    const rows = visibleClusters.map((c) => [
      c.cluster_id + 1,
      c.size,
      c.evidence_strength,
      (c.avg_similarity * 100).toFixed(1),
      (c.max_similarity * 100).toFixed(1),
      c.suspicious_pairs,
      c.center,
      c.members.join('; '),
    ]);
    const csv = [header, ...rows].map((row) => row.map(csvCell).join(',')).join('\r\n');
    const stamp = new Intl.DateTimeFormat('en-CA').format(new Date());
    triggerDownload(`similarity-clusters-${stamp}.csv`, new Blob(['\uFEFF' + csv + '\r\n'], { type: 'text/csv;charset=utf-8' }));
  };

  return (
    <DashboardLayout>
      <div className="theme-page-container space-y-6">
        {/* Back link kept as its own block above the canonical PageHeader. */}
        <Link href="/" className="theme-link inline-flex items-center gap-2 text-sm font-semibold">
          <ChevronLeft size={16} aria-hidden="true" />
          Back to Dashboard
        </Link>
        <PageHeader
          eyebrow="Engine & R&D"
          eyebrowStyle="badge"
          title="Cluster Detection"
          description="Find groups of submissions that are highly similar to one another through similarity network analysis"
          action={
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => loadClusters()}
                disabled={loading}
                className="inline-flex h-10 items-center gap-2 rounded-xl bg-blue-600 px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <RefreshCw size={16} className={loading ? 'animate-spin' : ''} aria-hidden="true" />
                {loading ? 'Refreshing…' : 'Refresh'}
              </button>
              {/* This button had no handler. It now exports the clusters currently listed. */}
              <button
                type="button"
                onClick={exportCsv}
                disabled={visibleClusters.length === 0}
                className="inline-flex h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
              >
                <Download size={16} aria-hidden="true" />
                Export CSV
              </button>
            </div>
          }
        />

        <p
          role="note"
          className="flex items-start gap-3 rounded-2xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-700 dark:border-blue-500/20 dark:bg-blue-500/10 dark:text-blue-300"
        >
          <Info size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
          <span>
            A cluster shows submissions that resemble each other. It does not show who copied from whom, or that anyone did.
            Shared starter code, common textbook solutions and approved collaboration all produce clusters, so review the
            submissions before drawing any conclusion.
          </span>
        </p>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
          <SummaryCard value={stat(String(stats.clusters))} label="Clusters Found" />
          <SummaryCard value={stat(String(stats.submissions))} label="Submissions in Clusters" />
          <SummaryCard value={stat(String(stats.pairs))} label="Suspicious Pairs" />
          <SummaryCard value={stat(percent(stats.avg))} label="Avg Cluster Similarity" />
        </div>

        {error && (
          <div
            role="alert"
            className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300"
          >
            <AlertCircle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
            <span className="flex-1">{error}{hasData ? ' Showing the last loaded clusters.' : ''}</span>
            <button
              type="button"
              onClick={() => loadClusters()}
              className="inline-flex h-9 shrink-0 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
            >
              Retry
            </button>
          </div>
        )}

        {/* Clusters */}
        <div className="overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-5 py-4 dark:border-slate-800">
            <div className="flex items-center gap-2">
              <Network size={16} className="text-slate-500 dark:text-slate-400" aria-hidden="true" />
              {/* "Detected Cheating Groups" asserted misconduct that the analysis can't establish. */}
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Similarity Clusters</h2>
            </div>
            {loadedAt && <span className="text-xs text-slate-500 dark:text-slate-400">Updated {formatTime(loadedAt)}</span>}
          </div>

          {clusters.length > 0 && (
            <div className="flex flex-wrap items-center gap-3 border-b border-slate-200 px-5 py-4 dark:border-slate-800">
              <div className="relative w-full sm:w-64">
                <Search
                  size={16}
                  className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                  aria-hidden="true"
                />
                <input
                  type="search"
                  name="cluster-search"
                  autoComplete="off"
                  value={query}
                  onChange={(e) => { setQuery(e.target.value); setVisibleCount(PAGE_STEP); }}
                  placeholder="Search submissions"
                  aria-label="Search submissions in clusters"
                  className="h-10 w-full rounded-xl border border-slate-200 bg-white pl-9 pr-4 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white dark:placeholder:text-slate-500"
                />
              </div>
              <div className="relative">
                <select
                  value={strengthFilter}
                  onChange={(e) => { setStrengthFilter(e.target.value); setVisibleCount(PAGE_STEP); }}
                  aria-label="Filter by evidence strength"
                  className="h-10 appearance-none rounded-xl border border-slate-200 bg-white pl-4 pr-9 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white"
                >
                  <option value="all">All strengths</option>
                  {strengths.map((s) => (
                    <option key={s} value={s}>{humanize(s)}</option>
                  ))}
                </select>
                <ChevronDown
                  size={14}
                  className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400"
                  aria-hidden="true"
                />
              </div>
              <div className="relative ml-auto">
                <select
                  value={order}
                  onChange={(e) => setOrder(e.target.value as SortOrder)}
                  aria-label="Order clusters"
                  className="h-10 appearance-none rounded-xl border border-slate-200 bg-white pl-4 pr-9 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white"
                >
                  <option value="strength">Strongest evidence first</option>
                  <option value="size">Largest group first</option>
                  <option value="similarity">Highest similarity first</option>
                  <option value="reported">As reported</option>
                </select>
                <ChevronDown
                  size={14}
                  className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400"
                  aria-hidden="true"
                />
              </div>
            </div>
          )}

          {loading && !hasData ? (
            // Skeleton bars in the placeholder card (rule 5); the status text is kept for screen readers.
            <div role="status" className="p-5">
              <span className="sr-only">Analyzing similarity graph...</span>
              <div className="flex flex-col gap-4" aria-hidden="true">
                {[0, 1, 2].map((row) => (
                  <div key={row} className="flex flex-col gap-2.5">
                    <div className="h-4 w-56 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
                    <div className="h-3 w-80 max-w-full animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
                    <div className="h-3 w-40 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
                  </div>
                ))}
              </div>
            </div>
          ) : !hasData ? (
            // The load failed. This used to fall through to "No Cheating Groups Detected", a false all-clear.
            <div className="p-8 text-center text-sm text-slate-500 dark:text-slate-400">
              The clusters couldn’t be loaded, so nothing can be said about groups yet.
            </div>
          ) : clusters.length === 0 ? (
            <div className="px-5 py-16 text-center">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-slate-100 text-slate-500 dark:bg-slate-900 dark:text-slate-400">
                <ShieldCheck size={22} aria-hidden="true" />
              </div>
              <h3 className="mt-4 text-base font-semibold text-slate-900 dark:text-white">No Similarity Clusters Found</h3>
              <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500 dark:text-slate-400">
                No groups of highly similar submissions were found. Run analysis on more submissions to look for coordinated similarity.
              </p>
            </div>
          ) : visibleClusters.length === 0 ? (
            <div className="px-5 py-16 text-center">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-slate-100 text-slate-500 dark:bg-slate-900 dark:text-slate-400">
                <Search size={22} aria-hidden="true" />
              </div>
              <h3 className="mt-4 text-base font-semibold text-slate-900 dark:text-white">No matching clusters</h3>
              <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500 dark:text-slate-400">
                No clusters match the current filters.
              </p>
            </div>
          ) : (
            <>
              <p role="status" className="sr-only">{visibleClusters.length} of {clusters.length} clusters shown</p>
              <ul className="divide-y divide-slate-200 dark:divide-slate-800">
                {visibleClusters.slice(0, visibleCount).map((cluster) => (
                  <li key={cluster.cluster_id}>
                    {/* A clickable <div> before, which keyboard users couldn't reach; the whole row is now one button. */}
                    <button
                      type="button"
                      onClick={() => setSelectedCluster(cluster)}
                      aria-label={`Group ${cluster.cluster_id + 1}, ${cluster.size} submissions, ${humanize(cluster.evidence_strength)} evidence. View details`}
                      className="flex w-full items-center justify-between gap-4 p-4 text-left transition hover:bg-slate-50 focus-visible:bg-slate-50 focus-visible:outline-none dark:hover:bg-slate-900 dark:focus-visible:bg-slate-900"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="mb-2 flex flex-wrap items-center gap-3">
                          <span className="font-medium text-slate-900 dark:text-white">
                            Group #{cluster.cluster_id + 1} • {cluster.size} submission{cluster.size === 1 ? '' : 's'}
                          </span>
                          <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold ${strengthClass(cluster.evidence_strength)}`}>
                            {humanize(cluster.evidence_strength)}
                          </span>
                        </div>
                        <div className="flex flex-wrap items-center gap-4 text-sm text-slate-500 dark:text-slate-400">
                          <span>Avg Similarity: {percent(cluster.avg_similarity, 1)}</span>
                          <span>Max: {percent(cluster.max_similarity, 1)}</span>
                          <span>Suspicious Pairs: {cluster.suspicious_pairs}</span>
                        </div>
                        <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
                          {cluster.members.slice(0, 5).map((m, i) => (
                            <span
                              key={`${m}-${i}`}
                              className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-600 dark:bg-slate-800 dark:text-slate-300"
                              title={m}
                            >
                              {memberLabel(m)}
                            </span>
                          ))}
                          {cluster.members.length > 5 && <span>+{cluster.members.length - 5} more</span>}
                        </div>
                      </div>
                      <ChevronRight size={16} className="shrink-0 text-slate-400" aria-hidden="true" />
                    </button>
                  </li>
                ))}
              </ul>
              {visibleClusters.length > visibleCount && (
                <div className="border-t border-slate-200 p-3 dark:border-slate-800">
                  <button
                    type="button"
                    onClick={() => setVisibleCount((n) => n + PAGE_STEP)}
                    className="inline-flex h-10 w-full items-center justify-center rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
                  >
                    Show more ({visibleClusters.length - visibleCount} remaining)
                  </button>
                </div>
              )}
            </>
          )}
        </div>

        {/* Detail Panel */}
        <Modal
          open={Boolean(selectedCluster)}
          title={selectedCluster ? `Group #${selectedCluster.cluster_id + 1} details` : 'Group details'}
          onClose={() => setSelectedCluster(null)}
        >
          {selectedCluster && (
            <div className="space-y-4">
              <div>
                <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
                  Members ({selectedCluster.size})
                </div>
                <ul className="scrollbar-thin max-h-48 space-y-1 overflow-y-auto" tabIndex={0} aria-label="Cluster members">
                  {selectedCluster.members.map((m, i) => (
                    <li
                      key={`${m}-${i}`}
                      className={`break-all text-sm font-mono text-slate-700 dark:text-slate-300 ${m === selectedCluster.center ? 'font-semibold' : ''}`}
                    >
                      {m}
                      {m === selectedCluster.center && (
                        <span className="ml-2 font-sans text-xs text-slate-500 dark:text-slate-400">(most central)</span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
                    Avg Similarity
                  </div>
                  <div className="text-lg font-semibold text-slate-900 dark:text-white">
                    {percent(selectedCluster.avg_similarity, 1)}
                  </div>
                </div>
                <div>
                  <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
                    Max Similarity
                  </div>
                  <div className="text-lg font-semibold text-slate-900 dark:text-white">
                    {percent(selectedCluster.max_similarity, 1)}
                  </div>
                </div>
                <div>
                  <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
                    Suspicious Pairs
                  </div>
                  <div className="text-lg font-semibold text-slate-900 dark:text-white">
                    {selectedCluster.suspicious_pairs}
                  </div>
                </div>
                <div>
                  <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
                    Evidence Strength
                  </div>
                  <div className="text-lg font-semibold text-slate-900 dark:text-white">
                    {humanize(selectedCluster.evidence_strength)}
                  </div>
                </div>
              </div>
              <p className="text-xs leading-5 text-slate-500 dark:text-slate-400">
                Similarity between submissions is a reason to look closer, not a finding. Check for shared starter code or permitted collaboration first.
              </p>
            </div>
          )}
        </Modal>
      </div>
    </DashboardLayout>
  );
}
