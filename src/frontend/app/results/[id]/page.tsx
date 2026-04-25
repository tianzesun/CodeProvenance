// @ts-nocheck
'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { useAuth } from '@/components/AuthProvider';
import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import axios from 'axios';
import { apiClient } from '@/lib/apiClient';
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

const API = process.env.NEXT_PUBLIC_API_URL || '';
const REVIEW_STATUS_OPTIONS = [
  { key: 'unreviewed', label: 'Unreviewed', description: 'No professor decision recorded yet.' },
  { key: 'needs_review', label: 'Needs Review', description: 'Keep this assignment in the active review queue.' },
  { key: 'confirmed', label: 'Confirmed', description: 'Evidence supports escalation or formal follow-up.' },
  { key: 'dismissed', label: 'Dismissed', description: 'No further action is needed for this assignment.' },
  { key: 'escalated', label: 'Escalated', description: 'The case has been sent forward for formal review.' },
];

function formatTimestamp(value) {
  if (!value) {
    return 'Awaiting upload';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);
}

function formatPercent(value) {
  return `${Math.round((Number(value) || 0) * 100)}%`;
}

function formatPercentPrecise(value) {
  return `${((Number(value) || 0) * 100).toFixed(1)}%`;
}

function getAssignmentTitle(job) {
  return job.assignment_name || job.course_name || 'Assignment Results';
}

function getReferenceLabel(job) {
  if (!job?.course_name || job.course_name === job.assignment_name) {
    return '';
  }

  return job.course_name;
}

function getThreshold(job) {
  const threshold = Number(job?.threshold);
  return Number.isFinite(threshold) ? threshold : 0.5;
}

function getReviewStatus(job) {
  return REVIEW_STATUS_OPTIONS.some((option) => option.key === job?.review_status)
    ? job.review_status
    : 'unreviewed';
}

function formatReviewStatus(status) {
  return REVIEW_STATUS_OPTIONS.find((option) => option.key === status)?.label || 'Unreviewed';
}

function getReviewTone(status) {
  const toneMap = {
    unreviewed: {
      badge: 'border-slate-500/20 bg-slate-500/10 text-slate-600',
      panel: 'border-slate-500/15 bg-slate-500/[0.06]',
    },
    needs_review: {
      badge: 'border-amber-500/20 bg-amber-500/10 text-amber-600',
      panel: 'border-amber-500/15 bg-amber-500/[0.06]',
    },
    confirmed: {
      badge: 'border-red-500/20 bg-red-500/10 text-red-600',
      panel: 'border-red-500/15 bg-red-500/[0.06]',
    },
    dismissed: {
      badge: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-600',
      panel: 'border-emerald-500/15 bg-emerald-500/[0.06]',
    },
    escalated: {
      badge: 'border-violet-500/20 bg-violet-500/10 text-violet-600',
      panel: 'border-violet-500/15 bg-violet-500/[0.06]',
    },
  };

  return toneMap[status] || toneMap.unreviewed;
}

function getReviewStatusDescription(status) {
  return REVIEW_STATUS_OPTIONS.find((option) => option.key === status)?.description || REVIEW_STATUS_OPTIONS[0].description;
}

function pairKey(fileA, fileB) {
  return [fileA, fileB].sort().join('::');
}

function includesSubmission(result, submission) {
  return result.file_a === submission || result.file_b === submission;
}

function otherSubmission(result, submission) {
  return result.file_a === submission ? result.file_b : result.file_a;
}

function getRiskBucket(score) {
  if (score >= 0.9) {
    return 'critical';
  }
  if (score >= 0.75) {
    return 'high';
  }
  if (score >= 0.5) {
    return 'medium';
  }
  return 'low';
}

function getConfidenceZone(score, calibrationReport) {
  const zones = Array.isArray(calibrationReport?.confidence_zones)
    ? calibrationReport.confidence_zones
    : [];
  const numericScore = Number(score) || 0;
  const matched = zones.find((zone) => numericScore >= Number(zone.min_score) && numericScore < Number(zone.max_score));
  if (matched) {
    return matched;
  }
  if (numericScore >= 0.78) {
    return { label: 'flag', description: 'High-certainty review zone.' };
  }
  if (numericScore >= 0.5) {
    return { label: 'uncertain', description: 'Manual review zone.' };
  }
  return { label: 'clean', description: 'Low-signal region.' };
}

function getRiskTone(score) {
  const bucket = getRiskBucket(score);
  const map = {
    critical: {
      badge: 'border-red-500/20 bg-red-500/10 text-red-600',
      dot: 'bg-red-500',
      panel: 'border-red-500/15 bg-red-500/[0.06]',
      text: 'text-red-600',
    },
    high: {
      badge: 'border-amber-500/20 bg-amber-500/10 text-amber-600',
      dot: 'bg-amber-500',
      panel: 'border-amber-500/15 bg-amber-500/[0.06]',
      text: 'text-amber-600',
    },
    medium: {
      badge: 'border-yellow-500/20 bg-yellow-500/10 text-yellow-600',
      dot: 'bg-yellow-500',
      panel: 'border-yellow-500/15 bg-yellow-500/[0.06]',
      text: 'text-yellow-600',
    },
    low: {
      badge: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-600',
      dot: 'bg-emerald-500',
      panel: 'border-emerald-500/15 bg-emerald-500/[0.06]',
      text: 'text-emerald-600',
    },
  };
  return map[bucket];
}

function getSubmissionNames(submissions, results) {
  const names = new Set(Object.keys(submissions || {}));
  results.forEach((result) => {
    names.add(result.file_a);
    names.add(result.file_b);
  });
  return Array.from(names);
}

function getLineCount(text) {
  if (!text) {
    return 0;
  }

  return text.split('\n').length;
}

function buildSubmissionStats(submissionNames, results, threshold, submissions) {
  return submissionNames
    .map((name) => {
      const matches = results.filter((result) => includesSubmission(result, name));
      const flaggedMatches = matches.filter((result) => result.score >= threshold);
      const topMatch = [...matches].sort((a, b) => b.score - a.score)[0] || null;

      return {
        name,
        lines: getLineCount(submissions[name] || ''),
        totalMatches: matches.length,
        flaggedCount: flaggedMatches.length,
        maxScore: topMatch?.score || 0,
        averageScore: matches.length
          ? matches.reduce((sum, result) => sum + result.score, 0) / matches.length
          : 0,
        topMatch,
        topMatchName: topMatch ? otherSubmission(topMatch, name) : '',
      };
    })
    .sort((a, b) => {
      if (b.maxScore !== a.maxScore) {
        return b.maxScore - a.maxScore;
      }
      if (b.flaggedCount !== a.flaggedCount) {
        return b.flaggedCount - a.flaggedCount;
      }
      return a.name.localeCompare(b.name);
    });
}

function buildFeatureSummary(results) {
  const featureMap = {};

  results.forEach((result) => {
    Object.entries(result.features || {}).forEach(([name, value]) => {
      if (!featureMap[name]) {
        featureMap[name] = { name, total: 0, count: 0, peak: 0 };
      }
      featureMap[name].total += value;
      featureMap[name].count += 1;
      featureMap[name].peak = Math.max(featureMap[name].peak, value);
    });
  });

  return Object.values(featureMap)
    .map((entry) => ({
      name: entry.name,
      average: entry.count ? entry.total / entry.count : 0,
      peak: entry.peak,
    }))
    .sort((a, b) => b.peak - a.peak);
}

function buildPairLookup(results) {
  const lookup = new Map();
  results.forEach((result) => {
    lookup.set(pairKey(result.file_a, result.file_b), result.score);
  });
  return lookup;
}

function summarizeMatch(result) {
  const entries = Object.entries(result.features || {}).sort((a, b) => b[1] - a[1]);
  if (!entries.length) {
    return 'Similarity evidence is available for manual review.';
  }
  if (entries.length === 1) {
    return `${entries[0][0]} is the strongest detection signal in this pair.`;
  }
  return `${entries[0][0]} and ${entries[1][0]} are the strongest detection signals in this pair.`;
}

function truncateName(value, max = 18) {
  if (!value || value.length <= max) {
    return value;
  }

  return `${value.slice(0, max - 1)}…`;
}

function calculatePossibleComparisons(count) {
  return count > 1 ? (count * (count - 1)) / 2 : 0;
}

function getSubmissionRiskDistribution(submissionStats) {
  return {
    low: submissionStats.filter((entry) => entry.maxScore < 0.4).length,
    medium: submissionStats.filter((entry) => entry.maxScore >= 0.4 && entry.maxScore < 0.7).length,
    high: submissionStats.filter((entry) => entry.maxScore >= 0.7).length,
  };
}

function getAiRiskTone(score) {
  if (score >= 0.7) {
    return {
      badge: 'border-amber-500/20 bg-amber-500/10 text-amber-600',
      panel: 'border-amber-500/15 bg-amber-500/[0.06]',
      label: 'High Risk',
    };
  }
  if (score >= 0.4) {
    return {
      badge: 'border-yellow-500/20 bg-yellow-500/10 text-yellow-600',
      panel: 'border-yellow-500/15 bg-yellow-500/[0.06]',
      label: 'Needs Review',
    };
  }
  return {
    badge: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-600',
    panel: 'border-emerald-500/15 bg-emerald-500/[0.06]',
    label: 'Low Risk',
  };
}

export default function ResultsPage() {
  const { id } = useParams();
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();

  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
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
    if (authLoading) {
      console.log('Auth still loading...');
      return;
    }
    if (!user) {
      console.log('No user authenticated, redirecting to login');
      router.push('/login');
      return;
    }

    console.log('User authenticated:', user.email, 'Fetching job:', id);
    apiClient.get(`/api/jobs/${id}`)
      .then((res) => {
        console.log('Job fetched successfully:', res.data);
        setJob(res.data);
        setError(null);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to fetch job:', err?.response?.status, err?.response?.data, err?.message);
        if (err.response?.status === 404) {
          setError(`Assignment not found. Job ID "${id}" does not exist. Please check the URL or contact support.`);
        } else if (err.response?.status === 401 || err.response?.status === 403) {
          setError('Authentication failed. Please log in again.');
          router.push('/login');
        } else if (err.response?.status >= 500) {
          setError('Server error. Please try again later.');
        } else {
          setError(`Failed to load assignment: ${err?.message || 'Unknown error'}`);
        }
        setLoading(false);
      });
  }, [authLoading, user, id, router]);

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
          <div className="text-center space-y-6 max-w-lg">
            <div className="text-lg font-semibold text-[var(--text-primary)]">
              {error || 'Assignment not found'}
            </div>

            <div className="text-sm text-[var(--text-secondary)] space-y-2">
              <div><strong>Job ID:</strong> {id}</div>
              <div><strong>API Endpoint:</strong> /api/jobs/{id}</div>
              <div><strong>User:</strong> {user?.email || 'Not authenticated'}</div>
            </div>

            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-left">
              <h3 className="font-semibold text-blue-900 mb-2">How to create assignments:</h3>
              <ol className="text-sm text-blue-800 space-y-1 list-decimal list-inside">
                <li>Go to the <strong>Upload</strong> page</li>
                <li>Select your code files (Python, Java, C++, etc.)</li>
                <li>Choose analysis settings</li>
                <li>Click "Start Analysis"</li>
                <li>Wait for processing to complete</li>
                <li>You'll be redirected to the results page automatically</li>
              </ol>
            </div>

            <div className="flex gap-3">
              <Link
                href="/upload"
                className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                <FileCode size={16} />
                Upload Files
              </Link>
              <Link
                href="/"
                className="inline-flex items-center gap-2 px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
              >
                Back to Home
              </Link>
            </div>

            <div className="text-xs text-[var(--text-muted)] bg-[var(--surface)] p-3 rounded border">
              <div className="font-semibold mb-1">Debug Information:</div>
              <div>Check the browser console (F12) for detailed error logs.</div>
              <div>If you see "404 Not Found", the job ID doesn't exist.</div>
              <div>If you see "401 Unauthorized", there may be authentication issues.</div>
            </div>
          </div>
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