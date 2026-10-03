'use client';

import DashboardLayout from '@/components/DashboardLayout';
import {
  ButtonLink,
  Card,
  CardHeader,
  FilterChip,
  PageHeader,
  StatCard,
  TableBody,
  TableHeader,
} from '@/components/saas/SaaSPrimitives';
import { apiClient } from '@/lib/apiClient';
import {
  ArrowRight,
  CheckCircle2,
  FileUp,
  Inbox,
  Search,
  ShieldAlert,
  Users,
} from 'lucide-react';
import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';

// ── Types ────────────────────────────────────────────────────────────────────

type RawResult = {
  risk_level?: string;
  score?: number;
  review_status?: string;
};

type RawJob = {
  id: string;
  assignment_name?: string;
  course_name?: string;
  file_count?: number;
  status?: string;
  created_at?: string;
  summary?: { suspicious_pairs?: number; average_similarity?: number };
  results?: RawResult[];
  review_status?: string;
};

type Tier = 'high' | 'medium' | 'low' | 'unscored';

type JobRow = {
  id: string;
  /** Position in the full ranking; stays the same whichever filter is active. */
  rank: number;
  assignmentName: string;
  courseName: string;
  submissions: number;
  highRiskPairs: number;
  /** 0–1, highest score in the job. null when the list response carries no per-pair scores. */
  maxSimilarity: number | null;
  status: string;
  reviewStatus: string;
  createdAt: string;
};

// ── Constants ─────────────────────────────────────────────────────────────────

// One definition of the tiers. These cut-offs were repeated in six places.
const HIGH_THRESHOLD = 0.75;
const MEDIUM_THRESHOLD = 0.45;
const PAGE_STEP = 25;

const FILTERS = ['All', 'High Risk', 'Medium', 'Low', 'Unreviewed'] as const;
type Filter = (typeof FILTERS)[number];

const FILTER_TONES: Record<Filter, 'neutral' | 'negative' | 'warning'> = {
  All: 'neutral',
  'High Risk': 'negative',
  Medium: 'warning',
  Low: 'neutral',
  Unreviewed: 'neutral',
};

const FILTER_SLUGS: Record<Filter, string> = {
  All: 'all',
  'High Risk': 'high',
  Medium: 'medium',
  Low: 'low',
  Unreviewed: 'unreviewed',
};

const TIER_LABELS: Record<Tier, string> = {
  high: 'High Risk',
  medium: 'Medium',
  low: 'Low',
  unscored: 'Not scored',
};

const TIER_BADGE: Record<Tier, string> = {
  high: 'bg-red-50 text-red-700 ring-1 ring-red-100',
  medium: 'bg-amber-50 text-amber-700 ring-1 ring-amber-100',
  low: 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-100',
  unscored: 'bg-slate-100 text-slate-500',
};

const TIER_BAR: Record<Exclude<Tier, 'unscored'>, string> = {
  high: 'bg-red-500',
  medium: 'bg-amber-500',
  low: 'bg-emerald-500',
};

const REVIEW_LABELS: Record<string, string> = {
  confirmed: 'Confirmed',
  needs_review: 'Needs review',
  dismissed: 'Dismissed',
  escalated: 'Escalated',
  unreviewed: 'Unreviewed',
};

const REVIEW_BADGE: Record<string, string> = {
  confirmed: 'bg-red-50 text-red-700 ring-1 ring-red-100',
  needs_review: 'bg-amber-50 text-amber-700 ring-1 ring-amber-100',
  escalated: 'bg-violet-50 text-violet-700 ring-1 ring-violet-100',
  dismissed: 'bg-slate-100 text-slate-500',
  unreviewed: 'bg-slate-100 text-slate-500',
};

// ── Helpers ───────────────────────────────────────────────────────────────────

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
    message = 'You don’t have permission to view these checks.';
  } else {
    message = 'Failed to load data. Please try again.';
  }

  return reference ? `${message} (Reference: ${reference})` : message;
}

function riskTier(max: number | null): Tier {
  if (max === null) return 'unscored';
  if (max >= HIGH_THRESHOLD) return 'high';
  if (max >= MEDIUM_THRESHOLD) return 'medium';
  return 'low';
}

function reviewKey(status: string): string {
  return Object.prototype.hasOwnProperty.call(REVIEW_LABELS, status) ? status : 'unreviewed';
}

function pct(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function toTime(value: string): number {
  const time = new Date(value).getTime();
  return Number.isNaN(time) ? 0 : time;
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (!value || Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString();
}

function buildJobRow(j: RawJob): Omit<JobRow, 'rank'> {
  const results = Array.isArray(j.results) ? j.results : [];
  let high = 0;
  let scoreMax = 0;

  for (const r of results) {
    const level = String(r.risk_level || '').toUpperCase();
    const score = Number(r.score) || 0;
    // NOTE: "high-risk pairs" counts by the engine's risk_level, while the tier badge uses
    // the score cut-offs above, so the two can occasionally disagree.
    if (level === 'CRITICAL' || level === 'HIGH') high += 1;
    if (score > scoreMax) scoreMax = score;
  }

  const hasScores = results.length > 0;

  return {
    id: j.id,
    assignmentName: j.assignment_name || 'Untitled',
    courseName: j.course_name || '',
    submissions: Number(j.file_count) || 0,
    // Fall back to summary data if results are absent (the list endpoint can omit them).
    highRiskPairs: hasScores ? high : j.summary?.suspicious_pairs ?? 0,
    // Without per-pair scores the highest similarity is unknown. It used to be forced to 0,
    // which labelled a check with flagged pairs "0% · Cleared" and counted it as cleared.
    maxSimilarity: hasScores ? scoreMax : null,
    status: j.status || 'unknown',
    reviewStatus: j.review_status || 'unreviewed',
    createdAt: j.created_at || '',
  };
}

function compareJobs(a: Omit<JobRow, 'rank'>, b: Omit<JobRow, 'rank'>): number {
  return (
    (b.maxSimilarity ?? -1) - (a.maxSimilarity ?? -1) ||
    b.highRiskPairs - a.highRiskPairs ||
    toTime(b.createdAt) - toTime(a.createdAt)
  );
}

/** Single source of truth for what each filter selects. */
function matchesFilter(job: JobRow, filter: Filter): boolean {
  if (filter === 'High Risk') return riskTier(job.maxSimilarity) === 'high';
  if (filter === 'Medium') return riskTier(job.maxSimilarity) === 'medium';
  if (filter === 'Low') return riskTier(job.maxSimilarity) === 'low';
  if (filter === 'Unreviewed') return reviewKey(job.reviewStatus) === 'unreviewed';
  return true;
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function AssignmentsPage() {
  const [activeFilter, setActiveFilter] = useState<Filter>('All');
  const [search, setSearch] = useState('');
  const [visibleCount, setVisibleCount] = useState(PAGE_STEP);
  const [jobs, setJobs] = useState<JobRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [filterRestored, setFilterRestored] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    apiClient
      .get('/api/jobs', { signal: controller.signal })
      .then((res) => {
        const data = res.data;
        const raw: RawJob[] = Array.isArray(data) ? data : Array.isArray(data?.jobs) ? data.jobs : [];
        // Only show completed jobs on this page
        setJobs(
          raw
            .filter((j) => j.status === 'completed')
            .map(buildJobRow)
            .sort(compareJobs)
            .map((job, index) => ({ ...job, rank: index + 1 }))
        );
      })
      .catch((err) => {
        if (!controller.signal.aborted) setError(describeLoadError(err));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [reloadKey]);

  // Keep the chosen filter in the URL so Back from a result returns to the same view.
  useEffect(() => {
    const slug = new URLSearchParams(window.location.search).get('filter');
    const match = FILTERS.find((f) => FILTER_SLUGS[f] === slug);
    if (match) setActiveFilter(match);
    setFilterRestored(true);
  }, []);

  useEffect(() => {
    if (!filterRestored) return;
    const params = new URLSearchParams(window.location.search);
    if (activeFilter === 'All') params.delete('filter');
    else params.set('filter', FILTER_SLUGS[activeFilter]);

    const query = params.toString();
    const next = `${window.location.pathname}${query ? `?${query}` : ''}`;
    if (next !== `${window.location.pathname}${window.location.search}`) {
      window.history.replaceState(window.history.state, '', next);
    }
  }, [filterRestored, activeFilter]);

  // Aggregate stats
  const totalSubmissions = useMemo(() => jobs.reduce((s, j) => s + j.submissions, 0), [jobs]);

  const tierCounts = useMemo(() => {
    const counts: Record<Tier, number> = { high: 0, medium: 0, low: 0, unscored: 0 };
    for (const job of jobs) counts[riskTier(job.maxSimilarity)] += 1;
    return counts;
  }, [jobs]);

  const filterCounts = useMemo(() => {
    const counts = {} as Record<Filter, number>;
    for (const filter of FILTERS) {
      counts[filter] = jobs.filter((job) => matchesFilter(job, filter)).length;
    }
    return counts;
  }, [jobs]);

  const rows = useMemo(() => {
    const q = search.trim().toLowerCase();
    return jobs.filter((job) => {
      if (!matchesFilter(job, activeFilter)) return false;
      if (!q) return true;
      return job.assignmentName.toLowerCase().includes(q) || job.courseName.toLowerCase().includes(q);
    });
  }, [jobs, activeFilter, search]);

  const shownRows = rows.slice(0, visibleCount);

  const selectFilter = (filter: Filter) => {
    setActiveFilter(filter);
    setVisibleCount(PAGE_STEP);
  };

  const statValue = (n: number) => (loading ? '…' : error ? '—' : n.toLocaleString('en-US'));

  return (
    <DashboardLayout>
      <div className="theme-page-container space-y-6">
        <PageHeader
          eyebrow="Assignment Results"
          title="Review similarity results for completed checks."
          description="Each row is a completed plagiarism check. Click View to open the full side-by-side comparison."
          action={
            <ButtonLink href="/upload" icon={FileUp}>
              Upload New Assignment
            </ButtonLink>
          }
          eyebrowStyle="badge"
        />

        {/* Stats */}
        <section aria-label="Summary" className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="Total submissions"
            value={statValue(totalSubmissions)}
            detail="Files analyzed across completed checks"
            icon={Users}
            tone="blue"
          />
          <StatCard
            label="High risk checks"
            value={statValue(tierCounts.high)}
            detail={`Checks with max similarity ≥ ${pct(HIGH_THRESHOLD)}`}
            icon={ShieldAlert}
            tone="red"
          />
          <StatCard
            label="Medium risk checks"
            value={statValue(tierCounts.medium)}
            detail={`Checks with max similarity ${pct(MEDIUM_THRESHOLD)}–${pct(HIGH_THRESHOLD - 0.01)}`}
            icon={Inbox}
            tone="amber"
          />
          <StatCard
            // "Cleared" claimed a determination the tool doesn't make; low similarity is not a clearance.
            label="Low similarity"
            value={statValue(tierCounts.low)}
            detail={`Checks with max similarity < ${pct(MEDIUM_THRESHOLD)}`}
            icon={CheckCircle2}
            tone="green"
          />
        </section>

        {/* Table */}
        <Card className="overflow-hidden">
          <div className="px-6 pt-6 pb-5 lg:px-7 lg:pt-7">
            <CardHeader
              title="Checks ranked by highest similarity"
              description="Scores from the analysis pipeline — click View to inspect pairs, evidence signals, and code diffs."
              action={
                <div role="group" aria-label="Filter checks" className="flex flex-wrap gap-2">
                  {FILTERS.map((f) => (
                    <FilterChip
                      key={f}
                      label={f}
                      count={filterCounts[f]}
                      tone={FILTER_TONES[f]}
                      active={activeFilter === f}
                      onClick={() => selectFilter(f)}
                    />
                  ))}
                </div>
              }
            />
          </div>

          <div className="px-6 pb-4 lg:px-7">
            <label className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-500 shadow-sm focus-within:border-blue-300 focus-within:ring-2 focus-within:ring-blue-50 dark:border-slate-800 dark:bg-slate-950 sm:w-80">
              <Search size={15} aria-hidden="true" />
              <input
                type="search"
                name="check-search"
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setVisibleCount(PAGE_STEP);
                }}
                placeholder="Search assignments or courses..."
                aria-label="Search checks"
                autoComplete="off"
                className="w-full bg-transparent text-slate-900 placeholder:text-slate-400 focus:outline-none dark:text-white"
              />
            </label>
            <p role="status" className="sr-only">
              {loading || error ? '' : `${rows.length} ${rows.length === 1 ? 'check' : 'checks'} shown`}
            </p>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px]">
              <caption className="sr-only">Completed checks ranked by highest similarity</caption>
              <TableHeader>
                <tr className="border-b border-slate-200 dark:border-slate-800">
                  {[
                    'Rank',
                    'Assignment',
                    'Submissions',
                    'Max similarity',
                    'High-risk pairs',
                    'Review status',
                    'Actions',
                  ].map((h) => (
                    <th key={h} scope="col" className="theme-table-header px-4 py-3 text-left">
                      {h}
                    </th>
                  ))}
                </tr>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <tr>
                    <td
                      colSpan={7}
                      role="status"
                      className="px-4 py-10 text-center text-sm text-slate-500 dark:text-slate-400"
                    >
                      Loading checks…
                    </td>
                  </tr>
                ) : error ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-10 text-center">
                      <p role="alert" className="text-sm text-red-600 dark:text-red-400">
                        {error}
                      </p>
                      <button
                        type="button"
                        onClick={() => setReloadKey((key) => key + 1)}
                        className="mt-3 inline-flex h-9 items-center rounded-lg border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300 dark:hover:bg-slate-900"
                      >
                        Try again
                      </button>
                    </td>
                  </tr>
                ) : rows.length === 0 ? (
                  <tr>
                    <td
                      colSpan={7}
                      className="px-4 py-10 text-center text-sm text-slate-500 dark:text-slate-400"
                    >
                      {jobs.length === 0
                        ? 'No completed checks yet. Upload an assignment to get started.'
                        : 'No checks match the current filter or search.'}
                    </td>
                  </tr>
                ) : (
                  shownRows.map((job) => {
                    const tier = riskTier(job.maxSimilarity);
                    const review = reviewKey(job.reviewStatus);
                    const created = formatDate(job.createdAt);

                    return (
                      <tr
                        key={job.id}
                        className="bg-white transition hover:bg-slate-50 dark:bg-slate-950 dark:hover:bg-slate-900/40"
                      >
                        {/* Rank (overall, not position within the filtered list) */}
                        <td className="px-4 py-4 text-sm font-semibold text-slate-500 dark:text-slate-400">
                          #{job.rank}
                        </td>

                        {/* Assignment name + course */}
                        <td className="px-4 py-4">
                          <div className="text-sm font-semibold text-slate-900 dark:text-white">
                            {job.assignmentName}
                          </div>
                          {job.courseName && (
                            <div className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                              {job.courseName}
                            </div>
                          )}
                          {created && (
                            <div className="mt-0.5 font-mono text-[10px] text-slate-500 dark:text-slate-500">
                              {created}
                            </div>
                          )}
                        </td>

                        {/* Submissions */}
                        <td className="px-4 py-4 text-sm font-medium text-slate-700 dark:text-slate-300">
                          {job.submissions.toLocaleString('en-US')}
                        </td>

                        {/* Max similarity: score with tier badge, or "not scored" when the list has no scores */}
                        <td className="px-4 py-4">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-sm font-semibold text-slate-900 dark:text-white">
                              {job.maxSimilarity === null ? '—' : pct(job.maxSimilarity)}
                            </span>
                            <span
                              className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold ${TIER_BADGE[tier]}`}
                            >
                              {TIER_LABELS[tier]}
                            </span>
                          </div>
                          {tier !== 'unscored' && job.maxSimilarity !== null && (
                            <div
                              className="mt-1 h-1.5 w-24 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800"
                              aria-hidden="true"
                            >
                              <div
                                className={`h-full rounded-full transition-all ${TIER_BAR[tier]}`}
                                style={{ width: `${Math.min(100, Math.round(job.maxSimilarity * 100))}%` }}
                              />
                            </div>
                          )}
                        </td>

                        {/* High-risk pairs */}
                        <td className="px-4 py-4 text-sm text-slate-700 dark:text-slate-300">
                          {job.highRiskPairs > 0 ? (
                            <span className="inline-flex items-center rounded-full bg-red-50 px-2.5 py-1 text-xs font-semibold text-red-700 ring-1 ring-red-100">
                              {job.highRiskPairs}
                            </span>
                          ) : (
                            <span className="text-slate-500">0</span>
                          )}
                        </td>

                        {/* Review status */}
                        <td className="px-4 py-4">
                          <span
                            className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${REVIEW_BADGE[review]}`}
                          >
                            {REVIEW_LABELS[review]}
                          </span>
                        </td>

                        {/* Actions: link to /results/:id (the real review workspace) */}
                        <td className="px-4 py-4">
                          <Link
                            href={`/results/${encodeURIComponent(job.id)}`}
                            aria-label={`View ${job.assignmentName}`}
                            className="inline-flex items-center gap-1.5 text-sm font-semibold text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
                          >
                            View <ArrowRight size={12} aria-hidden="true" />
                          </Link>
                        </td>
                      </tr>
                    );
                  })
                )}
              </TableBody>
            </table>
          </div>

          {!loading && !error && rows.length > 0 && (
            <div className="flex flex-col gap-2 border-t border-slate-200 px-6 py-3.5 text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400 sm:flex-row sm:items-center sm:justify-between lg:px-7">
              <span>
                Showing {shownRows.length.toLocaleString('en-US')} of {rows.length.toLocaleString('en-US')}{' '}
                {rows.length === 1 ? 'check' : 'checks'}
                {tierCounts.unscored > 0 && (
                  <>
                    {' '}
                    · {tierCounts.unscored} without scores in this list (open a check to see its results)
                  </>
                )}
              </span>
              {shownRows.length < rows.length && (
                <button
                  type="button"
                  onClick={() => setVisibleCount((count) => count + PAGE_STEP)}
                  className="inline-flex h-8 items-center rounded-lg border border-slate-200 bg-white px-3 font-semibold text-slate-700 transition hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300 dark:hover:bg-slate-900"
                >
                  Show more
                </button>
              )}
            </div>
          )}
        </Card>
      </div>
    </DashboardLayout>
  );
}
