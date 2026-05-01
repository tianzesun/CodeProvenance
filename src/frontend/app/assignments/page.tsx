// @ts-nocheck
'use client';

import DashboardLayout from '@/components/DashboardLayout';
import {
  ButtonLink,
  Card,
  CardHeader,
  PageHeader,
  RiskBadge,
  StatCard,
  StatusBadge,
} from '@/components/saas/SaaSPrimitives';
import { assignmentCases } from '@/lib/mockIntegrityData';
import { CheckCircle2, FileUp, Filter, Inbox, ShieldAlert, Users } from 'lucide-react';
import { useState } from 'react';

const filters = ['High Risk', 'Medium', 'New', 'Reviewed'];

export default function AssignmentsPage() {
  const [activeFilter, setActiveFilter] = useState('High Risk');
  const rows = assignmentCases.filter((item) => {
    if (activeFilter === 'High Risk') return item.risk >= 90;
    if (activeFilter === 'Medium') return item.risk >= 60 && item.risk < 90;
    if (activeFilter === 'New') return item.status === 'New';
    if (activeFilter === 'Reviewed') return item.status === 'Reviewed';
    return true;
  });

  return (
    <DashboardLayout>
      <div className="max-w-none px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <PageHeader
          eyebrow="Assignment Results"
          title="Review programming assignment risk in one professional table."
          description="The summary tells the teaching team where to spend time before opening individual compare cases."
          action={<ButtonLink href="/upload?mode=zip" icon={FileUp}>Upload New Assignment</ButtonLink>}
        />

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Total submissions" value="412" detail="CSC108 / A2" icon={Users} tone="blue" />
          <StatCard label="High risk" value="9" detail="Needs professor review" icon={ShieldAlert} tone="red" />
          <StatCard label="Medium risk" value="23" detail="TA triage recommended" icon={Inbox} />
          <StatCard label="Cleared" value="380" detail="No action needed" icon={CheckCircle2} tone="green" />
        </section>

        <Card>
          <CardHeader
            title="Cases ranked by review priority"
            description="Filters keep the assignment table focused and quick to scan."
            action={
              <div className="flex flex-wrap gap-2">
                {filters.map((filter) => (
                  <button
                    key={filter}
                    type="button"
                    onClick={() => setActiveFilter(filter)}
                    className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold transition ${activeFilter === filter
                      ? 'bg-blue-600 text-white'
                      : 'border border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
                      }`}
                  >
                    <Filter size={14} />
                    {filter}
                  </button>
                ))}
              </div>
            }
          />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[920px]">
              <thead className="bg-slate-50">
                <tr>
                  {['Rank', 'Students', 'Risk Score', 'Confidence', 'Reason', 'Actions'].map((heading) => (
                    <th key={heading} className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {rows.map((item) => (
                  <tr key={item.id} className="transition hover:bg-slate-50">
                    <td className="px-5 py-4 text-sm font-semibold text-slate-600">#{item.rank}</td>
                    <td className="px-5 py-4">
                      <div className="text-sm font-semibold text-slate-950">{item.students}</div>
                      <div className="mt-1 text-xs text-slate-500">{item.course} / {item.assignment}</div>
                    </td>
                    <td className="px-5 py-4"><RiskBadge value={item.risk} /></td>
                    <td className="px-5 py-4 text-sm font-medium text-slate-700">{item.confidence}</td>
                    <td className="px-5 py-4 text-sm text-slate-600">{item.reason}</td>
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-2">
                        <StatusBadge status={item.status} />
                        <a href={`/cases/${item.id}`} className="text-sm font-semibold text-blue-600">Compare</a>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </DashboardLayout>
  );
}
