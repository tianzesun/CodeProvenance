'use client';

import { useState } from 'react';
import DashboardLayout from '@/components/DashboardLayout';
import { ButtonLink, Card, CardHeader, PageHeader } from '@/components/saas/SaaSPrimitives';
import {
  BarChart3,
  CheckCircle2,
  Clock,
  Download,
  FileText,
  Landmark,
  Loader2,
  PieChart,
} from 'lucide-react';

// ─── Types ─────────────────────────────────────────────────────────────────────

type ExportFormat = 'PDF' | 'CSV' | 'XLSX';
type ExportStatus = 'ready' | 'generating' | 'coming-soon';

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
}

interface RecentExport {
  id: string;
  name: string;
  format: ExportFormat;
  generatedAt: string;
  size: string;
  course?: string;
}

// ─── Data ──────────────────────────────────────────────────────────────────────

const REPORTS: ReportDefinition[] = [
  {
    id: 'evidence-packet',
    title: 'Evidence Packets',
    description: 'Case-specific evidence bundles for academic integrity review committees.',
    detail: 'Includes submission diff, similarity score, flagged passages, and reviewer notes.',
    icon: FileText,
    format: 'PDF',
    status: 'ready',
    accentColor: 'border-blue-100 dark:border-slate-900 hover:dark:border-blue-900/40',
    iconBg: 'bg-blue-50 dark:bg-blue-950/50',
    iconColor: 'text-blue-600 dark:text-blue-400',
  },
  {
    id: 'semester-summary',
    title: 'Semester Summary',
    description: 'Course-level review outcomes, reviewer activity, and trend summaries.',
    detail: 'Per-course breakdown of flagged, cleared, and escalated cases with timeline.',
    icon: PieChart,
    format: 'PDF',
    status: 'ready',
    accentColor: 'border-violet-100 dark:border-slate-900 hover:dark:border-violet-900/40',
    iconBg: 'bg-violet-50 dark:bg-violet-950/50',
    iconColor: 'text-violet-600 dark:text-violet-400',
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
  },
];

const RECENT_EXPORTS: RecentExport[] = [
  {
    id: '1',
    name: 'CSC108 A2 — Evidence Packet',
    format: 'PDF',
    generatedAt: '2026-05-30T14:22:00Z',
    size: '1.2 MB',
    course: 'CSC108',
  },
  {
    id: '2',
    name: 'CSC148 — Semester Summary',
    format: 'PDF',
    generatedAt: '2026-05-28T09:05:00Z',
    size: '840 KB',
    course: 'CSC148',
  },
  {
    id: '3',
    name: 'Department — February Statistics',
    format: 'CSV',
    generatedAt: '2026-05-25T16:47:00Z',
    size: '64 KB',
  },
];

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
    PDF: 'bg-red-50 text-red-600 dark:bg-red-950/30 dark:text-red-400',
    CSV: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-400',
    XLSX: 'bg-teal-50 text-teal-700 dark:bg-teal-950/30 dark:text-teal-400',
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
  if (status === 'ready') return null;

  if (status === 'coming-soon') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-500 dark:bg-slate-800 dark:text-slate-400">
        <Clock size={10} />
        Coming soon
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-600 dark:bg-amber-900/20 dark:text-amber-400">
      <Loader2 size={10} className="animate-spin" />
      Generating…
    </span>
  );
}

// ─── Report card ───────────────────────────────────────────────────────────────

function ReportCard({ report }: { report: ReportDefinition }) {
  const [exporting, setExporting] = useState(false);
  const [done, setDone] = useState(false);

  const isDisabled = report.status === 'coming-soon' || exporting;

  const handleExport = async () => {
    if (isDisabled) return;
    setExporting(true);
    // Simulate async export — replace with real API call
    await new Promise((resolve) => setTimeout(resolve, 1800));
    setExporting(false);
    setDone(true);
    setTimeout(() => setDone(false), 3000);
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
            className={`inline-flex h-9 items-center gap-2 rounded-xl px-4 text-sm font-semibold transition disabled:cursor-not-allowed ${done
              ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-400'
              : 'bg-slate-950 text-white hover:bg-slate-800 disabled:opacity-60 dark:bg-white dark:text-slate-950 dark:hover:bg-slate-100'
              }`}
          >
            {exporting ? (
              <Loader2 size={14} className="animate-spin" />
            ) : done ? (
              <CheckCircle2 size={14} />
            ) : (
              <Download size={14} />
            )}
            {exporting ? 'Generating…' : done ? 'Ready — check downloads' : 'Export'}
          </button>
        )}
      </div>
    </div>
  );
}

// ─── Recent export row ─────────────────────────────────────────────────────────

function RecentExportRow({ item }: { item: RecentExport }) {
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
            {item.course && (
              <>
                <span aria-hidden="true">·</span>
                <span className="rounded-md bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                  {item.course}
                </span>
              </>
            )}
          </div>
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-3">
        <FormatBadge format={item.format} />
        <button
          type="button"
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
  return (
    <DashboardLayout>
      <div className="max-w-none px-4 py-6 sm:px-6 lg:px-8 lg:py-8 space-y-6">

        <PageHeader
            eyebrow="Reports"
            title="Export evidence for departments and committees"
            description="Reports are formatted for academic review — not raw detector output. Every export is audit-ready and clearly attributed."
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
            <ReportCard key={report.id} report={report} />
          ))}
        </section>

        {/* ── Recent exports ──────────────────────────────────────────────────── */}
        <section className="overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
          <CardHeader
              title="Recent exports"
              description="An audit trail of all generated reports for this workspace."
              action={null}
            />

          {RECENT_EXPORTS.length === 0 ? (
            <div className="px-5 py-14 text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 dark:bg-slate-900">
                <Download size={20} className="text-slate-400 dark:text-slate-600" />
              </div>
              <h3 className="mt-4 text-sm font-semibold text-slate-900 dark:text-white">
                No exports yet
              </h3>
              <p className="mt-1.5 text-sm text-slate-500 dark:text-slate-400">
                Generate your first report above to see it here.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-slate-200 dark:divide-slate-800">
              {RECENT_EXPORTS.map((item) => (
                <RecentExportRow key={item.id} item={item} />
              ))}
            </div>
          )}

          {/* Footer */}
          <div className="border-t border-slate-200 px-5 py-3 dark:border-slate-800">
            <p className="text-xs text-slate-400 dark:text-slate-600">
              Exports are retained for 30 days. Download before they expire.
            </p>
          </div>
        </section>

      </div>
    </DashboardLayout>
  );
}