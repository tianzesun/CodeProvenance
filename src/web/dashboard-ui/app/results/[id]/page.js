'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import axios from 'axios';
import {
  ArrowLeft,
  Download,
  FileText,
  Shield,
  AlertTriangle,
  BarChart3,
  Code2,
  ChevronDown,
  ChevronUp,
  Building2,
} from 'lucide-react';
import Link from 'next/link';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8500';

export default function ResultsPage() {
  const { id } = useParams();
  const router = useRouter();
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [expanded, setExpanded] = useState({});

  useEffect(() => {
    if (id) fetchJob();
  }, [id]);

  const fetchJob = async () => {
    try {
      const res = await axios.get(`${API}/api/job/${id}`);
      setJob(res.data);
    } catch {
      router.push('/');
    }
    setLoading(false);
  };

  if (loading) return <DashboardLayout><div className="p-8 flex justify-center"><div className="animate-spin w-8 h-8 border-4 border-slate-200 border-t-brand-600 rounded-full" /></div></DashboardLayout>;
  if (!job) return null;

  const results = job.results || [];
  const summary = job.summary || {};
  const critical = results.filter((r) => r.score >= 0.9);
  const high = results.filter((r) => r.score >= 0.75 && r.score < 0.9);
  const medium = results.filter((r) => r.score >= 0.5 && r.score < 0.75);
  const low = results.filter((r) => r.score < 0.5);

  const filtered = filter === 'all' ? results
    : filter === 'critical' ? critical
    : filter === 'high' ? high
    : filter === 'flagged' ? results.filter((r) => r.score >= job.threshold)
    : results;

  const toggleCode = (idx) => {
    setExpanded((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  return (
    <DashboardLayout>
      <div className="p-6 lg:p-8 max-w-6xl">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-sm text-slate-500 mb-6">
          <Link href="/" className="hover:text-brand-600">Dashboard</Link>
          <span>/</span>
          <span className="text-slate-900 font-medium">{job.course_name}</span>
        </div>

        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">{job.course_name} -- {job.assignment_name}</h1>
            <p className="text-sm text-slate-500 mt-1">
              Case ID: {job.id} | {job.created_at?.slice(0, 16).replace('T', ' ')} | Threshold: {(job.threshold * 100).toFixed(0)}%
            </p>
          </div>
          <div className="flex gap-2 flex-wrap">
            <a href={`${API}/report/${id}/download`} className="inline-flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm font-medium text-slate-700 hover:border-brand-300 hover:text-brand-600 transition-colors">
              <FileText size={16} /> HTML Report
            </a>
            <a href={`${API}/report/${id}/download-json`} className="inline-flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm font-medium text-slate-700 hover:border-brand-300 hover:text-brand-600 transition-colors">
              <Download size={16} /> JSON
            </a>
            <a href={`${API}/report/${id}/committee`} className="inline-flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-semibold hover:bg-red-700 transition-colors">
              <Building2 size={16} /> Committee Report
            </a>
          </div>
        </div>

        {/* Alert banner */}
        {summary.suspicious_pairs > 0 && (
          <div className="bg-amber-50 border border-amber-200 border-l-4 border-l-amber-500 rounded-lg p-4 mb-6 flex items-center justify-between flex-wrap gap-3">
            <div>
              <p className="font-semibold text-amber-800">{summary.suspicious_pairs} flagged pair(s) detected above threshold</p>
              <p className="text-sm text-amber-700">{critical.length} critical and {high.length} high-risk findings require review.</p>
            </div>
            <a href={`${API}/report/${id}/committee`} className="inline-flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-semibold hover:bg-red-700 transition-colors shrink-0">
              <Shield size={14} /> Generate Committee Report
            </a>
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <StatCard label="Submissions" value={job.file_count} />
          <StatCard label="Pairs Compared" value={summary.total_pairs || 0} />
          <StatCard label="Flagged Pairs" value={summary.suspicious_pairs || 0} color="red" />
          <StatCard label="Critical Risk" value={critical.length} color="red" />
        </div>

        {/* Risk distribution */}
        <div className="grid grid-cols-4 gap-3 mb-6">
          <RiskCard count={critical.length} label="Critical (90%+)" color="red" />
          <RiskCard count={high.length} label="High (75-89%)" color="amber" />
          <RiskCard count={medium.length} label="Medium (50-74%)" color="yellow" />
          <RiskCard count={low.length} label="Low (<50%)" color="green" />
        </div>

        {/* Results */}
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between flex-wrap gap-3">
            <h2 className="font-semibold text-slate-900">Pairwise Similarity Results</h2>
            <div className="flex gap-1">
              {[
                { key: 'all', label: `All (${results.length})` },
                { key: 'critical', label: `Critical (${critical.length})` },
                { key: 'high', label: `High (${high.length})` },
                { key: 'flagged', label: `Flagged (${summary.suspicious_pairs || 0})` },
              ].map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setFilter(tab.key)}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                    filter === tab.key
                      ? 'bg-brand-600 text-white'
                      : 'text-slate-500 hover:bg-slate-100'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {filtered.length === 0 ? (
            <div className="text-center py-16 text-slate-400">
              <BarChart3 size={40} className="mx-auto mb-3" />
              <p>No results match the selected filter.</p>
            </div>
          ) : (
            filtered.map((result, idx) => {
              const risk = result.score >= 0.9 ? 'critical'
                : result.score >= 0.75 ? 'high'
                : result.score >= 0.5 ? 'medium' : 'low';
              const riskColors = {
                critical: 'bg-red-100 text-red-700',
                high: 'bg-amber-100 text-amber-700',
                medium: 'bg-yellow-100 text-yellow-700',
                low: 'bg-green-100 text-green-700',
              };
              const features = result.features || {};
              const featureEntries = Object.entries(features).sort((a, b) => b[1] - a[1]).slice(0, 5);
              const isExpanded = expanded[idx];

              return (
                <div key={idx} className="border-t border-slate-100 p-5 hover:bg-slate-50/50 transition-colors">
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-semibold text-slate-900 text-sm">
                      {result.file_a} <span className="text-slate-400 font-normal mx-1">vs</span> {result.file_b}
                    </span>
                    <span className={`px-2.5 py-1 rounded-full text-xs font-bold ${riskColors[risk]}`}>
                      {risk.toUpperCase()} -- {(result.score * 100).toFixed(1)}%
                    </span>
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-3">
                    {featureEntries.map(([name, value]) => {
                      const barColor = value >= 0.75 ? 'bg-red-500' : value >= 0.5 ? 'bg-amber-500' : 'bg-green-500';
                      return (
                        <div key={name}>
                          <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">{name}</div>
                          <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden mb-1">
                            <div className={`h-full rounded-full ${barColor}`} style={{ width: `${value * 100}%` }} />
                          </div>
                          <div className="text-xs font-bold text-slate-700">{(value * 100).toFixed(1)}%</div>
                        </div>
                      );
                    })}
                  </div>

                  <button
                    onClick={() => toggleCode(idx)}
                    className="text-sm text-brand-600 hover:text-brand-700 font-medium flex items-center gap-1"
                  >
                    <Code2 size={14} />
                    {isExpanded ? 'Hide source comparison' : 'View source comparison'}
                    {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                  </button>

                  {isExpanded && job.submissions && (
                    <div className="mt-3 grid md:grid-cols-2 gap-3">
                      <div className="border border-slate-200 rounded-lg overflow-hidden">
                        <div className="px-3 py-1.5 bg-slate-50 text-xs font-semibold text-slate-600 border-b border-slate-200">{result.file_a}</div>
                        <pre className="p-3 text-xs font-mono bg-slate-900 text-slate-200 overflow-x-auto max-h-64">{job.submissions[result.file_a]?.slice(0, 2000)}{job.submissions[result.file_a]?.length > 2000 ? '\n... [truncated]' : ''}</pre>
                      </div>
                      <div className="border border-slate-200 rounded-lg overflow-hidden">
                        <div className="px-3 py-1.5 bg-slate-50 text-xs font-semibold text-slate-600 border-b border-slate-200">{result.file_b}</div>
                        <pre className="p-3 text-xs font-mono bg-slate-900 text-slate-200 overflow-x-auto max-h-64">{job.submissions[result.file_b]?.slice(0, 2000)}{job.submissions[result.file_b]?.length > 2000 ? '\n... [truncated]' : ''}</pre>
                      </div>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}

function StatCard({ label, value, color = 'brand' }) {
  const colors = {
    brand: 'text-slate-900',
    red: 'text-red-600',
  };
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <div className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">{label}</div>
      <div className={`text-2xl font-bold ${colors[color]}`}>{value}</div>
    </div>
  );
}

function RiskCard({ count, label, color }) {
  const borderColors = { red: 'border-t-red-500', amber: 'border-t-amber-500', yellow: 'border-t-yellow-500', green: 'border-t-green-500' };
  const textColors = { red: 'text-red-600', amber: 'text-amber-600', yellow: 'text-yellow-600', green: 'text-green-600' };
  return (
    <div className={`bg-white rounded-lg border border-slate-200 border-t-4 ${borderColors[color]} p-4`}>
      <div className={`text-xl font-bold ${textColors[color]}`}>{count}</div>
      <div className="text-xs text-slate-500 mt-0.5">{label}</div>
    </div>
  );
}
