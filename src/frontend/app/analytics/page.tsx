'use client';

import { useEffect, useState } from 'react';
import type { ElementType, ReactNode } from 'react';
import DashboardLayout from '@/components/DashboardLayout';
import {
  Card,
  CardHeader,
  ErrorState,
  LoadingState,
  PageHeader,
  StatCard,
} from '@/components/saas/SaaSPrimitives';
import {
  CompactBarChart,
  CourseCasesChart,
  SemesterRiskChart,
  SuspiciousTrendChart,
} from '@/components/saas/Charts';
import { apiClient } from '@/lib/apiClient';
import {
  AlertTriangle,
  BarChart3,
  Bot,
  RefreshCw,
  Repeat,
  ShieldAlert,
  TrendingUp,
} from 'lucide-react';

// ─── Types ─────────────────────────────────────────────────────────────────────

type Insight = { kind: string; text: string };
type CourseCases = { course: string; cases: number };
type SemesterRisk = { semester: string; high: number; medium: number };
type RepeatStat = { label: string; value: number };
type TrendPoint = { week: string; cases: number; high: number };

interface AnalyticsOverview {
  generated_at?: string;
  summary?: {
    total_cases: number;
    open_cases: number;
    courses_affected: number;
    high_priority: number;
    repeats: number;
    trend_change: number | null;
  };
  cases_by_course?: CourseCases[];
  semester_risk?: SemesterRisk[];
  repeat_offenders?: RepeatStat[];
  suspicion_trend?: TrendPoint[];
  insights?: Insight[];
}

const INSIGHT_ICONS: Record<string, ElementType> = {
  hotspot: AlertTriangle,
  trend: TrendingUp,
  repeat: Repeat,
};

const INSIGHT_LABELS: Record<string, string> = {
  hotspot: 'Hotspot',
  trend: 'Trend',
  repeat: 'Repeat patterns',
};

// ─── Helpers ───────────────────────────────────────────────────────────────────

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
    message = 'You don’t have permission to view analytics.';
  } else {
    message = 'Failed to load analytics data.';
  }

  return reference ? `${message} (Reference: ${reference})` : message;
}

function pluralize(count: number, singular: string, plural = `${singular}s`): string {
  return `${count.toLocaleString('en-US')} ${count === 1 ? singular : plural}`;
}

function formatUpdated(value?: string): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat('en-US', { dateStyle: 'medium', timeStyle: 'short' }).format(date);
}

// ─── Insight banner ────────────────────────────────────────────────────────────

function InsightBanner({ insights }: { insights: Insight[] }) {
  const items = insights
    .map(({ kind, text }) => ({
      kind,
      icon: INSIGHT_ICONS[kind] || AlertTriangle,
      label: INSIGHT_LABELS[kind] || 'Insight',
      text,
    }))
    .filter((item) => Boolean(item.text));

  if (!items.length) {
    return null;
  }

  return (
    <section
      aria-label="Key insights"
      className="flex flex-col gap-3 rounded-[24px] border border-blue-100 bg-blue-50 p-4 dark:border-blue-900/40 dark:bg-blue-950/30 sm:flex-row sm:items-stretch"
    >
      {items.map(({ kind, icon: Icon, label, text }, i) => (
        <div
          // Two insights of the same kind share a label, so the label alone isn't a unique key.
          key={`${kind}-${i}`}
          className={`flex flex-1 items-start gap-3 ${i < items.length - 1
            ? 'border-b border-blue-100 pb-3 dark:border-blue-900/40 sm:border-b-0 sm:border-r sm:pb-0 sm:pr-4'
            : ''
            }`}
        >
          <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-xl bg-blue-100 dark:bg-blue-900/40">
            <Icon size={13} className="text-blue-600 dark:text-blue-400" aria-hidden="true" />
          </div>
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-blue-600 dark:text-blue-400">
              {label}
            </div>
            <div className="mt-0.5 text-sm leading-5 text-blue-900 dark:text-blue-200">
              {text}
            </div>
          </div>
        </div>
      ))}
    </section>
  );
}

// ─── Section label ─────────────────────────────────────────────────────────────

function SectionLabel({
  icon: Icon,
  label,
  description,
}: {
  icon: ElementType;
  label: string;
  description?: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-slate-100 dark:bg-slate-900">
        <Icon size={15} className="text-slate-600 dark:text-slate-400" aria-hidden="true" />
      </div>
      <div>
        <h2 className="text-sm font-semibold text-slate-900 dark:text-white">{label}</h2>
        {description && (
          <div className="text-xs text-slate-500 dark:text-slate-400">{description}</div>
        )}
      </div>
    </div>
  );
}

// ─── Empty chart state ─────────────────────────────────────────────────────────

function ChartEmpty({ message }: { message: string }) {
  return (
    <div className="flex h-72 items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50 px-6 text-center dark:border-slate-800 dark:bg-slate-900/40">
      <div className="text-sm leading-6 text-slate-500 dark:text-slate-400">{message}</div>
    </div>
  );
}

/**
 * Renders a chart, or an empty state. It is generic so each chart receives its own typed
 * rows (it used to widen everything to `unknown[]`). The chart is drawn as SVG, so the same
 * numbers are also exposed to screen readers as a visually hidden table.
 */
function ChartWithData<T extends object>({
  data,
  render,
  empty,
  tableCaption,
  columns,
}: {
  data: T[] | undefined;
  render: (data: T[]) => ReactNode;
  empty: string;
  tableCaption: string;
  columns: { key: keyof T & string; label: string }[];
}) {
  if (!data || data.length === 0) {
    return <ChartEmpty message={empty} />;
  }

  return (
    <>
      {render(data)}
      <table className="sr-only">
        <caption>{tableCaption}</caption>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} scope="col">
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, index) => (
            <tr key={index}>
              {columns.map((column) => (
                <td key={column.key}>{String(row[column.key] ?? '')}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

// ─── Main page ─────────────────────────────────────────────────────────────────

export default function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    if (reloadKey > 0) setRefreshing(true);
    setError('');

    apiClient
      .get('/api/analytics/overview', { signal: controller.signal })
      .then((res) => {
        setData(res.data && typeof res.data === 'object' ? (res.data as AnalyticsOverview) : null);
      })
      .catch((err) => {
        // Keeps whatever was already on screen; a failed refresh must not blank the page.
        if (!controller.signal.aborted) setError(describeLoadError(err));
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
          setRefreshing(false);
        }
      });

    return () => controller.abort();
  }, [reloadKey]);

  const summary = data?.summary;
  const casesByCourse = data?.cases_by_course;
  const semesterRisk = data?.semester_risk;
  const repeatOffenders = data?.repeat_offenders;
  const suspicionTrend = data?.suspicion_trend;
  const insights = data?.insights || [];

  const totalCases = summary?.total_cases ?? 0;
  const openCases = summary?.open_cases;
  const highPriority = summary?.high_priority;
  const coursesAffected = summary?.courses_affected ?? 0;
  const repeats = summary?.repeats ?? 0;
  const trendChange = summary?.trend_change ?? null;
  // Clamped so inconsistent data can't produce something like 140%.
  const repeatPct = totalCases > 0 ? Math.min(100, Math.round((repeats / totalCases) * 100)) : 0;
  const hasTrend = trendChange !== null && Number.isFinite(trendChange);
  const highRiskTrend = hasTrend
    ? `${trendChange > 0 ? '+' : ''}${Number(trendChange.toFixed(1))}%`
    : 'n/a';

  const updatedAt = formatUpdated(data?.generated_at);

  // An empty object or all-zero response means "nothing yet", not a page of zeros.
  const hasAnyData =
    totalCases > 0 ||
    Boolean(casesByCourse?.length || semesterRisk?.length || repeatOffenders?.length || suspicionTrend?.length);

  return (
    <DashboardLayout>
      <div className="theme-page-container space-y-6">

        {/* ── Page header ─────────────────────────────────────────────────── */}
        <PageHeader
          eyebrow="Analytics"
          title="Department integrity overview"
          description="Track where academic integrity cases are rising, which courses need attention, and how review load shifts each term."
          action={
            data ? (
              <button
                type="button"
                onClick={() => setReloadKey((key) => key + 1)}
                disabled={refreshing || loading}
                className="inline-flex h-9 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3.5 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300 dark:hover:bg-slate-900"
              >
                <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} aria-hidden="true" />
                {refreshing ? 'Refreshing…' : 'Refresh'}
              </button>
            ) : null
          }
          eyebrowStyle="badge"
        />

        {loading && <LoadingState label="Loading analytics…" />}

        {error && (
          <div role="alert" className="space-y-3">
            <ErrorState message={error} />
            {!data && !loading && (
              <button
                type="button"
                onClick={() => setReloadKey((key) => key + 1)}
                className="inline-flex h-9 items-center rounded-xl border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300 dark:hover:bg-slate-900"
              >
                Try again
              </button>
            )}
          </div>
        )}

        {!loading && !error && !hasAnyData && (
          <ChartEmpty message="No analytics data available yet. Run an analysis on an assignment to start populating this overview." />
        )}

        {!loading && data && hasAnyData && (
          <>
            {/* ── KPI stat cards ──────────────────────────────────────────── */}
            <section aria-label="Key figures" className="grid gap-4 sm:grid-cols-3">
              <StatCard
                // This card showed the total case count under the label "Cases by course".
                label="Total cases"
                value={totalCases.toLocaleString('en-US')}
                detail={`${openCases !== undefined ? `${openCases.toLocaleString('en-US')} open · ` : ''}across ${pluralize(coursesAffected, 'active course')}`}
                icon={BarChart3}
                tone="blue"
              />
              <StatCard
                label="Repeat patterns"
                value={`${repeatPct}%`}
                detail={`${pluralize(repeats, 'case')} flagged for department review`}
                icon={Repeat}
                tone="red"
              />
              <StatCard
                label="High-risk trend"
                value={highRiskTrend}
                detail={
                  hasTrend
                    ? `${highPriority !== undefined ? `${pluralize(highPriority, 'high-priority case')} · ` : ''}vs prior term`
                    : 'No prior term to compare yet'
                }
                icon={TrendingUp}
                tone="amber"
              />
            </section>

            {/* ── Key insights banner ─────────────────────────────────────── */}
            <InsightBanner insights={insights} />

            {/* ── Volume section ──────────────────────────────────────────── */}
            <div className="space-y-4">
              <SectionLabel
                icon={BarChart3}
                label="Case volume"
                description="Where review effort is concentrated across courses and time"
              />

              <div className="grid gap-6 xl:grid-cols-2">
                <Card>
                  <CardHeader
                    title="Cases by course"
                    description="Distribution of flagged submissions per active course."
                    action={null}
                  />
                  <ChartWithData
                    data={casesByCourse}
                    empty="No cases recorded yet by course."
                    tableCaption="Cases by course"
                    columns={[
                      { key: 'course', label: 'Course' },
                      { key: 'cases', label: 'Cases' },
                    ]}
                    render={(chartData) => <CourseCasesChart data={chartData} />}
                  />
                </Card>

                <Card>
                  <CardHeader
                    title="Risk trends over semesters"
                    description="High and medium risk case movement across recent terms."
                    action={null}
                  />
                  <ChartWithData
                    data={semesterRisk}
                    empty="No term-by-term risk data yet."
                    tableCaption="High and medium risk cases by semester"
                    columns={[
                      { key: 'semester', label: 'Semester' },
                      { key: 'high', label: 'High risk' },
                      { key: 'medium', label: 'Medium risk' },
                    ]}
                    render={(chartData) => <SemesterRiskChart data={chartData} />}
                  />
                </Card>
              </div>
            </div>

            {/* ── Behaviour section ───────────────────────────────────────── */}
            <div className="space-y-4">
              <SectionLabel
                icon={ShieldAlert}
                label="Repeat behaviour & AI suspicion"
                description="Pattern depth and AI-assisted submission signals over time"
              />

              <div className="grid gap-6 xl:grid-cols-2">
                <Card>
                  <CardHeader
                    // "Offender" presumes a finding; the rest of the product says "repeat patterns".
                    title="Repeat-pattern statistics"
                    description="Prior-warning and confirmed repeat-pattern distribution."
                    action={null}
                  />
                  <ChartWithData
                    data={repeatOffenders}
                    empty="No case-repeat history yet."
                    tableCaption="Repeat-pattern distribution"
                    columns={[
                      { key: 'label', label: 'Category' },
                      { key: 'value', label: 'Cases' },
                    ]}
                    render={(chartData) => <CompactBarChart data={chartData} />}
                  />
                </Card>

                <Card>
                  <CardHeader
                    title="AI-generated suspicion trend"
                    // Said "by month", but the data points are keyed by week.
                    description="Teaching-team review load from AI-assisted submissions, over time."
                    action={null}
                  />
                  <ChartWithData
                    data={suspicionTrend}
                    empty="No suspicion-trend data yet."
                    tableCaption="AI-assisted submission cases over time"
                    columns={[
                      { key: 'week', label: 'Period' },
                      { key: 'cases', label: 'Cases' },
                      { key: 'high', label: 'High priority' },
                    ]}
                    render={(chartData) => <SuspiciousTrendChart data={chartData} />}
                  />
                </Card>
              </div>
            </div>

            {/* ── Footer note ─────────────────────────────────────────────── */}
            <div className="space-y-1 text-xs text-slate-500 dark:text-slate-500">
              <p className="flex items-center gap-1.5">
                <Bot size={12} aria-hidden="true" />
                Metrics reflect case-level data only. Detection engine internals are not exposed in this
                view.
              </p>
              {updatedAt && <p>Last updated {updatedAt}.</p>}
            </div>
          </>
        )}

      </div>
    </DashboardLayout>
  );
}
