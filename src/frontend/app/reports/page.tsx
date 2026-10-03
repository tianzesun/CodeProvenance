'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import type { ElementType } from 'react';
import DashboardLayout from '@/components/DashboardLayout';
import { ButtonLink, CardHeader, PageHeader } from '@/components/saas/SaaSPrimitives';
import { apiClient } from '@/lib/apiClient';
import {
  AlertCircle,
  BarChart3,
  Clock,
  Download,
  FileText,
  Landmark,
  Loader2,
  PieChart,
} from 'lucide-react';

// ─── Types ─────────────────────────────────────────────────────────────────────

type ExportFormat = 'JSON' | 'CSV' | 'PDF';
type ExportStatus = 'ready' | 'coming-soon';

interface ExportContext {
  signal: AbortSignal;
  onProgress: (done: number, total: number) => void;
}

interface ExportResult {
  filename: string;
  blob: Blob;
  /** Non-fatal problems the user should know about (partial or truncated exports). */
  warnings: string[];
}

interface ReportDefinition {
  id: string;
  title: string;
  description: string;
  detail: string;
  icon: ElementType;
  format: ExportFormat;
  status: ExportStatus;
  accentColor: string;
  iconBg: string;
  iconColor: string;
  run: (context: ExportContext) => Promise<ExportResult>;
}

interface RecentExport {
  id: string;
  name: string;
  filename: string;
  format: ExportFormat;
  generatedAt: string;
  size: string;
  blob: Blob;
}

type ExportOutcome =
  | { ok: true; warnings: string[] }
  | { ok: false; kind: 'empty' | 'cancelled' | 'error'; message: string };

type AnyCase = {
  id?: string;
  title?: string;
  status?: string;
  priority?: string;
  assignment?: { title?: string; course_name?: string };
};

class NothingToExportError extends Error {}

// ─── Constants ─────────────────────────────────────────────────────────────────

const CASE_LIMIT = 1000;
const EXPORT_CONCURRENCY = 5;
const MAX_RECENT_EXPORTS = 10;

// ─── Errors ────────────────────────────────────────────────────────────────────

const REFERENCE_HEADERS = ['x-correlation-id', 'x-request-id'];

function getErrorInfo(error: unknown): { status?: number; reference?: string } {
  const response = (error as { response?: { status?: unknown; headers?: unknown } } | null)?.response;
  if (!response || typeof response !== 'object') {
    return {};
  }

  const status = typeof response.status === 'number' ? response.status : undefined;
  const headers = (response.headers ?? {}) as Record<string, unknown>;
  const reference = REFERENCE_HEADERS.map((name) => headers[name]).find(
    (value): value is string => typeof value === 'string' && value.length > 0
  );

  return { status, reference };
}

/** Generic, status-keyed text; a correlation id is appended when the backend sends one. */
function describeExportError(error: unknown): string {
  const { status, reference } = getErrorInfo(error);

  let message: string;
  if (status === 401) {
    message = 'Your session has expired. Please sign in again.';
  } else if (status === 403) {
    message = 'You don’t have permission to export this report.';
  } else if (status === 429) {
    message = 'Too many requests. Please wait a moment and try again.';
  } else {
    message = 'Export failed. Please try again.';
  }

  return reference ? `${message} (Reference: ${reference})` : message;
}

// ─── Export builders ───────────────────────────────────────────────────────────

/** Local calendar date (YYYY-MM-DD). toISOString() is UTC and gives tomorrow's date in the evening. */
function dateStamp(): string {
  return new Intl.DateTimeFormat('en-CA').format(new Date());
}

function triggerDownload(filename: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  // Revoking straight away can cancel the download in some browsers.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function formatBytes(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${bytes} B`;
}

/**
 * CSV-safe cell. Text beginning with = + - @ (or a tab / carriage return) is
 * prefixed with an apostrophe so Excel and Sheets show it as text instead of
 * running it as a formula (CSV injection): course names are user-entered.
 */
function csvCell(value: string | number): string {
  let text = String(value);
  if (typeof value === 'string' && /^[=+\-@\t\r]/.test(text)) {
    text = `'${text}`;
  }
  if (/[",\r\n]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

async function fetchCases(signal: AbortSignal): Promise<{ cases: AnyCase[]; truncated: boolean }> {
  const res = await apiClient.get('/api/cases', { params: { limit: CASE_LIMIT }, signal });
  const data = res.data;
  const cases: AnyCase[] = Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : [];
  // The endpoint is called with a hard limit and no paging, so a full page means there may be more.
  return { cases, truncated: cases.length >= CASE_LIMIT };
}

/** Run `worker` over `items` with a bounded number in flight, keeping result order. */
async function mapWithConcurrency<T, R>(
  items: T[],
  limit: number,
  signal: AbortSignal,
  worker: (item: T) => Promise<R>
): Promise<R[]> {
  const results = new Array<R>(items.length);
  let next = 0;

  const runners = Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (true) {
      if (signal.aborted) {
        throw new DOMException('Aborted', 'AbortError');
      }
      const index = next++;
      if (index >= items.length) {
        return;
      }
      results[index] = await worker(items[index]);
    }
  });

  await Promise.all(runners);
  return results;
}

async function buildEvidencePackets({ signal, onProgress }: ExportContext): Promise<ExportResult> {
  const { cases, truncated } = await fetchCases(signal);
  const withIds = cases.filter((c) => c.id);

  if (withIds.length === 0) {
    throw new NothingToExportError('There are no cases to export yet.');
  }

  let done = 0;
  let failed = 0;
  onProgress(0, withIds.length);

  const bundles = await mapWithConcurrency(withIds, EXPORT_CONCURRENCY, signal, async (c) => {
    try {
      const r = await apiClient.get(`/api/cases/${encodeURIComponent(String(c.id))}/export`, { signal });
      return (r.data || {}) as unknown;
    } catch (error) {
      if (signal.aborted) {
        throw error;
      }
      failed += 1;
      return { id: c.id, title: c.title, error: 'export unavailable' };
    } finally {
      done += 1;
      onProgress(done, withIds.length);
    }
  });

  const warnings: string[] = [];
  if (failed > 0) {
    warnings.push(
      `${failed} of ${withIds.length} cases couldn’t be exported and are marked “export unavailable” in the file.`
    );
  }
  if (truncated) {
    warnings.push(`Only the first ${CASE_LIMIT.toLocaleString('en-US')} cases were exported; there may be more.`);
  }

  const payload = {
    generated_at: new Date().toISOString(),
    case_count: bundles.length,
    failed_count: failed,
    truncated,
    cases: bundles,
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  return { filename: `evidence-packets-${dateStamp()}.json`, blob, warnings };
}

async function buildSemesterSummary({ signal }: ExportContext): Promise<ExportResult> {
  const { cases, truncated } = await fetchCases(signal);

  if (cases.length === 0) {
    throw new NothingToExportError('There are no cases to export yet.');
  }

  const byCourse = new Map<
    string,
    { open: number; under_review: number; escalated: number; closed: number; high: number; medium: number; low: number }
  >();
  for (const c of cases) {
    const course = c.assignment?.course_name || 'Unknown Course';
    const row = byCourse.get(course) || { open: 0, under_review: 0, escalated: 0, closed: 0, high: 0, medium: 0, low: 0 };
    const status = (c.status || '').toUpperCase();
    if (status === 'OPEN') row.open += 1;
    if (status === 'UNDER_REVIEW') row.under_review += 1;
    if (status === 'ESCALATED') row.escalated += 1;
    if (status === 'CLOSED') row.closed += 1;
    const priority = (c.priority || '').toUpperCase();
    if (priority === 'HIGH' || priority === 'URGENT') row.high += 1;
    else if (priority === 'MEDIUM') row.medium += 1;
    else if (priority === 'LOW') row.low += 1;
    byCourse.set(course, row);
  }

  // generated_at is a column rather than a trailing "generated_at,<time>" line, which
  // was a two-cell row under an eight-column header and broke imports and pivots.
  const generatedAt = new Date().toISOString();
  const header = [
    'course',
    'open',
    'under_review',
    'escalated',
    'closed',
    'high_priority',
    'medium_priority',
    'low_priority',
    'generated_at',
  ];
  const lines = [header.map(csvCell).join(',')];
  const courses = [...byCourse.entries()].sort(([a], [b]) => a.localeCompare(b));
  for (const [course, row] of courses) {
    const cells = [course, row.open, row.under_review, row.escalated, row.closed, row.high, row.medium, row.low, generatedAt];
    lines.push(cells.map(csvCell).join(','));
  }

  // BOM so Excel reads accented course names as UTF-8; CRLF per the CSV convention.
  const blob = new Blob(['\uFEFF' + lines.join('\r\n') + '\r\n'], { type: 'text/csv;charset=utf-8' });
  const warnings = truncated
    ? [`Only the first ${CASE_LIMIT.toLocaleString('en-US')} cases were counted; totals may be incomplete.`]
    : [];
  return { filename: `semester-summary-${dateStamp()}.csv`, blob, warnings };
}

// ─── Data ──────────────────────────────────────────────────────────────────────

const REPORTS: ReportDefinition[] = [
  {
    id: 'evidence-packets',
    title: 'Evidence Packets',
    description: 'Case-specific evidence bundles for academic integrity review committees.',
    detail: 'Every case in the live record: metadata, linked results, and reviewer notes.',
    icon: FileText,
    format: 'JSON',
    status: 'ready',
    accentColor: 'border-blue-100 dark:border-slate-900 hover:dark:border-blue-900/40',
    iconBg: 'bg-blue-50 dark:bg-blue-950/50',
    iconColor: 'text-blue-600 dark:text-blue-400',
    run: buildEvidencePackets,
  },
  {
    id: 'semester-summary',
    title: 'Semester Summary',
    description: 'Course-level review outcomes by case status and priority.',
    detail: 'Per-course tallies of case status and priority computed from the live case list.',
    icon: PieChart,
    format: 'CSV',
    status: 'ready',
    accentColor: 'border-violet-100 dark:border-slate-900 hover:dark:border-violet-900/40',
    iconBg: 'bg-violet-50 dark:bg-violet-950/50',
    iconColor: 'text-violet-600 dark:text-violet-400',
    run: buildSemesterSummary,
  },
  {
    id: 'department-stats',
    title: 'Department Statistics',
    description: 'Cross-course integrity patterns for department administrators.',
    detail: 'Aggregated risk scores, repeat-offender rates, and semester-over-semester deltas.',
    icon: Landmark,
    format: 'CSV',
    status: 'coming-soon',
    accentColor: 'border-slate-200 dark:border-slate-900 hover:dark:border-slate-800',
    iconBg: 'bg-slate-100 dark:bg-slate-900',
    iconColor: 'text-slate-500 dark:text-slate-400',
    run: () => Promise.reject(new Error('Coming soon')),
  },
];

const EMPTY_STATE_COPY = {
  title: 'No exports yet',
  description: 'Generate your first report above to see it here.',
};

// ─── Helpers ───────────────────────────────────────────────────────────────────

function startOfDay(date: Date): number {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
}

/** Calendar-day based, so something exported at 11 pm shows "Yesterday" the next morning. */
function formatRelativeDate(iso: string): string {
  const date = new Date(iso);
  const diffDays = Math.round((startOfDay(new Date()) - startOfDay(date)) / (1000 * 60 * 60 * 24));

  if (diffDays <= 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays} days ago`;

  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(date);
}

// ─── Sub-components ────────────────────────────────────────────────────────────

function FormatBadge({ format }: { format: ExportFormat }) {
  const styles: Record<ExportFormat, string> = {
    JSON: 'bg-blue-50 text-blue-600 dark:bg-blue-950/30 dark:text-blue-400',
    CSV: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-400',
    PDF: 'bg-red-50 text-red-600 dark:bg-red-950/30 dark:text-red-400',
  };

  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 font-mono text-[11px] font-semibold tracking-wide ${styles[format]}`}
    >
      {format}
    </span>
  );
}

function StatusChip({ status }: { status: ExportStatus }) {
  if (status !== 'coming-soon') return null;
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-500 dark:bg-slate-800 dark:text-slate-400">
      <Clock size={10} aria-hidden="true" />
      Coming soon
    </span>
  );
}

// ─── Report card ───────────────────────────────────────────────────────────────

type CardMessage = { tone: 'error' | 'warning' | 'info'; text: string };

const MESSAGE_STYLES: Record<CardMessage['tone'], string> = {
  error: 'text-red-600 dark:text-red-400',
  warning: 'text-amber-700 dark:text-amber-400',
  info: 'text-slate-500 dark:text-slate-400',
};

function ReportCard({
  report,
  activeId,
  progress,
  onExport,
  onCancel,
}: {
  report: ReportDefinition;
  activeId: string | null;
  progress: { done: number; total: number } | null;
  onExport: (report: ReportDefinition) => Promise<ExportOutcome>;
  onCancel: () => void;
}) {
  const [message, setMessage] = useState<CardMessage | null>(null);

  const isActive = activeId === report.id;
  // One export at a time: a large export fires many requests, so don't stack them.
  const isDisabled = report.status === 'coming-soon' || activeId !== null;

  const handleExport = async () => {
    if (isDisabled) return;
    setMessage(null);

    const outcome = await onExport(report);
    if (outcome.ok) {
      setMessage(outcome.warnings.length > 0 ? { tone: 'warning', text: outcome.warnings.join(' ') } : null);
    } else {
      setMessage({ tone: outcome.kind === 'error' ? 'error' : 'info', text: outcome.message });
    }
  };

  return (
    <div
      className={`group flex flex-col rounded-[24px] border bg-white p-6 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md dark:bg-slate-950 ${report.accentColor}`}
    >
      {/* Icon + format */}
      <div className="flex items-start justify-between">
        <div
          className={`flex h-11 w-11 items-center justify-center rounded-xl ${report.iconBg}`}
        >
          <report.icon size={19} className={report.iconColor} aria-hidden="true" />
        </div>
        <FormatBadge format={report.format} />
      </div>

      {/* Title + description */}
      <h2 className="mt-5 text-base font-semibold text-slate-900 dark:text-white">
        {report.title}
      </h2>
      <p className="mt-1.5 text-sm leading-6 text-slate-600 dark:text-slate-400">
        {report.description}
      </p>

      {/* Detail line */}
      <p className="mt-3 text-xs leading-5 text-slate-500 dark:text-slate-500">
        {report.detail}
      </p>

      {/* CTA */}
      <div className="mt-6 flex items-center gap-3">
        {report.status === 'coming-soon' ? (
          <StatusChip status="coming-soon" />
        ) : (
          <>
            <button
              type="button"
              disabled={isDisabled}
              aria-busy={isActive}
              aria-label={isActive ? `Generating ${report.title}` : `Export ${report.title}`}
              onClick={handleExport}
              className="inline-flex h-9 items-center gap-2 rounded-xl bg-slate-950 px-4 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-white dark:text-slate-950 dark:hover:bg-slate-100"
            >
              {isActive ? (
                <Loader2 size={14} className="animate-spin" aria-hidden="true" />
              ) : (
                <Download size={14} aria-hidden="true" />
              )}
              {isActive ? (progress ? `Generating… ${progress.done}/${progress.total}` : 'Generating…') : 'Export'}
            </button>
            {isActive && (
              <button
                type="button"
                onClick={onCancel}
                className="inline-flex h-9 items-center rounded-xl border border-slate-200 px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-100 dark:border-slate-800 dark:text-slate-300 dark:hover:bg-slate-900"
              >
                Cancel
              </button>
            )}
          </>
        )}
      </div>

      {message && (
        <p
          role={message.tone === 'error' ? 'alert' : 'status'}
          className={`mt-3 inline-flex items-start gap-1.5 text-xs font-medium ${MESSAGE_STYLES[message.tone]}`}
        >
          <AlertCircle size={13} className="mt-0.5 shrink-0" aria-hidden="true" />
          <span>{message.text}</span>
        </p>
      )}
    </div>
  );
}

// ─── Recent export row ─────────────────────────────────────────────────────────

function RecentExportRow({ item }: { item: RecentExport }) {
  // Re-download under the original filename (it used to be rebuilt without the date).
  const handleDownload = () => {
    triggerDownload(item.filename, item.blob);
  };

  return (
    <div className="flex items-center justify-between gap-4 px-5 py-4">
      <div className="flex min-w-0 items-center gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-100 dark:bg-slate-900">
          <FileText size={15} className="text-slate-500 dark:text-slate-400" aria-hidden="true" />
        </div>
        <div className="min-w-0">
          <div className="truncate text-sm font-medium text-slate-900 dark:text-white">
            {item.name}
          </div>
          <div className="mt-0.5 flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
            <span>{formatRelativeDate(item.generatedAt)}</span>
            <span aria-hidden="true">·</span>
            <span>{item.size}</span>
          </div>
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-3">
        <FormatBadge format={item.format} />
        <button
          type="button"
          onClick={handleDownload}
          aria-label={`Download ${item.name} (${item.format})`}
          className="inline-flex h-8 items-center gap-1.5 rounded-xl border border-slate-200 px-3 text-xs font-semibold text-slate-700 transition hover:bg-slate-100 dark:border-slate-800 dark:text-slate-300 dark:hover:bg-slate-900"
        >
          <Download size={12} aria-hidden="true" />
          Download
        </button>
      </div>
    </div>
  );
}

// ─── Page ──────────────────────────────────────────────────────────────────────

export default function ReportsPage() {
  const [recentExports, setRecentExports] = useState<RecentExport[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [announcement, setAnnouncement] = useState('');
  const abortRef = useRef<AbortController | null>(null);
  const counterRef = useRef(0);

  // Leaving the page cancels any export still fetching.
  useEffect(() => () => abortRef.current?.abort(), []);

  const runExport = useCallback(async (report: ReportDefinition): Promise<ExportOutcome> => {
    if (abortRef.current) {
      return { ok: false, kind: 'error', message: 'Another export is already running.' };
    }

    const controller = new AbortController();
    abortRef.current = controller;
    setActiveId(report.id);
    setProgress(null);
    setAnnouncement('');

    try {
      const result = await report.run({
        signal: controller.signal,
        onProgress: (done, total) => setProgress({ done, total }),
      });

      triggerDownload(result.filename, result.blob);

      counterRef.current += 1;
      const item: RecentExport = {
        id: `${report.id}-${Date.now()}-${counterRef.current}`,
        name: report.title,
        filename: result.filename,
        format: report.format,
        generatedAt: new Date().toISOString(),
        size: formatBytes(result.blob.size),
        blob: result.blob,
      };
      // Each blob holds case data in memory, so only the latest few are kept.
      setRecentExports((prev) => [item, ...prev].slice(0, MAX_RECENT_EXPORTS));
      setAnnouncement(`${report.title} exported.`);

      return { ok: true, warnings: result.warnings };
    } catch (error) {
      if (controller.signal.aborted) {
        return { ok: false, kind: 'cancelled', message: 'Export cancelled.' };
      }
      if (error instanceof NothingToExportError) {
        return { ok: false, kind: 'empty', message: error.message };
      }
      return { ok: false, kind: 'error', message: describeExportError(error) };
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
      }
      setActiveId(null);
      setProgress(null);
    }
  }, []);

  const handleCancel = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  return (
    <DashboardLayout>
      <div className="theme-page-container space-y-6">

        <PageHeader
          eyebrow="Reports"
          title="Export evidence for departments and committees"
          description="Reports are generated from the live case record so every export is audit-ready."
          action={
            <ButtonLink href="/analytics" icon={BarChart3}>
              View Analytics
            </ButtonLink>
          }
          eyebrowStyle="badge"
        />

        {/* Screen-reader announcement when an export finishes */}
        <p role="status" className="sr-only">
          {announcement}
        </p>

        {/* ── Report cards ────────────────────────────────────────────────────── */}
        <section className="grid gap-4 md:grid-cols-3">
          {REPORTS.map((report) => (
            <ReportCard
              key={report.id}
              report={report}
              activeId={activeId}
              progress={progress}
              onExport={runExport}
              onCancel={handleCancel}
            />
          ))}
        </section>

        {/* ── Recent exports ──────────────────────────────────────────────────── */}
        <section className="overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
          <div className="px-6 pt-6 pb-5 lg:px-7 lg:pt-7">
            <CardHeader
              title="Recent exports"
              description={`Latest ${MAX_RECENT_EXPORTS} files generated in this session, kept in the browser for re-download.`}
              action={
                recentExports.length > 0 ? (
                  <button
                    type="button"
                    onClick={() => setRecentExports([])}
                    className="inline-flex h-8 items-center rounded-xl border border-slate-200 px-3 text-xs font-semibold text-slate-700 transition hover:bg-slate-100 dark:border-slate-800 dark:text-slate-300 dark:hover:bg-slate-900"
                  >
                    Clear
                  </button>
                ) : null
              }
            />
          </div>

          {recentExports.length === 0 ? (
            <div className="px-6 py-14 text-center lg:px-7">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 dark:bg-slate-900">
                <Download size={20} className="text-slate-400 dark:text-slate-600" aria-hidden="true" />
              </div>
              <h3 className="mt-4 text-sm font-semibold text-slate-900 dark:text-white">
                {EMPTY_STATE_COPY.title}
              </h3>
              <p className="mt-1.5 text-sm text-slate-500 dark:text-slate-400">
                {EMPTY_STATE_COPY.description}
              </p>
            </div>
          ) : (
            <div className="divide-y divide-slate-200 dark:divide-slate-800">
              {recentExports.map((item) => (
                <RecentExportRow key={item.id} item={item} />
              ))}
            </div>
          )}

          {/* Footer */}
          <div className="border-t border-slate-200 px-6 py-3.5 dark:border-slate-800 lg:px-7">
            <p className="text-xs text-slate-500 dark:text-slate-500">
              Generated on demand from the current case data. Refresh the page to start a new session.
            </p>
          </div>
        </section>

      </div>
    </DashboardLayout>
  );
}
