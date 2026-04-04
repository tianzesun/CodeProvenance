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
  Users,
  TrendingUp,
  FileSearch,
  CheckCircle2,
  AlertCircle,
  ChevronRight,
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

  const completedJobs = jobs.filter((j) => j.status === 'completed');
  const totalFiles = completedJobs.reduce((s, j) => s + (j.file_count || 0), 0);
  const totalFlagged = completedJobs.reduce(
    (s, j) => s + (j.summary?.suspicious_pairs || 0), 0
  );
  const totalCritical = completedJobs.reduce(
    (s, j) => s + (j.results?.filter((r) => r.score >= 0.9).length || 0), 0
  );

  const recentJobs = jobs.slice(0, 8);

  return (
    <DashboardLayout>
      <div className="p-6 lg:p-8">
        {/* Welcome Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-slate-900 tracking-tight">
            Welcome back
          </h1>
          <p className="text-slate-500 mt-1.5 text-base">
            Monitor code similarity analyses and academic integrity cases across your courses.
          </p>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatCard
            icon={FileCheck}
            label="Total Analyses"
            value={jobs.length}
            gradient="from-blue-500 to-blue-600"
            bgLight="bg-blue-50"
          />
          <StatCard
            icon={Users}
            label="Files Analyzed"
            value={totalFiles}
            gradient="from-emerald-500 to-emerald-600"
            bgLight="bg-emerald-50"
          />
          <StatCard
            icon={AlertTriangle}
            label="Flagged Cases"
            value={totalFlagged}
            gradient="from-amber-500 to-amber-600"
            bgLight="bg-amber-50"
          />
          <StatCard
            icon={Shield}
            label="Critical Risk"
            value={totalCritical}
            gradient="from-red-500 to-red-600"
            bgLight="bg-red-50"
          />
        </div>

        {/* Quick Actions */}
        <div className="grid md:grid-cols-3 gap-4 mb-8">
          <Link
            href="/upload"
            className="group relative overflow-hidden rounded-2xl border border-slate-200 bg-white p-6 hover:border-brand-300 hover:shadow-lg hover:shadow-brand-500/5 transition-all duration-300"
          >
            <div className="absolute top-0 right-0 w-24 h-24 bg-gradient-to-br from-brand-500/10 to-transparent rounded-bl-full" />
            <div className="relative">
              <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-brand-500 to-brand-600 flex items-center justify-center mb-4 shadow-lg shadow-brand-500/25">
                <Upload size={20} className="text-white" />
              </div>
              <h3 className="font-semibold text-slate-900 mb-1">New Analysis</h3>
              <p className="text-sm text-slate-500 leading-relaxed">
                Upload individual files or a ZIP archive to check for code similarity
              </p>
            </div>
            <div className="absolute bottom-6 right-6 opacity-0 group-hover:opacity-100 translate-x-2 group-hover:translate-x-0 transition-all duration-300">
              <ArrowRight size={18} className="text-brand-600" />
            </div>
          </Link>

          <Link
            href="/benchmark"
            className="group relative overflow-hidden rounded-2xl border border-slate-200 bg-white p-6 hover:border-violet-300 hover:shadow-lg hover:shadow-violet-500/5 transition-all duration-300"
          >
            <div className="absolute top-0 right-0 w-24 h-24 bg-gradient-to-br from-violet-500/10 to-transparent rounded-bl-full" />
            <div className="relative">
              <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-violet-500 to-violet-600 flex items-center justify-center mb-4 shadow-lg shadow-violet-500/25">
                <BarChart3 size={20} className="text-white" />
              </div>
              <h3 className="font-semibold text-slate-900 mb-1">Benchmark</h3>
              <p className="text-sm text-slate-500 leading-relaxed">
                Compare IntegrityDesk against MOSS, JPlag, Dolos, and Codequiry
              </p>
            </div>
            <div className="absolute bottom-6 right-6 opacity-0 group-hover:opacity-100 translate-x-2 group-hover:translate-x-0 transition-all duration-300">
              <ArrowRight size={18} className="text-violet-600" />
            </div>
          </Link>

          <Link
            href="/reports"
            className="group relative overflow-hidden rounded-2xl border border-slate-200 bg-white p-6 hover:border-slate-300 hover:shadow-lg hover:shadow-slate-500/5 transition-all duration-300"
          >
            <div className="absolute top-0 right-0 w-24 h-24 bg-gradient-to-br from-slate-500/10 to-transparent rounded-bl-full" />
            <div className="relative">
              <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-slate-600 to-slate-700 flex items-center justify-center mb-4 shadow-lg shadow-slate-500/25">
                <FileSearch size={20} className="text-white" />
              </div>
              <h3 className="font-semibold text-slate-900 mb-1">Reports</h3>
              <p className="text-sm text-slate-500 leading-relaxed">
                View, download, and generate committee-ready analysis reports
              </p>
            </div>
            <div className="absolute bottom-6 right-6 opacity-0 group-hover:opacity-100 translate-x-2 group-hover:translate-x-0 transition-all duration-300">
              <ArrowRight size={18} className="text-slate-600" />
            </div>
          </Link>
        </div>

        {/* Recent Analyses */}
        <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-sm">
          <div className="px-6 py-5 border-b border-slate-100 flex items-center justify-between">
            <div>
              <h2 className="font-semibold text-slate-900 text-lg">Recent Analyses</h2>
              <p className="text-sm text-slate-500 mt-0.5">
                {completedJobs.length} completed analysis{completedJobs.length !== 1 ? 'es' : ''}
              </p>
            </div>
            <Link
              href="/reports"
              className="text-sm text-brand-600 hover:text-brand-700 font-medium flex items-center gap-1"
            >
              View all
              <ChevronRight size={14} />
            </Link>
          </div>

          {loading ? (
            <div className="flex flex-col items-center justify-center py-20">
              <div className="w-10 h-10 border-4 border-slate-200 border-t-brand-500 rounded-full animate-spin" />
              <p className="text-sm text-slate-500 mt-4">Loading analyses...</p>
            </div>
          ) : recentJobs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 px-6">
              <div className="w-16 h-16 rounded-2xl bg-slate-50 flex items-center justify-center mb-4">
                <Clock size={28} className="text-slate-300" />
              </div>
              <h3 className="font-semibold text-slate-900 mb-1">No analyses yet</h3>
              <p className="text-sm text-slate-500 text-center max-w-sm mb-6">
                Upload student submissions to detect code similarity and potential academic integrity issues.
              </p>
              <Link
                href="/upload"
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-brand-600 text-white rounded-xl text-sm font-semibold hover:bg-brand-700 transition-colors shadow-lg shadow-brand-500/25"
              >
                <Upload size={16} />
                Start your first analysis
              </Link>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-[11px] uppercase tracking-wider text-slate-400 bg-slate-50/80">
                    <th className="text-left px-6 py-3.5 font-semibold">Course</th>
                    <th className="text-left px-6 py-3.5 font-semibold">Assignment</th>
                    <th className="text-center px-6 py-3.5 font-semibold">Files</th>
                    <th className="text-center px-6 py-3.5 font-semibold">Flagged</th>
                    <th className="text-left px-6 py-3.5 font-semibold">Status</th>
                    <th className="text-left px-6 py-3.5 font-semibold">Date</th>
                    <th className="px-6 py-3.5" />
                  </tr>
                </thead>
                <tbody>
                  {recentJobs.map((job) => (
                    <tr
                      key={job.id}
                      className="border-t border-slate-50 hover:bg-slate-50/60 transition-colors group"
                    >
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-lg bg-brand-50 flex items-center justify-center shrink-0">
                            <FileCheck size={14} className="text-brand-600" />
                          </div>
                          <span className="font-medium text-slate-900 text-sm truncate max-w-[200px]">
                            {job.course_name}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-600 max-w-[200px] truncate">
                        {job.assignment_name}
                      </td>
                      <td className="px-6 py-4 text-center">
                        <span className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-slate-100 text-sm font-semibold text-slate-700">
                          {job.file_count}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-center">
                        <RiskBadge count={job.summary?.suspicious_pairs || 0} />
                      </td>
                      <td className="px-6 py-4">
                        <StatusBadge status={job.status} />
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-400 whitespace-nowrap">
                        {job.created_at?.slice(0, 16).replace('T', ' ')}
                      </td>
                      <td className="px-6 py-4 text-right">
                        {job.status === 'completed' ? (
                          <Link
                            href={`/results/${job.id}`}
                            className="inline-flex items-center gap-1 text-sm text-brand-600 hover:text-brand-700 font-medium opacity-0 group-hover:opacity-100 transition-opacity"
                          >
                            View
                            <ChevronRight size={14} />
                          </Link>
                        ) : (
                          <span className="text-xs text-slate-400">--</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}

function StatCard({ icon: Icon, label, value, gradient, bgLight }) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-5 hover:shadow-md transition-shadow group">
      <div className="flex items-center justify-between mb-4">
        <div className={`w-10 h-10 rounded-xl ${bgLight} flex items-center justify-center group-hover:scale-110 transition-transform`}>
          <Icon size={18} className={`bg-gradient-to-br ${gradient} bg-clip-text text-transparent`} style={{ WebkitTextFillColor: 'transparent' }} />
        </div>
        <TrendingUp size={14} className="text-slate-300" />
      </div>
      <div className="text-2xl font-bold text-slate-900 tracking-tight">{value}</div>
      <div className="text-xs font-medium text-slate-400 mt-1 uppercase tracking-wider">{label}</div>
    </div>
  );
}

function StatusBadge({ status }) {
  const map = {
    completed: { bg: 'bg-emerald-50', text: 'text-emerald-700', dot: 'bg-emerald-500', label: 'Completed' },
    processing: { bg: 'bg-blue-50', text: 'text-blue-700', dot: 'bg-blue-500', label: 'Processing' },
    analyzing: { bg: 'bg-amber-50', text: 'text-amber-700', dot: 'bg-amber-500', label: 'Analyzing' },
    failed: { bg: 'bg-red-50', text: 'text-red-700', dot: 'bg-red-500', label: 'Failed' },
  };
  const s = map[status] || { bg: 'bg-slate-100', text: 'text-slate-600', dot: 'bg-slate-400', label: status };
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${s.bg} ${s.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${s.dot}`} />
      {s.label}
    </span>
  );
}

function RiskBadge({ count }) {
  if (count === 0)
    return <span className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-slate-50 text-sm font-semibold text-slate-400">0</span>;
  if (count > 5)
    return <span className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-red-50 text-sm font-bold text-red-600">{count}</span>;
  if (count > 2)
    return <span className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-amber-50 text-sm font-bold text-amber-600">{count}</span>;
  return <span className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-emerald-50 text-sm font-bold text-emerald-600">{count}</span>;
}
