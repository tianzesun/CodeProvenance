'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import axios from 'axios';
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  BarChart3,
  Brain,
  CheckCircle2,
  ChevronRight,
  Code2,
  Download,
  FileCode,
  FileSearch,
  FileText,
  Globe2,
  Loader2,
  Search,
  Shield,
  Target,
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
  return job?.assignment_name || job?.course_name || 'Assignment Check';
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

export default function ResultsPage() {
  const { id } = useParams();
  const router = useRouter();

  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');
  const [matchFilter, setMatchFilter] = useState('all');
  const [drillerMode, setDrillerMode] = useState('flagged');
  const [insightSubmissionFilter, setInsightSubmissionFilter] = useState('all');
  const [selectedSubmission, setSelectedSubmission] = useState('');
  const [selectedMatchKey, setSelectedMatchKey] = useState('');
  const [expandedMatches, setExpandedMatches] = useState({});
  const [reviewStatus, setReviewStatus] = useState('unreviewed');
  const [reviewNotes, setReviewNotes] = useState('');
  const [reviewSaving, setReviewSaving] = useState(false);
  const [reviewError, setReviewError] = useState('');

  useEffect(() => {
    if (id) {
      fetchJob();
    }
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

  const results = [...(job?.results || [])].sort((a, b) => b.score - a.score);
  const submissions = job?.submissions || {};
  const summary = job?.summary || {};
  const threshold = getThreshold(job);
  const assignmentTitle = getAssignmentTitle(job);
  const referenceLabel = getReferenceLabel(job);
  const persistedReviewStatus = getReviewStatus(job);
  const flaggedResults = results.filter((result) => result.score >= threshold);
  const critical = results.filter((result) => result.score >= 0.9);
  const high = results.filter((result) => result.score >= 0.75 && result.score < 0.9);
  const medium = results.filter((result) => result.score >= 0.5 && result.score < 0.75);
  const low = results.filter((result) => result.score < 0.5);
  const submissionNames = getSubmissionNames(submissions, results);
  const submissionStats = buildSubmissionStats(submissionNames, results, threshold, submissions);
  const topSignals = buildFeatureSummary(results).slice(0, 5);
  const pairLookup = buildPairLookup(results);
  const cleanSubmissions = submissionStats.filter((entry) => entry.flaggedCount === 0).length;
  const flaggedSubmissions = submissionStats.filter((entry) => entry.maxScore >= threshold).length;
  const highestMatch = results[0] || null;
  const matrixSubmissions = submissionStats.slice(0, Math.min(submissionStats.length, 8));
  const totalLinesAnalyzed = submissionStats.reduce((sum, entry) => sum + entry.lines, 0);
  const possibleComparisons = calculatePossibleComparisons(submissionStats.length);
  const averageStrongestMatch = submissionStats.length
    ? submissionStats.reduce((sum, entry) => sum + entry.maxScore, 0) / submissionStats.length
    : 0;
  const averagePeerScore = results.length
    ? results.reduce((sum, result) => sum + result.score, 0) / results.length
    : 0;
  const overallReviewScore = highestMatch ? highestMatch.score : averageStrongestMatch;
  const maxSubmissionScore = submissionStats.length ? Math.max(...submissionStats.map((entry) => entry.maxScore)) : 0;
  const minSubmissionScore = submissionStats.length ? Math.min(...submissionStats.map((entry) => entry.maxScore)) : 0;
  const scoreSpread = maxSubmissionScore - minSubmissionScore;
  const riskDistribution = getSubmissionRiskDistribution(submissionStats);
  const reviewDirty = reviewStatus !== persistedReviewStatus || reviewNotes !== (job?.review_notes || '');
  const reviewTone = getReviewTone(reviewStatus);
  const visibleInsightSubmissions = insightSubmissionFilter === 'review'
    ? submissionStats.filter((entry) => entry.maxScore >= threshold)
    : insightSubmissionFilter === 'safe'
      ? submissionStats.filter((entry) => entry.maxScore < threshold)
      : submissionStats;

  useEffect(() => {
    if (!job) {
      return;
    }

    setReviewStatus(getReviewStatus(job));
    setReviewNotes(job.review_notes || '');
    setReviewError('');
  }, [job]);

  useEffect(() => {
    if (!submissionStats.length) {
      return;
    }

    if (!selectedSubmission || !submissionStats.some((entry) => entry.name === selectedSubmission)) {
      setSelectedSubmission(submissionStats[0].name);
    }
  }, [job, selectedSubmission]);

  const selectedSubmissionStats = submissionStats.find((entry) => entry.name === selectedSubmission) || null;
  const selectedSubmissionMatchesAll = selectedSubmission
    ? results.filter((result) => includesSubmission(result, selectedSubmission))
    : [];
  const selectedSubmissionMatches = drillerMode === 'flagged'
    ? selectedSubmissionMatchesAll.filter((result) => result.score >= threshold)
    : selectedSubmissionMatchesAll;
  const visibleDrillerMatches = selectedSubmissionMatches.length > 0
    ? selectedSubmissionMatches
    : selectedSubmissionMatchesAll;
  const selectedMatch = visibleDrillerMatches.find((result) => pairKey(result.file_a, result.file_b) === selectedMatchKey)
    || visibleDrillerMatches[0]
    || null;
  const selectedMatchIndex = selectedMatch
    ? visibleDrillerMatches.findIndex((result) => pairKey(result.file_a, result.file_b) === pairKey(selectedMatch.file_a, selectedMatch.file_b))
    : -1;

  useEffect(() => {
    if (!visibleDrillerMatches.length) {
      if (selectedMatchKey) {
        setSelectedMatchKey('');
      }
      return;
    }

    const hasSelected = visibleDrillerMatches.some((result) => pairKey(result.file_a, result.file_b) === selectedMatchKey);
    if (!hasSelected) {
      setSelectedMatchKey(pairKey(visibleDrillerMatches[0].file_a, visibleDrillerMatches[0].file_b));
    }
  }, [job, selectedSubmission, drillerMode, selectedMatchKey]);

  useEffect(() => {
    if (activeTab !== 'result_driller' || visibleDrillerMatches.length < 2) {
      return;
    }

    const handleKeyDown = (event) => {
      const targetTag = event.target?.tagName;
      if (targetTag === 'INPUT' || targetTag === 'TEXTAREA' || targetTag === 'SELECT') {
        return;
      }

      if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') {
        return;
      }

      event.preventDefault();
      const currentIndex = selectedMatchIndex >= 0 ? selectedMatchIndex : 0;
      const nextIndex = event.key === 'ArrowDown'
        ? (currentIndex + 1) % visibleDrillerMatches.length
        : (currentIndex - 1 + visibleDrillerMatches.length) % visibleDrillerMatches.length;
      const nextMatch = visibleDrillerMatches[nextIndex];
      setSelectedMatchKey(pairKey(nextMatch.file_a, nextMatch.file_b));
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [activeTab, selectedMatchIndex, selectedSubmission, drillerMode, job]);

  const filteredMatches = matchFilter === 'all'
    ? results
    : matchFilter === 'flagged'
      ? flaggedResults
      : matchFilter === 'critical'
        ? critical
        : matchFilter === 'high'
          ? high
          : results;

  const openDriller = (result, preferredSubmission = result.file_a) => {
    setSelectedSubmission(preferredSubmission);
    setSelectedMatchKey(pairKey(result.file_a, result.file_b));
    setActiveTab('result_driller');
  };

  const toggleExpanded = (key) => {
    setExpandedMatches((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const saveReview = async () => {
    setReviewSaving(true);
    setReviewError('');

    try {
      const res = await axios.patch(`${API}/api/job/${id}/review`, {
        review_status: reviewStatus,
        review_notes: reviewNotes,
      });
      setJob(res.data);
    } catch (error) {
      setReviewError(error?.response?.data?.detail || 'Could not save the professor review for this assignment.');
    } finally {
      setReviewSaving(false);
    }
  };

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
    return null;
  }

  const tabs = [
    { key: 'overview', label: 'Overview', icon: Shield, count: flaggedResults.length },
    { key: 'files', label: 'Files', icon: FileCode, count: submissionStats.length },
    { key: 'ai_detection', label: 'AI Detection', icon: Brain, count: 0 },
    { key: 'insights', label: 'Insights', icon: BarChart3, count: flaggedResults.length },
    { key: 'peer_similarity', label: 'Peer Similarity', icon: Users, count: summary.total_pairs || results.length },
    { key: 'web_analysis', label: 'Web Analysis', icon: Globe2, count: 0 },
    { key: 'matches', label: 'Matches', icon: Search, count: results.length },
    { key: 'result_driller', label: 'Result Driller', icon: Code2, count: visibleDrillerMatches.length },
  ];

  return (
    <DashboardLayout>
      <div className="px-4 py-4 lg:px-6 lg:py-6">
        <div className="space-y-6">
          <div className="flex items-center gap-2 text-sm text-[var(--text-muted)]">
            <Link href="/" className="theme-link inline-flex items-center gap-1">
              <ArrowLeft size={14} />
              Home
            </Link>
            <span>/</span>
            <span className="text-[var(--text-primary)] font-medium">{assignmentTitle}</span>
          </div>

          <section className="theme-card-strong rounded-[30px] overflow-hidden">
            <div className="theme-section-line px-6 py-5 lg:px-7">
              <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
                <div className="space-y-4">
                  <div className="inline-flex items-center gap-2 rounded-full border border-blue-600/10 bg-blue-600/[0.06] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--accent-blue)]">
                    <Shield size={13} />
                    Assignment workspace
                  </div>
                  <div>
                    <h1 className="font-display text-3xl font-semibold tracking-tight text-[var(--text-primary)] sm:text-4xl">
                      {assignmentTitle}
                    </h1>
                    <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
                      {referenceLabel ? `${referenceLabel} • ` : ''}
                      Case ID {job.id} • {formatTimestamp(job.created_at)}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <ReviewBadge status={persistedReviewStatus} />
                    {job.review_updated_at && (
                      <span className="text-xs text-[var(--text-muted)]">
                        Updated {formatTimestamp(job.review_updated_at)}
                      </span>
                    )}
                  </div>
                  <p className="max-w-3xl text-sm leading-7 text-[var(--text-secondary)]">
                    Review this assignment from multiple angles: file-level risk, peer similarity, pairwise evidence, and a code driller for side-by-side comparison.
                  </p>
                </div>

                <div className="flex flex-wrap gap-3">
                  <a
                    href={`${API}/report/${id}/download`}
                    className="theme-button-secondary inline-flex items-center gap-2 rounded-2xl px-4 py-3 text-sm font-semibold"
                  >
                    <FileText size={16} />
                    HTML Report
                  </a>
                  <a
                    href={`${API}/report/${id}/download-json`}
                    className="theme-button-secondary inline-flex items-center gap-2 rounded-2xl px-4 py-3 text-sm font-semibold"
                  >
                    <Download size={16} />
                    JSON
                  </a>
                  <a
                    href={`${API}/report/${id}/committee`}
                    className="theme-button-primary inline-flex items-center gap-2 rounded-2xl px-4 py-3 text-sm font-semibold"
                  >
                    <Shield size={16} />
                    Committee Report
                  </a>
                </div>
              </div>
            </div>

            <div className="grid gap-4 px-6 pb-6 pt-5 sm:grid-cols-2 xl:grid-cols-4 lg:px-7">
              <MetricCard label="Submissions" value={job.file_count || submissionStats.length} icon={Users} />
              <MetricCard label="Pairs Compared" value={summary.total_pairs || results.length} icon={Target} />
              <MetricCard label="Flagged Pairs" value={summary.suspicious_pairs || flaggedResults.length} icon={AlertTriangle} />
              <MetricCard
                label="Highest Match"
                value={highestMatch ? formatPercent(highestMatch.score) : '0%'}
                icon={Shield}
              />
            </div>
          </section>

          <section className="theme-card rounded-[30px] overflow-hidden">
            <div className="theme-section-line px-4 py-4 lg:px-5">
              <div className="flex flex-wrap gap-2">
                {tabs.map((tab) => (
                  <ResultTabButton
                    key={tab.key}
                    active={activeTab === tab.key}
                    label={tab.label}
                    count={tab.count}
                    icon={tab.icon}
                    onClick={() => setActiveTab(tab.key)}
                  />
                ))}
              </div>
            </div>

            <div className="p-4 lg:p-6">
              {activeTab === 'overview' && (
                <div className="space-y-6">
                  <div className="grid gap-6 xl:grid-cols-[1.02fr_0.98fr]">
                    <div className="theme-card-muted rounded-[24px] p-5">
                      <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                        Overview
                      </div>
                      <h2 className="mt-2 text-2xl font-semibold text-[var(--text-primary)]">
                        Assignment verdict and review status
                      </h2>

                      <div className={`mt-5 rounded-[24px] border px-5 py-5 ${flaggedResults.length > 0 ? 'border-amber-500/20 bg-amber-500/[0.08]' : 'border-emerald-500/20 bg-emerald-500/[0.08]'}`}>
                        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                          <div className="space-y-3">
                            <div className="flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
                              {flaggedResults.length > 0 ? (
                                <AlertTriangle size={16} className="text-amber-600" />
                              ) : (
                                <CheckCircle2 size={16} className="text-emerald-600" />
                              )}
                              {flaggedResults.length > 0
                                ? `${flaggedResults.length} pair${flaggedResults.length === 1 ? '' : 's'} require review`
                                : 'No pair crossed the current review threshold'}
                            </div>
                            <div className="text-4xl font-semibold tracking-tight text-[var(--text-primary)]">
                              {formatPercentPrecise(overallReviewScore)}
                            </div>
                            <p className="max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">
                              {highestMatch
                                ? `The strongest peer similarity is ${formatPercentPrecise(highestMatch.score)} between ${highestMatch.file_a} and ${highestMatch.file_b}.`
                                : 'No pairwise similarity result is available for this assignment yet.'}
                            </p>
                          </div>

                          <div className="flex flex-wrap gap-3">
                            {highestMatch && (
                              <button
                                type="button"
                                onClick={() => openDriller(highestMatch)}
                                className="theme-button-primary inline-flex items-center gap-2 rounded-2xl px-4 py-3 text-sm font-semibold"
                              >
                                <Code2 size={16} />
                                Open Top Match
                              </button>
                            )}
                            <button
                              type="button"
                              onClick={() => setActiveTab('insights')}
                              className="theme-button-secondary inline-flex items-center gap-2 rounded-2xl px-4 py-3 text-sm font-semibold"
                            >
                              <BarChart3 size={16} />
                              Open Insights
                            </button>
                          </div>
                        </div>
                      </div>

                      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                        <MiniStat label="Submissions" value={submissionStats.length} note="Files in this assignment" compact />
                        <MiniStat label="Stored Matches" value={results.length} note="Peer comparisons kept" compact />
                        <MiniStat label="Lines Analyzed" value={totalLinesAnalyzed.toLocaleString('en-US')} note="Across stored previews" compact />
                        <MiniStat label="Threshold" value={formatPercent(threshold)} note="Current review cutoff" compact />
                      </div>
                    </div>

                    <div className="theme-card-muted rounded-[24px] p-5">
                      <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                        Risk breakdown
                      </div>
                      <h2 className="mt-2 text-xl font-semibold text-[var(--text-primary)]">
                        Source-by-source coverage
                      </h2>
                      <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
                        Peer similarity is active for this assignment. AI and web panels are present so the dashboard can grow into a multi-source review workspace.
                      </p>

                      <div className="mt-5 grid gap-3 sm:grid-cols-3">
                        <OverviewBreakdownCard
                          label="Peer Similarity"
                          value={formatPercentPrecise(averageStrongestMatch)}
                          note={`${flaggedResults.length} flagged pair${flaggedResults.length === 1 ? '' : 's'}`}
                          tone="ready"
                        />
                        <OverviewBreakdownCard
                          label="AI Detection"
                          value="Not Run"
                          note="Backend engine not enabled"
                          tone="pending"
                        />
                        <OverviewBreakdownCard
                          label="Web Analysis"
                          value="Not Run"
                          note="Backend engine not enabled"
                          tone="pending"
                        />
                      </div>

                      <div className="mt-5 border-t border-[color:var(--border)] pt-5">
                        <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                          Quick actions
                        </div>
                        <div className="mt-3 grid gap-3 sm:grid-cols-2">
                          <button
                            type="button"
                            onClick={() => setActiveTab('files')}
                            className="theme-card block rounded-[22px] px-4 py-4 text-left transition hover:-translate-y-0.5"
                          >
                            <div className="text-sm font-semibold text-[var(--text-primary)]">Review submissions</div>
                            <div className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">
                              Open the file-level review list for this assignment.
                            </div>
                          </button>
                          <button
                            type="button"
                            onClick={() => setActiveTab('matches')}
                            className="theme-card block rounded-[22px] px-4 py-4 text-left transition hover:-translate-y-0.5"
                          >
                            <div className="text-sm font-semibold text-[var(--text-primary)]">Inspect all matches</div>
                            <div className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">
                              Filter and expand every stored peer similarity finding.
                            </div>
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
                    <div className={`rounded-[24px] border px-5 py-5 ${reviewTone.panel}`}>
                      <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                        Professor review
                      </div>
                      <h2 className="mt-2 text-xl font-semibold text-[var(--text-primary)]">
                        Set the case status for this assignment
                      </h2>
                      <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
                        The selected review status is saved with the case history so it stays available after backend restarts.
                      </p>

                      <div className="mt-5 flex flex-wrap items-center gap-2">
                        <ReviewBadge status={reviewStatus} />
                        <span className="text-sm text-[var(--text-secondary)]">
                          {getReviewStatusDescription(reviewStatus)}
                        </span>
                      </div>

                      <div className="mt-5 grid gap-2 sm:grid-cols-2">
                        {REVIEW_STATUS_OPTIONS.map((option) => (
                          <button
                            key={option.key}
                            type="button"
                            onClick={() => setReviewStatus(option.key)}
                            className={`rounded-[20px] border px-4 py-4 text-left transition ${
                              reviewStatus === option.key
                                ? `${getReviewTone(option.key).panel} border-current`
                                : 'border-[color:var(--border)] bg-[var(--surface)] hover:-translate-y-0.5'
                            }`}
                          >
                            <div className="text-sm font-semibold text-[var(--text-primary)]">{option.label}</div>
                            <div className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">{option.description}</div>
                          </button>
                        ))}
                      </div>

                      <div className="mt-5 grid gap-3 sm:grid-cols-3">
                        <MiniStat label="Review state" value={formatReviewStatus(reviewStatus)} note="Professor decision" compact />
                        <MiniStat label="Flagged pairs" value={flaggedResults.length} note="Above current threshold" compact />
                        <MiniStat
                          label="Last update"
                          value={job.review_updated_at ? formatTimestamp(job.review_updated_at) : 'Not saved'}
                          note="Persisted with the case"
                          compact
                        />
                      </div>
                    </div>

                    <div className="theme-card-muted rounded-[24px] p-5">
                      <div className="flex items-end justify-between gap-4">
                        <div>
                          <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                            Reviewer notes
                          </div>
                          <h2 className="mt-2 text-xl font-semibold text-[var(--text-primary)]">
                            Keep the assignment rationale with the result
                          </h2>
                        </div>
                      </div>

                      <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
                        Record why the case is safe, why it needs follow-up, or what evidence should be discussed in committee.
                      </p>

                      <textarea
                        value={reviewNotes}
                        onChange={(event) => setReviewNotes(event.target.value)}
                        rows={8}
                        placeholder="Add professor notes, review rationale, or next steps for this assignment."
                        className="theme-input mt-5 w-full rounded-[22px] px-4 py-4 text-sm leading-6"
                      />

                      <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                        <div className="text-sm text-[var(--text-secondary)]">
                          {reviewError ? (
                            <span className="text-red-600">{reviewError}</span>
                          ) : reviewDirty ? (
                            'You have unsaved review changes.'
                          ) : job.review_updated_at ? (
                            `Saved ${formatTimestamp(job.review_updated_at)}`
                          ) : (
                            'No review decision has been saved yet.'
                          )}
                        </div>

                        <button
                          type="button"
                          onClick={saveReview}
                          disabled={reviewSaving || !reviewDirty}
                          className="theme-button-primary inline-flex items-center justify-center rounded-2xl px-5 py-3 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {reviewSaving ? 'Saving review...' : 'Save Review'}
                        </button>
                      </div>
                    </div>
                  </div>

                  <div className="grid gap-6 xl:grid-cols-[0.92fr_1.08fr]">
                    <div className="theme-card-muted rounded-[24px] p-5">
                      <div className="flex items-end justify-between gap-4">
                        <div>
                          <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                            Review queue
                          </div>
                          <h2 className="mt-2 text-xl font-semibold text-[var(--text-primary)]">
                            Highest-risk submissions first
                          </h2>
                        </div>
                        <button
                          type="button"
                          onClick={() => setActiveTab('files')}
                          className="theme-link inline-flex items-center gap-1 text-sm font-medium"
                        >
                          Open files
                          <ChevronRight size={16} />
                        </button>
                      </div>

                      <div className="mt-5 grid gap-3">
                        {submissionStats.slice(0, 6).map((entry) => (
                          <OverviewSubmissionCard
                            key={entry.name}
                            entry={entry}
                            threshold={threshold}
                            onOpen={() => {
                              setSelectedSubmission(entry.name);
                              if (entry.topMatch) {
                                setSelectedMatchKey(pairKey(entry.topMatch.file_a, entry.topMatch.file_b));
                              }
                              setActiveTab('result_driller');
                            }}
                          />
                        ))}
                      </div>
                    </div>

                    <div className="theme-card-muted rounded-[24px] p-5">
                      <div className="flex items-end justify-between gap-4">
                        <div>
                          <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                            Top findings
                          </div>
                          <h2 className="mt-2 text-xl font-semibold text-[var(--text-primary)]">
                            Key matches to inspect next
                          </h2>
                        </div>
                        <button
                          type="button"
                          onClick={() => setActiveTab('result_driller')}
                          className="theme-link inline-flex items-center gap-1 text-sm font-medium"
                        >
                          Open driller
                          <ChevronRight size={16} />
                        </button>
                      </div>

                      <div className="mt-5 space-y-3">
                        {(flaggedResults.length > 0 ? flaggedResults : results).slice(0, 5).map((result) => (
                          <FindingRow
                            key={pairKey(result.file_a, result.file_b)}
                            result={result}
                            threshold={threshold}
                            subtitle={summarizeMatch(result)}
                            onOpen={() => openDriller(result)}
                          />
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'insights' && (
                <div className="space-y-6">
                  <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                    <InsightHeroMetric
                      label="Average Strongest Match"
                      value={formatPercentPrecise(averageStrongestMatch)}
                      note="Average strongest peer match per submission"
                      tone={averageStrongestMatch >= threshold ? 'warning' : 'safe'}
                    />
                    <InsightHeroMetric
                      label="Submissions"
                      value={submissionStats.length}
                      note={`${flaggedSubmissions} review • ${cleanSubmissions} safe`}
                    />
                    <InsightHeroMetric
                      label="Stored Matches"
                      value={results.length}
                      note={`${possibleComparisons} possible comparisons`}
                    />
                    <InsightHeroMetric
                      label="Lines Analyzed"
                      value={totalLinesAnalyzed.toLocaleString('en-US')}
                      note="Across stored code previews"
                    />
                  </div>

                  <div className="grid gap-6 xl:grid-cols-[1.02fr_0.98fr]">
                    <div className="theme-card-muted rounded-[24px] p-5">
                      <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                        Risk distribution
                      </div>
                      <h2 className="mt-2 text-xl font-semibold text-[var(--text-primary)]">
                        Submission breakdown by strongest peer score
                      </h2>
                      <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
                        Each submission is grouped by its strongest stored peer match so you can see how many files deserve immediate review.
                      </p>

                      <div className="mt-5 grid gap-3 md:grid-cols-3">
                        <RiskDistributionTile
                          label="Low Risk"
                          range="< 40%"
                          count={riskDistribution.low}
                          total={submissionStats.length}
                          tone="safe"
                        />
                        <RiskDistributionTile
                          label="Medium Risk"
                          range="40-70%"
                          count={riskDistribution.medium}
                          total={submissionStats.length}
                          tone="medium"
                        />
                        <RiskDistributionTile
                          label="High Risk"
                          range="> 70%"
                          count={riskDistribution.high}
                          total={submissionStats.length}
                          tone="warning"
                        />
                      </div>
                    </div>

                    <div className="theme-card-muted rounded-[24px] p-5">
                      <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                        Score analysis
                      </div>
                      <h2 className="mt-2 text-xl font-semibold text-[var(--text-primary)]">
                        Assignment-level score summary
                      </h2>

                      <div className="mt-5 space-y-4">
                        <InsightDetailRow
                          label="Average Peer Score"
                          value={formatPercentPrecise(averagePeerScore)}
                          note="Across stored peer comparisons"
                        />
                        <InsightDetailRow
                          label="Highest Pair"
                          value={highestMatch ? formatPercentPrecise(highestMatch.score) : '0.0%'}
                          note={highestMatch ? `${highestMatch.file_a} vs ${highestMatch.file_b}` : 'No pair available'}
                        />
                        <InsightDetailRow
                          label="Score Spread"
                          value={formatPercentPrecise(scoreSpread)}
                          note="Difference between highest and lowest submission peak"
                        />
                        <InsightDetailRow
                          label="Review Threshold"
                          value={formatPercent(threshold)}
                          note={`${flaggedResults.length} flagged pair${flaggedResults.length === 1 ? '' : 's'} above threshold`}
                        />
                      </div>

                      <div className="mt-5 border-t border-[color:var(--border)] pt-5">
                        <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                          Coverage
                        </div>
                        <div className="mt-3 flex flex-wrap gap-2">
                          <CoverageChip label="Peer Similarity" tone="ready" />
                          <CoverageChip label="AI Detection" tone="pending" />
                          <CoverageChip label="Web Analysis" tone="pending" />
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
                    <div className="theme-card-muted rounded-[24px] p-5">
                      <div className="flex items-end justify-between gap-4">
                        <div>
                          <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                            Engine signal summary
                          </div>
                          <h2 className="mt-2 text-xl font-semibold text-[var(--text-primary)]">
                            What drives the strongest findings
                          </h2>
                        </div>
                      </div>

                      <div className="mt-5 space-y-4">
                        {topSignals.length === 0 ? (
                          <EmptyInline text="No engine signal data is available for this assignment." />
                        ) : (
                          topSignals.map((signal) => (
                            <SignalRow
                              key={signal.name}
                              label={signal.name}
                              average={signal.average}
                              peak={signal.peak}
                            />
                          ))
                        )}
                      </div>

                      <div className="mt-6 border-t border-[color:var(--border)] pt-5">
                        <div className="flex items-end justify-between gap-4">
                          <div>
                            <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                              Top detected matches
                            </div>
                            <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
                              Highest-risk pairs from this assignment.
                            </p>
                          </div>
                          <button
                            type="button"
                            onClick={() => setActiveTab('matches')}
                            className="theme-link inline-flex items-center gap-1 text-sm font-medium"
                          >
                            Open matches
                            <ChevronRight size={16} />
                          </button>
                        </div>

                        <div className="mt-4 space-y-3">
                          {(flaggedResults.length > 0 ? flaggedResults : results).slice(0, 4).map((result) => (
                            <FindingRow
                              key={pairKey(result.file_a, result.file_b)}
                              result={result}
                              threshold={threshold}
                              subtitle={summarizeMatch(result)}
                              onOpen={() => openDriller(result)}
                            />
                          ))}
                        </div>
                      </div>
                    </div>

                    <div className="theme-card-muted rounded-[24px] p-5">
                      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                        <div>
                          <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                            Submissions
                          </div>
                          <h2 className="mt-2 text-xl font-semibold text-[var(--text-primary)]">
                            Review files by overall risk
                          </h2>
                          <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
                            Filter the assignment list, then open any submission directly in the driller.
                          </p>
                        </div>

                        <div className="flex flex-wrap gap-2">
                          {[
                            { key: 'all', label: `All ${submissionStats.length}` },
                            { key: 'review', label: `Review ${flaggedSubmissions}` },
                            { key: 'safe', label: `Safe ${cleanSubmissions}` },
                          ].map((entry) => (
                            <button
                              key={entry.key}
                              type="button"
                              onClick={() => setInsightSubmissionFilter(entry.key)}
                              className={`rounded-full px-3 py-2 text-sm font-semibold transition ${
                                insightSubmissionFilter === entry.key
                                  ? 'bg-[var(--accent-blue)] text-white'
                                  : 'theme-card text-[var(--text-secondary)]'
                              }`}
                            >
                              {entry.label}
                            </button>
                          ))}
                        </div>
                      </div>

                      <div className="mt-5 grid gap-3">
                        {visibleInsightSubmissions.length === 0 ? (
                          <EmptyInline text="No submissions match this insights filter." />
                        ) : (
                          visibleInsightSubmissions.map((entry) => (
                            <SubmissionInsightCard
                              key={entry.name}
                              entry={entry}
                              threshold={threshold}
                              onOpen={() => {
                                setSelectedSubmission(entry.name);
                                if (entry.topMatch) {
                                  setSelectedMatchKey(pairKey(entry.topMatch.file_a, entry.topMatch.file_b));
                                }
                                setActiveTab('result_driller');
                              }}
                            />
                          ))
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'files' && (
                <div className="space-y-4">
                  <div className="flex items-end justify-between gap-4">
                    <div>
                      <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                        Files
                      </div>
                      <h2 className="mt-2 text-2xl font-semibold text-[var(--text-primary)]">
                        Review submissions by file
                      </h2>
                      <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
                        Each submission shows its highest peer score, how many flagged comparisons it participates in, and a shortcut into the driller.
                      </p>
                    </div>
                  </div>

                  {submissionStats.length === 0 ? (
                    <EmptyState
                      icon={FileCode}
                      title="No submission files found"
                      description="This assignment does not have stored submission previews yet."
                    />
                  ) : (
                    <div className="space-y-3">
                      {submissionStats.map((entry) => (
                        <SubmissionRow
                          key={entry.name}
                          entry={entry}
                          onOpen={() => {
                            setSelectedSubmission(entry.name);
                            if (entry.topMatch) {
                              setSelectedMatchKey(pairKey(entry.topMatch.file_a, entry.topMatch.file_b));
                            }
                            setActiveTab('result_driller');
                          }}
                        />
                      ))}
                    </div>
                  )}
                </div>
              )}

              {activeTab === 'peer_similarity' && (
                <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
                  <div className="theme-card-muted rounded-[24px] p-5">
                    <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                      Ranked submissions
                    </div>
                    <h2 className="mt-2 text-xl font-semibold text-[var(--text-primary)]">
                      Which files need attention first
                    </h2>

                    <div className="mt-5 space-y-3">
                      {submissionStats.map((entry) => (
                        <button
                          key={entry.name}
                          type="button"
                          onClick={() => {
                            setSelectedSubmission(entry.name);
                            if (entry.topMatch) {
                              setSelectedMatchKey(pairKey(entry.topMatch.file_a, entry.topMatch.file_b));
                            }
                            setActiveTab('result_driller');
                          }}
                          className="theme-card block w-full rounded-[20px] px-4 py-4 text-left transition hover:-translate-y-0.5"
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <div className="font-semibold text-[var(--text-primary)] break-all">{entry.name}</div>
                              <div className="mt-1 text-xs text-[var(--text-muted)]">
                                {entry.flaggedCount} flagged pair{entry.flaggedCount === 1 ? '' : 's'} • {entry.totalMatches} stored match{entry.totalMatches === 1 ? '' : 'es'}
                              </div>
                            </div>
                            <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${getRiskTone(entry.maxScore).badge}`}>
                              {formatPercent(entry.maxScore)}
                            </span>
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="theme-card-muted rounded-[24px] p-5">
                    <div className="flex items-end justify-between gap-4">
                      <div>
                        <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                          Similarity matrix
                        </div>
                        <h2 className="mt-2 text-xl font-semibold text-[var(--text-primary)]">
                          Peer similarity across the highest-risk submissions
                        </h2>
                      </div>
                    </div>

                    {matrixSubmissions.length < 2 ? (
                      <div className="mt-5">
                        <EmptyInline text="At least two submissions are needed to show the similarity matrix." />
                      </div>
                    ) : (
                      <div className="mt-5 overflow-x-auto">
                        <table className="min-w-full border-separate border-spacing-2">
                          <thead>
                            <tr>
                              <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                                File
                              </th>
                              {matrixSubmissions.map((entry) => (
                                <th
                                  key={entry.name}
                                  className="min-w-[88px] px-2 py-2 text-center text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]"
                                  title={entry.name}
                                >
                                  {truncateName(entry.name, 12)}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {matrixSubmissions.map((row) => (
                              <tr key={row.name}>
                                <th className="px-3 py-2 text-left text-sm font-medium text-[var(--text-primary)]" title={row.name}>
                                  {truncateName(row.name, 20)}
                                </th>
                                {matrixSubmissions.map((column) => {
                                  if (row.name === column.name) {
                                    return (
                                      <td key={column.name} className="px-2 py-2">
                                        <div className="flex h-12 items-center justify-center rounded-2xl border border-[color:var(--border)] bg-[var(--surface)] text-xs font-semibold text-[var(--text-muted)]">
                                          —
                                        </div>
                                      </td>
                                    );
                                  }

                                  const score = pairLookup.get(pairKey(row.name, column.name)) || 0;
                                  const tone = getRiskTone(score);

                                  return (
                                    <td key={column.name} className="px-2 py-2">
                                      <button
                                        type="button"
                                        onClick={() => {
                                          const match = results.find((result) => pairKey(result.file_a, result.file_b) === pairKey(row.name, column.name));
                                          if (match) {
                                            openDriller(match, row.name);
                                          }
                                        }}
                                        className={`flex h-12 w-full items-center justify-center rounded-2xl border text-sm font-semibold transition hover:-translate-y-0.5 ${tone.panel} ${tone.text}`}
                                      >
                                        {formatPercent(score)}
                                      </button>
                                    </td>
                                  );
                                })}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {activeTab === 'matches' && (
                <div className="space-y-5">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                    <div>
                      <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                        Matches
                      </div>
                      <h2 className="mt-2 text-2xl font-semibold text-[var(--text-primary)]">
                        Pairwise similarity findings
                      </h2>
                      <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
                        Filter all stored comparisons, then expand any pair to inspect engine signals and the source preview.
                      </p>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      {[
                        { key: 'all', label: `All ${results.length}` },
                        { key: 'flagged', label: `Flagged ${flaggedResults.length}` },
                        { key: 'critical', label: `Critical ${critical.length}` },
                        { key: 'high', label: `High ${high.length}` },
                      ].map((entry) => (
                        <button
                          key={entry.key}
                          type="button"
                          onClick={() => setMatchFilter(entry.key)}
                          className={`rounded-full px-3 py-2 text-sm font-semibold transition ${
                            matchFilter === entry.key
                              ? 'bg-[var(--accent-blue)] text-white'
                              : 'theme-card-muted text-[var(--text-secondary)]'
                          }`}
                        >
                          {entry.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  {filteredMatches.length === 0 ? (
                    <EmptyState
                      icon={CheckCircle2}
                      title="No matches in this filter"
                      description="Try a broader filter to review the stored pairwise comparisons."
                    />
                  ) : (
                    <div className="space-y-3">
                      {filteredMatches.map((result) => {
                        const key = pairKey(result.file_a, result.file_b);
                        return (
                          <MatchCard
                            key={key}
                            result={result}
                            threshold={threshold}
                            expanded={Boolean(expandedMatches[key])}
                            onToggle={() => toggleExpanded(key)}
                            onDrill={() => openDriller(result)}
                            codeA={submissions[result.file_a] || ''}
                            codeB={submissions[result.file_b] || ''}
                          />
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              {activeTab === 'result_driller' && (
                <div className="grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
                  <div className="space-y-4">
                    <div className="theme-card-muted rounded-[24px] p-5">
                      <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                        Result driller
                      </div>
                      <h2 className="mt-2 text-xl font-semibold text-[var(--text-primary)]">
                        Inspect one submission at a time
                      </h2>
                      <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
                        Use the submission picker, then move through matches. Arrow up and down step between matches while this tab is open.
                      </p>
                    </div>

                    <div className="theme-card-muted rounded-[24px] p-5">
                      <label className="block text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                        Submission
                      </label>
                      <select
                        value={selectedSubmission}
                        onChange={(event) => setSelectedSubmission(event.target.value)}
                        className="theme-input mt-3 w-full rounded-2xl px-4 py-3 text-sm"
                      >
                        {submissionStats.map((entry) => (
                          <option key={entry.name} value={entry.name}>
                            {entry.name}
                          </option>
                        ))}
                      </select>

                      {selectedSubmissionStats && (
                        <div className="mt-4 grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
                          <MiniStat label="Lines" value={selectedSubmissionStats.lines || '—'} note="Stored preview size" compact />
                          <MiniStat label="Flagged" value={selectedSubmissionStats.flaggedCount} note="Pairs above threshold" compact />
                          <MiniStat label="Top score" value={formatPercent(selectedSubmissionStats.maxScore)} note={selectedSubmissionStats.topMatchName || 'No top pair'} compact />
                        </div>
                      )}
                    </div>

                    <div className="theme-card-muted rounded-[24px] p-5">
                      <div className="flex items-end justify-between gap-4">
                        <div>
                          <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                            Match list
                          </div>
                          <h2 className="mt-2 text-lg font-semibold text-[var(--text-primary)]">
                            {selectedSubmission ? truncateName(selectedSubmission, 28) : 'No submission selected'}
                          </h2>
                        </div>

                        <div className="flex gap-2">
                          <button
                            type="button"
                            onClick={() => setDrillerMode('flagged')}
                            className={`rounded-full px-3 py-2 text-xs font-semibold transition ${
                              drillerMode === 'flagged'
                                ? 'bg-[var(--accent-blue)] text-white'
                                : 'theme-card text-[var(--text-secondary)]'
                            }`}
                          >
                            Flagged
                          </button>
                          <button
                            type="button"
                            onClick={() => setDrillerMode('all')}
                            className={`rounded-full px-3 py-2 text-xs font-semibold transition ${
                              drillerMode === 'all'
                                ? 'bg-[var(--accent-blue)] text-white'
                                : 'theme-card text-[var(--text-secondary)]'
                            }`}
                          >
                            All
                          </button>
                        </div>
                      </div>

                      <div className="mt-4 space-y-2 max-h-[520px] overflow-y-auto pr-1">
                        {visibleDrillerMatches.length === 0 ? (
                          <EmptyInline text="No matches are available for this submission in the current filter." />
                        ) : (
                          visibleDrillerMatches.map((result) => {
                            const key = pairKey(result.file_a, result.file_b);
                            const counterpart = otherSubmission(result, selectedSubmission);
                            const tone = getRiskTone(result.score);

                            return (
                              <button
                                key={key}
                                type="button"
                                onClick={() => setSelectedMatchKey(key)}
                                className={`block w-full rounded-[20px] border px-4 py-4 text-left transition ${
                                  selectedMatchKey === key
                                    ? 'border-[color:var(--accent-blue)] bg-blue-600/[0.08]'
                                    : 'border-[color:var(--border)] bg-[var(--surface)] hover:-translate-y-0.5'
                                }`}
                              >
                                <div className="flex items-start justify-between gap-3">
                                  <div className="min-w-0">
                                    <div className="font-medium text-[var(--text-primary)] break-all">{counterpart}</div>
                                    <div className="mt-1 text-xs text-[var(--text-muted)]">
                                      {summarizeMatch(result)}
                                    </div>
                                  </div>
                                  <span className={`inline-flex rounded-full border px-2 py-1 text-[11px] font-semibold ${tone.badge}`}>
                                    {formatPercent(result.score)}
                                  </span>
                                </div>
                              </button>
                            );
                          })
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="space-y-4">
                    {!selectedMatch ? (
                      <EmptyState
                        icon={Code2}
                        title="Select a submission or match"
                        description="Choose a submission on the left to inspect the pairwise evidence and code preview."
                      />
                    ) : (
                      <>
                        <div className={`rounded-[24px] border px-5 py-5 ${getRiskTone(selectedMatch.score).panel}`}>
                          <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                            <div className="space-y-3">
                              <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                                Selected match
                              </div>
                              <div className="text-2xl font-semibold text-[var(--text-primary)] break-all">
                                {selectedMatch.file_a}
                                <span className="mx-3 text-[var(--text-muted)]">vs</span>
                                {selectedMatch.file_b}
                              </div>
                              <p className="max-w-3xl text-sm leading-6 text-[var(--text-secondary)]">
                                {summarizeMatch(selectedMatch)}
                              </p>
                            </div>

                            <div className="flex flex-wrap gap-3">
                              <span className={`inline-flex rounded-full border px-3 py-2 text-sm font-semibold ${getRiskTone(selectedMatch.score).badge}`}>
                                {getRiskBucket(selectedMatch.score).toUpperCase()} {formatPercentPrecise(selectedMatch.score)}
                              </span>
                              <button
                                type="button"
                                onClick={() => setActiveTab('matches')}
                                className="theme-button-secondary inline-flex items-center gap-2 rounded-2xl px-4 py-3 text-sm font-semibold"
                              >
                                <Search size={16} />
                                Open Match List
                              </button>
                            </div>
                          </div>

                          <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                            {Object.entries(selectedMatch.features || {})
                              .sort((a, b) => b[1] - a[1])
                              .slice(0, 5)
                              .map(([name, value]) => (
                                <MiniStat
                                  key={name}
                                  label={name}
                                  value={formatPercent(value)}
                                  note="Engine strength"
                                  compact
                                />
                              ))}
                          </div>
                        </div>

                        <div className="grid gap-4 xl:grid-cols-2">
                          <CodePanel
                            title={selectedSubmission}
                            subtitle="Primary submission"
                            code={submissions[selectedSubmission] || ''}
                            tone="blue"
                          />
                          <CodePanel
                            title={otherSubmission(selectedMatch, selectedSubmission)}
                            subtitle="Matched submission"
                            code={submissions[otherSubmission(selectedMatch, selectedSubmission)] || ''}
                            tone="emerald"
                          />
                        </div>
                      </>
                    )}
                  </div>
                </div>
              )}

              {activeTab === 'ai_detection' && (
                <div className="space-y-6">
                  <FeatureStatusBanner
                    icon={Brain}
                    title="AI detection workspace is ready, but the backend AI engine is not enabled"
                    description="This tab now follows the assignment analytics pattern used in dedicated AI result dashboards. Once the backend provides AI scores, this page can show assignment averages, score distribution, and per-submission details without another redesign."
                    tone="pending"
                  />

                  <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                    <InsightHeroMetric
                      label="Average AI Score"
                      value="Not Run"
                      note={`${submissionStats.length} submission${submissionStats.length === 1 ? '' : 's'} available for future analysis`}
                    />
                    <InsightHeroMetric
                      label="Submissions"
                      value={submissionStats.length}
                      note="Ready for AI review when enabled"
                    />
                    <InsightHeroMetric
                      label="Highest Score"
                      value="—"
                      note="No AI scoring data yet"
                    />
                    <InsightHeroMetric
                      label="Flagged"
                      value="0"
                      note="No AI flags recorded"
                    />
                  </div>

                  <div className="grid gap-6 xl:grid-cols-[0.92fr_1.08fr]">
                    <div className="theme-card-muted rounded-[24px] p-5">
                      <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                        Distribution
                      </div>
                      <h2 className="mt-2 text-xl font-semibold text-[var(--text-primary)]">
                        AI risk distribution
                      </h2>
                      <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
                        The layout is ready for low, medium, and high AI scores once the detection engine is connected.
                      </p>

                      <div className="mt-5 grid gap-3 md:grid-cols-3">
                        <RiskDistributionTile label="Low Risk" range="< 40%" count={0} total={submissionStats.length || 1} tone="safe" />
                        <RiskDistributionTile label="Medium Risk" range="40-70%" count={0} total={submissionStats.length || 1} tone="medium" />
                        <RiskDistributionTile label="High Risk" range="> 70%" count={0} total={submissionStats.length || 1} tone="warning" />
                      </div>

                      <div className="mt-5 border-t border-[color:var(--border)] pt-5">
                        <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                          Planned outputs
                        </div>
                        <div className="mt-3 flex flex-wrap gap-2">
                          <CoverageChip label="Submission AI score" tone="pending" />
                          <CoverageChip label="Score range" tone="pending" />
                          <CoverageChip label="Model attribution" tone="pending" />
                          <CoverageChip label="Sentence evidence" tone="pending" />
                        </div>
                      </div>
                    </div>

                    <div className="theme-card-muted rounded-[24px] p-5">
                      <div className="flex items-end justify-between gap-4">
                        <div>
                          <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                            Submissions
                          </div>
                          <h2 className="mt-2 text-xl font-semibold text-[var(--text-primary)]">
                            AI analysis queue
                          </h2>
                          <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
                            Every submission is already listed here so AI results can drop into place once the backend starts returning them.
                          </p>
                        </div>
                      </div>

                      <div className="mt-5 space-y-3">
                        {submissionStats.length === 0 ? (
                          <EmptyInline text="No submissions are available for AI analysis." />
                        ) : (
                          submissionStats.map((entry) => (
                            <AiSubmissionRow key={entry.name} entry={entry} />
                          ))
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'web_analysis' && (
                <EmptyState
                  icon={Globe2}
                  title="Web analysis is not enabled for this assignment"
                  description="This assignment currently stores peer-to-peer code similarity only. When web source checking is available, this tab can list matched sources, source confidence, and export-ready web evidence."
                />
              )}
            </div>
          </section>
        </div>
      </div>
    </DashboardLayout>
  );
}

function ResultTabButton({ active, label, count, icon: Icon, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-2 rounded-full px-4 py-2.5 text-sm font-semibold transition ${
        active
          ? 'bg-[var(--accent-blue)] text-white shadow-lg shadow-blue-500/15'
          : 'theme-card-muted text-[var(--text-secondary)]'
      }`}
    >
      <Icon size={15} />
      {label}
      <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${active ? 'bg-white/15 text-white' : 'bg-[var(--surface)] text-[var(--text-muted)]'}`}>
        {count}
      </span>
    </button>
  );
}

function MetricCard({ label, value, icon: Icon }) {
  return (
    <div className="theme-card-muted rounded-[22px] px-4 py-4">
      <div className="flex items-center justify-between gap-3">
        <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
          {label}
        </div>
        <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[var(--surface)] text-[var(--accent-blue)]">
          <Icon size={16} />
        </div>
      </div>
      <div className="mt-4 text-3xl font-semibold tracking-tight text-[var(--text-primary)]">{value}</div>
    </div>
  );
}

function ReviewBadge({ status }) {
  const tone = getReviewTone(status);

  return (
    <span className={`inline-flex rounded-full border px-3 py-1.5 text-xs font-semibold ${tone.badge}`}>
      {formatReviewStatus(status)}
    </span>
  );
}

function InsightHeroMetric({ label, value, note, tone = 'default' }) {
  const toneMap = {
    default: 'border-[color:var(--border)] bg-[var(--surface)]',
    warning: 'border-amber-500/20 bg-amber-500/[0.08]',
    safe: 'border-emerald-500/20 bg-emerald-500/[0.08]',
  };

  return (
    <div className={`rounded-[24px] border px-4 py-4 ${toneMap[tone] || toneMap.default}`}>
      <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">{label}</div>
      <div className="mt-3 text-3xl font-semibold tracking-tight text-[var(--text-primary)]">{value}</div>
      <div className="mt-2 text-xs leading-5 text-[var(--text-secondary)]">{note}</div>
    </div>
  );
}

function OverviewBreakdownCard({ label, value, note, tone }) {
  const toneMap = {
    ready: 'border-blue-600/20 bg-blue-600/[0.08] text-blue-600',
    pending: 'border-[color:var(--border)] bg-[var(--surface)] text-[var(--text-secondary)]',
  };

  return (
    <div className={`rounded-[22px] border px-4 py-4 ${toneMap[tone] || toneMap.pending}`}>
      <div className="text-[11px] font-semibold uppercase tracking-[0.18em] opacity-80">{label}</div>
      <div className="mt-3 text-2xl font-semibold">{value}</div>
      <div className="mt-2 text-xs leading-5 opacity-80">{note}</div>
    </div>
  );
}

function MiniStat({ label, value, note, compact = false }) {
  return (
    <div className={`rounded-[20px] border border-[color:var(--border)] bg-[var(--surface)] px-4 py-4 ${compact ? '' : 'min-h-[118px]'}`}>
      <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-[var(--text-primary)]">{value}</div>
      <div className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">{note}</div>
    </div>
  );
}

function FeatureStatusBanner({ icon: Icon, title, description, tone = 'pending' }) {
  const toneMap = {
    pending: 'border-[color:var(--border)] bg-[var(--surface-muted)]',
    ready: 'border-blue-600/20 bg-blue-600/[0.08]',
  };

  return (
    <div className={`rounded-[24px] border px-5 py-5 ${toneMap[tone] || toneMap.pending}`}>
      <div className="flex items-start gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[var(--surface)] text-[var(--accent-blue)]">
          <Icon size={18} />
        </div>
        <div>
          <div className="text-lg font-semibold text-[var(--text-primary)]">{title}</div>
          <div className="mt-2 max-w-3xl text-sm leading-6 text-[var(--text-secondary)]">{description}</div>
        </div>
      </div>
    </div>
  );
}

function RiskDistributionTile({ label, range, count, total, tone }) {
  const toneMap = {
    safe: 'border-emerald-500/20 bg-emerald-500/[0.08] text-emerald-600',
    medium: 'border-yellow-500/20 bg-yellow-500/[0.08] text-yellow-600',
    warning: 'border-amber-500/20 bg-amber-500/[0.08] text-amber-600',
  };
  const percent = total > 0 ? Math.round((count / total) * 100) : 0;

  return (
    <div className={`rounded-[22px] border px-4 py-4 ${toneMap[tone] || toneMap.safe}`}>
      <div className="text-[11px] font-semibold uppercase tracking-[0.18em] opacity-80">{label}</div>
      <div className="mt-1 text-xs opacity-80">{range}</div>
      <div className="mt-4 text-3xl font-semibold">{count}</div>
      <div className="mt-1 text-xs opacity-80">{percent}% of submissions</div>
    </div>
  );
}

function OverviewSubmissionCard({ entry, threshold, onOpen }) {
  const tone = getRiskTone(entry.maxScore);
  const status = entry.maxScore >= threshold ? 'Review' : 'Safe';

  return (
    <button
      type="button"
      onClick={onOpen}
      className="theme-card block w-full rounded-[22px] px-4 py-4 text-left transition hover:-translate-y-0.5"
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <div className="font-semibold text-[var(--text-primary)] break-all">{entry.name}</div>
            <span className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-semibold ${tone.badge}`}>
              {status}
            </span>
          </div>
          <div className="mt-2 flex flex-wrap gap-2 text-xs text-[var(--text-muted)]">
            <span>{entry.flaggedCount} flagged pair{entry.flaggedCount === 1 ? '' : 's'}</span>
            <span>{entry.totalMatches} stored match{entry.totalMatches === 1 ? '' : 'es'}</span>
            <span>{entry.lines || '—'} lines</span>
          </div>
        </div>

        <div className="shrink-0 text-sm font-semibold text-[var(--text-primary)]">
          {formatPercentPrecise(entry.maxScore)}
        </div>
      </div>
    </button>
  );
}

function InsightDetailRow({ label, value, note }) {
  return (
    <div className="flex items-start justify-between gap-4 rounded-[20px] border border-[color:var(--border)] bg-[var(--surface)] px-4 py-4">
      <div className="min-w-0">
        <div className="text-sm font-semibold text-[var(--text-primary)]">{label}</div>
        <div className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">{note}</div>
      </div>
      <div className="shrink-0 text-lg font-semibold text-[var(--text-primary)]">{value}</div>
    </div>
  );
}

function CoverageChip({ label, tone }) {
  const toneMap = {
    ready: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-600',
    pending: 'border-[color:var(--border)] bg-[var(--surface)] text-[var(--text-secondary)]',
  };

  return (
    <span className={`inline-flex rounded-full border px-3 py-1.5 text-xs font-semibold ${toneMap[tone] || toneMap.pending}`}>
      {label}
    </span>
  );
}

function AiSubmissionRow({ entry }) {
  return (
    <div className="theme-card rounded-[22px] px-4 py-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="font-semibold text-[var(--text-primary)] break-all">{entry.name}</div>
          <div className="mt-2 flex flex-wrap gap-2 text-xs text-[var(--text-muted)]">
            <span>{entry.lines || '—'} lines</span>
            <span>{entry.totalMatches} peer match{entry.totalMatches === 1 ? '' : 'es'} already available</span>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex rounded-full border border-[color:var(--border)] bg-[var(--surface)] px-2.5 py-1 text-xs font-semibold text-[var(--text-secondary)]">
            Score —
          </span>
          <span className="inline-flex rounded-full border border-[color:var(--border)] bg-[var(--surface)] px-2.5 py-1 text-xs font-semibold text-[var(--text-secondary)]">
            Pending
          </span>
        </div>
      </div>
    </div>
  );
}

function SignalRow({ label, average, peak }) {
  return (
    <div>
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-medium text-[var(--text-primary)]">{label}</div>
        <div className="text-xs text-[var(--text-muted)]">
          avg {formatPercent(average)} • peak {formatPercent(peak)}
        </div>
      </div>
      <div className="mt-2 h-2 rounded-full bg-[color:var(--border)]">
        <div
          className="h-full rounded-full bg-gradient-to-r from-[var(--accent-blue)] to-[var(--accent-indigo)]"
          style={{ width: `${Math.max(peak * 100, 4)}%` }}
        />
      </div>
    </div>
  );
}

function SubmissionInsightCard({ entry, threshold, onOpen }) {
  const tone = getRiskTone(entry.maxScore);
  const status = entry.maxScore >= threshold ? 'Review' : 'Safe';

  return (
    <button
      type="button"
      onClick={onOpen}
      className="theme-card block w-full rounded-[22px] px-4 py-4 text-left transition hover:-translate-y-0.5"
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <div className="font-semibold text-[var(--text-primary)] break-all">{entry.name}</div>
            <span className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-semibold ${tone.badge}`}>
              {status}
            </span>
          </div>
          <div className="mt-2 flex flex-wrap gap-2 text-xs text-[var(--text-muted)]">
            <span>Peer {formatPercentPrecise(entry.maxScore)}</span>
            <span>{entry.flaggedCount} flagged pair{entry.flaggedCount === 1 ? '' : 's'}</span>
            <span>{entry.lines || '—'} lines</span>
          </div>
        </div>

        <span className="theme-link inline-flex items-center gap-1 text-sm font-medium">
          Open
          <ArrowRight size={15} />
        </span>
      </div>
    </button>
  );
}

function FindingRow({ result, threshold, subtitle, onOpen }) {
  const tone = getRiskTone(result.score);
  const flagged = result.score >= threshold;

  return (
    <div className="theme-card rounded-[22px] px-4 py-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
            <span className={`h-2.5 w-2.5 rounded-full ${tone.dot}`} />
            <span className="break-all">{result.file_a}</span>
            <span className="text-[var(--text-muted)]">vs</span>
            <span className="break-all">{result.file_b}</span>
          </div>
          <div className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">{subtitle}</div>
        </div>

        <div className="flex items-center gap-3">
          <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${tone.badge}`}>
            {flagged ? 'Flagged' : 'Stored'} {formatPercentPrecise(result.score)}
          </span>
          <button
            type="button"
            onClick={onOpen}
            className="theme-link inline-flex items-center gap-1 text-sm font-medium"
          >
            Drill in
            <ArrowRight size={15} />
          </button>
        </div>
      </div>
    </div>
  );
}

function SubmissionRow({ entry, onOpen }) {
  const tone = getRiskTone(entry.maxScore);

  return (
    <div className="theme-card rounded-[24px] px-5 py-5">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0">
          <div className="text-lg font-semibold text-[var(--text-primary)] break-all">{entry.name}</div>
          <div className="mt-2 flex flex-wrap gap-2 text-xs text-[var(--text-muted)]">
            <span>{entry.lines || '—'} lines</span>
            <span>{entry.totalMatches} stored match{entry.totalMatches === 1 ? '' : 'es'}</span>
            <span>{entry.flaggedCount} flagged pair{entry.flaggedCount === 1 ? '' : 's'}</span>
          </div>
          <div className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">
            {entry.topMatchName
              ? `Strongest peer match is ${entry.topMatchName} at ${formatPercentPrecise(entry.maxScore)}.`
              : 'No peer comparison was stored for this file.'}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <span className={`inline-flex rounded-full border px-3 py-1.5 text-sm font-semibold ${tone.badge}`}>
            {formatPercent(entry.maxScore)}
          </span>
          <button
            type="button"
            onClick={onOpen}
            className="theme-button-secondary inline-flex items-center gap-2 rounded-2xl px-4 py-3 text-sm font-semibold"
          >
            <Code2 size={16} />
            Open Driller
          </button>
        </div>
      </div>
    </div>
  );
}

function MatchCard({ result, threshold, expanded, onToggle, onDrill, codeA, codeB }) {
  const tone = getRiskTone(result.score);
  const featureEntries = Object.entries(result.features || {}).sort((a, b) => b[1] - a[1]).slice(0, 5);

  return (
    <div className="theme-card rounded-[24px] overflow-hidden">
      <div className="px-5 py-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
              <span className={`h-2.5 w-2.5 rounded-full ${tone.dot}`} />
              <span className="break-all">{result.file_a}</span>
              <span className="text-[var(--text-muted)]">vs</span>
              <span className="break-all">{result.file_b}</span>
            </div>
            <div className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
              {summarizeMatch(result)}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${tone.badge}`}>
              {result.score >= threshold ? 'Flagged' : 'Stored'} {formatPercentPrecise(result.score)}
            </span>
            <button
              type="button"
              onClick={onDrill}
              className="theme-link inline-flex items-center gap-1 text-sm font-medium"
            >
              Drill in
              <ArrowRight size={15} />
            </button>
            <button
              type="button"
              onClick={onToggle}
              className="theme-button-secondary inline-flex items-center gap-2 rounded-2xl px-4 py-2.5 text-sm font-semibold"
            >
              <FileSearch size={15} />
              {expanded ? 'Hide preview' : 'Show preview'}
            </button>
          </div>
        </div>

        {featureEntries.length > 0 && (
          <div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            {featureEntries.map(([name, value]) => (
              <SignalRow key={name} label={name} average={value} peak={value} />
            ))}
          </div>
        )}
      </div>

      {expanded && (
        <div className="border-t border-[color:var(--border)] bg-[var(--surface-muted)] px-5 py-5">
          <div className="grid gap-4 xl:grid-cols-2">
            <CodePanel title={result.file_a} subtitle="Source preview" code={codeA} tone="blue" />
            <CodePanel title={result.file_b} subtitle="Matched preview" code={codeB} tone="emerald" />
          </div>
        </div>
      )}
    </div>
  );
}

function CodePanel({ title, subtitle, code, tone }) {
  const headerTone = tone === 'emerald'
    ? 'bg-emerald-500/10 text-emerald-600'
    : 'bg-blue-600/10 text-blue-600';

  return (
    <div className="overflow-hidden rounded-[24px] border border-[color:var(--border)] bg-[var(--surface)]">
      <div className={`flex items-center justify-between gap-3 border-b border-[color:var(--border)] px-4 py-3 ${headerTone}`}>
        <div className="min-w-0">
          <div className="text-sm font-semibold break-all">{title || 'Unknown file'}</div>
          <div className="text-[11px] uppercase tracking-[0.18em] opacity-80">{subtitle}</div>
        </div>
      </div>
      <pre className="max-h-[580px] overflow-x-auto overflow-y-auto bg-slate-950 px-4 py-4 text-xs leading-6 text-slate-200">
        {code || '// No stored preview available for this file.'}
      </pre>
    </div>
  );
}

function EmptyState({ icon: Icon, title, description }) {
  return (
    <div className="theme-card-muted rounded-[24px] px-6 py-14 text-center">
      <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-[var(--surface)] text-[var(--accent-blue)]">
        <Icon size={22} />
      </div>
      <h3 className="mt-4 text-xl font-semibold text-[var(--text-primary)]">{title}</h3>
      <p className="mx-auto mt-3 max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">
        {description}
      </p>
    </div>
  );
}

function EmptyInline({ text }) {
  return (
    <div className="rounded-[20px] border border-dashed border-[color:var(--border)] px-4 py-5 text-sm leading-6 text-[var(--text-secondary)]">
      {text}
    </div>
  );
}
