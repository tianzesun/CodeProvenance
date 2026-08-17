'use client';

import { useEffect, useState } from 'react';
import DashboardLayout from '@/components/DashboardLayout';
import {
  Card,
  CardHeader,
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
  Loader2,
  Repeat,
  ShieldAlert,
  TrendingUp,
} from 'lucide-react';

// ─── Types ─────────────────────────────────────────────────────────────────────

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
  cases_by_course?: { course: string; cases: number }[];
  semester_risk?: { semester: string; high: number; medium: number }[];
  repeat_offenders?: { label: string; value: number }[];
  suspicion_trend?: { week: string; cases: number; high: number }[];
  insights?: { kind: string; text: string }[];
}

const INSIGHT_ICONS: Record<string, React.ElementType> = {
  hotspot: AlertTriangle,
  trend: TrendingUp,
  repeat: Repeat,
};

const INSIGHT_LABELS: Record<string, string> = {
  hotspot: 'Hotspot',
  trend: 'Trend',
  repeat: 'Repeat patterns',
};

// ─── Insight banner ────────────────────────────────────────────────────────────

function InsightBanner({
  insights,
}: {
  insights: { kind: string; text: string }[];
}) {
  const items = insights
    .map(({ kind, text }) => ({
      icon: INSIGHT_ICONS[kind] || AlertTriangle,
      label: INSIGHT_LABELS[kind] || 'Insight',
      text,
    }))
    .filter((item) => Boolean(item.text));

  if (!items.length) {
    return null;
  }

  return (
    <div className="flex flex-col gap-3 rounded-[24px] border border-blue-100 bg-blue-50 p-4 dark:border-blue-900/40 dark:bg-blue-950/30 sm:flex-row sm:items-stretch">
      {items.map(({ icon: Icon, label, text }, i) => (
        <div
          key={label}
          className={`flex flex-1 items-start gap-3 ${i < items.length - 1
            ? 'border-b border-blue-100 pb-3 dark:border-blue-900/40 sm:border-b-0 sm:border-r sm:pb-0 sm:pr-4'
            : ''
            }`}
        >
          <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-xl bg-blue-100 dark:bg-blue-900/40">
            <Icon size={13} className="text-blue-600 dark:text-blue-400" />
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
    </div>
  );
}

// ─── Section label ─────────────────────────────────────────────────────────────

function SectionLabel({
  icon: Icon,
  label,
  description,
}: {
  icon: React.ElementType;
  label: string;
  description?: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-slate-100 dark:bg-slate-900">
        <Icon size={15} className="text-slate-600 dark:text-slate-400" />
      </div>
      <div>
        <div className="text-sm font-semibold text-slate-900 dark:text-white">{label}</div>
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
    <div className="flex h-72 items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50 px-6 text-center">
      <div className="text-sm leading-6 text-slate-500">{message}</div>
    </div>
  );
}

function ChartWithData({
  data,
  render,
  empty,
}: {
  data: unknown[] | undefined;
  render: (data: unknown[]) => React.ReactNode;
  empty: string;
}) {
  if (!data || data.length === 0) {
    return <ChartEmpty message={empty} />;
  }
  return <>{render(data)}</>;
}

// ─── Main page ─────────────────────────────────────────────────────────────────

export default function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    apiClient
      .get('/api/analytics/overview')
      .then((res) => {
        if (active) setData(res.data);
      })
      .catch(() => {
        if (active) setError('Failed to load analytics data.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  // Chart-ready data comes straight from the backend; transformed in render below.
  const summary = data?.summary;
  const casesByCourse = data?.cases_by_course || [];
  const semesterRisk = data?.semester_risk || [];
  const repeatOffenders = data?.repeat_offenders || [];
  const insights = data?.insights || [];

  const totalCases = summary?.total_cases ?? 0;
  const coursesAffected = summary?.courses_affected ?? 0;
  const repeats = summary?.repeats ?? 0;
  const trendChange = summary?.trend_change ?? null;
  const repeatPct = totalCases > 0 ? Math.round((repeats / totalCases) * 100) : 0;
  const highRiskTrend =
    trendChange === null || Number.isNaN(trendChange)
      ? 'n/a'
      : `${trendChange > 0 ? '+' : ''}${trendChange}%`;

  return (
    <DashboardLayout>
      <div className="max-w-none px-4 py-6 sm:px-6 lg:px-8 lg:py-8 space-y-6">

        {/* ── Page header ─────────────────────────────────────────────────── */}
        <PageHeader
          eyebrow="Analytics"
          title="Department integrity overview"
          description="Track where academic integrity cases are rising, which courses need attention, and how review load shifts each term."
          action={null}
          eyebrowStyle="badge"
        />

        {loading && (
          <div className="flex items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-white px-5 py-16 text-sm text-slate-500">
            <Loader2 size={16} className="animate-spin" />
            Loading analytics…
          </div>
        )}

        {error && (
          <section className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
            <AlertTriangle size={16} className="mt-0.5 shrink-0" />
            <span>{error}</span>
          </section>
        )}

        {!loading && !error && !data && (
          <ChartEmpty message="No analytics data available yet. Run an analysis on an assignment to start populating this overview." />
        )}

        {!loading && !error && data && (
          <>
            {/* ── KPI stat cards ──────────────────────────────────────────── */}
            <section className="grid gap-4 sm:grid-cols-3">
              <StatCard
                label="Cases by course"
                value={String(totalCases)}
                detail={`Across ${coursesAffected} active course${coursesAffected === 1 ? '' : 's'}`}
                icon={BarChart3}
                tone="blue"
              />
              <StatCard
                label="Repeat patterns"
                value={`${repeatPct}%`}
                detail={`${repeats} case(s) flagged for department review`}
                icon={Repeat}
                tone="red"
              />
              <StatCard
                label="High-risk trend"
                value={highRiskTrend}
                detail="High-priority cases vs prior term"
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
                  <div className="p-5">
                    <ChartWithData
                      data={casesByCourse}
                      empty="No cases recorded yet by course."
                      render={(chartData) => <CourseCasesChart data={chartData} />}
                    />
                  </div>
                </Card>

                <Card>
                  <CardHeader
                    title="Risk trends over semesters"
                    description="High and medium risk case movement across recent terms."
                    action={null}
                  />
                  <div className="p-5">
                    <ChartWithData
                      data={semesterRisk}
                      empty="No term-by-term risk data yet."
                      render={(chartData) => <SemesterRiskChart data={chartData} />}
                    />
                  </div>
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
                    title="Repeat offender statistics"
                    description="Prior-warning and confirmed repeat-pattern distribution."
                    action={null}
                  />
                  <div className="p-5">
                    <ChartWithData
                      data={repeatOffenders}
                      empty="No case-repeat history yet."
                      render={(chartData) => <CompactBarChart data={chartData} />}
                    />
                  </div>
                </Card>

                <Card>
                  <CardHeader
                    title="AI-generated suspicion trend"
                    description="Teaching-team review load from AI-assisted submissions, by month."
                    action={null}
                  />
                  <div className="p-5">
                    <ChartWithData
                      data={data?.suspicion_trend}
                      empty="No suspicion-trend data yet."
                      render={(chartData) => <SuspiciousTrendChart data={chartData} />}
                    />
                  </div>
                </Card>
              </div>
            </div>

            {/* ── Footer note ─────────────────────────────────────────────── */}
            <p className="flex items-center gap-1.5 text-xs text-slate-400 dark:text-slate-600">
              <Bot size={12} />
              Metrics reflect case-level data only. Detection engine internals are not exposed in this
              view.
            </p>
          </>
        )}

      </div>
    </DashboardLayout>
  );
}