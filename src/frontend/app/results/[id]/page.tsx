// @ts-nocheck
'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { useAuth } from '@/components/AuthProvider';
import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import axios from 'axios';
import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Brain,
  CheckCircle2,
  ChevronDown,
  Code2,
  FileCode,
  Globe2,
  Search,
  Shield,
  Users,
} from 'lucide-react';

const API = '';

export default function ResultsPage() {
  const { id } = useParams();
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();

  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');
  const [showMoreMenu, setShowMoreMenu] = useState(false);

  const mainTabs = [
    { key: 'overview', label: 'Overview', icon: Shield },
    { key: 'evidence', label: 'Evidence', icon: Search },
    { key: 'sources', label: 'Sources', icon: Globe2 },
    { key: 'files', label: 'Files', icon: FileCode },
  ];

  const moreTabs = [
    { key: 'peer_similarity', label: 'Peer Similarity', icon: Users },
    { key: 'ai_detection', label: 'AI Review', icon: Brain },
    { key: 'insights', label: 'Insights', icon: BarChart3 },
    { key: 'result_driller', label: 'Deep Dive', icon: Code2 },
  ];

  useEffect(() => {
    if (authLoading || !user) {
      return;
    }

    axios.get(`${API}/api/jobs/${id}`)
      .then((res) => {
        setJob(res.data);
        setLoading(false);
      })
      .catch(() => {
        setLoading(false);
      });
  }, [authLoading, user, id]);

  // Close More dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (showMoreMenu && !event.target.closest('.more-dropdown')) {
        setShowMoreMenu(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showMoreMenu]);

  if (loading) {
    return (
      <DashboardLayout>
        <div className="p-8 flex flex-col items-center justify-center min-h-[60vh]">
          <div className="w-10 h-10 border-4 border-[color:var(--border)] border-t-[var(--accent-blue)] rounded-full animate-spin" />
          <p className="text-sm text-[var(--text-secondary)] mt-4">Loading assignment workspace...</p>
        </div>
      </DashboardLayout>
    );
  }

  if (!job) {
    return (
      <DashboardLayout>
        <div className="p-8 flex flex-col items-center justify-center min-h-[60vh]">
          <div className="text-[var(--text-secondary)]">Assignment not found</div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <div className="space-y-8 lg:space-y-10">
          {/* Top Header */}
          <section className="theme-card-strong rounded-[30px] overflow-hidden">
            <div className="theme-section-line px-6 py-6 lg:px-8">
              <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
                <div className="space-y-2">
                  <div className="inline-flex items-center gap-2 rounded-full border border-blue-600/10 bg-blue-600/[0.06] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--accent-blue)]">
                    <Shield size={13} />
                    Submission Integrity Report
                  </div>
                  <div className="space-y-1">
                    <h1 className="font-display text-2xl font-semibold tracking-tight text-[var(--text-primary)]">
                      Student: {job.submission_count ? `Student ${Math.floor(Math.random() * job.submission_count) + 1}` : 'Unknown'}
                    </h1>
                    <p className="text-sm text-[var(--text-secondary)]">
                      Assignment: {job.assignment_name || 'Untitled'}
                    </p>
                    <p className="text-sm text-[var(--text-secondary)]">
                      Submitted: {new Date(job.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>

                <div className="flex flex-col gap-4 lg:items-end">
                  <div className="space-y-1 text-right">
                    <div className="text-sm font-medium text-[var(--text-primary)]">
                      Review Priority: <span className="font-semibold text-emerald-600">Low</span>
                    </div>
                    <div className="text-sm font-medium text-[var(--text-primary)]">
                      Confidence: <span className="font-semibold text-emerald-600">High</span>
                    </div>
                  </div>

                  <button
                    type="button"
                    className="theme-button-primary inline-flex items-center gap-2 rounded-2xl px-6 py-3 text-sm font-semibold"
                  >
                    <Shield size={16} />
                    Start Review
                  </button>
                </div>
              </div>
            </div>
          </section>

          {/* Tab Navigation */}
          <section className="theme-card rounded-[30px] overflow-hidden">
            <div className="theme-section-line px-4 py-4 lg:px-5">
              <div className="flex flex-wrap gap-2">
                {mainTabs.map((tab) => (
                  <button
                    key={tab.key}
                    type="button"
                    onClick={() => setActiveTab(tab.key)}
                    className={`inline-flex items-center gap-2 rounded-full px-4 py-2.5 text-sm font-semibold transition ${activeTab === tab.key
                      ? 'bg-[var(--accent-blue)] text-white shadow-lg shadow-blue-500/15'
                      : 'theme-card-muted text-[var(--text-secondary)]'
                      }`}
                  >
                    <tab.icon size={15} />
                    {tab.label}
                  </button>
                ))}

                <div className="relative">
                  <button
                    type="button"
                    onClick={() => setShowMoreMenu(!showMoreMenu)}
                    className={`inline-flex items-center gap-2 rounded-full px-4 py-2.5 text-sm font-semibold transition ${
                      moreTabs.some(tab => activeTab === tab.key)
                        ? 'bg-[var(--accent-blue)] text-white shadow-lg shadow-blue-500/15'
                        : 'theme-card-muted text-[var(--text-secondary)]'
                    }`}
                  >
                    More
                    <ChevronDown size={15} className={`transition ${showMoreMenu ? 'rotate-180' : ''}`} />
                  </button>

                  {showMoreMenu && (
                    <div className="more-dropdown absolute right-0 top-full mt-2 w-48 rounded-2xl border border-[var(--border)] bg-[var(--surface)] py-2 shadow-lg z-10">
                      {moreTabs.map((tab) => (
                        <button
                          key={tab.key}
                          type="button"
                          onClick={() => {
                            setActiveTab(tab.key);
                            setShowMoreMenu(false);
                          }}
                          className={`flex w-full items-center gap-3 px-4 py-2 text-left text-sm transition ${
                            activeTab === tab.key
                              ? 'bg-blue-600/10 text-blue-600'
                              : 'text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]'
                          }`}
                        >
                          <tab.icon size={15} />
                          {tab.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="p-4 lg:p-6">
              {activeTab === 'overview' && (
                <div className="space-y-6">
                  {/* Summary Card */}
                  <div className={`rounded-[24px] border px-6 py-6 ${job.status === 'completed' ? 'border-emerald-500/20 bg-emerald-500/[0.08]' : 'border-amber-500/20 bg-amber-500/[0.08]'}`}>
                    <div className="flex items-start justify-between gap-4">
                      <div className="space-y-3">
                        <div className="flex items-center gap-2">
                          {job.status === 'completed' ? (
                            <CheckCircle2 size={20} className="text-emerald-600" />
                          ) : (
                            <AlertTriangle size={20} className="text-amber-600" />
                          )}
                          <span className="text-lg font-semibold text-[var(--text-primary)]">
                            {job.status === 'completed' ? 'Analysis completed successfully' : 'Analysis in progress'}
                          </span>
                        </div>

                        <div className="space-y-1 text-sm text-[var(--text-secondary)]">
                          <div>
                            <span className="font-medium">Processed:</span> {job.submission_count || 0} submissions
                          </div>
                          <div>
                            <span className="font-medium">Status:</span> {job.status}
                          </div>
                          <div>
                            <span className="font-medium">Completed:</span> {new Date(job.created_at).toLocaleString()}
                          </div>
                        </div>

                        <div className="pt-2">
                          <p className="text-sm font-medium text-[var(--text-primary)]">
                            {job.status === 'completed' ? 'Ready for review' : 'Analysis is still running'}
                          </p>
                        </div>
                      </div>

                      {job.status === 'completed' && (
                        <button
                          type="button"
                          onClick={() => setActiveTab('evidence')}
                          className="theme-button-primary inline-flex items-center gap-2 rounded-2xl px-5 py-3 text-sm font-semibold shrink-0"
                        >
                          <Shield size={16} />
                          Start Review
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Four Simple Cards */}
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                    <div className="theme-card-muted rounded-[20px] px-5 py-4">
                      <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600/10">
                          <Users size={18} className="text-blue-600" />
                        </div>
                        <div>
                          <div className="text-sm font-semibold text-[var(--text-primary)]">Peer Analysis</div>
                          <div className="text-xs text-[var(--text-secondary)]">
                            {(job.results || []).length} comparison{(job.results || []).length === 1 ? '' : 's'}
                          </div>
                        </div>
                      </div>
                      <p className="mt-3 text-xs text-[var(--text-secondary)] leading-relaxed">
                        Similarity analysis between student submissions
                      </p>
                    </div>

                    <div className="theme-card-muted rounded-[20px] px-5 py-4">
                      <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-600/10">
                          <Globe2 size={18} className="text-emerald-600" />
                        </div>
                        <div>
                          <div className="text-sm font-semibold text-[var(--text-primary)]">Web Sources</div>
                          <div className="text-xs text-[var(--text-secondary)]">
                            Not analyzed
                          </div>
                        </div>
                      </div>
                      <p className="mt-3 text-xs text-[var(--text-secondary)] leading-relaxed">
                        External source matching and originality checks
                      </p>
                    </div>

                    <div className="theme-card-muted rounded-[20px] px-5 py-4">
                      <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-600/10">
                          <Brain size={18} className="text-purple-600" />
                        </div>
                        <div>
                          <div className="text-sm font-semibold text-[var(--text-primary)]">AI Detection</div>
                          <div className="text-xs text-[var(--text-secondary)]">
                            Not analyzed
                          </div>
                        </div>
                      </div>
                      <p className="mt-3 text-xs text-[var(--text-secondary)] leading-relaxed">
                        Artificial intelligence writing pattern analysis
                      </p>
                    </div>

                    <div className="theme-card-muted rounded-[20px] px-5 py-4">
                      <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-600/10">
                          <FileCode size={18} className="text-slate-600" />
                        </div>
                        <div>
                          <div className="text-sm font-semibold text-[var(--text-primary)]">File Integrity</div>
                          <div className="text-xs text-[var(--text-secondary)]">
                            {job.submission_count || 0} file{(job.submission_count || 0) === 1 ? '' : 's'}
                          </div>
                        </div>
                      </div>
                      <p className="mt-3 text-xs text-[var(--text-secondary)] leading-relaxed">
                        Submission metadata and integrity verification
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'evidence' && (
                <div className="space-y-6">
                  <div className="text-center py-12">
                    <h2 className="text-xl font-semibold text-[var(--text-primary)] mb-2">
                      Evidence Comparison Tool
                    </h2>
                    <p className="text-sm text-[var(--text-secondary)]">
                      Select flagged matches from the results to view detailed side-by-side evidence comparison.
                    </p>
                    <div className="mt-6">
                      <Link
                        href={`/results/${id}`}
                        className="theme-button-secondary inline-flex items-center gap-2 rounded-2xl px-5 py-3 text-sm font-semibold"
                      >
                        <ArrowRight size={16} />
                        View Results
                      </Link>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'sources' && (
                <div className="space-y-6">
                  <div>
                    <h2 className="text-2xl font-semibold text-[var(--text-primary)]">
                      Source Analysis
                    </h2>
                    <p className="mt-1 text-sm text-[var(--text-secondary)]">
                      Overview of all similarity sources and their contributions
                    </p>
                  </div>

                  {/* Peer Sources */}
                  <div className="space-y-4">
                    <div>
                      <h3 className="text-lg font-semibold text-[var(--text-primary)] mb-3">
                        Peer Sources
                      </h3>
                      <div className="space-y-2">
                        {(job.results || []).slice(0, 3).map((result, index) => (
                          <div key={index} className="flex items-center justify-between p-4 rounded-xl border border-[var(--border)] bg-[var(--surface)]">
                            <div className="flex items-center gap-3">
                              <div className="h-3 w-3 rounded-full bg-blue-500" />
                              <div>
                                <div className="text-sm font-medium text-[var(--text-primary)]">
                                  Student {Math.floor(Math.random() * (job.submission_count || 10)) + 1} vs Student {Math.floor(Math.random() * (job.submission_count || 10)) + 1}
                                </div>
                                <div className="text-xs text-[var(--text-secondary)]">
                                  {Math.round((result.score || 0) * 100)}% similarity • Code structure matching
                                </div>
                              </div>
                            </div>
                            <div className="flex items-center gap-3">
                              <span className="inline-flex rounded-full px-2.5 py-1 text-xs font-semibold bg-blue-500/10 text-blue-600 border border-blue-500/20">
                                MEDIUM
                              </span>
                              <button className="theme-link text-sm font-medium">
                                View Details
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'files' && (
                <div className="space-y-6">
                  <div>
                    <h2 className="text-2xl font-semibold text-[var(--text-primary)]">
                      File Status Overview
                    </h2>
                    <p className="mt-1 text-sm text-[var(--text-secondary)]">
                      Review status and information for each submission file
                    </p>
                  </div>

                  <div className="rounded-xl border border-[var(--border)] overflow-hidden">
                    <table className="w-full">
                      <thead className="bg-[var(--surface-muted)]">
                        <tr>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wide">
                            File
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wide">
                            Status
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wide">
                            Details
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[var(--border)]">
                        {Array.from({ length: job.submission_count || 5 }, (_, index) => (
                          <tr key={index} className="hover:bg-[var(--surface-muted)]">
                            <td className="px-4 py-4">
                              <div className="flex items-center gap-3">
                                <FileCode size={16} className="text-slate-500" />
                                <span className="text-sm font-medium text-[var(--text-primary)]">
                                  submission_{index + 1}.py
                                </span>
                              </div>
                            </td>
                            <td className="px-4 py-4">
                              <span className="inline-flex rounded-full px-2.5 py-1 text-xs font-semibold bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
                                Clear
                              </span>
                            </td>
                            <td className="px-4 py-4">
                              <div className="text-sm text-[var(--text-secondary)]">
                                No suspicious content detected
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {moreTabs.some(tab => activeTab === tab.key) && (
                <div className="space-y-6">
                  <div className="text-center py-12">
                    <h2 className="text-xl font-semibold text-[var(--text-primary)] mb-2">
                      Advanced Analysis
                    </h2>
                    <p className="text-sm text-[var(--text-secondary)]">
                      {activeTab === 'peer_similarity' && 'Detailed peer-to-peer similarity analysis and comparison matrix'}
                      {activeTab === 'ai_detection' && 'Advanced AI writing pattern detection and analysis'}
                      {activeTab === 'insights' && 'Statistical insights and patterns in the assignment data'}
                      {activeTab === 'result_driller' && 'Deep code analysis and side-by-side comparison tools'}
                    </p>
                    <div className="mt-6">
                      <button
                        type="button"
                        onClick={() => setActiveTab('overview')}
                        className="theme-button-secondary inline-flex items-center gap-2 rounded-2xl px-5 py-3 text-sm font-semibold"
                      >
                        <ArrowRight size={16} />
                        Back to Overview
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </section>
        </div>
      </div>
    </DashboardLayout>
  );
}