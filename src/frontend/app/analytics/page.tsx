'use client';

import { useMemo } from 'react';
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
import {
  analyticsByCourse,
  generatedSuspicionData,
  repeatOffenderData,
  semesterRiskData,
} from '@/lib/mockIntegrityData';
import {
  AlertTriangle,
  BarChart3,
  Bot,
  ChevronRight,
  Repeat,
  ShieldAlert,
  TrendingUp,
} from 'lucide-react';

// ─── Types ─────────────────────────────────────────────────────────────────────

interface SuspicionDataPoint {
  week: string;
  cases: number;
  high: number;
}

// ─── Insight banner ────────────────────────────────────────────────────────────

interface InsightProps {
  icon: React.ElementType;
  label: string;
  children: React.ReactNode;
}

function InsightBanner({ items }: { items: InsightProps[] }) {
  return (
    <div className="flex flex-col gap-3 rounded-[24px] border border-blue-100 bg-blue-50 p-4 dark:border-blue-900/40 dark:bg-blue-950/30 sm:flex-row sm:items-stretch">
      {items.map(({ icon: Icon, label, children }, i) => (
        <div
          key={i}
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
              {children}
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

// ─── Main page ─────────────────────────────────────────────────────────────────

export default function AnalyticsPage() {
  // Derive chart-ready data outside JSX — no inline transforms in render
  const suspicionTrendData = useMemo<SuspicionDataPoint[]>(
    () =>
      generatedSuspicionData.map((item) => ({
        week: item.month,
        cases: item.cases,
        high: Math.round(item.cases * 0.38),
      })),
    []
  );

  return (
    <DashboardLayout>
      <div className="max-w-none px-4 py-6 sm:px-6 lg:px-8 lg:py-8 space-y-6">

        {/* ── Page header ─────────────────────────────────────────────────────── */}
        <PageHeader
          eyebrow="Analytics"
          title="Department integrity overview"
          description="Track where academic integrity cases are rising, which courses need attention, and how review load shifts each term."
          action={null}
          eyebrowStyle="badge"
        />

        {/* ── KPI stat cards ──────────────────────────────────────────────────── */}
        <section className="grid gap-4 sm:grid-cols-3">
          <StatCard
            label="Cases by course"
            value="81"
            detail="Across all active courses"
            icon={BarChart3}
            tone="blue"
          />
          <StatCard
            label="Repeat patterns"
            value="11%"
            detail="Flagged for department review"
            icon={Repeat}
            tone="red"
          />
          <StatCard
            label="High-risk trend"
            value="+18%"
            detail="Winter 2026 vs prior term"
            icon={TrendingUp}
            tone="amber"
          />
        </section>

        {/* ── Key insights banner ─────────────────────────────────────────────── */}
        <InsightBanner
          items={[
            {
              icon: AlertTriangle,
              label: 'Hotspot',
              children: (
                <>
                  <strong>CS 301</strong> accounts for 34% of all flagged cases — consider targeted
                  policy communication.
                </>
              ),
            },
            {
              icon: TrendingUp,
              label: 'Trend',
              children: (
                <>
                  High-risk submissions have increased <strong>3 terms in a row</strong>. Winter 2026
                  shows the steepest rise.
                </>
              ),
            },
            {
              icon: Repeat,
              label: 'Repeat patterns',
              children: (
                <>
                  <strong>9 students</strong> across 4 courses have prior-warning history active this
                  semester.
                </>
              ),
            },
          ]}
        />

        {/* ── Volume section ──────────────────────────────────────────────────── */}
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
                <CourseCasesChart data={analyticsByCourse} />
              </div>
            </Card>

            <Card>
              <CardHeader
                title="Risk trends over semesters"
                description="High and medium risk case movement across recent terms."
                action={null}
              />
              <div className="p-5">
                <SemesterRiskChart data={semesterRiskData} />
              </div>
            </Card>
          </div>
        </div>

        {/* ── Behaviour section ───────────────────────────────────────────────── */}
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
                <CompactBarChart data={repeatOffenderData} />
              </div>
            </Card>

            <Card>
              <CardHeader
                title="AI-generated suspicion trend"
                description="Teaching-team review load from AI-assisted submissions, by week."
                action={null}
              />
              <div className="p-5">
                <SuspiciousTrendChart data={suspicionTrendData} />
              </div>
            </Card>
          </div>
        </div>

        {/* ── Footer note ─────────────────────────────────────────────────────── */}
        <p className="flex items-center gap-1.5 text-xs text-slate-400 dark:text-slate-600">
          <Bot size={12} />
          Metrics reflect case-level data only. Detection engine internals are not exposed in this
          view.
        </p>

      </div>
    </DashboardLayout>
  );
}