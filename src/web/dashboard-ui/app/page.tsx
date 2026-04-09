// @ts-nocheck
'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { useAuth } from '@/components/AuthProvider';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import axios from 'axios';
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  Download,
  FileSearch,
  FileText,
  FolderArchive,
  Loader2,
  Settings2,
  Shield,
  Upload,
} from 'lucide-react';

const API = '';
const REVIEW_STATUS_LABELS = {
  unreviewed: 'Unreviewed',
  needs_review: 'Needs Review',
  confirmed: 'Confirmed',
  dismissed: 'Dismissed',
  escalated: 'Escalated',
};

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
  return `${Math.round((value || 0) * 100)}%`;
}

function getAssignmentTitle(job) {
  return job.assignment_name || job.course_name || 'Untitled assignment check';
}

function getReferenceLabel(job) {
  if (!job.course_name || job.course_name === job.assignment_name) {
    return '';
  }

  return job.course_name;
}

function getThreshold(job) {
  const threshold = Number(job?.threshold);
  return Number.isFinite(threshold) ? threshold : 0.5;
}

function getReviewStatus(job) {
  return REVIEW_STATUS_LABELS[job?.review_status] ? job.review_status : 'unreviewed';
}

function formatReviewStatus(status) {
  return REVIEW_STATUS_LABELS[status] || REVIEW_STATUS_LABELS.unreviewed;
}

function getReviewTone(status) {
  const toneMap = {
    unreviewed: 'border-slate-500/20 bg-slate-500/10 text-slate-600',
    needs_review: 'border-amber-500/20 bg-amber-500/10 text-amber-600',
    confirmed: 'border-red-500/20 bg-red-500/10 text-red-600',
    dismissed: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-600',
    escalated: 'border-violet-500/20 bg-violet-500/10 text-violet-600',
  };

  return toneMap[status] || toneMap.unreviewed;
}

function truncateText(value, max = 120) {
  if (!value || value.length <= max) {
    return value;
  }

  return `${value.slice(0, max - 1)}…`;
}

function getFlaggedResults(job) {
  if (!job?.results?.length) {
    return [];
  }

  const threshold = getThreshold(job);
  return [...job.results]
    .filter((result) => result.score >= threshold)
    .sort((a, b) => b.score - a.score);
}

function getTopFeature(result) {
  const topFeature = Object.entries(result?.features || {}).sort((a, b) => b[1] - a[1])[0];

  if (!topFeature) {
    return 'Evidence ready for manual review';
  }

  return `${topFeature[0]} strongest`;
}

export default function Home() {
  const { user, loading: authLoading } = useAuth();
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (authLoading) {
      return;
    }
    if (!user) {
      setLoading(false);
      return;
    }

    fetchJobs();
    const interval = setInterval(fetchJobs, 30000);

    return () => clearInterval(interval);
  }, [authLoading, user]);

  const fetchJobs = async () => {
    try {
      const res = await axios.get(`${API}/api/jobs`);
      setJobs(res.data.jobs || []);
    } catch {
      setJobs([]);
    }

    setLoading(false);
  };

  const recentJobs = jobs.slice(0, 4);
  const latestCompleted = jobs.find((job) => job.status === 'completed');
  const runningCount = jobs.filter((job) => ['processing', 'analyzing'].includes(job.status)).length;
  const latestFlaggedResults = latestCompleted ? getFlaggedResults(latestCompleted) : [];
  const latestPreviewResults = latestFlaggedResults.slice(0, 3);
  const latestThreshold = getThreshold(latestCompleted);
  const latestSummary = latestCompleted?.summary || {};
  const latestHighestMatch = latestFlaggedResults[0];
  const latestReviewStatus = getReviewStatus(latestCompleted);

  return (
    <DashboardLayout>
      <div className="px-4 py-4 lg:px-6 lg:py-6">
        <div className="space-y-6">
          <section className="theme-card-strong theme-section-line relative overflow-hidden rounded-[32px] px-6 py-6 lg:px-8 lg:py-8">
            <div className="absolute right-0 top-0 h-40 w-40 rounded-full bg-blue-600/[0.08] blur-3xl" />

            <div className="relative grid gap-6 xl:grid-cols-[1.35fr_0.9fr]">
              <div className="space-y-6">
                <div className="inline-flex items-center gap-2 rounded-full border border-blue-600/10 bg-blue-600/[0.06] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-blue-600">
                  <Shield size={13} />
                  Assignment checker
                </div>

                <div className="space-y-4">
                  <h1 className="font-display max-w-3xl text-4xl font-semibold leading-tight text-[var(--text-primary)] sm:text-5xl">
                    Upload submissions and review the result without dashboard clutter.
                  </h1>
                  <p className="max-w-2xl text-sm leading-7 text-[var(--text-secondary)] sm:text-base">
                    This workspace is centered on one job: checking a single assignment for suspicious similarity,
                    then opening the flagged result quickly.
                  </p>
                </div>

                <div className="flex flex-wrap gap-3">
                  <Link
                    href="/upload?mode=individual"
                    className="theme-button-primary inline-flex items-center gap-2 rounded-2xl px-5 py-3 text-sm font-semibold transition"
                  >
                    <Upload size={16} />
                    Upload Files
                  </Link>

                  <Link
                    href="/upload?mode=zip"
                    className="theme-button-secondary inline-flex items-center gap-2 rounded-2xl px-5 py-3 text-sm font-semibold transition"
                  >
                    <FolderArchive size={16} />
                    Upload ZIP
                  </Link>

                  {latestCompleted && (
                    <Link
                      href={`/results/${latestCompleted.id}`}
                      className="theme-button-secondary inline-flex items-center gap-2 rounded-2xl px-5 py-3 text-sm font-semibold transition"
                    >
                      <FileSearch size={16} />
                      Open Latest Result
                    </Link>
                  )}
                </div>

                <div className="flex flex-wrap gap-3 text-sm">
                  <span className="rounded-full border border-[color:var(--border)] bg-[var(--surface-muted)] px-3 py-1.5 text-[var(--text-secondary)]">
                    {runningCount > 0 ? `${runningCount} check${runningCount === 1 ? '' : 's'} in progress` : 'No checks running'}
                  </span>
                  <span className="rounded-full border border-[color:var(--border)] bg-[var(--surface-muted)] px-3 py-1.5 text-[var(--text-secondary)]">
                    {latestCompleted ? `Latest result ready ${formatTimestamp(latestCompleted.created_at)}` : 'No completed result yet'}
                  </span>
                </div>
              </div>

              <div className="theme-card rounded-[28px] p-5 lg:p-6">
                <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                  How it works
                </div>
                <div className="mt-4 space-y-4">
                  <GuideStep
                    index="01"
                    title="Upload the assignment"
                    description="Add individual files or a ZIP archive from the submission set you want to review."
                  />
                  <GuideStep
                    index="02"
                    title="Wait for analysis"
                    description="IntegrityDesk runs the check and keeps polling until the result is ready."
                  />
                  <GuideStep
                    index="03"
                    title="Open flagged pairs"
                    description="Review suspicious matches, then export the supporting report if needed."
                  />
                </div>
              </div>
            </div>
          </section>

          <section className="grid gap-6 xl:grid-cols-[1.3fr_0.7fr]">
            <div className="space-y-6">
              <div className="theme-card rounded-[30px] overflow-hidden">
                <div className="theme-section-line px-6 py-5">
                  <div className="flex items-end justify-between gap-4">
                    <div>
                      <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                        Latest verdict
                      </div>
                      <h2 className="font-display mt-2 text-2xl font-semibold text-[var(--text-primary)]">
                        Review the last completed assignment at a glance
                      </h2>
                    </div>

                    {latestCompleted && (
                      <Link href={`/results/${latestCompleted.id}`} className="theme-link inline-flex items-center gap-1 text-sm font-medium">
                        Open result
                        <ChevronRight size={16} />
                      </Link>
                    )}
                  </div>
                </div>

                <div className="px-6 pb-6">
                  {!latestCompleted ? (
                    <div className="theme-card-muted rounded-[24px] px-6 py-10">
                      <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-[var(--surface)] text-[var(--accent-blue)]">
                        {runningCount > 0 ? <Loader2 size={22} className="animate-spin" /> : <Upload size={22} />}
                      </div>
                      <h3 className="mt-4 text-center text-xl font-semibold text-[var(--text-primary)]">
                        {runningCount > 0 ? 'Waiting for the first result' : 'No completed checks yet'}
                      </h3>
                      <p className="mx-auto mt-3 max-w-xl text-center text-sm leading-6 text-[var(--text-secondary)]">
                        {runningCount > 0
                          ? 'The current assignment is still running. This space will show the verdict, top flagged pairs, and report links as soon as the first result is ready.'
                          : 'Upload an assignment to generate the first result. Once a check completes, you will see the key verdict and report actions here.'}
                      </p>
                      <div className="mt-6 flex justify-center">
                        <Link
                          href="/upload"
                          className="theme-button-primary inline-flex items-center gap-2 rounded-2xl px-5 py-3 text-sm font-semibold"
                        >
                          <Upload size={16} />
                          Upload Assignment
                        </Link>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-5">
                      <div
                        className={`rounded-[24px] border px-5 py-5 ${
                          latestFlaggedResults.length > 0
                            ? 'border-amber-500/20 bg-amber-500/[0.08]'
                            : 'border-emerald-500/20 bg-emerald-500/[0.08]'
                        }`}
                      >
                        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                          <div className="min-w-0">
                            <div className="flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
                              {latestFlaggedResults.length > 0 ? (
                                <AlertTriangle size={16} className="text-amber-600" />
                              ) : (
                                <CheckCircle2 size={16} className="text-emerald-600" />
                              )}
                              {latestFlaggedResults.length > 0
                                ? `${latestFlaggedResults.length} pair${latestFlaggedResults.length === 1 ? '' : 's'} flagged for review`
                                : 'No pairs crossed the review threshold'}
                            </div>
                            <div className="mt-3 flex flex-wrap items-center gap-2">
                              <ReviewBadge status={latestReviewStatus} />
                              {latestCompleted.review_updated_at && (
                                <span className="text-xs text-[var(--text-muted)]">
                                  Updated {formatTimestamp(latestCompleted.review_updated_at)}
                                </span>
                              )}
                            </div>
                            <div className="mt-3">
                              <div className="text-xl font-semibold text-[var(--text-primary)]">{getAssignmentTitle(latestCompleted)}</div>
                              {getReferenceLabel(latestCompleted) && (
                                <div className="mt-1 text-sm text-[var(--text-muted)]">{getReferenceLabel(latestCompleted)}</div>
                              )}
                            </div>
                            <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">
                              {latestHighestMatch
                                ? `Highest match: ${formatPercent(latestHighestMatch.score)} between ${latestHighestMatch.file_a} and ${latestHighestMatch.file_b}. Open the result to inspect the evidence and engine breakdown.`
                                : `The latest assignment finished below the ${formatPercent(latestThreshold)} review threshold. You can still open the result and export reports if needed.`}
                            </p>
                            {latestCompleted.review_notes && (
                              <div className="mt-3 rounded-[18px] border border-[color:var(--border)] bg-[var(--surface)] px-4 py-3 text-sm leading-6 text-[var(--text-secondary)]">
                                {truncateText(latestCompleted.review_notes)}
                              </div>
                            )}
                          </div>

                          <div className="flex flex-wrap gap-3">
                            <Link
                              href={`/results/${latestCompleted.id}`}
                              className="theme-button-primary inline-flex items-center gap-2 rounded-2xl px-5 py-3 text-sm font-semibold"
                            >
                              <FileSearch size={16} />
                              Open Result
                            </Link>
                            <Link
                              href="/upload"
                              className="theme-button-secondary inline-flex items-center gap-2 rounded-2xl px-5 py-3 text-sm font-semibold"
                            >
                              <Upload size={16} />
                              Start New Check
                            </Link>
                          </div>
                        </div>
                      </div>

                      <div className="grid gap-3 sm:grid-cols-3">
                        <SummaryChip label="Files checked" value={latestCompleted.file_count || 0} />
                        <SummaryChip label="Flagged pairs" value={latestSummary.suspicious_pairs || 0} />
                        <SummaryChip label="Review status" value={formatReviewStatus(latestReviewStatus)} />
                      </div>

                      <div>
                        <div className="flex items-end justify-between gap-4">
                          <div>
                            <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                              Top flagged pairs
                            </div>
                            <p className="mt-2 text-sm text-[var(--text-secondary)]">
                              The most important findings from the latest completed assignment.
                            </p>
                          </div>

                          <Link href={`/results/${latestCompleted.id}`} className="theme-link inline-flex items-center gap-1 text-sm font-medium">
                            Review all
                            <ChevronRight size={16} />
                          </Link>
                        </div>

                        {latestPreviewResults.length === 0 ? (
                          <div className="theme-card-muted mt-4 rounded-[22px] px-5 py-6 text-sm leading-6 text-[var(--text-secondary)]">
                            No flagged pairs were found in the latest completed assignment. The full result is still available if you want to review all comparisons.
                          </div>
                        ) : (
                          <div className="mt-4 space-y-3">
                            {latestPreviewResults.map((result) => (
                              <FindingPreviewRow key={`${result.file_a}-${result.file_b}`} result={result} />
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              <div className="theme-card rounded-[30px] overflow-hidden">
                <div className="theme-section-line px-6 py-5">
                  <div className="flex items-end justify-between gap-4">
                    <div>
                      <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                        Recent checks
                      </div>
                      <h2 className="font-display mt-2 text-2xl font-semibold text-[var(--text-primary)]">
                        Open a recent assignment quickly
                      </h2>
                    </div>

                    <Link href="/upload" className="theme-link inline-flex items-center gap-1 text-sm font-medium">
                      Start new check
                      <ChevronRight size={16} />
                    </Link>
                  </div>
                </div>

                {loading ? (
                  <div className="space-y-3 px-6 pb-6">
                    {[1, 2, 3, 4].map((item) => (
                      <div key={item} className="h-20 rounded-[22px] skeleton" />
                    ))}
                  </div>
                ) : recentJobs.length === 0 ? (
                  <div className="px-6 pb-6">
                    <div className="theme-card-muted rounded-[24px] px-6 py-12 text-center">
                      <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-[var(--surface)] text-[var(--accent-blue)]">
                        <Upload size={22} />
                      </div>
                      <h3 className="mt-4 text-xl font-semibold text-[var(--text-primary)]">No checks yet</h3>
                      <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-[var(--text-secondary)]">
                        Upload an assignment to start the first similarity check. The latest results will appear here.
                      </p>
                      <Link
                        href="/upload"
                        className="theme-button-primary mt-6 inline-flex items-center gap-2 rounded-2xl px-5 py-3 text-sm font-semibold"
                      >
                        <Upload size={16} />
                        Upload Assignment
                      </Link>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-3 px-6 pb-6">
                    {recentJobs.map((job) => (
                      <div
                        key={job.id}
                        className="theme-card-muted rounded-[22px] px-4 py-4 transition hover:-translate-y-0.5"
                      >
                        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                          <div className="min-w-0">
                            <div className="font-medium text-[var(--text-primary)]">{getAssignmentTitle(job)}</div>
                            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-[var(--text-muted)]">
                              {getReferenceLabel(job) && <span>{getReferenceLabel(job)}</span>}
                              <span>{job.file_count || 0} files</span>
                              <span>{formatTimestamp(job.created_at)}</span>
                            </div>
                          </div>

                          <div className="flex flex-wrap items-center gap-3">
                            <StatusBadge status={job.status} />
                            {job.status === 'completed' && <ReviewBadge status={getReviewStatus(job)} />}
                            {job.status === 'completed' ? (
                              <Link
                                href={`/results/${job.id}`}
                                className="theme-link inline-flex items-center gap-1 text-sm font-medium"
                              >
                                Open
                                <ArrowRight size={15} />
                              </Link>
                            ) : (
                              <span className="inline-flex items-center gap-2 text-sm text-[var(--text-muted)]">
                                <Loader2 size={14} className="animate-spin" />
                                Running
                              </span>
                            )}
                          </div>
                        </div>
                        {job.review_notes && (
                          <div className="mt-3 text-xs leading-5 text-[var(--text-secondary)]">
                            {truncateText(job.review_notes, 96)}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="space-y-4">
              <div className="theme-card rounded-[28px] overflow-hidden">
                <div className="theme-section-line px-5 py-5">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                    Report center
                  </div>
                  <h2 className="font-display mt-2 text-xl font-semibold text-[var(--text-primary)]">
                    Export the latest completed check
                  </h2>
                </div>

                <div className="px-5 pb-5">
                  {!latestCompleted ? (
                    <div className="theme-card-muted rounded-[22px] px-4 py-5 text-sm leading-6 text-[var(--text-secondary)]">
                      Reports appear here after the first assignment finishes. Professors can then export the HTML summary, structured JSON, or committee report directly from the dashboard home.
                    </div>
                  ) : (
                    <div className="space-y-3">
                      <div className="theme-card-muted rounded-[22px] px-4 py-4">
                        <div className="text-sm font-semibold text-[var(--text-primary)]">{getAssignmentTitle(latestCompleted)}</div>
                        <div className="mt-1 text-xs text-[var(--text-muted)]">
                          Ready {formatTimestamp(latestCompleted.created_at)}
                        </div>
                      </div>

                      <ReportLink
                        href={`${API}/report/${latestCompleted.id}/download`}
                        icon={FileText}
                        title="HTML report"
                        description="Open the formatted report with verdict summary and evidence."
                      />
                      <ReportLink
                        href={`${API}/report/${latestCompleted.id}/download-json`}
                        icon={Download}
                        title="JSON data"
                        description="Download the structured analysis output for records or tooling."
                      />
                      <ReportLink
                        href={`${API}/report/${latestCompleted.id}/committee`}
                        icon={Shield}
                        title="Committee report"
                        description="Open the evidence-focused report prepared for formal review."
                      />

                      <Link
                        href={`/results/${latestCompleted.id}`}
                        className="theme-button-secondary inline-flex w-full items-center justify-center gap-2 rounded-2xl px-4 py-3 text-sm font-semibold"
                      >
                        <FileSearch size={16} />
                        Open Latest Result
                      </Link>
                    </div>
                  )}
                </div>
              </div>

              <ActionCard
                href="/upload?mode=individual"
                icon={Upload}
                title="Upload individual files"
                description="Use this when the submissions are already split into separate source files."
              />
              <ActionCard
                href="/upload?mode=zip"
                icon={FolderArchive}
                title="Upload one ZIP archive"
                description="Use this when the assignment comes as a folder export or submission bundle."
              />
              <ActionCard
                href="/settings"
                icon={Settings2}
                title="Review default threshold"
                description="Adjust the similarity cutoff before you start a new check."
              />
            </div>
          </section>
        </div>
      </div>
    </DashboardLayout>
  );
}

const GuideStep = ({ index, title, description }) => (
  <div className="rounded-2xl border border-[color:var(--border)] bg-[var(--surface-muted)] px-4 py-4">
    <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--accent-blue)]">{index}</div>
    <div className="mt-2 text-base font-semibold text-[var(--text-primary)]">{title}</div>
    <div className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">{description}</div>
  </div>
);

const SummaryChip = ({ label, value }) => (
  <div className="theme-card-muted rounded-[22px] px-4 py-4">
    <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">{label}</div>
    <div className="mt-2 text-2xl font-semibold text-[var(--text-primary)]">{value}</div>
  </div>
);

const ReviewBadge = ({ status }) => (
  <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${getReviewTone(status)}`}>
    {formatReviewStatus(status)}
  </span>
);

const FindingPreviewRow = ({ result }) => {
  const risk = result.score >= 0.9 ? 'Critical' : result.score >= 0.75 ? 'High' : 'Review';
  const badgeTone = result.score >= 0.9
    ? 'border-red-500/20 bg-red-500/10 text-red-600'
    : result.score >= 0.75
      ? 'border-amber-500/20 bg-amber-500/10 text-amber-600'
      : 'border-blue-600/20 bg-blue-600/10 text-blue-600';
  const barTone = result.score >= 0.9 ? 'bg-red-500' : result.score >= 0.75 ? 'bg-amber-500' : 'bg-blue-600';

  return (
    <div className="theme-card-muted rounded-[22px] px-4 py-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm font-semibold text-[var(--text-primary)] break-all">
            {result.file_a}
            <span className="mx-2 text-[var(--text-muted)]">vs</span>
            {result.file_b}
          </div>
          <div className="mt-1 text-xs text-[var(--text-muted)]">
            {getTopFeature(result)} • Ready for evidence review
          </div>
        </div>
        <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${badgeTone}`}>
          {risk} {formatPercent(result.score)}
        </span>
      </div>

      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-[color:var(--border)]">
        <div className={`h-full rounded-full ${barTone}`} style={{ width: `${Math.max(result.score * 100, 4)}%` }} />
      </div>
    </div>
  );
};

const ReportLink = ({ href, icon: Icon, title, description }) => (
  <a
    href={href}
    className="theme-card-muted group flex items-start gap-3 rounded-[22px] px-4 py-4 transition hover:-translate-y-0.5"
  >
    <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[var(--surface)] text-[var(--accent-blue)]">
      <Icon size={17} />
    </div>
    <div className="min-w-0 flex-1">
      <div className="text-sm font-semibold text-[var(--text-primary)]">{title}</div>
      <div className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">{description}</div>
    </div>
    <ArrowRight size={16} className="mt-1 text-[var(--text-muted)] transition group-hover:translate-x-0.5" />
  </a>
);

const ActionCard = ({ href, icon: Icon, title, description }) => (
  <Link
    href={href}
    className="theme-card group block rounded-[28px] px-5 py-5 transition hover:-translate-y-0.5"
  >
    <div className="flex items-start justify-between gap-4">
      <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-600/10 text-blue-600">
        <Icon size={18} />
      </div>
      <ArrowRight size={17} className="text-[var(--text-muted)] transition group-hover:translate-x-0.5" />
    </div>
    <div className="mt-5 text-lg font-semibold text-[var(--text-primary)]">{title}</div>
    <div className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">{description}</div>
  </Link>
);

const StatusBadge = ({ status }) => {
  const toneMap = {
    analyzing: 'border-amber-500/20 bg-amber-500/10 text-amber-600',
    completed: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-600',
    failed: 'border-red-500/20 bg-red-500/10 text-red-600',
    processing: 'border-blue-600/20 bg-blue-600/10 text-blue-600',
  };

  return (
    <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${toneMap[status] || toneMap.processing}`}>
      {status}
    </span>
  );
};
