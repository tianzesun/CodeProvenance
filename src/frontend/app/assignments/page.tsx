'use client';

import DashboardLayout from '@/components/DashboardLayout';
import {
  ButtonLink,
  Card,
  CardHeader,
  PageHeader,
  StatCard,
  TableBody,
  TableHeader,
} from '@/components/saas/SaaSPrimitives';
import { apiClient } from '@/lib/apiClient';
import {
  CheckCircle2,
  FileUp,
  Filter,
  Inbox,
  ShieldAlert,
  Users,
  ExternalLink,
} from 'lucide-react';
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

type JobRow = {
  id: string;
  assignmentName: string;
  courseName: string;
  submissions: number;
  highRiskPairs: number;
  mediumRiskPairs: number;
  totalPairs: number;
  avgSimilarity: number;      // 0–1, computed from results
  maxSimilarity: number;      // 0–1, highest score in the job
  status: string;
  reviewStatus: string;
  createdAt: string;
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function riskTierLabel(max: number): string {
  if (max >= 0.75) return 'High Risk';
  if (max >= 0.45) return 'Medium';
  return 'Cleared';
}

function riskTierClass(max: number): string {
  if (max >= 0.75) return 'bg-red-50 text-red-700 ring-1 ring-red-100';
  if (max >= 0.45) return 'bg-amber-50 text-amber-700 ring-1 ring-amber-100';
  return 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-100';
}

function reviewBadgeClass(status: string): string {
  if (status === 'confirmed') return 'bg-red-50 text-red-700 ring-1 ring-red-100';
  if (status === 'needs_review') return 'bg-amber-50 text-amber-700 ring-1 ring-amber-100';
  if (status === 'dismissed') return 'bg-slate-100 text-slate-500';
  return 'bg-slate-100 text-slate-500';
}

function reviewBadgeLabel(status: string): string {
  const map: Record<string, string> = {
    confirmed: 'Confirmed',
    needs_review: 'Needs review',
    dismissed: 'Dismissed',
    unreviewed: 'Unreviewed',
  };
  return map[status] ?? 'Unreviewed';
}

function pct(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function buildJobRow(j: RawJob): JobRow {
  const results = Array.isArray(j.results) ? j.results : [];
  let high = 0, medium = 0;
  let scoreSum = 0, scoreMax = 0;

  for (const r of results) {
    const level = String(r.risk_level || '').toUpperCase();
    const score = Number(r.score) || 0;
    if (level === 'CRITICAL' || level === 'HIGH') high += 1;
    else if (level === 'MEDIUM') medium += 1;
    scoreSum += score;
    if (score > scoreMax) scoreMax = score;
  }

  const total = results.length;
  // Fallback to summary data if results array is absent (history page truncation)
  const suspiciousFallback = j.summary?.suspicious_pairs ?? 0;
  const avgFallback = j.summary?.average_similarity ?? 0;

  return {
    id: j.id,
    assignmentName: j.assignment_name || 'Untitled',
    courseName: j.course_name || '',
    submissions: Number(j.file_count) || 0,
    highRiskPairs: total ? high : suspiciousFallback,
    mediumRiskPairs: medium,
    totalPairs: total,
    avgSimilarity: total ? scoreSum / total : avgFallback,
    maxSimilarity: total ? scoreMax : 0,
    status: j.status || 'unknown',
    reviewStatus: j.review_status || 'unreviewed',
    createdAt: j.created_at || '',
  };
}

// ── Page ──────────────────────────────────────────────────────────────────────

const FILTERS = ['All', 'High Risk', 'Medium', 'Cleared', 'Unreviewed'] as const;
type Filter = (typeof FILTERS)[number];

export default function AssignmentsPage() {
  const [activeFilter, setActiveFilter] = useState<Filter>('All');
  const [jobs, setJobs] = useState<JobRow[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiClient
      .get('/api/jobs')
      .then((res) => {
        const raw: RawJob[] = (res.data?.jobs ?? []) as RawJob[];
        // Only show completed jobs on this page
        setJobs(
          raw
            .filter((j) => j.status === 'completed')
            .map(buildJobRow)
            .sort((a, b) => b.maxSimilarity - a.maxSimilarity)
        );
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to load data.');
      })
      .finally(() => setLoaded(true));
  }, []);

  // Aggregate stats
  const totalSubmissions = useMemo(
    () => jobs.reduce((s, j) => s + j.submissions, 0),
    [jobs]
  );
  const highRiskCount = useMemo(
    () => jobs.filter((j) => j.maxSimilarity >= 0.75).length,
    [jobs]
  );
  const mediumCount = useMemo(
    () => jobs.filter((j) => j.maxSimilarity >= 0.45 && j.maxSimilarity < 0.75).length,
    [jobs]
  );
  const clearedCount = useMemo(
    () => jobs.filter((j) => j.maxSimilarity < 0.45).length,
    [jobs]
  );

  const rows = useMemo(() => {
    if (activeFilter === 'High Risk') return jobs.filter((j) => j.maxSimilarity >= 0.75);
    if (activeFilter === 'Medium')
      return jobs.filter((j) => j.maxSimilarity >= 0.45 && j.maxSimilarity < 0.75);
    if (activeFilter === 'Cleared') return jobs.filter((j) => j.maxSimilarity < 0.45);
    if (activeFilter === 'Unreviewed')
      return jobs.filter((j) => j.reviewStatus === 'unreviewed');
    return jobs;
  }, [jobs, activeFilter]);

  return (
    <DashboardLayout>
      <div className="theme-page-container space-y-6">
        <PageHeader
          eyebrow="Assignment Results"
          title="Review programming assignment risk in one professional table."
          description="Each row is a completed plagiarism check. Click View to open the full side-by-side comparison."
          action={
            <ButtonLink href="/upload" icon={FileUp}>
              Upload New Assignment
            </ButtonLink>
          }
          eyebrowStyle="badge"
        />

        {/* Stats */}
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="Total submissions"
            value={loaded ? String(totalSubmissions) : '…'}
            detail="Files analyzed across completed checks"
            icon={Users}
            tone="blue"
          />
          <StatCard
            label="High risk checks"
            value={loaded ? String(highRiskCount) : '…'}
            detail="Checks with max similarity ≥ 75%"
            icon={ShieldAlert}
            tone="red"
          />
          <StatCard
            label="Medium risk checks"
            value={loaded ? String(mediumCount) : '…'}
            detail="Checks with max similarity 45–74%"
            icon={Inbox}
          />
          <StatCard
            label="Cleared"
            value={loaded ? String(clearedCount) : '…'}
            detail="Checks with max similarity < 45%"
            icon={CheckCircle2}
            tone="green"
          />
        </section>

        {/* Table */}
        <Card>
          <CardHeader
            title="Checks ranked by highest similarity"
            description="Real scores from the analysis pipeline — click View to inspect pairs, evidence signals, and code diffs."
            action={
              <div className="flex flex-wrap gap-2">
                {FILTERS.map((f) => (
                  <button
                    key={f}
                    type="button"
                    onClick={() => setActiveFilter(f)}
                    className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold transition ${activeFilter === f
                        ? 'bg-blue-600 text-white'
                        : 'border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800'
                      }`}
                  >
                    <Filter size={14} />
                    {f}
                  </button>
                ))}
              </div>
            }
          />

          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px]">
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
                    <th
                      key={h}
                      className="theme-table-header px-4 py-3 text-left"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </TableHeader>
              <TableBody>
                {!loaded ? (
                  <tr>
                    <td
                      colSpan={7}
                      className="px-4 py-10 text-center text-sm text-slate-500 dark:text-slate-400"
                    >
                      Loading checks…
                    </td>
                  </tr>
                ) : error ? (
                  <tr>
                    <td
                      colSpan={7}
                      className="px-4 py-10 text-center text-sm text-red-600 dark:text-red-400"
                    >
                      {error}
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
                        : 'No checks match this filter.'}
                    </td>
                  </tr>
                ) : (
                  rows.map((job, index) => (
                    <tr
                      key={job.id}
                      className="bg-white transition hover:bg-slate-50 dark:bg-slate-950 dark:hover:bg-slate-900/40"
                    >
                      {/* Rank */}
                      <td className="px-4 py-4 text-sm font-semibold text-slate-500 dark:text-slate-400">
                        #{index + 1}
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
                        <div className="mt-0.5 text-[10px] text-slate-400 dark:text-slate-600 font-mono">
                          {new Date(job.createdAt).toLocaleDateString()}
                        </div>
                      </td>

                      {/* Submissions */}
                      <td className="px-4 py-4 text-sm font-medium text-slate-700 dark:text-slate-300">
                        {job.submissions}
                      </td>

                      {/* Max similarity — real score with risk tier badge */}
                      <td className="px-4 py-4">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-sm font-semibold text-slate-900 dark:text-white">
                            {pct(job.maxSimilarity)}
                          </span>
                          <span
                            className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold ${riskTierClass(
                              job.maxSimilarity
                            )}`}
                          >
                            {riskTierLabel(job.maxSimilarity)}
                          </span>
                        </div>
                        <div className="mt-1 h-1.5 w-24 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                          <div
                            className={`h-full rounded-full transition-all ${job.maxSimilarity >= 0.75
                                ? 'bg-red-500'
                                : job.maxSimilarity >= 0.45
                                  ? 'bg-amber-500'
                                  : 'bg-emerald-500'
                              }`}
                            style={{ width: `${Math.min(100, Math.round(job.maxSimilarity * 100))}%` }}
                          />
                        </div>
                      </td>

                      {/* High-risk pairs */}
                      <td className="px-4 py-4 text-sm text-slate-700 dark:text-slate-300">
                        {job.highRiskPairs > 0 ? (
                          <span className="inline-flex items-center rounded-full bg-red-50 px-2.5 py-1 text-xs font-semibold text-red-700 ring-1 ring-red-100">
                            {job.highRiskPairs}
                          </span>
                        ) : (
                          <span className="text-slate-400">0</span>
                        )}
                      </td>

                      {/* Review status */}
                      <td className="px-4 py-4">
                        <span
                          className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${reviewBadgeClass(
                            job.reviewStatus
                          )}`}
                        >
                          {reviewBadgeLabel(job.reviewStatus)}
                        </span>
                      </td>

                      {/* Actions — link to /results/:id (the real review workspace) */}
                      <td className="px-4 py-4">
                        <a
                          href={`/results/${job.id}`}
                          className="inline-flex items-center gap-1.5 text-sm font-semibold text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
                        >
                          View <ExternalLink size={12} />
                        </a>
                      </td>
                    </tr>
                  ))
                )}
              </TableBody>
            </table>
          </div>
        </Card>
      </div>
    </DashboardLayout>
  );
}
