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
  CheckCircle2,
  AlertCircle,
  FileCode,
  Clock,
  Users,
  Target,
  Zap,
  Layers,
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

  if (loading) return (
    <DashboardLayout>
      <div className="p-8 flex flex-col items-center justify-center min-h-[60vh]">
        <div className="w-10 h-10 border-4 border-slate-200 border-t-blue-500 rounded-full animate-spin" />
        <p className="text-sm text-slate-500 mt-4">Loading results...</p>
      </div>
    </DashboardLayout>
  );
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
      <div className="p-4 lg:p-6 ">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-sm text-slate-500 mb-6 animate-fade-in">
          <Link href="/" className="hover:text-blue-600 transition-colors">Dashboard</Link>
          <span className="text-slate-300">/</span>
          <span className="text-slate-900 font-medium">{job.course_name}</span>
        </div>

        {/* Header */}
        <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4 mb-8 animate-fade-in">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
                <Shield size={18} className="text-white" />
              </div>
              <h1 className="text-3xl font-bold text-slate-900 tracking-tight">{job.course_name}</h1>
            </div>
            <p className="text-slate-500 mt-1">
              {job.assignment_name}
              <span className="mx-2 text-slate-300">|</span>
              Case ID: <span className="font-mono text-slate-700 bg-slate-100 px-2 py-0.5 rounded text-xs">{job.id}</span>
              <span className="mx-2 text-slate-300">|</span>
              {job.created_at?.slice(0, 16).replace('T', ' ')}
            </p>
          </div>
          <div className="flex gap-2 flex-wrap">
            <a href={`${API}/report/${id}/download`} className="inline-flex items-center gap-2 px-4 py-2.5 bg-white border border-slate-200 rounded-xl text-sm font-medium text-slate-700 hover:border-blue-300 hover:text-blue-600 transition-all">
              <FileText size={16} /> HTML Report
            </a>
            <a href={`${API}/report/${id}/download-json`} className="inline-flex items-center gap-2 px-4 py-2.5 bg-white border border-slate-200 rounded-xl text-sm font-medium text-slate-700 hover:border-blue-300 hover:text-blue-600 transition-all">
              <Download size={16} /> JSON
            </a>
          </div>
        </div>

        {/* Alert banner with evidence */}
        {summary.suspicious_pairs > 0 && (
          <div className="space-y-4 mb-8 animate-fade-in">
            <div className="bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200 rounded-2xl p-5 flex items-center justify-between flex-wrap gap-4">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl bg-amber-100 flex items-center justify-center shrink-0">
                  <AlertTriangle size={20} className="text-amber-600" />
                </div>
                <div>
                  <p className="font-semibold text-amber-900">{summary.suspicious_pairs} flagged pair(s) detected above {(job.threshold * 100).toFixed(0)}% threshold</p>
                  <p className="text-sm text-amber-700 mt-0.5">
                    {critical.length} critical and {high.length} high-risk findings require review.
                  </p>
                </div>
              </div>
              <a href={`${API}/report/${id}/committee`} className="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-red-600 to-red-500 text-white rounded-xl text-sm font-semibold hover:from-red-700 hover:to-red-600 transition-all shadow-lg shadow-red-500/20 shrink-0">
                <Shield size={14} /> Generate Committee Report
              </a>
            </div>

            {/* Evidence Panel */}
            {results.filter((r) => r.score >= job.threshold).map((result, idx) => {
              const risk = result.score >= 0.9 ? 'critical' : result.score >= 0.75 ? 'high' : 'medium';
              const features = result.features || {};
              const featureEntries = Object.entries(features).sort((a, b) => b[1] - a[1]).slice(0, 5);
              const codeA = job.submissions?.[result.file_a] || '';
              const codeB = job.submissions?.[result.file_b] || '';

              // Find matching lines (simple approach: show first 10 lines of each)
              const linesA = codeA.split('\n').slice(0, 12);
              const linesB = codeB.split('\n').slice(0, 12);

              return (
                <div key={idx} className="bg-white rounded-2xl border border-amber-200 shadow-sm overflow-hidden">
                  <div className="px-5 py-4 border-b border-amber-100 bg-amber-50/50">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className={`w-3 h-3 rounded-full ${risk === 'critical' ? 'bg-red-500' : risk === 'high' ? 'bg-amber-500' : 'bg-yellow-500'}`} />
                        <h3 className="font-semibold text-slate-900">Evidence: {result.file_a} vs {result.file_b}</h3>
                      </div>
                      <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold ${
                        risk === 'critical' ? 'bg-red-100 text-red-700' : risk === 'high' ? 'bg-amber-100 text-amber-700' : 'bg-yellow-100 text-yellow-700'
                      }`}>
                        {risk.toUpperCase()} {(result.score * 100).toFixed(1)}%
                      </span>
                    </div>
                  </div>

                  <div className="p-5">
                    {/* Engine Breakdown */}
                    <div className="mb-5">
                      <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Detection Engine Results</h4>
                      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
                        {featureEntries.map(([name, value]) => {
                          const barColor = value >= 0.75 ? 'bg-red-500' : value >= 0.5 ? 'bg-amber-500' : 'bg-emerald-500';
                          return (
                            <div key={name} className="bg-slate-50 rounded-lg p-3">
                              <div className="flex items-center justify-between mb-1.5">
                                <span className="text-[10px] font-semibold text-slate-500 uppercase">{name}</span>
                                <span className="text-xs font-bold text-slate-700">{(value * 100).toFixed(0)}%</span>
                              </div>
                              <div className="h-1.5 bg-slate-200 rounded-full overflow-hidden">
                                <div className={`h-full rounded-full ${barColor}`} style={{ width: `${value * 100}%` }} />
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    {/* Code Evidence */}
                    <div>
                      <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Matching Code Evidence</h4>
                      <div className="grid md:grid-cols-2 gap-3">
                        <div className="border border-slate-200 rounded-xl overflow-hidden">
                          <div className="px-3 py-2 bg-blue-50 border-b border-blue-100 flex items-center gap-2">
                            <div className="w-2 h-2 rounded-full bg-blue-500" />
                            <span className="text-xs font-semibold text-blue-700">{result.file_a}</span>
                          </div>
                          <pre className="p-3 text-xs font-mono bg-slate-900 text-slate-300 overflow-x-auto max-h-48 leading-relaxed">
                            {linesA.join('\n')}
                            {codeA.split('\n').length > 12 && '\n\n// ... [truncated]'}
                          </pre>
                        </div>
                        <div className="border border-slate-200 rounded-xl overflow-hidden">
                          <div className="px-3 py-2 bg-emerald-50 border-b border-emerald-100 flex items-center gap-2">
                            <div className="w-2 h-2 rounded-full bg-emerald-500" />
                            <span className="text-xs font-semibold text-emerald-700">{result.file_b}</span>
                          </div>
                          <pre className="p-3 text-xs font-mono bg-slate-900 text-slate-300 overflow-x-auto max-h-48 leading-relaxed">
                            {linesB.join('\n')}
                            {codeB.split('\n').length > 12 && '\n\n// ... [truncated]'}
                          </pre>
                        </div>
                      </div>
                    </div>

                    {/* Analysis Summary */}
                    <div className="mt-4 p-3 bg-blue-50 border border-blue-100 rounded-lg">
                      <div className="flex items-start gap-2">
                        <Zap size={14} className="text-blue-600 mt-0.5 shrink-0" />
                        <div>
                          <p className="text-sm font-semibold text-blue-900">Analysis Summary</p>
                          <p className="text-xs text-blue-700 mt-1">
                            {result.score >= 0.99
                              ? `Near-perfect match across ${featureEntries.length} forensic engines. The submissions are functionally identical, strongly suggesting a direct file copy.`
                              : result.score >= 0.9
                              ? `High similarity detected across ${featureEntries.length} independent engines. The strongest matches are in ${featureEntries.slice(0, 2).map(e => e[0]).join(' and ')}, indicating substantial code sharing.`
                              : `Significant structural similarities detected. ${featureEntries.length} engines flagged overlapping patterns in ${featureEntries.slice(0, 2).map(e => e[0]).join(' and ')}. Manual review recommended.`
                            }
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8 animate-fade-in">
          <StatCard label="Submissions" value={job.file_count} icon={Users} color="blue" />
          <StatCard label="Pairs Compared" value={summary.total_pairs || 0} icon={Target} color="slate" />
          <StatCard label="Flagged Pairs" value={summary.suspicious_pairs || 0} icon={AlertTriangle} color="amber" />
          <StatCard label="Critical Risk" value={critical.length} icon={Shield} color="red" />
        </div>

        {/* Risk distribution */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-8 animate-fade-in">
          <RiskCard count={critical.length} label="Critical" range="90%+" color="red" />
          <RiskCard count={high.length} label="High" range="75-89%" color="amber" />
          <RiskCard count={medium.length} label="Medium" range="50-74%" color="yellow" />
          <RiskCard count={low.length} label="Low" range="<50%" color="green" />
        </div>

        {/* Results */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden animate-fade-in">
          <div className="px-6 py-5 border-b border-slate-100 flex items-center justify-between flex-wrap gap-3">
            <div>
              <h2 className="font-semibold text-slate-900">Pairwise Similarity Results</h2>
              <p className="text-sm text-slate-500 mt-0.5">{results.length} pairs analyzed</p>
            </div>
            <div className="flex gap-1 bg-slate-100 rounded-lg p-1">
              {[
                { key: 'all', label: 'All' },
                { key: 'flagged', label: 'Flagged' },
                { key: 'critical', label: 'Critical' },
                { key: 'high', label: 'High' },
              ].map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setFilter(tab.key)}
                  className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
                    filter === tab.key
                      ? 'bg-white text-slate-900 shadow-sm'
                      : 'text-slate-500 hover:text-slate-700'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20">
              <div className="w-16 h-16 rounded-2xl bg-slate-50 flex items-center justify-center mb-4">
                <CheckCircle2 size={28} className="text-emerald-500" />
              </div>
              <h3 className="font-semibold text-slate-900 mb-1">No matching results</h3>
              <p className="text-sm text-slate-500">No pairs match the selected filter.</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-50">
              {filtered.map((result, idx) => {
                const risk = result.score >= 0.9 ? 'critical'
                  : result.score >= 0.75 ? 'high'
                  : result.score >= 0.5 ? 'medium' : 'low';
                const riskConfig = {
                  critical: { bg: 'bg-red-50', text: 'text-red-700', dot: 'bg-red-500' },
                  high: { bg: 'bg-amber-50', text: 'text-amber-700', dot: 'bg-amber-500' },
                  medium: { bg: 'bg-yellow-50', text: 'text-yellow-700', dot: 'bg-yellow-500' },
                  low: { bg: 'bg-emerald-50', text: 'text-emerald-700', dot: 'bg-emerald-500' },
                };
                const rc = riskConfig[risk];
                const features = result.features || {};
                const featureEntries = Object.entries(features).sort((a, b) => b[1] - a[1]).slice(0, 5);
                const isExpanded = expanded[idx];

                return (
                  <div key={idx} className="p-6 hover:bg-slate-50/50 transition-colors animate-fade-in" style={{ animationDelay: `${idx * 50}ms` }}>
                    <div className="flex items-start justify-between gap-4 mb-4">
                      <div className="flex items-center gap-3 min-w-0 flex-1">
                        <div className={`w-2 h-8 rounded-full ${rc.dot}`} />
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                            <FileCode size={14} className="text-slate-400 shrink-0" />
                            <span className="truncate">{result.file_a}</span>
                            <span className="text-slate-300 font-normal shrink-0">vs</span>
                            <span className="truncate">{result.file_b}</span>
                          </div>
                        </div>
                      </div>
                      <div className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold ${rc.bg} ${rc.text} shrink-0`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${rc.dot}`} />
                        {risk.toUpperCase()} {(result.score * 100).toFixed(1)}%
                      </div>
                    </div>

                    {featureEntries.length > 0 && (
                      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-4 mb-4">
                        {featureEntries.map(([name, value]) => {
                          const barColor = value >= 0.75 ? 'bg-red-500' : value >= 0.5 ? 'bg-amber-500' : 'bg-emerald-500';
                          return (
                            <div key={name}>
                              <div className="flex items-center justify-between mb-1">
                                <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">{name}</span>
                                <span className="text-xs font-bold text-slate-700">{(value * 100).toFixed(0)}%</span>
                              </div>
                              <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                                <div className={`h-full rounded-full ${barColor} transition-all duration-500`} style={{ width: `${value * 100}%` }} />
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}

                    <button
                      onClick={() => toggleCode(idx)}
                      className="text-sm text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1.5"
                    >
                      <Code2 size={14} />
                      {isExpanded ? 'Hide source comparison' : 'View source comparison'}
                      {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </button>

                    {isExpanded && job.submissions && (
                      <div className="mt-4 grid md:grid-cols-2 gap-4">
                        <div className="border border-slate-200 rounded-xl overflow-hidden">
                          <div className="px-4 py-2 bg-slate-50 border-b border-slate-100 flex items-center gap-2">
                            <div className="w-2 h-2 rounded-full bg-blue-500" />
                            <span className="text-xs font-semibold text-slate-600">{result.file_a}</span>
                          </div>
                          <pre className="p-4 text-xs font-mono bg-slate-900 text-slate-300 overflow-x-auto max-h-72 leading-relaxed">{job.submissions[result.file_a]?.slice(0, 2000)}{job.submissions[result.file_a]?.length > 2000 ? '\n\n// ... [truncated]' : ''}</pre>
                        </div>
                        <div className="border border-slate-200 rounded-xl overflow-hidden">
                          <div className="px-4 py-2 bg-slate-50 border-b border-slate-100 flex items-center gap-2">
                            <div className="w-2 h-2 rounded-full bg-emerald-500" />
                            <span className="text-xs font-semibold text-slate-600">{result.file_b}</span>
                          </div>
                          <pre className="p-4 text-xs font-mono bg-slate-900 text-slate-300 overflow-x-auto max-h-72 leading-relaxed">{job.submissions[result.file_b]?.slice(0, 2000)}{job.submissions[result.file_b]?.length > 2000 ? '\n\n// ... [truncated]' : ''}</pre>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}

function StatCard({ label, value, icon: Icon, color }) {
  const colorMap = {
    blue: { bg: 'bg-blue-50', text: 'text-blue-600', icon: 'text-blue-600' },
    slate: { bg: 'bg-slate-50', text: 'text-slate-600', icon: 'text-slate-600' },
    amber: { bg: 'bg-amber-50', text: 'text-amber-600', icon: 'text-amber-600' },
    red: { bg: 'bg-red-50', text: 'text-red-600', icon: 'text-red-600' },
  };
  const c = colorMap[color] || colorMap.blue;
  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-5 hover:shadow-md transition-all duration-200 group">
      <div className="flex items-center justify-between mb-3">
        <div className={`w-10 h-10 rounded-xl ${c.bg} flex items-center justify-center group-hover:scale-110 transition-transform duration-200`}>
          <Icon size={18} className={c.icon} />
        </div>
      </div>
      <div className="text-2xl font-bold text-slate-900 tracking-tight">{value}</div>
      <div className="text-xs font-medium text-slate-400 mt-1 uppercase tracking-wider">{label}</div>
    </div>
  );
}

function RiskCard({ count, label, range, color }) {
  const config = {
    red: { border: 'border-t-red-500', text: 'text-red-600', bg: 'bg-red-50' },
    amber: { border: 'border-t-amber-500', text: 'text-amber-600', bg: 'bg-amber-50' },
    yellow: { border: 'border-t-yellow-500', text: 'text-yellow-600', bg: 'bg-yellow-50' },
    green: { border: 'border-t-emerald-500', text: 'text-emerald-600', bg: 'bg-emerald-50' },
  };
  const c = config[color];
  return (
    <div className={`bg-white rounded-xl border border-slate-200 border-t-4 ${c.border} p-4 hover:shadow-md transition-shadow`}>
      <div className={`text-xl font-bold ${c.text}`}>{count}</div>
      <div className="text-xs font-medium text-slate-500 mt-0.5">{label}</div>
      <div className="text-[10px] text-slate-400">{range}</div>
    </div>
  );
}
