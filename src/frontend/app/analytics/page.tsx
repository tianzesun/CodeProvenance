// @ts-nocheck
'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { Card, CardHeader, PageHeader, RiskBadge, StatCard } from '@/components/saas/SaaSPrimitives';
import { CompactBarChart, CourseCasesChart, SemesterRiskChart, SuspiciousTrendChart } from '@/components/saas/Charts';
import {
  analyticsByCourse,
  generatedSuspicionData,
  repeatOffenderData,
  semesterRiskData,
  trendData,
} from '@/lib/mockIntegrityData';
import { BarChart3, Repeat, ShieldAlert, TrendingUp } from 'lucide-react';

export default function AnalyticsPage() {
  return (
    <DashboardLayout>
      <div className="max-w-none px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <PageHeader
          eyebrow="Analytics"
          title="Department-level insight without noisy detector metrics."
          description="Track where academic integrity work is rising, which courses need support, and how review load changes over time."
        />

        <section className="grid gap-4 md:grid-cols-3">
          <StatCard label="Cases by course" value="81" detail="Across active courses" icon={BarChart3} tone="blue" />
          <StatCard label="Repeat patterns" value="11%" detail="Require department attention" icon={Repeat} tone="red" />
          <StatCard label="High-risk trend" value="+18%" detail="Winter 2026 vs prior term" icon={TrendingUp} />
        </section>

        <section className="grid gap-6 xl:grid-cols-2">
          <Card>
            <CardHeader title="Cases by course" description="Where review effort is concentrated." />
            <div className="p-5"><CourseCasesChart data={analyticsByCourse} /></div>
          </Card>

          <Card>
            <CardHeader title="Risk trends over semesters" description="High and medium risk case movement." />
            <div className="p-5"><SemesterRiskChart data={semesterRiskData} /></div>
          </Card>

          <Card>
            <CardHeader title="Repeat offender statistics" description="Prior-warning and repeat-pattern distribution." />
            <div className="p-5"><CompactBarChart data={repeatOffenderData} /></div>
          </Card>

          <Card>
            <CardHeader
              title="AI-generated suspicion trend"
              description="Displayed as teaching-team workload, not raw model internals."
            />
            <div className="p-5"><SuspiciousTrendChart data={generatedSuspicionData.map((item) => ({ week: item.month, cases: item.cases, high: Math.round(item.cases * 0.38) }))} /></div>
          </Card>
        </section>
      </div>
    </DashboardLayout>
  );
}
