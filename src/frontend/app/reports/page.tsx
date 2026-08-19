'use client';

import { useState } from 'react';
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

interface ExportResult {
  filename: string;
  blob: Blob;
}

interface ReportDefinition {
  id: string;
  title: string;
  description: string;
  detail: string;
  icon: React.ElementType;
  format: ExportFormat;
  status: ExportStatus;
  accentColor: string;
  iconBg: string;
  iconColor: string;
  run: () => Promise<ExportResult>;
}

interface RecentExport {
  id: string;
  name: string;
  format: ExportFormat;
  generatedAt: string;
  size: string;
  blob: Blob;
}

type AnyCase = {
  id?: string;
  title?: string;
  status?: string;
  priority?: string;
  assignment?: { title?: string; course_name?: string };
};

// ─── Export builders ───────────────────────────────────────────────────────────

function dateStamp(): string {
  return new Date().toISOString().slice(0, 10);
}

function triggerDownload(filename: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function formatBytes(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${bytes} B`;
}

function csvCell(value: string | number): string {
  const text = String(value);
  if (/[",\n]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

async function buildEvidencePackets(): Promise<ExportResult> {
  const casesRes = await apiClient.get('/api/cases', { params: { limit: 1000 } });
  const cases = (casesRes.data || []) as AnyCase[];
  const bundles: unknown[] = [];
  for (const c of cases) {
    if (!c.id) continue;
    try {
      const r = await apiClient.get(`/api/cases/${c.id}/export`);
      bundles.push(r.data || {});
    } catch {
      bundles.push({ id: c.id, title: c.title, error: 'export unavailable' });
    }
  }
  const payload = {
    generated_at: new Date().toISOString(),
    case_count: bundles.length,
    cases: bundles,
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  return { filename: `evidence-packets-${dateStamp()}.json`, blob };
}

async function buildSemesterSummary(): Promise<ExportResult> {
  const casesRes = await apiClient.get('/api/cases', { params: { limit: 1000 } });
  const cases = (casesRes.data || []) as AnyCase[];
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
  const header = ['course', 'open', 'under_review', 'escalated', 'closed', 'high_priority', 'medium_priority', 'low_priority'];
  const lines = [header.map(csvCell).join(',')];
  for (const [course, row] of byCourse) {
    const cells = [course, row.open, row.under_review, row.escalated, row.closed, row.high, row.medium, row.low];
    lines.push(cells.map(csvCell).join(','));
  }
  lines.push(`generated_at,${csvCell(new Date().toISOString())}`);
  const blob = new Blob([lines.join('\n')], { type: 'text/csv' });
  return { filename: `semester-summary-${dateStamp()}.csv`, blob };
}

// ─── Data ──────────────────────────────────────────────────────────────────────

const REPORTS: ReportDefinition[] = [
  {
    id: 'evidence-packets',
    title: 'Evidence Packets',
    description: 'Case-specific evidence bundles for academic integrity review committees.',
    detail: 'Each open case exported from the live record: metadata, linked results, and reviewer notes.',
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
    description: 'Course-level review outcomes, reviewer activity, and trend summaries.',
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

function formatRelativeDate(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return 'Today';
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
      <Clock size={10} />
      Coming soon
    </span>
  );
}

// ─── Report card ───────────────────────────────────────────────────────────────

function ReportCard({
  report,
  onExported,
}: {
  report: ReportDefinition;
  onExported: (item: RecentExport) => void;
}) {
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isDisabled = report.status === 'coming-soon' || exporting;

  const handleExport = async () => {
    if (isDisabled) return;
    setExporting(true);
    setError(null);
    try {
      const result = await report.run();
      triggerDownload(result.filename, result.blob);
      onExported({
        id: `${report.id}-${Date.now()}`,
        name: report.title,
        format: report.format,
        generatedAt: new Date().toISOString(),
        size: formatBytes(result.blob.size),
        blob: result.blob,
      });
    } catch {
      setError('Export failed. Please try again.');
    } finally {
      setExporting(false);
    }
  };

  return (
    <div
      className={`group flex flex-col rounded-[24px] border bg-white p-6 shadow-sm transition-all duration-250 hover:-translate-y-0.5 hover:shadow-md dark:bg-slate-950 ${report.accentColor}`}
    >
      {/* Icon + format */}
      <div className="flex items-start justify-between">
        <div
          className={`flex h-11 w-11 items-center justify-center rounded-xl ${report.iconBg}`}
        >
          <report.icon size={19} className={report.iconColor} />
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
      <p className="mt-3 text-xs leading-5 text-slate-400 dark:text-slate-500">
        {report.detail}
      </p>

      {/* CTA */}
      <div className="mt-6 flex items-center gap-3">
        {report.status === 'coming-soon' ? (
          <StatusChip status="coming-soon" />
        ) : (
          <button
            type="button"
            disabled={isDisabled}
            onClick={handleExport}
            className="inline-flex h-9 items-center gap-2 rounded-xl bg-slate-950 px-4 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-white dark:text-slate-950 dark:hover:bg-slate-100"
          >
            {exporting ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
            {exporting ? 'Generating…' : 'Export'}
          </button>
        )}
        {error && (
          <span className="inline-flex items-center gap-1.5 text-xs font-medium text-red-600 dark:text-red-400">
            <AlertCircle size={13} />
            {error}
          </span>
        )}
      </div>
    </div>
  );
}

// ─── Recent export row ─────────────────────────────────────────────────────────

function RecentExportRow({ item }: { item: RecentExport }) {
  const handleDownload = () => {
    triggerDownload(`${item.name.toLowerCase().replace(/\s+/g, '-')}.${item.format.toLowerCase()}`, item.blob);
  };

  return (
    <div className="flex items-center justify-between gap-4 px-5 py-4">
      <div className="flex min-w-0 items-center gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-100 dark:bg-slate-900">
          <FileText size={15} className="text-slate-500 dark:text-slate-400" />
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
          className="inline-flex h-8 items-center gap-1.5 rounded-xl border border-slate-200 px-3 text-xs font-semibold text-slate-700 transition hover:bg-slate-100 dark:border-slate-800 dark:text-slate-300 dark:hover:bg-slate-900"
        >
          <Download size={12} />
          Download
        </button>
      </div>
    </div>
  );
}

// ─── Page ──────────────────────────────────────────────────────────────────────

export default function ReportsPage() {
  const [recentExports, setRecentExports] = useState<RecentExport[]>([]);

  const handleExported = (item: RecentExport) => {
    setRecentExports((prev) => [item, ...prev]);
  };

  return (
    <DashboardLayout>
      <div className="max-w-none px-4 py-6 sm:px-6 lg:px-8 lg:py-8 space-y-6">

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

        {/* ── Report cards ────────────────────────────────────────────────────── */}
        <section className="grid gap-4 md:grid-cols-3">
          {REPORTS.map((report) => (
            <ReportCard key={report.id} report={report} onExported={handleExported} />
          ))}
        </section>

        {/* ── Recent exports ──────────────────────────────────────────────────── */}
        <section className="overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
          <CardHeader
            title="Recent exports"
            description="Files generated in this session, kept in the browser for re-download."
            action={null}
          />

          {recentExports.length === 0 ? (
            <div className="px-5 py-14 text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 dark:bg-slate-900">
                <Download size={20} className="text-slate-400 dark:text-slate-600" />
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
          <div className="border-t border-slate-200 px-5 py-3 dark:border-slate-800">
            <p className="text-xs text-slate-400 dark:text-slate-600">
              Generated on demand from the current case data. Refresh the page to start a new session.
            </p>
          </div>
        </section>

      </div>
    </DashboardLayout>
  );
}