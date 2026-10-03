// @ts-nocheck — TODO: add proper types (tracked in types/api.ts)
'use client';
import DashboardLayout from '@/components/DashboardLayout';
import { useAuth } from '@/components/AuthProvider';
import { PageHeader } from '@/components/saas/SaaSPrimitives';
import { apiClient } from '@/lib/apiClient';
import Link from 'next/link';
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  XCircle,
  TrendingUp,
  BarChart3,
  ChevronDown,
  ChevronUp,
  FileText,
  Lightbulb,
  Cpu,
  Loader2,
  GraduationCap,
  Zap,
  RefreshCw,
  Database,
  Info,
} from 'lucide-react';
/* ─── helpers ──────────────────────────────────────────────────────────── */
const num = (value: unknown, fallback = 0): number => {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
};
const pct = (n: unknown) => (Number.isFinite(Number(n)) ? `${(Number(n) * 100).toFixed(1)}%` : '—');
const clampPercent = (n: unknown) => Math.max(0, Math.min(100, num(n)));

const REFERENCE_HEADERS = ['x-correlation-id', 'x-request-id'];

/** Generic, status-keyed text; a correlation id is appended when the backend sends one. */
function describeLoadError(err) {
  const status = typeof err?.response?.status === 'number' ? err.response.status : undefined;
  const headers = err?.response?.headers || {};
  const reference = REFERENCE_HEADERS.map((name) => headers[name]).find((v) => typeof v === 'string' && v);

  let message = 'Failed to load the error analysis. Please try again.';
  if (status === 401) message = 'Your session has expired. Please sign in again.';
  else if (status === 403) message = 'You don’t have permission to view the error analysis.';

  return reference ? `${message} (Reference: ${reference})` : message;
}

const asList = (value: unknown) => (Array.isArray(value) ? value : []);
const asRecord = (value: unknown) => (value && typeof value === 'object' && !Array.isArray(value) ? value : {});

/**
 * The page used to destructure the response directly, so a missing summary, list or contribution
 * map crashed it, and a missing number rendered as "NaN%". Everything is given a safe shape here.
 */
function normalizeAnalysis(raw) {
  const summary = asRecord(raw?.summary) as Record<string, unknown>;
  const contributions = asRecord(raw?.engineContributions) as Record<string, unknown>;
  return {
    summary: {
      totalPairs: num(summary.totalPairs),
      truePositives: num(summary.truePositives),
      falsePositives: num(summary.falsePositives),
      falseNegatives: num(summary.falseNegatives),
      trueNegatives: num(summary.trueNegatives),
      accuracy: summary.accuracy,
      precision: summary.precision,
      recall: summary.recall,
      f1: summary.f1,
    },
    falsePositives: asList(raw?.falsePositives),
    falseNegatives: asList(raw?.falseNegatives),
    engineContributions: {
      falsePositives: asRecord(contributions.falsePositives) as Record<string, unknown>,
      falseNegatives: asRecord(contributions.falseNegatives) as Record<string, unknown>,
    },
    recommendations: asList(raw?.recommendations).map((rec: Record<string, unknown>) => ({ ...rec, items: asList(rec?.items) })),
    dataset: typeof raw?.dataset === 'string' && raw.dataset ? raw.dataset : 'unnamed dataset',
    hasGroundTruth: Boolean(raw?.has_ground_truth),
  };
}

const PAGE_STEP = 20;
/* ─── sub-components ───────────────────────────────────────────────────── */
function MetricCard({ label, value, sub, color, icon: Icon, estimated = false }) {
  const palette = {
    blue: { bg: 'bg-blue-50 dark:bg-blue-500/10', border: 'border-blue-200 dark:border-blue-500/20', text: 'text-blue-700', icon: 'text-blue-500 dark:text-blue-400', sub: 'text-blue-500 dark:text-blue-300' },
    emerald: { bg: 'bg-emerald-50 dark:bg-emerald-500/10', border: 'border-emerald-200 dark:border-emerald-500/20', text: 'text-emerald-700', icon: 'text-emerald-500 dark:text-emerald-400', sub: 'text-emerald-500 dark:text-emerald-300' },
    amber: { bg: 'bg-amber-50 dark:bg-amber-500/10', border: 'border-amber-200 dark:border-amber-500/20', text: 'text-amber-700', icon: 'text-amber-500 dark:text-amber-400', sub: 'text-amber-500 dark:text-amber-300' },
    slate: { bg: 'bg-slate-50 dark:bg-slate-500/10', border: 'border-slate-200 dark:border-slate-500/20', text: 'text-slate-700', icon: 'text-slate-500 dark:text-slate-400', sub: 'text-slate-500 dark:text-slate-400' },
  }[color];
  return (
    <div className={`${palette.bg} ${palette.border} border rounded-2xl p-5 flex flex-col gap-3`}>
      <div className="flex items-center justify-between">
        <span className={`text-[11px] font-semibold uppercase tracking-[0.14em] ${palette.sub}`}>
          {label}
          {estimated && <span className="ml-1.5 rounded-full bg-white px-1.5 py-0.5 text-[11px] font-semibold normal-case tracking-normal dark:bg-slate-900">estimated</span>}
        </span>
        <Icon size={16} className={palette.icon} aria-hidden="true" />
      </div>
      <div className={`text-4xl font-semibold ${palette.text} leading-none dark:text-white`}>{value}</div>
      <div className={`text-xs ${palette.sub}`}>{sub}</div>
    </div>
  );
}
function ConfusionMatrix({ tp, fp, fn, tn, estimated = false }) {
  const total = tp + fp + fn + tn || 1;
  const cell = (value, label, sub, bg, text, border) => (
    <div className={`${bg} ${border} border rounded-2xl p-5 flex flex-col gap-1`}>
      <span className={`text-3xl font-semibold ${text}`}>{value}</span>
      <span className={`text-sm font-semibold ${text}`}>{label}</span>
      <span className="text-xs text-slate-500 dark:text-slate-400">{sub}</span>
      <span className="text-xs text-slate-500 dark:text-slate-400 mt-1">{((value / total) * 100).toFixed(1)}% of total</span>
    </div>
  );
  return (
    <div
      role="group"
      aria-label={`Confusion matrix${estimated ? ' (estimated)' : ''}: ${tp} true positives, ${fn} false negatives, ${fp} false positives, ${tn} true negatives`}
      className="space-y-3"
    >
      <div className="grid grid-cols-[auto_1fr_1fr] gap-3 items-center text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
        <div />
        <div className="text-center">Predicted Plagiarism</div>
        <div className="text-center">Predicted Original</div>
      </div>
      <div className="grid grid-cols-[auto_1fr_1fr] gap-3 items-stretch">
        <div className="flex flex-col justify-around text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 text-right pr-2 gap-3 dark:text-slate-400">
          <div>Actual<br />Plagiarism</div>
          <div>Actual<br />Original</div>
        </div>
        {cell(tp, 'True Positives', estimated ? 'Likely plagiarism that was flagged' : 'Correctly flagged plagiarism', 'bg-white dark:bg-slate-950', 'text-emerald-700 dark:text-emerald-300', 'border-slate-200 dark:border-slate-800')}
        {cell(fn, 'False Negatives', estimated ? 'Possible plagiarism that slipped through' : 'Plagiarism that slipped through', 'bg-white dark:bg-slate-950', 'text-amber-700 dark:text-amber-300', 'border-slate-200 dark:border-slate-800')}
        {cell(fp, 'False Positives', estimated ? 'Work that may have been flagged incorrectly' : 'Legitimate work incorrectly flagged', 'bg-white dark:bg-slate-950', 'text-red-700 dark:text-red-300', 'border-slate-200 dark:border-slate-800')}
        {cell(tn, 'True Negatives', estimated ? 'Likely original work that was cleared' : 'Correctly cleared as original', 'bg-white dark:bg-slate-950', 'text-slate-700 dark:text-slate-300', 'border-slate-200 dark:border-slate-800')}
      </div>
    </div>
  );
}
function ErrorCaseRow({ item, prefix, isOpen, onToggle, panelId }) {
  const score = num(item.score);
  const scorePct = (score * 100).toFixed(1);
  const scoreColor =
    score >= 0.7 ? 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300' :
      score >= 0.4 ? 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300' :
        'bg-slate-100 text-slate-700 dark:bg-slate-500/15 dark:text-slate-300';
  return (
    <div className="rounded-2xl border border-slate-200 overflow-hidden transition-shadow hover:shadow-sm dark:border-slate-800">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={isOpen}
        aria-controls={panelId}
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-slate-50/80 transition-colors text-left dark:hover:bg-slate-900/50"
      >
        <div className="flex items-center gap-3 min-w-0">
          <FileText size={15} className="text-slate-400 shrink-0" aria-hidden="true" />
          <span className="font-medium text-slate-900 truncate dark:text-white" title={item.fileA}>{item.fileA || 'Unnamed file'}</span>
          <span className="text-slate-400 shrink-0" aria-hidden="true">↔</span>
          <span className="sr-only"> and </span>
          <span className="font-medium text-slate-900 truncate dark:text-white" title={item.fileB}>{item.fileB || 'Unnamed file'}</span>
        </div>
        <div className="flex items-center gap-3 shrink-0 ml-4">
          <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${scoreColor}`}>
            {scorePct}% similarity
          </span>
          {isOpen ? <ChevronUp size={16} className="text-slate-400" aria-hidden="true" /> : <ChevronDown size={16} className="text-slate-400" aria-hidden="true" />}
        </div>
      </button>
      {isOpen && (
        <div id={panelId} className="border-t border-slate-200 px-5 pb-5 pt-4 space-y-4 dark:border-slate-800">
          <div className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700 dark:bg-slate-500/15 dark:text-slate-300">
            <AlertTriangle size={13} aria-hidden="true" />
            {item.reason}
          </div>
          <p className="text-sm text-slate-600 leading-relaxed dark:text-slate-400">{item.explanation}</p>
          {/* Engine feature breakdown */}
          {item.features && Object.keys(item.features).length > 0 && (
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 mb-2 dark:text-slate-400">Engine Scores</p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {Object.entries(item.features)
                  .sort(([, a], [, b]) => num(b) - num(a))
                  .slice(0, 6)
                  .map(([engine, score]) => (
                    <div key={engine} className="bg-slate-50 rounded-lg px-3 py-2 dark:bg-slate-900">
                      <div className="text-xs text-slate-500 capitalize dark:text-slate-400">{engine.replace(/_/g, ' ')}</div>
                      <div className="text-sm font-semibold text-slate-800 dark:text-white">{(num(score) * 100).toFixed(1)}%</div>
                      <div className="mt-1 h-1.5 bg-slate-200 rounded-full overflow-hidden dark:bg-slate-800" aria-hidden="true">
                        <div className="h-full bg-blue-500 rounded-full" style={{ width: `${clampPercent(num(score) * 100)}%` }} />
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          )}
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 mb-2 dark:text-slate-400">Feature Summary</p>
            <pre tabIndex={0} aria-label="Feature summary" className="bg-slate-950 text-slate-100 rounded-xl p-4 text-xs font-mono leading-relaxed overflow-x-auto">
              {item.codeSnippet}
            </pre>
          </div>
          <div className="flex items-start gap-3 bg-blue-50 border border-blue-200 rounded-2xl p-4 dark:border-blue-500/20 dark:bg-blue-500/10">
            <Lightbulb size={15} className="text-blue-500 mt-0.5 shrink-0 dark:text-blue-400" aria-hidden="true" />
            <div>
              <p className="text-xs font-semibold text-blue-700 mb-0.5 dark:text-blue-300">Recommendation</p>
              <p className="text-sm text-blue-700 dark:text-blue-300">{item.recommendation}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
function EngineBar({ engine, percent: rawPercent, color }) {
  const percent = Math.round(clampPercent(rawPercent) * 10) / 10;
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-sm">
        <span className="text-slate-700 capitalize font-medium dark:text-slate-300">{engine.replace(/_/g, ' ')}</span>
        <span className="font-semibold text-slate-900 tabular-nums dark:text-white">{percent}%</span>
      </div>
      <div className="w-full bg-slate-100 rounded-full h-2.5 dark:bg-slate-800" aria-hidden="true">
        <div className={`${color} h-2.5 rounded-full transition-all duration-700`} style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}
function SectionHeader({ icon: Icon, iconClass, title, count, description }) {
  return (
    <div className="mb-5">
      <div className="flex items-center gap-2.5 mb-1">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-100 dark:bg-slate-900">
          <Icon size={18} className={iconClass} aria-hidden="true" />
        </div>
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
          {title}
          {count !== undefined && (
            <span className="ml-2 text-sm font-semibold text-slate-500 dark:text-slate-400">({count} cases)</span>
          )}
        </h2>
      </div>
      <p className="text-sm text-slate-500 leading-relaxed pl-9 dark:text-slate-400">{description}</p>
    </div>
  );
}
/* ─── main page ────────────────────────────────────────────────────────── */
export default function ErrorAnalysisPage() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [data, setData] = useState(null);
  const [expandedErrors, setExpandedErrors] = useState(new Set());
  const [visibleFp, setVisibleFp] = useState(PAGE_STEP);
  const [visibleFn, setVisibleFn] = useState(PAGE_STEP);
  const requestIdRef = useRef(0);

  // Only the newest request may update state. A failed refresh keeps the report on screen (the old
  // code swapped it for a full-page spinner and then an error screen, losing scroll and open rows).
  const fetchData = useCallback(async (signal?: AbortSignal, { background = false } = {}) => {
    const requestId = ++requestIdRef.current;
    if (background) setRefreshing(true);
    else setLoading(true);
    setError('');
    try {
      const res = await apiClient.get('/api/error-analysis', { signal });
      if (requestId !== requestIdRef.current) return;
      setData(normalizeAnalysis(res.data));
    } catch (err) {
      if (signal?.aborted || requestId !== requestIdRef.current) return;
      setError(describeLoadError(err));
    } finally {
      if (requestId === requestIdRef.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetchData(controller.signal);
    return () => controller.abort();
  }, [fetchData]);

  const toggleError = (key) => {
    setExpandedErrors((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  if (loading && !data) {
    return (
      <DashboardLayout>
        <div className="theme-page-container space-y-6">
          <div role="status" className="flex min-h-[60vh] flex-col items-center justify-center gap-3">
            <Loader2 size={16} className="animate-spin text-slate-500 dark:text-slate-400" aria-hidden="true" />
            <p className="text-sm text-slate-500 font-medium dark:text-slate-400">Loading error analysis…</p>
          </div>
        </div>
      </DashboardLayout>
    );
  }
  if (error && !data) {
    return (
      <DashboardLayout>
        <div className="theme-page-container space-y-6">
          <div role="alert" className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300">
            <AlertTriangle size={16} className="shrink-0 mt-0.5" aria-hidden="true" />
            <span>{error}</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => fetchData()}
              className="inline-flex h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
            >
              <RefreshCw size={14} aria-hidden="true" /> Retry
            </button>
          </div>
        </div>
      </DashboardLayout>
    );
  }
  if (!data) return null;

  const { summary, falsePositives, falseNegatives, engineContributions, recommendations, dataset, hasGroundTruth } = data;
  const estimated = !hasGroundTruth;
  const noData = summary.totalPairs === 0;
  const isAdmin = user?.role === 'admin';

  return (
    <DashboardLayout>
      <div className="theme-page-container space-y-6">
          {/* ── Page Header ── */}
          <PageHeader
            eyebrow="Error Analysis"
            eyebrowStyle="badge"
            title="Error Analysis Report"
            description={
              noData
                ? 'No plagiarism checks or benchmark runs found yet.'
                : `Detection quality audit across ${summary.totalPairs.toLocaleString('en-US')} submission pairs`
            }
            action={
              <div className="flex flex-wrap items-center gap-2">
                {/* Data source badge */}
                <div className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${hasGroundTruth ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300' : 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300'
                  }`}>
                  <Database size={14} aria-hidden="true" />
                  {hasGroundTruth ? `Ground truth · ${dataset}` : `Heuristic · ${dataset}`}
                </div>
                {user && (
                  <div className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700 dark:bg-slate-500/15 dark:text-slate-300">
                    <GraduationCap size={14} aria-hidden="true" />
                    {isAdmin ? 'Admin View' : 'Professor View'}
                  </div>
                )}
                <button
                  type="button"
                  onClick={() => fetchData(undefined, { background: true })}
                  disabled={refreshing}
                  className="inline-flex h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
                >
                  <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} aria-hidden="true" /> {refreshing ? 'Refreshing…' : 'Refresh'}
                </button>
              </div>
            }
          />

          {error && (
            <div role="alert" className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300">
              <AlertTriangle size={16} className="shrink-0 mt-0.5" aria-hidden="true" />
              <span>{error} Showing the last loaded results.</span>
            </div>
          )}

          {/* ── No data state ── */}
          {noData && (
            <div className="rounded-[28px] border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
              <div className="px-5 py-16 text-center">
                <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-slate-100 text-slate-500 dark:bg-slate-900 dark:text-slate-400">
                  <Database size={22} aria-hidden="true" />
                </div>
                <h3 className="mt-4 text-base font-semibold text-slate-900 dark:text-white">No analysis data yet</h3>
                <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500 dark:text-slate-400">
                  Run a plagiarism check on the <strong>Upload</strong> page{isAdmin ? ', or run a benchmark with a labeled dataset' : ''} to generate real error analysis data.
                </p>
                <div className="mt-6 flex items-center justify-center gap-3">
                  <Link href="/upload" className="inline-flex h-10 items-center gap-2 rounded-xl bg-blue-600 px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50">
                    Run a Check
                  </Link>
                  {/* The benchmark page is admin-only; professors were sent to a page that rejected them. */}
                  {isAdmin && (
                    <Link href="/benchmark" className="inline-flex h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800">
                      Run Benchmark
                    </Link>
                  )}
                </div>
              </div>
            </div>
          )}
          {!noData && (
            <>
              {/* ── Ground truth notice ── */}
              {estimated && (
                <div role="status" className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-300">
                  <Info size={16} className="shrink-0 mt-0.5 text-amber-600 dark:text-amber-400" aria-hidden="true" />
                  <div>
                    <span className="font-semibold">Heuristic analysis — no ground-truth labels available.</span>
                    {' '}Every figure on this page is an estimate from score distributions, and a pair listed as a “false positive” or “false negative” has not been confirmed as one. Do not treat these lists as findings about students.
                    {isAdmin && ' Run a benchmark with a labeled dataset (for example a PAN or demo dataset) to get exact TP/FP/FN/TN counts.'}
                  </div>
                </div>
              )}
              {/* ── Metric Cards ── */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <MetricCard estimated={estimated} label="Accuracy" value={pct(summary.accuracy)} sub="Overall correctness" color="blue" icon={BarChart3} />
                <MetricCard estimated={estimated} label="Precision" value={pct(summary.precision)} sub="Flagged cases that are real" color="emerald" icon={CheckCircle2} />
                <MetricCard estimated={estimated} label="Recall" value={pct(summary.recall)} sub="Real cases detected" color="amber" icon={TrendingUp} />
                <MetricCard estimated={estimated} label="F1 Score" value={pct(summary.f1)} sub="Precision–recall balance" color="slate" icon={Zap} />
              </div>
              {/* ── Confusion Matrix ── */}
              <div className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950">
                <div className="flex items-center gap-2 mb-6">
                  <BarChart3 size={18} className="text-slate-500 dark:text-slate-400" aria-hidden="true" />
                  <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Confusion Matrix{estimated ? ' (estimated)' : ''}</h2>
                  <span className="ml-auto text-xs text-slate-500 font-medium dark:text-slate-400">
                    {summary.totalPairs.toLocaleString('en-US')} total pairs evaluated
                  </span>
                </div>
                <ConfusionMatrix
                  estimated={estimated}
                  tp={summary.truePositives}
                  fp={summary.falsePositives}
                  fn={summary.falseNegatives}
                  tn={summary.trueNegatives}
                />
              </div>
              {/* ── False Positives ── */}
              <div className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950">
                <SectionHeader
                  icon={XCircle}
                  iconClass="text-red-600 dark:text-red-400"
                  title={estimated ? 'Possible False Positives' : 'False Positives'}
                  count={falsePositives.length}
                  description={estimated
                    ? 'Pairs the system flagged that look more like legitimate work, judged from score patterns alone. Review them manually before drawing any conclusion.'
                    : 'Cases where the system incorrectly flagged legitimate work as plagiarism. These can damage student reputations and require urgent manual review.'}
                />
                {falsePositives.length === 0 ? (
                  <div className="px-5 py-16 text-center">
                    <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-slate-100 text-slate-500 dark:bg-slate-900 dark:text-slate-400">
                      <CheckCircle2 size={22} aria-hidden="true" />
                    </div>
                    <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500 dark:text-slate-400">
                      {estimated ? 'No likely false positives found in this data.' : 'No false positives detected in this dataset.'}
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {falsePositives.slice(0, visibleFp).map((fp, i) => {
                      const key = `fp-${fp.id ?? i}`;
                      return (
                        <ErrorCaseRow
                          key={key}
                          item={fp}
                          prefix="fp"
                          panelId={`panel-${key}`}
                          isOpen={expandedErrors.has(key)}
                          onToggle={() => toggleError(key)}
                        />
                      );
                    })}
                    {falsePositives.length > visibleFp && (
                      <button type="button" onClick={() => setVisibleFp((n) => n + PAGE_STEP)} className="inline-flex h-10 w-full items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800">
                        Show more ({falsePositives.length - visibleFp} remaining)
                      </button>
                    )}
                  </div>
                )}
              </div>
              {/* ── False Negatives ── */}
              <div className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950">
                <SectionHeader
                  icon={AlertTriangle}
                  iconClass="text-amber-600 dark:text-amber-400"
                  title={estimated ? 'Possible False Negatives' : 'False Negatives'}
                  count={falseNegatives.length}
                  description={estimated
                    ? 'Pairs that were not flagged but whose score patterns resemble plagiarism. These are estimates, not confirmed misses.'
                    : 'Cases where actual plagiarism went undetected. These are the more serious failure mode — cheating that reaches your gradebook unchallenged.'}
                />
                {falseNegatives.length === 0 ? (
                  <div className="px-5 py-16 text-center">
                    <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-slate-100 text-slate-500 dark:bg-slate-900 dark:text-slate-400">
                      <CheckCircle2 size={22} aria-hidden="true" />
                    </div>
                    <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500 dark:text-slate-400">
                      {estimated ? 'No likely false negatives found in this data.' : 'No false negatives detected in this dataset.'}
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {falseNegatives.slice(0, visibleFn).map((fn, i) => {
                      const key = `fn-${fn.id ?? i}`;
                      return (
                        <ErrorCaseRow
                          key={key}
                          item={fn}
                          prefix="fn"
                          panelId={`panel-${key}`}
                          isOpen={expandedErrors.has(key)}
                          onToggle={() => toggleError(key)}
                        />
                      );
                    })}
                    {falseNegatives.length > visibleFn && (
                      <button type="button" onClick={() => setVisibleFn((n) => n + PAGE_STEP)} className="inline-flex h-10 w-full items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800">
                        Show more ({falseNegatives.length - visibleFn} remaining)
                      </button>
                    )}
                  </div>
                )}
              </div>
              {/* ── Engine Contribution ── */}
              {(Object.keys(engineContributions.falsePositives).length > 0 ||
                Object.keys(engineContributions.falseNegatives).length > 0) && (
                  <div className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950">
                    <div className="flex items-center gap-2 mb-1">
                      <Cpu size={18} className="text-slate-500 dark:text-slate-400" aria-hidden="true" />
                      <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Engine Contribution to Errors</h2>
                    </div>
                    <p className="text-sm text-slate-500 mb-6 pl-7 dark:text-slate-400">
                      Which detection engines are responsible for each error type, computed from feature scores{estimated ? ' (estimated from the heuristic error lists above)' : ''}.
                    </p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 mb-4 dark:text-slate-400">False Positive Drivers</p>
                        <div className="space-y-4">
                          {Object.entries(engineContributions.falsePositives).map(([engine, percent]) => (
                            <EngineBar key={engine} engine={engine} percent={percent} color="bg-red-500" />
                          ))}
                          {Object.keys(engineContributions.falsePositives).length === 0 && (
                            <p className="text-sm text-slate-500 dark:text-slate-400">No false positive engine data available.</p>
                          )}
                        </div>
                      </div>
                      <div>
                        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 mb-4 dark:text-slate-400">False Negative Drivers</p>
                        <div className="space-y-4">
                          {Object.entries(engineContributions.falseNegatives).map(([engine, percent]) => (
                            <EngineBar key={engine} engine={engine} percent={percent} color="bg-amber-500" />
                          ))}
                          {Object.keys(engineContributions.falseNegatives).length === 0 && (
                            <p className="text-sm text-slate-500 dark:text-slate-400">No false negative engine data available.</p>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              {/* ── Recommendations ── */}
              {recommendations.length > 0 && (
                <div className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950">
                  <div className="flex items-center gap-2 mb-6">
                    <GraduationCap size={18} className="text-slate-500 dark:text-slate-400" aria-hidden="true" />
                    <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Actionable Recommendations</h2>
                    <span className="ml-auto text-xs text-slate-500 dark:text-slate-400">{estimated ? 'Based on estimated results' : 'Based on labeled results'}</span>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                    {recommendations.map((rec, recIndex) => {
                      const priorityColor = rec.priority === 'high'
                        ? 'border-t-red-500 dark:border-t-red-500'
                        : rec.priority === 'medium'
                          ? 'border-t-amber-500 dark:border-t-amber-500'
                          : 'border-t-emerald-500 dark:border-t-emerald-500';
                      const accentColor = rec.priority === 'high'
                        ? 'text-red-600 dark:text-red-400'
                        : rec.priority === 'medium'
                          ? 'text-amber-600 dark:text-amber-400'
                          : 'text-emerald-600 dark:text-emerald-400';
                      return (
                        <div key={`${rec.category ?? 'rec'}-${recIndex}`} className={`rounded-2xl border border-slate-200 border-t-2 ${priorityColor} bg-white p-4 space-y-3 dark:border-slate-800 dark:bg-slate-950`}>
                          <div className="flex items-center justify-between gap-2">
                            <h3 className={`text-sm font-semibold ${accentColor}`}>{rec.category}</h3>
                            <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold uppercase ${rec.priority === 'high' ? 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300' :
                                rec.priority === 'medium' ? 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300' :
                                  'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300'
                              }`}>{rec.priority}</span>
                          </div>
                          <ul className="space-y-3">
                            {rec.items.map((item, itemIndex) => (
                              <li key={`${item.title ?? 'item'}-${itemIndex}`}>
                                <p className="text-xs font-semibold text-slate-900 dark:text-white">{item.title}</p>
                                <p className="text-xs text-slate-500 leading-relaxed dark:text-slate-400">{item.detail}</p>
                              </li>
                            ))}
                          </ul>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </>
          )}
      </div>
    </DashboardLayout>
  );
}
