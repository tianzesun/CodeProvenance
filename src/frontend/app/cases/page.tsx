// @ts-nocheck
'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { Card, CardHeader, PageHeader, RiskBadge, StatusBadge } from '@/components/saas/SaaSPrimitives';
import { assignmentCases } from '@/lib/mockIntegrityData';
import { Search } from 'lucide-react';

export default function CasesQueuePage() {
  return (
    <DashboardLayout>
      <div className="max-w-none px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <PageHeader
          eyebrow="Cases"
          title="An inbox for academic integrity review."
          description="Teaching teams can assign, review, dismiss, and export cases without digging through raw tool output."
          action={
            <div className="flex w-full items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-500 lg:w-80">
              <Search size={16} />
              Search cases, students, courses
            </div>
          }
        />

        <Card>
          <CardHeader title="Queue" description="Sorted by risk and unreviewed status." />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px]">
              <thead className="bg-slate-50">
                <tr>
                  {['Status', 'Course', 'Pair', 'Risk', 'Assigned reviewer', ''].map((heading) => (
                    <th key={heading} className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {assignmentCases.map((item) => (
                  <tr key={item.id} className="transition hover:bg-slate-50">
                    <td className="px-5 py-4"><StatusBadge status={item.status} /></td>
                    <td className="px-5 py-4">
                      <div className="text-sm font-semibold text-slate-950">{item.course}</div>
                      <div className="mt-1 text-xs text-slate-500">{item.assignment}</div>
                    </td>
                    <td className="px-5 py-4">
                      <div className="text-sm font-semibold text-slate-950">{item.students}</div>
                      <div className="mt-1 text-xs text-slate-500">{item.reason}</div>
                    </td>
                    <td className="px-5 py-4"><RiskBadge value={item.risk} /></td>
                    <td className="px-5 py-4 text-sm text-slate-600">{item.reviewer}</td>
                    <td className="px-5 py-4 text-right">
                      <a href={`/cases/${item.id}`} className="text-sm font-semibold text-blue-600">Open</a>
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
