'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { PageHeader } from '@/components/saas/SaaSPrimitives';
import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import Link from 'next/link';
import { apiClient } from '@/lib/apiClient';
import {
  TrendingUp,
  ShieldCheck,
  AlertCircle,
  AlertTriangle,
  ChevronLeft,
  ChevronDown,
  RefreshCw,
  Download,
  Activity,
  Info,
  Search,
} from 'lucide-react';

// ─── Types ─────────────────────────────────────────────────────────────────────

interface StyleChange {
  submission_id: string;
  assignment_id: string;
  change_type: string;
  /** 0–1 */
  magnitude: number;
  /** 0–1 */
  confidence: number;
  explanation: string;
}

type SortOrder = 'confidence' | 'magnitude' | 'reported';

// ─── Constants ─────────────────────────────────────────────────────────────────

const HIGH_CONFIDENCE = 0.7;
const PAGE_STEP = 25;

const MAGNITUDE_BUCKETS = [
  { label: '0–20%', min: 0, max: 0.2 },
  { label: '20–40%', min: 0.2, max: 0.4 },
  { label: '40–60%', min: 0.4, max: 0.6 },
  { label: '60–80%', min: 0.6, max: 0.8 },
  { label: '80–100%', min: 0.8, max: 1.0001 },
];

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

  let message = 'Failed to load the style-change data. Please try again.';
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

/** The response used to be stored as-is, so anything but an array crashed `.filter`, and a missing number showed "NaN%". */
function normalizeAlerts(data: unknown): StyleChange[] {
  const raw = data as { alerts?: unknown } | null;
  const list = Array.isArray(data) ? data : Array.isArray(raw?.alerts) ? (raw?.alerts as unknown[]) : [];
  return list
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object')
    .map((item) => ({
      submission_id: String(item.submission_id ?? ''),
      assignment_id: String(item.assignment_id ?? ''),
      change_type: String(item.change_type ?? 'unknown'),
      magnitude: clamp01(item.magnitude),
      confidence: clamp01(item.confidence),
      explanation: String(item.explanation ?? ''),
    }));
}

function humanize(value: string): string {
  const text = value.replace(/_/g, ' ').trim();
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : 'Unknown';
}

function shortId(value: string): string {
  return value.length > 14 ? `${value.slice(0, 8)}…` : value;
}

/** CSV-safe cell: quotes escaped, and text starting with = + - @ prefixed so a spreadsheet won't run it as a formula. */
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

// ─── Components ────────────────────────────────────────────────────────────────

function SummaryCard({ value, label }: { value: string; label: string }) {
  return (
    <div className="rounded-[24px] border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950">
      <div className="text-2xl font-semibold text-slate-900 dark:text-white">{value}</div>
      <div className="text-sm text-slate-500 dark:text-slate-400">{label}</div>
    </div>
  );
}

// ─── Page ──────────────────────────────────────────────────────────────────────

export default function HistoricalFingerprintPage() {
  // The unused `useAuth`, `trends` state and `StyleTrend` type are gone.
  const [alerts, setAlerts] = useState<StyleChange[]>([]);
  // Starts true: with `false` the "No Style Changes Detected" message flashed before the request began.
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [loadedAt, setLoadedAt] = useState<Date | null>(null);

  const [query, setQuery] = useState('');
  const [highOnly, setHighOnly] = useState(false);
  const [typeFilter, setTypeFilter] = useState('all');
  const [order, setOrder] = useState<SortOrder>('confidence');
  const [visibleCount, setVisibleCount] = useState(PAGE_STEP);
  const requestIdRef = useRef(0);

  const loadHistoricalData = useCallback(async (signal?: AbortSignal) => {
    const requestId = ++requestIdRef.current;
    setLoading(true);
    setError('');
    try {
      const response = await apiClient.get('/api/historical-fingerprint/alerts', { signal });
      if (requestId !== requestIdRef.current) return;
      setAlerts(normalizeAlerts(response.data));
      setLoadedAt(new Date());
    } catch (err) {
      if (signal?.aborted || requestId !== requestIdRef.current) return;
      // Keeps the last alerts on screen; a failed refresh must not turn into "all clear".
      setError(describeError(err));
    } finally {
      if (requestId === requestIdRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    loadHistoricalData(controller.signal);
    return () => controller.abort();
  }, [loadHistoricalData]);

  const hasData = loadedAt !== null;

  const changeTypes = useMemo(() => Array.from(new Set(alerts.map((a) => a.change_type))).sort(), [alerts]);

  const visibleAlerts = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = alerts.filter((a) => {
      if (highOnly && a.confidence <= HIGH_CONFIDENCE) return false;
      if (typeFilter !== 'all' && a.change_type !== typeFilter) return false;
      if (q && ![a.assignment_id, a.submission_id, a.explanation, a.change_type].some((v) => v.toLowerCase().includes(q))) return false;
      return true;
    });
    if (order === 'confidence') return [...list].sort((a, b) => b.confidence - a.confidence || b.magnitude - a.magnitude);
    if (order === 'magnitude') return [...list].sort((a, b) => b.magnitude - a.magnitude || b.confidence - a.confidence);
    return list;
  }, [alerts, highOnly, typeFilter, query, order]);

  const stats = useMemo(() => {
    const high = alerts.filter((a) => a.confidence > HIGH_CONFIDENCE).length;
    const composite = alerts.filter((a) => a.change_type === 'composite').length;
    const avg = alerts.length ? alerts.reduce((sum, a) => sum + a.magnitude, 0) / alerts.length : 0;
    return { total: alerts.length, high, composite, avg };
  }, [alerts]);

  const buckets = useMemo(
    () => MAGNITUDE_BUCKETS.map((bucket) => ({
      ...bucket,
      count: alerts.filter((a) => a.magnitude >= bucket.min && a.magnitude < bucket.max).length,
    })),
    [alerts]
  );
  const maxBucket = Math.max(1, ...buckets.map((b) => b.count));

  const exportCsv = () => {
    const header = ['Submission', 'Assignment', 'Change type', 'Magnitude %', 'Confidence %', 'Explanation'];
    const rows = visibleAlerts.map((a) => [
      a.submission_id,
      a.assignment_id,
      a.change_type,
      (a.magnitude * 100).toFixed(1),
      (a.confidence * 100).toFixed(1),
      a.explanation,
    ]);
    const csv = [header, ...rows].map((row) => row.map(csvCell).join(',')).join('\r\n');
    const stamp = new Intl.DateTimeFormat('en-CA').format(new Date());
    triggerDownload(`style-change-alerts-${stamp}.csv`, new Blob(['\uFEFF' + csv + '\r\n'], { type: 'text/csv;charset=utf-8' }));
  };

  const stat = (value: string) => (loading && !hasData ? '…' : error && !hasData ? '—' : value);

  return (
    <DashboardLayout>
      <div className="theme-page-container space-y-6">
        {/* Header */}
        <div>
          <Link href="/" className="theme-link flex items-center gap-2 text-sm font-semibold">
            <ChevronLeft size={16} aria-hidden="true" />
            Back to Dashboard
          </Link>
        </div>
        <PageHeader
          eyebrow="Engine & R&D"
          eyebrowStyle="badge"
          title="Historical Fingerprint"
          description="Detect sudden style changes that may indicate AI or external code"
          action={
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => loadHistoricalData()}
                disabled={loading}
                className="inline-flex h-10 items-center gap-2 rounded-xl bg-blue-600 px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <RefreshCw size={16} className={loading ? 'animate-spin' : ''} aria-hidden="true" />
                {loading ? 'Refreshing…' : 'Refresh'}
              </button>
              {/* This button had no handler. It now exports the alerts currently listed. */}
              <button
                type="button"
                onClick={exportCsv}
                disabled={visibleAlerts.length === 0}
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
            A style change is a prompt for a conversation, not evidence of misconduct. Writing style shifts naturally with a new
            topic, tool, group work or simply learning. Review the submission and talk to the student before drawing any conclusion.
          </span>
        </p>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
          <SummaryCard value={stat(String(stats.total))} label="Style Changes Detected" />
          <SummaryCard value={stat(String(stats.high))} label="High Confidence Alerts" />
          <SummaryCard value={stat(String(stats.composite))} label="Composite Changes" />
          <SummaryCard value={stat(percent(stats.avg))} label="Avg Change Magnitude" />
        </div>

        {error && (
          <div
            role="alert"
            className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300"
          >
            <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
            <span className="flex-1">{error}{hasData ? ' Showing the last loaded alerts.' : ''}</span>
            <button
              type="button"
              onClick={() => loadHistoricalData()}
              className="inline-flex h-9 shrink-0 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
            >
              Retry
            </button>
          </div>
        )}

        {/* Alerts List */}
        <div className="overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-5 py-4 dark:border-slate-800">
            <div className="flex items-center gap-2">
              <TrendingUp size={16} className="text-slate-500 dark:text-slate-400" aria-hidden="true" />
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Style Change Alerts</h2>
            </div>
            {loadedAt && <span className="text-xs text-slate-500 dark:text-slate-400">Updated {formatTime(loadedAt)}</span>}
          </div>

          {alerts.length > 0 && (
            <div className="flex flex-wrap items-center gap-3 border-b border-slate-200 px-5 py-4 dark:border-slate-800">
              <div className="relative w-full sm:w-64">
                <Search
                  size={16}
                  className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                  aria-hidden="true"
                />
                <input
                  type="search"
                  name="alert-search"
                  autoComplete="off"
                  value={query}
                  onChange={(e) => { setQuery(e.target.value); setVisibleCount(PAGE_STEP); }}
                  placeholder="Search alerts"
                  aria-label="Search alerts"
                  className="h-10 w-full rounded-xl border border-slate-200 bg-white pl-9 pr-4 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white dark:placeholder:text-slate-500"
                />
              </div>
              <div className="relative">
                <select
                  value={typeFilter}
                  onChange={(e) => { setTypeFilter(e.target.value); setVisibleCount(PAGE_STEP); }}
                  aria-label="Filter by change type"
                  className="h-10 appearance-none rounded-xl border border-slate-200 bg-white pl-4 pr-9 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white"
                >
                  <option value="all">All change types</option>
                  {changeTypes.map((type) => (
                    <option key={type} value={type}>{humanize(type)}</option>
                  ))}
                </select>
                <ChevronDown
                  size={14}
                  className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400"
                  aria-hidden="true"
                />
              </div>
              <label className="inline-flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400">
                <input
                  type="checkbox"
                  checked={highOnly}
                  onChange={(e) => { setHighOnly(e.target.checked); setVisibleCount(PAGE_STEP); }}
                  className="mt-1 h-4 w-4 rounded border-slate-300 text-blue-600 dark:border-slate-700 dark:text-blue-400"
                />
                High confidence only (&gt; {Math.round(HIGH_CONFIDENCE * 100)}%)
              </label>
              <div className="ml-auto relative">
                <select
                  value={order}
                  onChange={(e) => setOrder(e.target.value as SortOrder)}
                  aria-label="Order alerts"
                  className="h-10 appearance-none rounded-xl border border-slate-200 bg-white pl-4 pr-9 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white"
                >
                  <option value="confidence">Highest confidence first</option>
                  <option value="magnitude">Largest change first</option>
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
            <div role="status" className="p-8 text-center">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-slate-900" aria-hidden="true"></div>
              <p className="mt-2 text-slate-500">Analyzing style trends...</p>
            </div>
          ) : !hasData ? (
            // The load failed. This used to fall through to "styles appear consistent", a false all-clear.
            <div className="p-8 text-center text-sm text-slate-500">The alerts couldn’t be loaded, so nothing can be said about style consistency yet.</div>
          ) : alerts.length === 0 ? (
            <div className="p-8 text-center">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-slate-100 mb-4">
                <ShieldCheck size={24} className="text-slate-400" aria-hidden="true" />
              </div>
              <h3 className="text-lg font-medium text-slate-800 mb-2">No Style Changes Flagged</h3>
              <p className="text-slate-500">
                No sudden style changes were found. This can also mean there isn’t enough submission history yet to compare.
              </p>
            </div>
          ) : visibleAlerts.length === 0 ? (
            <div className="p-8 text-center text-sm text-slate-500">No alerts match the current filters.</div>
          ) : (
            <>
              <p role="status" className="sr-only">{visibleAlerts.length} of {alerts.length} alerts shown</p>
              <ul className="divide-y divide-slate-100">
                {visibleAlerts.slice(0, visibleCount).map((alert, i) => {
                  const high = alert.confidence > HIGH_CONFIDENCE;
                  return (
                    <li key={`${alert.submission_id}-${alert.assignment_id}-${alert.change_type}-${i}`} className="p-4 hover:bg-slate-50">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="flex flex-wrap items-center gap-3 mb-2">
                            <span className="font-medium text-slate-900" title={alert.assignment_id}>
                              {alert.assignment_id ? shortId(alert.assignment_id) : 'Assignment'}
                            </span>
                            {/* The badge was always amber: it was coloured by getRiskColor('medium'). It now follows confidence. */}
                            <span className={`text-xs font-semibold px-2 py-1 rounded ${high ? 'text-orange-700 bg-orange-100' : 'text-slate-600 bg-slate-100'}`}>
                              {humanize(alert.change_type)}
                            </span>
                            {high && <span className="text-xs font-semibold text-orange-700">High confidence</span>}
                          </div>
                          {alert.submission_id && (
                            <div className="mb-1 text-xs text-slate-500">
                              Submission <span className="font-mono" title={alert.submission_id}>{shortId(alert.submission_id)}</span>
                            </div>
                          )}
                          {alert.explanation && <div className="text-sm text-slate-600 mb-2">{alert.explanation}</div>}
                          <div className="flex items-center gap-4 text-xs text-slate-500">
                            <span>Magnitude: {percent(alert.magnitude, 1)}</span>
                            <span>Confidence: {percent(alert.confidence)}</span>
                          </div>
                        </div>
                        <div className="text-right shrink-0">
                          <div className="text-lg font-bold text-slate-900">{percent(alert.magnitude)}</div>
                          <div className="text-xs text-slate-500">Change</div>
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
              {visibleAlerts.length > visibleCount && (
                <div className="border-t border-slate-100 p-3">
                  <button
                    type="button"
                    onClick={() => setVisibleCount((n) => n + PAGE_STEP)}
                    className="w-full rounded-xl border border-slate-200 py-2.5 text-sm font-semibold text-slate-600 hover:bg-slate-50"
                  >
                    Show more ({visibleAlerts.length - visibleCount} remaining)
                  </button>
                </div>
              )}
            </>
          )}
        </div>

        {/* Magnitude distribution, from the alerts above. This replaces a placeholder card that said
            "Style timeline visualization would appear here". */}
        {hasData && alerts.length > 0 && (
          <div className="mt-6 bg-white rounded-2xl border border-slate-200 p-4">
            <div className="flex items-center gap-2 mb-4">
              <Activity size={16} className="text-slate-500" aria-hidden="true" />
              <h2 className="font-medium text-slate-700">Change magnitude distribution</h2>
            </div>
            <div className="space-y-2">
              {buckets.map((bucket) => (
                <div key={bucket.label} className="flex items-center gap-3 text-sm">
                  <span className="w-20 shrink-0 text-slate-600">{bucket.label}</span>
                  <div className="h-3 flex-1 overflow-hidden rounded-full bg-slate-100" aria-hidden="true">
                    <div className="h-full rounded-full bg-violet-500" style={{ width: `${(bucket.count / maxBucket) * 100}%` }} />
                  </div>
                  <span className="w-10 shrink-0 text-right tabular-nums text-slate-700">{bucket.count}</span>
                </div>
              ))}
            </div>
            <p className="mt-3 text-xs text-slate-500">Number of alerts by how large the detected style change was.</p>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
