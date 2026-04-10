// @ts-nocheck
'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { useAuth } from '@/components/AuthProvider';
import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import {
  ArrowLeft,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  CheckCircle2,
  GripVertical,
  LayoutGrid,
  EyeOff,
  ChevronRight,
  Download,
  FileSearch,
  FileText,
  FolderArchive,
  Loader2,
  Plus,
  RotateCcw,
  Settings2,
  Shield,
  Upload,
  Users,
} from 'lucide-react';

const API = '';
const HOME_CARD_STORAGE_KEY = 'integritydesk-home-layout-v1';
const HOME_CARD_DEFAULT_ORDER = [
  'recent-checks',
  'report-center',
  'upload-files',
  'upload-zip',
  'settings',
];
const HOME_CARD_OPTIONAL_ORDER = ['benchmark-suite', 'admin-console'];
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

function getHomeCardStorageKey(userId) {
  return `${HOME_CARD_STORAGE_KEY}:${userId || 'guest'}`;
}

function normalizeCardOrder(value, validIds = [...HOME_CARD_DEFAULT_ORDER, ...HOME_CARD_OPTIONAL_ORDER]) {
  const validIdSet = new Set(validIds);
  const preferredOrder = validIds;
  const seen = new Set();
  const normalized = [];

  if (Array.isArray(value)) {
    value.forEach((id) => {
      if (validIdSet.has(id) && !seen.has(id)) {
        normalized.push(id);
        seen.add(id);
      }
    });
  }

  preferredOrder.forEach((id) => {
    if (!seen.has(id)) {
      normalized.push(id);
    }
  });

  return normalized;
}

function normalizeHiddenCards(value, validIds = [...HOME_CARD_DEFAULT_ORDER, ...HOME_CARD_OPTIONAL_ORDER]) {
  const validIdSet = new Set(validIds);
  const seen = new Set();
  const normalized = [];

  if (!Array.isArray(value)) {
    return normalized;
  }

  value.forEach((id) => {
    if (validIdSet.has(id) && !seen.has(id)) {
      normalized.push(id);
      seen.add(id);
    }
  });

  return normalized;
}

export default function Home() {
  const { user, loading: authLoading } = useAuth();
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [cardOrder, setCardOrder] = useState(HOME_CARD_DEFAULT_ORDER);
  const [hiddenCards, setHiddenCards] = useState([]);
  const [editMode, setEditMode] = useState(false);
  const [activeCardId, setActiveCardId] = useState(null);
  const [draggedCardId, setDraggedCardId] = useState(null);
  const [layoutLoaded, setLayoutLoaded] = useState(false);
  const longPressTimerRef = useRef(null);
  const longPressTriggeredRef = useRef(false);
  const availableCardIds = user?.role === 'admin'
    ? [...HOME_CARD_DEFAULT_ORDER, ...HOME_CARD_OPTIONAL_ORDER]
    : [...HOME_CARD_DEFAULT_ORDER, 'benchmark-suite'];
  const optionalCardIds = availableCardIds.filter((id) => !HOME_CARD_DEFAULT_ORDER.includes(id));

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

  useEffect(() => {
    if (authLoading || typeof window === 'undefined') {
      return;
    }

    setEditMode(false);
    setActiveCardId(null);

    try {
      const rawLayout = window.localStorage.getItem(getHomeCardStorageKey(user?.id));

      if (!rawLayout) {
        setCardOrder(availableCardIds);
        setHiddenCards(optionalCardIds);
      } else {
        const parsedLayout = JSON.parse(rawLayout);
        setCardOrder(normalizeCardOrder(parsedLayout?.order, availableCardIds));
        setHiddenCards(normalizeHiddenCards(parsedLayout?.hidden, availableCardIds));
      }
    } catch {
      setCardOrder(availableCardIds);
      setHiddenCards(optionalCardIds);
    }

    setLayoutLoaded(true);
  }, [authLoading, availableCardIds.join('|'), optionalCardIds.join('|'), user?.id]);

  useEffect(() => {
    if (!layoutLoaded || typeof window === 'undefined') {
      return;
    }

    window.localStorage.setItem(
      getHomeCardStorageKey(user?.id),
      JSON.stringify({
        order: normalizeCardOrder(cardOrder, availableCardIds),
        hidden: normalizeHiddenCards(hiddenCards, availableCardIds),
      })
    );
  }, [availableCardIds.join('|'), cardOrder, hiddenCards, layoutLoaded, user?.id]);

  useEffect(() => () => {
    if (longPressTimerRef.current) {
      clearTimeout(longPressTimerRef.current);
    }
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

  const recentJobs = jobs.slice(0, 4);
  const latestCompleted = jobs.find((job) => job.status === 'completed');
  const runningCount = jobs.filter((job) => ['processing', 'analyzing'].includes(job.status)).length;
  const latestFlaggedResults = latestCompleted ? getFlaggedResults(latestCompleted) : [];
  const latestPreviewResults = latestFlaggedResults.slice(0, 3);
  const latestThreshold = getThreshold(latestCompleted);
  const latestSummary = latestCompleted?.summary || {};
  const latestHighestMatch = latestFlaggedResults[0];
  const latestReviewStatus = getReviewStatus(latestCompleted);
  const visibleCardIds = normalizeCardOrder(cardOrder, availableCardIds).filter((id) => !hiddenCards.includes(id));

  const startCardPress = (cardId) => {
    if (editMode) {
      return;
    }

    longPressTriggeredRef.current = false;
    if (longPressTimerRef.current) {
      clearTimeout(longPressTimerRef.current);
    }

    longPressTimerRef.current = setTimeout(() => {
      longPressTriggeredRef.current = true;
      setEditMode(true);
      setActiveCardId(cardId);
    }, 550);
  };

  const stopCardPress = () => {
    if (longPressTimerRef.current) {
      clearTimeout(longPressTimerRef.current);
      longPressTimerRef.current = null;
    }
  };

  const handleCardClickCapture = (event) => {
    if (longPressTriggeredRef.current) {
      event.preventDefault();
      event.stopPropagation();
      longPressTriggeredRef.current = false;
    }
  };

  const moveCard = (cardId, direction) => {
    const currentVisible = visibleCardIds;
    const currentIndex = currentVisible.indexOf(cardId);
    const nextIndex = currentIndex + direction;

    if (currentIndex === -1 || nextIndex < 0 || nextIndex >= currentVisible.length) {
      return;
    }

    const targetId = currentVisible[nextIndex];
    const nextOrder = [...cardOrder];
    const sourceIndex = nextOrder.indexOf(cardId);
    const targetIndex = nextOrder.indexOf(targetId);

    nextOrder[sourceIndex] = targetId;
    nextOrder[targetIndex] = cardId;
    setCardOrder(nextOrder);
    setActiveCardId(cardId);
  };

  const moveCardBefore = (draggedId, targetId) => {
    if (!draggedId || !targetId || draggedId === targetId) {
      return;
    }

    const nextOrder = cardOrder.filter((id) => id !== draggedId);
    const targetIndex = nextOrder.indexOf(targetId);

    if (targetIndex === -1) {
      return;
    }

    nextOrder.splice(targetIndex, 0, draggedId);
    setCardOrder(nextOrder);
    setActiveCardId(draggedId);
  };

  const hideCard = (cardId) => {
    if (hiddenCards.includes(cardId)) {
      return;
    }

    setHiddenCards((current) => [...current, cardId]);
    setActiveCardId((current) => (current === cardId ? null : current));
  };

  const restoreCard = (cardId) => {
    setHiddenCards((current) => current.filter((id) => id !== cardId));
    setCardOrder((current) => normalizeCardOrder(current, availableCardIds));
    setEditMode(true);
    setActiveCardId(cardId);
  };

  const resetLayout = () => {
    setCardOrder(availableCardIds);
    setHiddenCards(optionalCardIds);
    setEditMode(false);
    setActiveCardId(null);
    setDraggedCardId(null);
  };

  const dashboardCards = {
    'recent-checks': {
      id: 'recent-checks',
      label: 'Recent checks',
      className: 'xl:col-span-8 lg:col-span-12',
      content: (
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
             <div className="space-y-4 px-6 pb-6">
               {[1, 2, 3, 4].map((item) => (
                 <div key={item} className="rounded-[22px] border border-[color:var(--border)] bg-[var(--surface-muted)] p-4">
                   <div className="flex items-center gap-4">
                     <div className="h-12 w-12 rounded-2xl skeleton" />
                     <div className="flex-1 space-y-2">
                       <div className="h-4 rounded skeleton w-3/4" />
                       <div className="h-3 rounded skeleton w-1/2" />
                     </div>
                     <div className="h-6 w-16 rounded-full skeleton" />
                   </div>
                 </div>
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
      ),
    },
    'report-center': {
      id: 'report-center',
      label: 'Report center',
      className: 'xl:col-span-4 lg:col-span-6',
      content: (
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
      ),
    },
    'upload-files': {
      id: 'upload-files',
      label: 'Upload individual files',
      className: 'xl:col-span-4 lg:col-span-6 sm:col-span-12',
      content: (
        <ActionCard
          href="/upload?mode=individual"
          icon={Upload}
          title="Upload individual files"
          description="Use this when the submissions are already split into separate source files."
        />
      ),
    },
    'upload-zip': {
      id: 'upload-zip',
      label: 'Upload one ZIP archive',
      className: 'xl:col-span-4 lg:col-span-6 sm:col-span-12',
      content: (
        <ActionCard
          href="/upload?mode=zip"
          icon={FolderArchive}
          title="Upload one ZIP archive"
          description="Use this when the assignment comes as a folder export or submission bundle."
        />
      ),
    },
    settings: {
      id: 'settings',
      label: 'Review default threshold',
      className: 'xl:col-span-4 lg:col-span-6 sm:col-span-12',
      content: (
        <ActionCard
          href="/settings"
          icon={Settings2}
          title="Review default threshold"
          description="Adjust the similarity cutoff before you start a new check."
        />
      ),
    },
    'benchmark-suite': {
      id: 'benchmark-suite',
      label: 'Benchmark suite',
      className: 'xl:col-span-4 lg:col-span-6 sm:col-span-12',
      content: (
        <ActionCard
          href="/benchmark"
          icon={BarChart3}
          title="Open benchmark suite"
          description="Compare detection engines, review score patterns, and export benchmark reports."
        />
      ),
    },
    ...(user?.role === 'admin'
      ? {
          'admin-console': {
            id: 'admin-console',
            label: 'Admin console',
            className: 'xl:col-span-4 lg:col-span-6 sm:col-span-12',
            content: (
              <ActionCard
                href="/admin"
                icon={Users}
                title="Open admin console"
                description="Manage accounts, roles, and workspace access from the dashboard."
              />
            ),
          },
        }
      : {}),
  };
  return (
    <DashboardLayout>
      <div className="px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <div className="space-y-8 lg:space-y-10">
          <section className="theme-card-strong theme-section-line relative overflow-hidden rounded-[32px] px-6 py-6 lg:px-8 lg:py-8">
            <div className="absolute right-0 top-0 h-40 w-40 rounded-full bg-blue-600/[0.08] blur-3xl" />

            <div className="relative grid gap-8 xl:grid-cols-[1.2fr_1fr]">
              <div className="space-y-8">
                <div className="inline-flex items-center gap-2 rounded-full border border-blue-600/10 bg-blue-600/[0.06] px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.2em] text-blue-600">
                  <Shield size={13} />
                  Integrity workspace
                </div>

                <div className="space-y-6">
                  <h1 className="font-display max-w-4xl text-3xl font-semibold leading-tight text-[var(--text-primary)] sm:text-4xl lg:text-5xl">
                    Review suspicious similarity, benchmark tools, and move through cases without dashboard clutter.
                  </h1>
                  <p className="max-w-3xl text-sm leading-7 text-[var(--text-secondary)] sm:text-base lg:text-lg">
                    Use one workspace for assignment review, benchmark comparisons, and follow-up decisions without
                    bouncing between separate tools.
                  </p>
                </div>

                <div className="flex flex-wrap gap-3 lg:gap-4">
                  <Link
                    href="/upload?mode=individual"
                    className="theme-button-primary inline-flex items-center gap-2 rounded-2xl px-6 py-3.5 text-sm font-semibold transition hover:scale-105"
                  >
                    <Upload size={16} />
                    Upload Files
                  </Link>

                  <Link
                    href="/upload?mode=zip"
                    className="theme-button-secondary inline-flex items-center gap-2 rounded-2xl px-6 py-3.5 text-sm font-semibold transition hover:scale-105"
                  >
                    <FolderArchive size={16} />
                    Upload ZIP
                  </Link>

                  {latestCompleted && (
                    <Link
                      href={`/results/${latestCompleted.id}`}
                      className="theme-button-secondary inline-flex items-center gap-2 rounded-2xl px-6 py-3.5 text-sm font-semibold transition hover:scale-105"
                    >
                      <FileSearch size={16} />
                      Open Latest Result
                    </Link>
                  )}
                </div>

                <div className="flex flex-wrap gap-3 lg:gap-4">
                  <span className="rounded-full border border-[color:var(--border)] bg-[var(--surface-muted)] px-4 py-2 text-sm text-[var(--text-secondary)]">
                    {runningCount > 0 ? `${runningCount} check${runningCount === 1 ? '' : 's'} in progress` : 'No checks running'}
                  </span>
                  <span className="rounded-full border border-[color:var(--border)] bg-[var(--surface-muted)] px-4 py-2 text-sm text-[var(--text-secondary)]">
                    {latestCompleted ? `Latest result ready ${formatTimestamp(latestCompleted.created_at)}` : 'No completed result yet'}
                  </span>
                </div>
              </div>

              <div className="theme-card rounded-[28px] overflow-hidden">
                <div className="theme-section-line px-5 py-5">
                  <div className="flex items-end justify-between gap-4">
                    <div>
                      <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                        Latest verdict
                      </div>
                      <h2 className="font-display mt-2 text-xl font-semibold text-[var(--text-primary)]">
                        Review the latest completed check
                      </h2>
                    </div>

                    {latestCompleted && (
                      <Link href={`/results/${latestCompleted.id}`} className="theme-link inline-flex items-center gap-1 text-sm font-medium">
                        Open
                        <ChevronRight size={16} />
                      </Link>
                    )}
                  </div>
                </div>

                <div className="px-5 pb-5">
                  {!latestCompleted ? (
                    <div className="theme-card-muted rounded-[22px] px-5 py-8">
                      <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-[var(--surface)] text-[var(--accent-blue)]">
                        {runningCount > 0 ? <Loader2 size={22} className="animate-spin" /> : <Upload size={22} />}
                      </div>
                      <h3 className="mt-4 text-center text-lg font-semibold text-[var(--text-primary)]">
                        {runningCount > 0 ? 'Waiting for the first result' : 'No completed checks yet'}
                      </h3>
                      <p className="mx-auto mt-3 max-w-md text-center text-sm leading-6 text-[var(--text-secondary)]">
                        {runningCount > 0
                          ? 'The current check is still running. This panel will update as soon as the latest verdict is ready.'
                          : 'Upload submissions to generate the first result. The latest verdict and quick actions will appear here.'}
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
                    <div className="space-y-4">
                      <div
                        className={`rounded-[22px] border px-4 py-4 ${
                          latestFlaggedResults.length > 0
                            ? 'border-amber-500/20 bg-amber-500/[0.08]'
                            : 'border-emerald-500/20 bg-emerald-500/[0.08]'
                        }`}
                      >
                        <div className="grid gap-4 2xl:grid-cols-[1.2fr_0.8fr] 2xl:items-start">
                          <div className="min-w-0">
                            <div className="flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
                              {latestFlaggedResults.length > 0 ? (
                                <AlertTriangle size={16} className="text-amber-600" />
                              ) : (
                                <CheckCircle2 size={16} className="text-emerald-600" />
                              )}
                              {latestFlaggedResults.length > 0
                                ? `${latestFlaggedResults.length} pair${latestFlaggedResults.length === 1 ? '' : 's'} flagged`
                                : 'No pairs crossed the review threshold'}
                            </div>
                            <div className="mt-3">
                              <div className="text-lg font-semibold text-[var(--text-primary)]">{getAssignmentTitle(latestCompleted)}</div>
                              {getReferenceLabel(latestCompleted) && (
                                <div className="mt-1 text-sm text-[var(--text-muted)]">{getReferenceLabel(latestCompleted)}</div>
                              )}
                            </div>
                            <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">
                              {latestHighestMatch
                                ? `Highest match: ${formatPercent(latestHighestMatch.score)} between ${latestHighestMatch.file_a} and ${latestHighestMatch.file_b}.`
                                : `The latest assignment finished below the ${formatPercent(latestThreshold)} review threshold.`}
                            </p>
                          </div>

                          <div className="flex flex-wrap content-start gap-2 2xl:justify-end">
                            <ReviewBadge status={latestReviewStatus} />
                            {latestCompleted.review_updated_at && (
                              <span className="inline-flex items-center rounded-full border border-[color:var(--border)] bg-[var(--surface)] px-2.5 py-1 text-xs text-[var(--text-muted)]">
                                Updated {formatTimestamp(latestCompleted.review_updated_at)}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      <div className="grid gap-3 sm:grid-cols-3">
                        <SummaryChip label="Files checked" value={latestCompleted.file_count || 0} />
                        <SummaryChip label="Flagged pairs" value={latestSummary.suspicious_pairs || 0} />
                        <SummaryChip label="Review status" value={formatReviewStatus(latestReviewStatus)} />
                      </div>

                      {latestPreviewResults.length > 0 && (
                        <div>
                          <div className="flex items-end justify-between gap-4">
                            <div>
                              <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                                Top flagged pairs
                              </div>
                              <p className="mt-2 text-sm text-[var(--text-secondary)]">
                                Quick review targets from the latest result.
                              </p>
                            </div>

                            <Link href={`/results/${latestCompleted.id}`} className="theme-link inline-flex items-center gap-1 text-sm font-medium">
                              Review all
                              <ChevronRight size={16} />
                            </Link>
                          </div>

                          <div className="mt-4">
                            {latestPreviewResults.slice(0, 1).map((result) => (
                              <FindingPreviewRow key={`${result.file_a}-${result.file_b}`} result={result} />
                            ))}
                          </div>
                        </div>
                      )}

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
                  )}
                </div>
              </div>
            </div>
          </section>

          <section className="space-y-4">
            <div className="flex flex-col gap-3 rounded-[28px] border border-[color:var(--border)] bg-[var(--surface-muted)] px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="space-y-1">
                <div className="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                  <LayoutGrid size={14} />
                  Dashboard layout
                </div>
                <p className="text-sm text-[var(--text-secondary)]">
                  {editMode
                    ? 'Layout mode is on. Drag cards to reorder them, hide the ones you do not need, or add more from the card library.'
                    : 'Press and hold any card for a moment to customize the home dashboard.'}
                </p>
              </div>

              <div className="flex flex-wrap gap-2">
                {editMode ? (
                  <>
                    <button
                      type="button"
                      onClick={resetLayout}
                      className="theme-button-secondary inline-flex items-center gap-2 rounded-2xl px-4 py-2 text-sm font-semibold"
                    >
                      <RotateCcw size={15} />
                      Reset
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setEditMode(false);
                        setActiveCardId(null);
                      }}
                      className="theme-button-primary inline-flex items-center gap-2 rounded-2xl px-4 py-2 text-sm font-semibold"
                    >
                      Done
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    onClick={() => setEditMode(true)}
                    className="theme-button-secondary inline-flex items-center gap-2 rounded-2xl px-4 py-2 text-sm font-semibold"
                  >
                    <GripVertical size={15} />
                    Customize cards
                  </button>
                )}
              </div>
            </div>

            {editMode && hiddenCards.length > 0 && (
              <div className="theme-card rounded-[28px] px-5 py-4">
                <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                  <Plus size={14} />
                  Add cards
                </div>
                <p className="mt-2 text-sm text-[var(--text-secondary)]">
                  Bring hidden or optional cards back onto the home dashboard.
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {hiddenCards.map((cardId) => (
                    <button
                      key={cardId}
                      type="button"
                      onClick={() => restoreCard(cardId)}
                      className="theme-button-secondary inline-flex items-center gap-2 rounded-2xl px-4 py-2 text-sm font-semibold"
                    >
                      <Plus size={14} />
                      Add {dashboardCards[cardId]?.label || cardId}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {visibleCardIds.length === 0 ? (
              <div className="theme-card rounded-[30px] px-6 py-10 text-center">
                <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-[var(--surface-muted)] text-[var(--accent-blue)]">
                  <LayoutGrid size={20} />
                </div>
                <h2 className="mt-4 text-xl font-semibold text-[var(--text-primary)]">All home cards are hidden</h2>
                <p className="mx-auto mt-3 max-w-lg text-sm leading-6 text-[var(--text-secondary)]">
                  Turn layout mode on and restore the cards you want to keep on your home dashboard.
                </p>
              </div>
            ) : (
              <div className="grid gap-6 lg:gap-8 xl:grid-cols-12">
                {visibleCardIds.map((cardId) => {
                  const card = dashboardCards[cardId];
                  const cardIndex = visibleCardIds.indexOf(cardId);

                  return (
                    <EditableDashboardCard
                      key={cardId}
                      className={card.className}
                      label={card.label}
                      editMode={editMode}
                      isActive={activeCardId === cardId}
                      canMoveEarlier={cardIndex > 0}
                      canMoveLater={cardIndex < visibleCardIds.length - 1}
                      onActivate={() => {
                        setEditMode(true);
                        setActiveCardId(cardId);
                      }}
                      onMoveEarlier={() => moveCard(cardId, -1)}
                      onMoveLater={() => moveCard(cardId, 1)}
                      onHide={() => hideCard(cardId)}
                      onDragStart={() => {
                        setDraggedCardId(cardId);
                        setActiveCardId(cardId);
                        setEditMode(true);
                      }}
                      onDragOver={() => {
                        if (editMode) {
                          setActiveCardId(cardId);
                        }
                      }}
                      onDrop={() => {
                        moveCardBefore(draggedCardId, cardId);
                        setDraggedCardId(null);
                      }}
                      onDragEnd={() => setDraggedCardId(null)}
                      isDragging={draggedCardId === cardId}
                      onPressStart={() => startCardPress(cardId)}
                      onPressEnd={stopCardPress}
                      onClickCapture={handleCardClickCapture}
                    >
                      {card.content}
                    </EditableDashboardCard>
                  );
                })}
              </div>
            )}
          </section>
        </div>
      </div>
    </DashboardLayout>
  );
}

const EditableDashboardCard = ({
  children,
  className,
  label,
  editMode,
  isActive,
  isDragging,
  canMoveEarlier,
  canMoveLater,
  onActivate,
  onMoveEarlier,
  onMoveLater,
  onHide,
  onDragStart,
  onDragOver,
  onDrop,
  onDragEnd,
  onPressStart,
  onPressEnd,
  onClickCapture,
}) => (
  <div
    className={`relative ${className || ''}`}
    draggable={editMode}
    onDragStart={(event) => {
      if (!editMode) {
        return;
      }

      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', label);
      onDragStart?.();
    }}
    onDragOver={(event) => {
      if (!editMode) {
        return;
      }

      event.preventDefault();
      event.dataTransfer.dropEffect = 'move';
      onDragOver?.();
    }}
    onDrop={(event) => {
      if (!editMode) {
        return;
      }

      event.preventDefault();
      onDrop?.();
    }}
    onDragEnd={onDragEnd}
    onMouseDown={onPressStart}
    onMouseUp={onPressEnd}
    onMouseLeave={onPressEnd}
    onTouchStart={onPressStart}
    onTouchEnd={onPressEnd}
    onTouchCancel={onPressEnd}
    onClickCapture={onClickCapture}
  >
    <div
      className={`transition ${editMode ? 'pointer-events-none select-none' : ''} ${
        isActive ? 'scale-[0.995] opacity-95' : ''
      } ${
        isDragging ? 'opacity-60' : ''
      }`}
    >
      {children}
    </div>

    {editMode && (
      <div
        className={`pointer-events-none absolute inset-0 rounded-[30px] border-2 border-dashed bg-blue-600/[0.04] ${
          isActive ? 'border-blue-600/45 shadow-[0_0_0_1px_rgba(37,99,235,0.12)]' : 'border-blue-600/30'
        }`}
      >
        <div className="pointer-events-auto absolute left-3 top-3 inline-flex items-center gap-2 rounded-full border border-blue-600/15 bg-[var(--surface)] px-3 py-1.5 text-xs font-semibold text-[var(--text-primary)] shadow-sm">
          <GripVertical size={14} className="text-blue-600" />
          Drag {label}
        </div>

        <div className="pointer-events-auto absolute right-3 top-3 flex flex-wrap justify-end gap-2">
          <button
            type="button"
            onClick={onActivate}
            className={`inline-flex items-center gap-1 rounded-full border px-3 py-1.5 text-xs font-semibold ${
              isActive
                ? 'border-blue-600/20 bg-blue-600/10 text-blue-600'
                : 'border-[color:var(--border)] bg-[var(--surface)] text-[var(--text-secondary)]'
            }`}
          >
            Select
          </button>
          <button
            type="button"
            onClick={onMoveEarlier}
            disabled={!canMoveEarlier}
            className="inline-flex items-center gap-1 rounded-full border border-[color:var(--border)] bg-[var(--surface)] px-3 py-1.5 text-xs font-semibold text-[var(--text-secondary)] disabled:cursor-not-allowed disabled:opacity-40"
          >
            <ArrowLeft size={13} />
            Earlier
          </button>
          <button
            type="button"
            onClick={onMoveLater}
            disabled={!canMoveLater}
            className="inline-flex items-center gap-1 rounded-full border border-[color:var(--border)] bg-[var(--surface)] px-3 py-1.5 text-xs font-semibold text-[var(--text-secondary)] disabled:cursor-not-allowed disabled:opacity-40"
          >
            Later
            <ArrowRight size={13} />
          </button>
          <button
            type="button"
            onClick={onHide}
            className="inline-flex items-center gap-1 rounded-full border border-red-500/20 bg-red-500/10 px-3 py-1.5 text-xs font-semibold text-red-600"
          >
            <EyeOff size={13} />
            Hide
          </button>
        </div>
      </div>
    )}
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
    className="theme-card-muted group flex items-start gap-4 rounded-[22px] px-5 py-5 transition-all duration-300 hover:-translate-y-1 hover:shadow-md"
  >
    <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[var(--surface)] text-[var(--accent-blue)] transition group-hover:bg-blue-50 group-hover:scale-110">
      <Icon size={18} />
    </div>
    <div className="min-w-0 flex-1">
      <div className="text-sm font-semibold text-[var(--text-primary)] group-hover:text-blue-600">{title}</div>
      <div className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">{description}</div>
    </div>
    <ArrowRight size={17} className="mt-1 text-[var(--text-muted)] transition-all group-hover:translate-x-1 group-hover:text-blue-600" />
  </a>
);

const ActionCard = ({ href, icon: Icon, title, description }) => (
  <Link
    href={href}
    className="theme-card group block rounded-[28px] px-6 py-6 transition-all duration-300 hover:-translate-y-1 hover:shadow-lg"
  >
    <div className="flex items-start justify-between gap-4">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-600/10 text-blue-600 transition group-hover:bg-blue-600/20 group-hover:scale-110">
        <Icon size={20} />
      </div>
      <ArrowRight size={18} className="text-[var(--text-muted)] transition-all group-hover:translate-x-1 group-hover:text-blue-600" />
    </div>
    <div className="mt-6 text-lg font-semibold text-[var(--text-primary)] group-hover:text-blue-600">{title}</div>
    <div className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">{description}</div>
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
