// @ts-nocheck
'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { Card, CardHeader, PageHeader, RiskBadge, StatusBadge } from '@/components/saas/SaaSPrimitives';
import { apiClient } from '@/lib/apiClient';
import { Search } from 'lucide-react';
import { useEffect, useState } from 'react';

type CaseItem = {
  id: string;
  title: string;
  status: string;
  priority: string;
  course?: string;
  assignment?: string;
  students?: string;
  risk?: number;
  reviewer?: string;
};

export default function CasesQueuePage() {
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchCases = async () => {
      try {
        const response = await apiClient.get('/api/cases');
        const casesData = response.data || [];
        
        // Transform API response to match UI expectations
        const transformedCases = casesData.map((c: any) => ({
          id: c.id,
          title: c.title,
          status: c.status || 'OPEN',
          priority: c.priority || 'MEDIUM',
          course: c.assignment?.course_name || c.course || 'Unknown Course',
          assignment: c.assignment?.title || c.title,
          students: c.students_display || 'Multiple students',
          risk: c.risk_score || 75,
          reviewer: c.investigator?.name || 'Unassigned',
        }));
        setCases(transformedCases);
      } catch (err: any) {
        console.error('Failed to fetch cases:', err);
        setError(err?.message || 'Failed to load cases. Please try again.');
      } finally {
        setLoading(false);
      }
    };

    fetchCases();
  }, []);

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

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 mb-4">
            {error}
          </div>
        )}

        <Card>
          <CardHeader title="Queue" description="Sorted by risk and unreviewed status." />
          <div className="overflow-x-auto">
            {loading ? (
              <div className="px-5 py-8 text-sm text-slate-500">Loading cases...</div>
            ) : (
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
                  {cases.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-5 py-8 text-sm text-slate-500">
                        No cases found. Run an AI detection or similarity analysis to create cases.
                      </td>
                    </tr>
                  ) : (
                    cases.map((item) => (
                      <tr key={item.id} className="transition hover:bg-slate-50">
                        <td className="px-5 py-4"><StatusBadge status={item.status} /></td>
                        <td className="px-5 py-4">
                          <div className="text-sm font-semibold text-slate-950">{item.course}</div>
                          <div className="mt-1 text-xs text-slate-500">{item.assignment}</div>
                        </td>
                        <td className="px-5 py-4">
                          <div className="text-sm font-semibold text-slate-950">{item.students}</div>
                          <div className="mt-1 text-xs text-slate-500">{item.title}</div>
                        </td>
                        <td className="px-5 py-4"><RiskBadge value={item.risk || 50} /></td>
                        <td className="px-5 py-4 text-sm text-slate-600">{item.reviewer}</td>
                        <td className="px-5 py-4 text-right">
                          <a href={`/cases/${item.id}`} className="text-sm font-semibold text-blue-600">Open</a>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            )}
          </div>
        </Card>
      </div>
    </DashboardLayout>
  );
}
