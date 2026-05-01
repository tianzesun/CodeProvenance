// @ts-nocheck
'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { ButtonLink, Card, PageHeader, RiskBadge } from '@/components/saas/SaaSPrimitives';
import { courseData } from '@/lib/mockIntegrityData';
import { ArrowRight, BookOpen, FileUp, Users } from 'lucide-react';

export default function CoursesPage() {
  return (
    <DashboardLayout>
      <div className="max-w-none px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <PageHeader
          eyebrow="Courses"
          title="Course workspaces built for teaching teams."
          description="Each course keeps assignments, flagged cases, prior-term memory, and reports in one clean place."
          action={<ButtonLink href="/upload?mode=zip" icon={FileUp}>Upload New Assignment</ButtonLink>}
        />

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {courseData.map((course) => (
            <Card key={course.code} className="p-5 transition hover:-translate-y-0.5 hover:shadow-md">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-sm font-medium text-slate-500">{course.code}</div>
                  <h2 className="mt-2 text-xl font-semibold text-slate-950">{course.name}</h2>
                </div>
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-blue-50 text-blue-700">
                  <BookOpen size={19} />
                </div>
              </div>

              <div className="mt-6 grid grid-cols-3 gap-3">
                <MiniMetric icon={Users} label="Students" value={course.students} />
                <MiniMetric label="Assignments" value={course.assignments} />
                <MiniMetric label="Flagged" value={course.flagged} danger />
              </div>

              <div className="mt-6 flex items-center justify-between border-t border-slate-200 pt-4">
                <RiskBadge value={Math.min(99, course.flagged * 8)} label={`${course.flagged} flagged`} />
                <a href="/assignments" className="inline-flex items-center gap-2 text-sm font-semibold text-blue-600">
                  Open course
                  <ArrowRight size={15} />
                </a>
              </div>
            </Card>
          ))}
        </section>
      </div>
    </DashboardLayout>
  );
}

function MiniMetric({ label, value, icon: Icon, danger = false }) {
  return (
    <div className="rounded-xl bg-slate-50 px-3 py-3">
      <div className="flex items-center gap-1.5 text-xs font-medium text-slate-500">
        {Icon && <Icon size={12} />}
        {label}
      </div>
      <div className={`mt-2 text-lg font-semibold ${danger ? 'text-red-700' : 'text-slate-950'}`}>{value}</div>
    </div>
  );
}
