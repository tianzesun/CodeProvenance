'use client';

import DashboardLayout from '@/components/DashboardLayout';
import Link from 'next/link';
import { useState, useEffect, useRef } from 'react';
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
  FileSearch,
  CheckCircle2,
  ChevronRight,
  TrendingUp,
  Zap,
  Layers,
  Target,
  Activity,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  Bell,
  Search,
  Plus,
} from 'lucide-react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8500';

function useAnimatedCounter(end, duration = 1200) {
  const [count, setCount] = useState(0);
  const [hasStarted, setHasStarted] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting && !hasStarted) setHasStarted(true); },
      { threshold: 0.3 }
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, [hasStarted]);

  useEffect(() => {
    if (!hasStarted) return;
    let start = 0;
    const step = end / (duration / 16);
    const timer = setInterval(() => {
      start += step;
      if (start >= end) { setCount(end); clearInterval(timer); }
      else setCount(Math.floor(start));
    }, 16);
    return () => clearInterval(timer);
  }, [end, duration, hasStarted]);

  return [count, ref];
}

export default function Home() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(fetchJobs, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchJobs = async () => {
    try {
      const res = await axios.get(`${API}/api/jobs`);
      setJobs(res.data.jobs || []);
    } catch { setJobs([]); }
    setLoading(false);
  };

  const completedJobs = jobs.filter((j) => j.status === 'completed');
  const totalFiles = completedJobs.reduce((s, j) => s + (j.file_count || 0), 0);
  const totalFlagged = completedJobs.reduce((s, j) => s + (j.summary?.suspicious_pairs || 0), 0);
  const totalCritical = completedJobs.reduce((s, j) => s + (j.results?.filter((r) => r.score >= 0.9).length || 0), 0);

  const recentJobs = jobs.slice(0, 8);
  const recentActivity = jobs.slice(0, 5).map((j) => ({
    id: j.id,
    course: j.course_name,
    assignment: j.assignment_name,
    status: j.status,
    flagged: j.summary?.suspicious_pairs || 0,
    time: j.created_at,
  }));

  const [totalRef, totalVal] = useAnimatedCounter(jobs.length);
  const [filesRef, filesVal] = useAnimatedCounter(totalFiles);
  const [flaggedRef, flaggedVal] = useAnimatedCounter(totalFlagged);
  const [criticalRef, criticalVal] = useAnimatedCounter(totalCritical);

  return (
    <DashboardLayout>
      <div className="p-6 lg:p-8 max-w-[1440px] mx-auto">
        {/* Top Bar */}
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 mb-8 animate-fade-in">
          <div>
            <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Dashboard</h1>
            <p className="text-slate-500 mt-1">
              Monitor code similarity analyses and academic integrity cases across your courses.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="relative hidden md:block">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search analyses..."
                className="pl-9 pr-4 py-2 bg-white border border-slate-200 rounded-xl text-sm w-64 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all"
              />
            </div>
            <button className="relative p-2.5 bg-white border border-slate-200 rounded-xl hover:bg-slate-50 transition-colors">
              <Bell size={18} className="text-slate-500" />
              {totalFlagged > 0 && (
                <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 rounded-full text-[9px] font-bold text-white flex items-center justify-center animate-pulse-glow">
                  {totalFlagged}
                </span>
              )}
            </button>
            <Link
              href="/upload"
              className="inline-flex items-center gap-2 px-4 py-2.5 bg-blue-600 text-white rounded-xl text-sm font-semibold hover:bg-blue-700 transition-colors shadow-lg shadow-blue-500/20"
            >
              <Plus size={16} />
              New Analysis
            </Link>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatCard
            ref={totalRef}
            value={totalVal}
            label="Total Analyses"
            icon={FileCheck}
            gradient="from-blue-500 to-blue-600"
            bgLight="bg-blue-50"
            trend="+12%"
            trendUp
          />
          <StatCard
            ref={filesRef}
            value={filesVal}
            label="Files Analyzed"
            icon={Users}
            gradient="from-emerald-500 to-emerald-600"
            bgLight="bg-emerald-50"
            trend="+8%"
            trendUp
          />
          <StatCard
            ref={flaggedRef}
            value={flaggedVal}
            label="Flagged Cases"
            icon={AlertTriangle}
            gradient="from-amber-500 to-amber-600"
            bgLight="bg-amber-50"
            trend={totalFlagged > 0 ? `${totalFlagged} active` : 'None'}
            trendUp={false}
            neutral
          />
          <StatCard
            ref={criticalRef}
            value={criticalVal}
            label="Critical Risk"
            icon={Shield}
            gradient="from-red-500 to-red-600"
            bgLight="bg-red-50"
            trend={totalCritical > 0 ? 'Requires action' : 'Clear'}
            trendUp={totalCritical === 0}
            neutral
          />
        </div>

        {/* Main Content Grid */}
        <div className="grid lg:grid-cols-3 gap-6 mb-8">
          {/* Quick Actions */}
          <div className="lg:col-span-2 space-y-4">
            <h2 className="text-lg font-semibold text-slate-900">Quick Actions</h2>
            <div className="grid sm:grid-cols-3 gap-4">
              <QuickAction
                href="/upload"
                icon={Upload}
                title="New Analysis"
                desc="Upload files or ZIP archive"
                gradient="from-blue-500 to-blue-600"
                shadow="shadow-blue-500/20"
                delay={0}
              />
              <QuickAction
                href="/benchmark"
                icon={Layers}
                title="Multi-Tool Compare"
                desc="Run 5 tools simultaneously"
                gradient="from-violet-500 to-violet-600"
                shadow="shadow-violet-500/20"
                delay={100}
              />
              <QuickAction
                href="/reports"
                icon={FileSearch}
                title="Reports"
                desc="Download & committee reports"
                gradient="from-slate-600 to-slate-700"
                shadow="shadow-slate-500/20"
                delay={200}
              />
            </div>

            {/* Recent Analyses Table */}
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden mt-6">
              <div className="px-6 py-5 border-b border-slate-100 flex items-center justify-between">
                <div>
                  <h2 className="font-semibold text-slate-900 text-lg">Recent Analyses</h2>
                  <p className="text-sm text-slate-500 mt-0.5">
                    {completedJobs.length} completed analysis{completedJobs.length !== 1 ? 'es' : ''}
                  </p>
                </div>
                <Link href="/reports" className="text-sm text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1">
                  View all <ChevronRight size={14} />
                </Link>
              </div>

              {loading ? (
                <div className="p-6 space-y-3">
                  {[1, 2, 3, 4].map((i) => (
                    <div key={i} className="flex items-center gap-4 animate-pulse">
                      <div className="w-8 h-8 rounded-lg bg-slate-100" />
                      <div className="flex-1 space-y-2">
                        <div className="h-4 bg-slate-100 rounded w-1/3 skeleton" />
                        <div className="h-3 bg-slate-100 rounded w-1/4 skeleton" />
                      </div>
                    </div>
                  ))}
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
                  <Link href="/upload" className="inline-flex items-center gap-2 px-5 py-2.5 bg-blue-600 text-white rounded-xl text-sm font-semibold hover:bg-blue-700 transition-colors shadow-lg shadow-blue-500/20">
                    <Upload size={16} /> Start your first analysis
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
                      {recentJobs.map((job, i) => (
                        <tr
                          key={job.id}
                          className="border-t border-slate-50 hover:bg-slate-50/60 transition-colors group animate-fade-in"
                          style={{ animationDelay: `${i * 50}ms` }}
                        >
                          <td className="px-6 py-4">
                            <div className="flex items-center gap-3">
                              <div className="w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center shrink-0">
                                <FileCheck size={14} className="text-blue-600" />
                              </div>
                              <span className="font-medium text-slate-900 text-sm truncate max-w-[200px]">
                                {job.course_name}
                              </span>
                            </div>
                          </td>
                          <td className="px-6 py-4 text-sm text-slate-600 max-w-[200px] truncate">{job.assignment_name}</td>
                          <td className="px-6 py-4 text-center">
                            <span className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-slate-100 text-sm font-semibold text-slate-700">{job.file_count}</span>
                          </td>
                          <td className="px-6 py-4 text-center"><RiskBadge count={job.summary?.suspicious_pairs || 0} /></td>
                          <td className="px-6 py-4"><StatusBadge status={job.status} /></td>
                          <td className="px-6 py-4 text-sm text-slate-400 whitespace-nowrap">{job.created_at?.slice(0, 16).replace('T', ' ')}</td>
                          <td className="px-6 py-4 text-right">
                            {job.status === 'completed' ? (
                              <Link href={`/results/${job.id}`} className="inline-flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700 font-medium opacity-0 group-hover:opacity-100 transition-opacity">
                                View <ChevronRight size={14} />
                              </Link>
                            ) : <span className="text-xs text-slate-400">--</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>

          {/* Activity Feed */}
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-slate-900">Activity Feed</h2>
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
              {loading ? (
                <div className="p-5 space-y-4">
                  {[1, 2, 3, 4, 5].map((i) => (
                    <div key={i} className="flex items-start gap-3 animate-pulse">
                      <div className="w-8 h-8 rounded-full bg-slate-100 shrink-0" />
                      <div className="flex-1 space-y-2">
                        <div className="h-3 bg-slate-100 rounded w-3/4 skeleton" />
                        <div className="h-2.5 bg-slate-100 rounded w-1/2 skeleton" />
                      </div>
                    </div>
                  ))}
                </div>
              ) : recentActivity.length === 0 ? (
                <div className="p-8 text-center text-slate-400 text-sm">No recent activity</div>
              ) : (
                <div className="divide-y divide-slate-50">
                  {recentActivity.map((activity, i) => (
                    <div key={activity.id} className="px-5 py-4 hover:bg-slate-50/50 transition-colors animate-fade-in" style={{ animationDelay: `${i * 80}ms` }}>
                      <div className="flex items-start gap-3">
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
                          activity.status === 'completed' ? 'bg-emerald-50' :
                          activity.status === 'failed' ? 'bg-red-50' : 'bg-blue-50'
                        }`}>
                          {activity.status === 'completed' ? (
                            <CheckCircle2 size={14} className="text-emerald-600" />
                          ) : activity.status === 'failed' ? (
                            <AlertTriangle size={14} className="text-red-600" />
                          ) : (
                            <Loader2 size={14} className="text-blue-600 animate-spin" />
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-slate-900 truncate">{activity.course}</p>
                          <p className="text-xs text-slate-500 truncate">{activity.assignment}</p>
                          <div className="flex items-center gap-2 mt-1.5">
                            <StatusBadge status={activity.status} />
                            {activity.flagged > 0 && (
                              <span className="text-[10px] font-semibold text-red-600 bg-red-50 px-1.5 py-0.5 rounded">
                                {activity.flagged} flagged
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* System Status */}
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5">
              <h3 className="text-sm font-semibold text-slate-900 mb-4">System Status</h3>
              <div className="space-y-3">
                <StatusItem label="Detection Engines" status="online" detail="6/6 active" />
                <StatusItem label="Embedding Model" status="online" detail="UniXcoder (CPU)" />
                <StatusItem label="Report Generator" status="online" detail="Ready" />
                <StatusItem label="Benchmark API" status="online" detail="5 tools available" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

const StatCard = ({ ref, value, label, icon: Icon, gradient, bgLight, trend, trendUp, neutral }) => (
  <div ref={ref} className="bg-white rounded-2xl border border-slate-200 p-5 hover:shadow-md transition-all duration-200 group">
    <div className="flex items-center justify-between mb-3">
      <div className={`w-10 h-10 rounded-xl ${bgLight} flex items-center justify-center group-hover:scale-110 transition-transform duration-200`}>
        <Icon size={18} className="text-slate-600" />
      </div>
      {trend && (
        <div className={`flex items-center gap-0.5 text-xs font-semibold ${
          neutral ? 'text-slate-500' : trendUp ? 'text-emerald-600' : 'text-red-600'
        }`}>
          {neutral ? <Minus size={12} /> : trendUp ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
          {trend}
        </div>
      )}
    </div>
    <div className="text-2xl font-bold text-slate-900 tracking-tight">{value}</div>
    <div className="text-xs font-medium text-slate-400 mt-1 uppercase tracking-wider">{label}</div>
  </div>
);

const QuickAction = ({ href, icon: Icon, title, desc, gradient, shadow, delay }) => (
  <Link
    href={href}
    className="group relative overflow-hidden rounded-2xl border border-slate-200 bg-white p-5 hover:border-slate-300 hover:shadow-lg transition-all duration-300 animate-fade-in"
    style={{ animationDelay: `${delay}ms` }}
  >
    <div className={`w-11 h-11 rounded-xl bg-gradient-to-br ${gradient} flex items-center justify-center mb-4 shadow-lg ${shadow} group-hover:scale-110 transition-transform duration-300`}>
      <Icon size={20} className="text-white" />
    </div>
    <h3 className="font-semibold text-slate-900 mb-1">{title}</h3>
    <p className="text-sm text-slate-500 leading-relaxed">{desc}</p>
    <div className="absolute bottom-5 right-5 opacity-0 group-hover:opacity-100 translate-x-2 group-hover:translate-x-0 transition-all duration-300">
      <ArrowRight size={18} className="text-slate-400" />
    </div>
  </Link>
);

const StatusBadge = ({ status }) => {
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
};

const RiskBadge = ({ count }) => {
  if (count === 0) return <span className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-slate-50 text-sm font-semibold text-slate-400">0</span>;
  if (count > 5) return <span className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-red-50 text-sm font-bold text-red-600">{count}</span>;
  if (count > 2) return <span className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-amber-50 text-sm font-bold text-amber-600">{count}</span>;
  return <span className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-emerald-50 text-sm font-bold text-emerald-600">{count}</span>;
};

const StatusItem = ({ label, status, detail }) => (
  <div className="flex items-center justify-between">
    <div className="flex items-center gap-2">
      <div className={`w-2 h-2 rounded-full ${status === 'online' ? 'bg-emerald-500' : 'bg-red-500'}`} />
      <span className="text-sm text-slate-700">{label}</span>
    </div>
    <span className="text-xs text-slate-400">{detail}</span>
  </div>
);
