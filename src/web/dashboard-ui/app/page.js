'use client';

import DashboardLayout from '@/components/DashboardLayout';
import Link from 'next/link';
import { useState, useEffect } from 'react';
import axios from 'axios';
import {
  Shield,
  Upload,
  BarChart3,
  AlertTriangle,
  FileCheck,
  Clock,
  ArrowRight,
  Loader2,
} from 'lucide-react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8500';

export default function Home() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchJobs();
  }, []);

  const fetchJobs = async () => {
    try {
      const res = await axios.get(`${API}/api/jobs`);
      setJobs(res.data.jobs || []);
    } catch {
      setJobs([]);
    }
    setLoading(false);
  };

  const stats = {
    total: jobs.length,
    completed: jobs.filter((j) => j.status === 'completed').length,
    flagged: jobs.reduce(
      (sum, j) => sum + (j.summary?.suspicious_pairs || 0),
      0
    ),
    critical: jobs.reduce(
      (sum, j) =>
        sum +
        (j.results?.filter((r) => r.score >= 0.9).length || 0),
      0
    ),
  };

  return (
    <DashboardLayout>
      <div className="p-6 lg:p-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
          <p className="text-slate-500 mt-1">
            Monitor your code similarity analyses and academic integrity cases.
          </p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatCard
            icon={FileCheck}
            label="Total Analyses"
            value={stats.total}
            color="brand"
          />
          <StatCard
            icon={Shield}
            label="Completed"
            value={stats.completed}
            color="green"
          />
          <StatCard
            icon={AlertTriangle}
            label="Flagged Cases"
            value={stats.flagged}
            color="amber"
          />
          <StatCard
            icon={AlertTriangle}
            label="Critical Risk"
            value={stats.critical}
            color="red"
          />
        </div>

        {/* Quick Actions */}
        <div className="grid md:grid-cols-2 gap-4 mb-8">
          <Link
            href="/upload"
            className="group flex items-center gap-4 p-5 rounded-xl border border-slate-200 bg-white hover:border-brand-300 hover:shadow-md transition-all"
          >
            <div className="w-12 h-12 rounded-xl bg-brand-50 flex items-center justify-center group-hover:bg-brand-100 transition-colors">
              <Upload size={22} className="text-brand-600" />
            </div>
            <div className="flex-1">
              <div className="font-semibold text-slate-900">New Analysis</div>
              <div className="text-sm text-slate-500">
                Upload files or a ZIP archive to check for similarity
              </div>
            </div>
            <ArrowRight
              size={18}
              className="text-slate-400 group-hover:text-brand-600 group-hover:translate-x-1 transition-all"
            />
          </Link>
          <Link
            href="/benchmark"
            className="group flex items-center gap-4 p-5 rounded-xl border border-slate-200 bg-white hover:border-brand-300 hover:shadow-md transition-all"
          >
            <div className="w-12 h-12 rounded-xl bg-violet-50 flex items-center justify-center group-hover:bg-violet-100 transition-colors">
              <BarChart3 size={22} className="text-violet-600" />
            </div>
            <div className="flex-1">
              <div className="font-semibold text-slate-900">Benchmark Tools</div>
              <div className="text-sm text-slate-500">
                Compare IntegrityDesk against other detection tools
              </div>
            </div>
            <ArrowRight
              size={18}
              className="text-slate-400 group-hover:text-violet-600 group-hover:translate-x-1 transition-all"
            />
          </Link>
        </div>

        {/* Recent Analyses */}
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
            <h2 className="font-semibold text-slate-900">Recent Analyses</h2>
            <Link
              href="/reports"
              className="text-sm text-brand-600 hover:text-brand-700 font-medium"
            >
              View all
            </Link>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 size={24} className="animate-spin text-slate-400" />
            </div>
          ) : jobs.length === 0 ? (
            <div className="text-center py-16">
              <Clock size={40} className="mx-auto text-slate-300 mb-3" />
              <p className="text-slate-500">No analyses yet.</p>
              <Link
                href="/upload"
                className="text-sm text-brand-600 hover:text-brand-700 font-medium mt-1 inline-block"
              >
                Start your first analysis
              </Link>
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="text-xs uppercase tracking-wider text-slate-500 bg-slate-50/50">
                  <th className="text-left px-5 py-3 font-medium">Course</th>
                  <th className="text-left px-5 py-3 font-medium">Assignment</th>
                  <th className="text-left px-5 py-3 font-medium">Files</th>
                  <th className="text-left px-5 py-3 font-medium">Flagged</th>
                  <th className="text-left px-5 py-3 font-medium">Status</th>
                  <th className="text-left px-5 py-3 font-medium">Date</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody>
                {jobs.slice(0, 10).map((job) => (
                  <tr
                    key={job.id}
                    className="border-t border-slate-100 hover:bg-slate-50/50 transition-colors"
                  >
                    <td className="px-5 py-3.5 font-medium text-slate-900 text-sm">
                      {job.course_name}
                    </td>
                    <td className="px-5 py-3.5 text-sm text-slate-600">
                      {job.assignment_name}
                    </td>
                    <td className="px-5 py-3.5 text-sm text-slate-600">
                      {job.file_count}
                    </td>
                    <td className="px-5 py-3.5">
                      <RiskBadge
                        count={job.summary?.suspicious_pairs || 0}
                      />
                    </td>
                    <td className="px-5 py-3.5">
                      <StatusBadge status={job.status} />
                    </td>
                    <td className="px-5 py-3.5 text-sm text-slate-500">
                      {job.created_at?.slice(0, 16).replace('T', ' ')}
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      {job.status === 'completed' && (
                        <Link
                          href={`/results/${job.id}`}
                          className="text-sm text-brand-600 hover:text-brand-700 font-medium"
                        >
                          View
                        </Link>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}

function StatCard({ icon: Icon, label, value, color }) {
  const colors = {
    brand: 'bg-brand-50 text-brand-600',
    green: 'bg-green-50 text-green-600',
    amber: 'bg-amber-50 text-amber-600',
    red: 'bg-red-50 text-red-600',
  };
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <div className="flex items-center gap-3 mb-3">
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${colors[color]}`}>
          <Icon size={18} />
        </div>
        <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">
          {label}
        </span>
      </div>
      <div className="text-2xl font-bold text-slate-900">{value}</div>
    </div>
  );
}

function StatusBadge({ status }) {
  const map = {
    completed: 'bg-green-50 text-green-700',
    processing: 'bg-blue-50 text-blue-700',
    analyzing: 'bg-amber-50 text-amber-700',
    failed: 'bg-red-50 text-red-700',
  };
  return (
    <span className={`inline-flex px-2.5 py-1 rounded-full text-xs font-semibold capitalize ${map[status] || 'bg-slate-100 text-slate-600'}`}>
      {status}
    </span>
  );
}

function RiskBadge({ count }) {
  if (count === 0)
    return <span className="text-xs text-slate-400">0</span>;
  if (count > 5)
    return <span className="inline-flex px-2 py-0.5 rounded-full text-xs font-bold bg-red-100 text-red-700">{count}</span>;
  if (count > 2)
    return <span className="inline-flex px-2 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-700">{count}</span>;
  return <span className="inline-flex px-2 py-0.5 rounded-full text-xs font-bold bg-green-100 text-green-700">{count}</span>;
}
