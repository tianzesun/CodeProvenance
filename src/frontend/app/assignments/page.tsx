'use client';

import DashboardLayout from '@/components/DashboardLayout';
import {
  ButtonLink,
  Card,
  CardHeader,
  PageHeader,
  RiskBadge,
  StatCard,
} from '@/components/saas/SaaSPrimitives';
import { apiClient } from '@/lib/apiClient';
import { CheckCircle2, FileUp, Filter, Inbox, ShieldAlert, Users } from 'lucide-react';
import { useEffect, useState } from 'react';

type AssignmentCase = {
  id: string;
  title: string;
  status: string;
  priority: string;
  course: string;
  assignment: string;
  investigator: string;
};

type RawCase = {
  id: string;
  title: string;
  status?: string;
  priority?: string;
  assignment?: { title?: string; course_name?: string };
  investigator?: { name?: string };
};

type RawResult = {
  risk_level?: string;
};

type RawJob = {
  file_count?: number;
  results?: RawResult[];
};

const PRIORITY_RISK: Record<string, number> = {
  URGENT: 97,
  HIGH: 92,
  MEDIUM: 72,
  LOW: 40,
};

const filters = ['High Risk', 'Medium', 'New', 'Reviewed'];

function riskTierOf(priority: string): string {
  if (priority === 'HIGH' || priority === 'URGENT') return 'High Risk';
  if (priority === 'MEDIUM') return 'Medium';
  return 'Reviewed';
}

export default function AssignmentsPage() {
  const [activeFilter, setActiveFilter] = useState('High Risk');
  const [cases, setCases] = useState<AssignmentCase[]>([]);
  const [totalSubmissions, setTotalSubmissions] = useState(0);
  const [highRisk, setHighRisk] = useState(0);
  const [mediumRisk, setMediumRisk] = useState(0);
  const [cleared, setCleared] = useState(0);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const [casesRes, jobsRes] = await Promise.all([
          apiClient.get('/api/cases', { params: { limit: 1000 } }),
          apiClient.get('/api/jobs'),
        ]);

        const casesData = (casesRes.data || []) as RawCase[];
        setCases(
          casesData.map((c) => ({
            id: c.id,
            title: c.title,
            status: c.status || 'OPEN',
            priority: c.priority || 'MEDIUM',
            course: c.assignment?.course_name || 'Unknown Course',
            assignment: c.assignment?.title || c.title,
            investigator: c.investigator?.name || 'Unassigned',
          }))
        );

        const jobs = ((jobsRes.data || {}).jobs || []) as RawJob[];
        setTotalSubmissions(
          jobs.reduce((sum: number, j) => sum + (Number(j.file_count) || 0), 0)
        );

        let high = 0;
        let medium = 0;
        let low = 0;
        for (const job of jobs) {
          for (const result of (job.results || []) as RawResult[]) {
            const level = String(result.risk_level || '').toUpperCase();
            if (level === 'CRITICAL' || level === 'HIGH') high += 1;
            else if (level === 'MEDIUM') medium += 1;
            else low += 1;
          }
        }
        setHighRisk(high);
        setMediumRisk(medium);
        setCleared(low);
      } catch (err) {
        console.error('Failed to load assignment risk data:', err);
        setError(
          err instanceof Error ? err.message : 'Failed to load data. Please try again.'
        );
      } finally {
        setLoaded(true);
      }
    };
    load();
  }, []);

  const rows = cases.filter((item) => {
    if (activeFilter === 'High Risk') return item.priority === 'HIGH' || item.priority === 'URGENT';
    if (activeFilter === 'Medium') return item.priority === 'MEDIUM';
    if (activeFilter === 'New') return item.status === 'OPEN';
    if (activeFilter === 'Reviewed') return item.status === 'CLOSED';
    return true;
  });

  return (
    <DashboardLayout>
      <div className="max-w-none px-4 py-6 sm:px-6 lg:px-8 lg:py-8 space-y-6">

        <PageHeader
          eyebrow="Assignment Results"
          title="Review programming assignment risk in one professional table."
          description="The summary tells the teaching team where to spend time before opening individual compare cases."
          action={<ButtonLink href="/upload?mode=zip" icon={FileUp}>Upload New Assignment</ButtonLink>}
          eyebrowStyle="badge"
        />

        {/* Stats Grid */}
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Total submissions" value={loaded ? String(totalSubmissions) : '…'} detail="Files analyzed across uploads" icon={Users} tone="blue" />
          <StatCard label="High risk" value={loaded ? String(highRisk) : '…'} detail="CRITICAL / HIGH detection pairs" icon={ShieldAlert} tone="red" />
          <StatCard label="Medium risk" value={loaded ? String(mediumRisk) : '…'} detail="MEDIUM detection pairs" icon={Inbox} />
          <StatCard label="Cleared" value={loaded ? String(cleared) : '…'} detail="Low-risk pairs, no action needed" icon={CheckCircle2} tone="green" />
        </section>

        {/* Table Card */}
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
                      : 'border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 dark:border-slate-850 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800'
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
              <thead className="bg-slate-50 dark:bg-slate-900/50">
                <tr className="border-b border-slate-200 dark:border-slate-800">
                  {['Rank', 'Case', 'Risk Score', 'Course / Assignment', 'Reviewer', 'Actions'].map((heading) => (
                    <th key={heading} className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                {!loaded ? (
                  <tr>
                    <td colSpan={6} className="px-5 py-10 text-center text-sm text-slate-500 dark:text-slate-400 bg-white dark:bg-slate-950">
                      Loading cases…
                    </td>
                  </tr>
                ) : error ? (
                  <tr>
                    <td colSpan={6} className="px-5 py-10 text-center text-sm text-red-600 dark:text-red-400 bg-white dark:bg-slate-950">
                      {error}
                    </td>
                  </tr>
                ) : rows.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-5 py-10 text-center text-sm text-slate-500 dark:text-slate-400 bg-white dark:bg-slate-950">
                      No cases found matching this filter.
                    </td>
                  </tr>
                ) : (
                  rows.map((item, index) => (
                    <tr key={item.id} className="transition bg-white hover:bg-slate-50 dark:bg-slate-950 dark:hover:bg-slate-900/40">
                      <td className="px-5 py-4 text-sm font-semibold text-slate-600 dark:text-slate-400">#{index + 1}</td>
                      <td className="px-5 py-4">
                        <div className="text-sm font-semibold text-slate-950 dark:text-white">{item.title}</div>
                        <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">{item.status}</div>
                      </td>
                      <td className="px-5 py-4"><RiskBadge value={PRIORITY_RISK[item.priority] ?? 40} label={riskTierOf(item.priority)} /></td>
                      <td className="px-5 py-4 text-sm font-medium text-slate-700 dark:text-slate-300">{item.course} / {item.assignment}</td>
                      <td className="px-5 py-4 text-sm text-slate-600 dark:text-slate-400">{item.investigator}</td>
                      <td className="px-5 py-4">
                        <a href={`/cases/${item.id}`} className="text-sm font-semibold text-blue-600 dark:text-blue-400 hover:underline">
                          Compare
                        </a>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </DashboardLayout>
  );
}