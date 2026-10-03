'use client';

import DashboardLayout from '@/components/DashboardLayout';
import {
  ActionButton,
  Card,
  CardHeader,
  PageHeader,
  RiskBadge,
  StatusBadge,
} from '@/components/saas/SaaSPrimitives';
import { apiClient } from '@/lib/apiClient';
import {
  AlertTriangle,
  CheckCircle2,
  ChevronLeft,
  Clock3,
  Download,
  FileText,
  History,
  Loader2,
  MessageSquare,
  SearchCheck,
  ShieldCheck,
  XCircle,
} from 'lucide-react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';
import type { ComponentType, Ref } from 'react';

// ─── Types ─────────────────────────────────────────────────────────────────────

type CaseComment = { id: string; user_id: string; body: string; created_at: string };

type CaseData = {
  id: string;
  title: string;
  status: string;
  priority: string;
  risk_score?: number;
  confidence?: number;
  investigator?: { id: string; name: string } | null;
  assignment?: { title: string; course_name: string };
  result_ids?: string[];
  comments?: CaseComment[];
};

type UserItem = {
  id: string;
  name: string;
  email: string;
  role: string;
};

type Notice = {
  scope: 'actions' | 'notes';
  tone: 'success' | 'error' | 'warning';
  text: string;
};

type ActionName = 'assign' | 'review' | 'escalate' | 'dismiss' | 'export' | 'note';

class CaseShapeError extends Error {}

// ─── Constants ─────────────────────────────────────────────────────────────────

// NOTE: stand-in used only when the case has no `risk_score`. It is derived from
// priority, not measured.
const PRIORITY_RISK: Record<string, number> = {
  URGENT: 97,
  HIGH: 92,
  MEDIUM: 72,
  LOW: 40,
};

// The panels marked "sample" below (flagged reasons, code comparison, history, context
// notes, confidence basis) contain fixed text and fixed code, not data from the case.
// They are off by default so they can't be mistaken for evidence; set
// NEXT_PUBLIC_SHOW_SAMPLE_EVIDENCE=true to show them, labelled, for demos and layout work.
const SHOW_SAMPLE_EVIDENCE = process.env.NEXT_PUBLIC_SHOW_SAMPLE_EVIDENCE === 'true';

// ─── Helpers ───────────────────────────────────────────────────────────────────

const REFERENCE_HEADERS = ['x-correlation-id', 'x-request-id'];

function getErrorInfo(error: unknown): { status?: number; reference?: string } {
  const response = (error as { response?: { status?: unknown; headers?: unknown } } | null)?.response;
  if (!response || typeof response !== 'object') {
    return {};
  }

  const status = typeof response.status === 'number' ? response.status : undefined;
  const headers = (response.headers ?? {}) as Record<string, unknown>;
  const reference = REFERENCE_HEADERS.map((name) => headers[name]).find(
    (value): value is string => typeof value === 'string' && value.length > 0
  );

  return { status, reference };
}

/** Generic, status-keyed text; a correlation id is appended when the backend sends one. */
function describeError(error: unknown, fallback: string): string {
  const { status, reference } = getErrorInfo(error);

  let message = fallback;
  if (error instanceof CaseShapeError || status === 404) {
    message = 'This case could not be found. It may have been removed.';
  } else if (status === 401) {
    message = 'Your session has expired. Please sign in again.';
  } else if (status === 403) {
    message = 'You don’t have permission to do that.';
  } else if (status === 409) {
    message = 'This case was changed by someone else. Refresh the page and try again.';
  } else if (status === 429) {
    message = 'Too many requests. Please wait a moment and try again.';
  }

  return reference ? `${message} (Reference: ${reference})` : message;
}

/** Accepts 0–1 or 0–100 scores and returns a 0–100 integer, or null when there is no usable value. */
function toPercent(value: unknown): number | null {
  if (value === null || value === undefined || value === '') return null;
  const n = Number(value);
  if (!Number.isFinite(n)) return null;
  const pct = n <= 1 ? n * 100 : n;
  return Math.max(0, Math.min(100, Math.round(pct)));
}

function parseCaseResponse(data: unknown): { caseData: CaseData; comments: CaseComment[] } {
  const payload = data as ({ case?: CaseData; comments?: CaseComment[] } & Partial<CaseData>) | null | undefined;
  const found = (payload?.case ?? payload) as CaseData | undefined;

  if (!found || typeof found.id !== 'string' || !found.id) {
    throw new CaseShapeError('Unexpected case response');
  }

  const comments = payload?.comments ?? found.comments ?? [];
  return { caseData: found, comments: Array.isArray(comments) ? comments : [] };
}

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat('en-US', { dateStyle: 'medium', timeStyle: 'short' }).format(date);
}

function titleCase(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1).toLowerCase();
}

function triggerDownload(filename: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  // Revoking straight away can cancel the download in some browsers.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ─── Page ──────────────────────────────────────────────────────────────────────

export default function CompareCasePage() {
  const params = useParams<{ id: string | string[] }>();
  const caseId = Array.isArray(params?.id) ? params.id[0] : params?.id;

  const [caseData, setCaseData] = useState<CaseData | null>(null);
  const [comments, setComments] = useState<CaseComment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [users, setUsers] = useState<UserItem[]>([]);
  const [noteText, setNoteText] = useState('');
  const [pendingAction, setPendingAction] = useState<ActionName | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);

  const leftRef = useRef<HTMLDivElement>(null);
  const rightRef = useRef<HTMLDivElement>(null);
  const syncing = useRef(false);

  const casePath = caseId ? `/api/cases/${encodeURIComponent(caseId)}` : '';

  // Load the case. Aborts when the id changes or the page unmounts so a slow response
  // for case A can't overwrite case B.
  useEffect(() => {
    if (!caseId) return;

    const controller = new AbortController();
    setLoading(true);
    setError(null);

    apiClient
      .get(casePath, { signal: controller.signal })
      .then((response) => {
        const parsed = parseCaseResponse(response.data);
        setCaseData(parsed.caseData);
        setComments(parsed.comments);
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        setError(describeError(err, 'Failed to load case details. Please try again.'));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [caseId, casePath, reloadKey]);

  // Reviewer list for the assignment dropdown. A failure only means an empty list.
  useEffect(() => {
    const controller = new AbortController();

    apiClient
      .get('/api/users', { signal: controller.signal })
      .then((response) => {
        setUsers(Array.isArray(response.data) ? response.data : []);
      })
      .catch(() => {
        /* the dropdown simply stays empty */
      });

    return () => controller.abort();
  }, []);

  /** Re-read the case in place (replaces the old window.location.reload()). */
  const refreshCase = useCallback(async () => {
    const response = await apiClient.get(casePath);
    const parsed = parseCaseResponse(response.data);
    setCaseData(parsed.caseData);
    setComments(parsed.comments);
  }, [casePath]);

  /**
   * Run one write action with shared pending / success / error handling. Failures are now
   * shown to the user; before, they were only logged to the console.
   */
  const runAction = async (options: {
    name: ActionName;
    scope: Notice['scope'];
    request: () => Promise<unknown>;
    success: string;
    failure: string;
    refresh?: boolean;
  }) => {
    if (pendingAction) return;

    setPendingAction(options.name);
    setNotice(null);

    try {
      await options.request();
    } catch (err) {
      setNotice({ scope: options.scope, tone: 'error', text: describeError(err, options.failure) });
      setPendingAction(null);
      return;
    }

    if (options.refresh === false) {
      setNotice({ scope: options.scope, tone: 'success', text: options.success });
      setPendingAction(null);
      return;
    }

    try {
      await refreshCase();
      setNotice({ scope: options.scope, tone: 'success', text: options.success });
    } catch {
      setNotice({
        scope: options.scope,
        tone: 'warning',
        text: 'Saved, but the page couldn’t refresh. Reload to see the latest.',
      });
    } finally {
      setPendingAction(null);
    }
  };

  const changeStatus = (name: ActionName, status: string, success: string, failure: string) =>
    runAction({
      name,
      scope: 'actions',
      request: () => apiClient.patch(casePath, { status }),
      success,
      failure,
    });

  const handleAssign = (reviewerId: string) => {
    if (!reviewerId) return;
    return runAction({
      name: 'assign',
      scope: 'actions',
      request: () => apiClient.post(`${casePath}/assign`, { reviewer_id: reviewerId }),
      success: 'Reviewer assigned.',
      failure: 'Couldn’t assign the reviewer. Please try again.',
    });
  };

  const handleDismiss = () => {
    // Closing a case is the end of the review, so ask first.
    const confirmed = window.confirm(
      'Dismiss this case? It will be closed without further review. Add a note first if you need to record why.'
    );
    if (!confirmed) return;
    return changeStatus('dismiss', 'CLOSED', 'Case dismissed.', 'Couldn’t dismiss the case. Please try again.');
  };

  const handleExport = () =>
    runAction({
      name: 'export',
      scope: 'actions',
      refresh: false,
      request: async () => {
        const response = await apiClient.get(`${casePath}/export`);
        const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: 'application/json' });
        triggerDownload(`case-${caseId}.json`, blob);
      },
      success: 'Case exported.',
      failure: 'Couldn’t export the case. Please try again.',
    });

  const handleSaveNote = () => {
    const body = noteText.trim();
    if (!body) return;
    return runAction({
      name: 'note',
      scope: 'notes',
      request: async () => {
        await apiClient.post(`${casePath}/comments`, { body });
        setNoteText('');
      },
      success: 'Note saved.',
      failure: 'Couldn’t save the note. Your text is still here, so you can try again.',
    });
  };

  const syncScroll = (
    source: { current: HTMLDivElement | null },
    target: { current: HTMLDivElement | null }
  ) => {
    if (syncing.current || !source.current || !target.current) return;
    syncing.current = true;
    target.current.scrollTop = source.current.scrollTop;
    requestAnimationFrame(() => {
      syncing.current = false;
    });
  };

  // ── Loading / error ──────────────────────────────────────────────────────────

  if (loading) {
    return (
      <DashboardLayout>
        <div className="theme-page-container space-y-6">
          <div role="status" className="flex min-h-[50vh] items-center justify-center gap-2">
            <Loader2 size={16} className="animate-spin text-slate-400" aria-hidden="true" />
            <p className="text-sm text-slate-500 dark:text-slate-400">Loading case details...</p>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  if (error || !caseData) {
    return (
      <DashboardLayout>
        <div className="theme-page-container space-y-6">
          <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4 px-4">
            <div
              role="alert"
              className="flex w-full max-w-2xl items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300"
            >
              <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
              <span className="flex-1">{error || 'This case could not be loaded.'}</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setReloadKey((key) => key + 1)}
                className="inline-flex h-9 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
              >
                Try again
              </button>
              <Link
                href="/cases"
                className="text-sm font-semibold text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
              >
                Back to cases
              </Link>
            </div>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  // ── Derived values ───────────────────────────────────────────────────────────

  const priority = (caseData.priority || 'MEDIUM').toUpperCase();
  const status = (caseData.status || 'OPEN').toUpperCase();
  const priorityLabel = titleCase(priority);
  const riskPct = toPercent(caseData.risk_score);
  const confidencePct = toPercent(caseData.confidence);
  const linkedResults = Array.isArray(caseData.result_ids) ? caseData.result_ids.length : null;
  const badgeValue = riskPct ?? PRIORITY_RISK[priority] ?? 72;
  const priorityTone: 'red' | 'blue' | 'slate' =
    priority === 'URGENT' || priority === 'HIGH' ? 'red' : priority === 'MEDIUM' ? 'blue' : 'slate';
  const assignmentCourse = caseData.assignment?.course_name || 'Course';
  const assignmentTitle = caseData.assignment?.title || caseData.title;
  const isBusy = pendingAction !== null;
  const investigator = caseData.investigator;

  const authorName = (userId: string) => users.find((u) => u.id === userId)?.name || 'Instructor';

  const actionsNotice = notice?.scope === 'actions' ? notice : null;
  const notesNotice = notice?.scope === 'notes' ? notice : null;

  return (
    <DashboardLayout>
      <div className="theme-page-container space-y-6">
        {/* ── Header ──────────────────────────────────────────────────────────── */}
        {/* Breadcrumb + status row */}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm dark:border-slate-800 dark:bg-slate-950">
          <Link
            href="/cases"
            className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
          >
            <ChevronLeft size={13} aria-hidden="true" />
            Cases
          </Link>
          <span aria-hidden="true" className="text-slate-300 dark:text-slate-700">
            /
          </span>
          <span className="font-mono text-xs text-slate-500 dark:text-slate-400">{caseData.id.slice(0, 8)}</span>
          <span className="ml-auto flex flex-wrap items-center gap-2">
            <StatusBadge status={caseData.status || 'OPEN'} />
            <RiskBadge value={badgeValue} label={`${priorityLabel} priority`} />
          </span>
        </div>

        <PageHeader
          eyebrow="Case"
          eyebrowStyle="badge"
          title="Instructor Review Case"
          description={`${assignmentCourse} · ${assignmentTitle}`}
        />

        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-slate-600 dark:text-slate-400">
          <span>
            <span className="font-medium text-slate-500 dark:text-slate-400">Reviewer: </span>
            {investigator?.name || 'Unassigned'}
          </span>
          <span aria-hidden="true" className="hidden h-4 w-px bg-slate-200 sm:block dark:bg-slate-800" />
          <span className="inline-flex items-center gap-1.5">
            <Clock3 size={14} className="text-slate-400" aria-hidden="true" />
            {comments.length} reviewer {comments.length === 1 ? 'note' : 'notes'}
          </span>
        </div>

        <div
          role="status"
          className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-300"
        >
          <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
          <span>Similarity does not by itself imply misconduct. Instructor review is required.</span>
        </div>

        {/* Case-specific figures. These used to be workspace-wide totals (all submissions,
            all open cases), which don't belong on one case and cost two heavy requests. */}
        <dl className="grid grid-cols-2 gap-4 text-sm text-slate-600 dark:text-slate-400 xl:grid-cols-4">
          <HeaderMetric value={riskPct !== null ? `${riskPct}/100` : '—'} label="Risk score" />
          <HeaderMetric value={linkedResults !== null ? linkedResults : '—'} label="Linked results" />
          <HeaderMetric value={comments.length} label="Reviewer notes" />
          <HeaderMetric value={priority} label="Queue priority" />
        </dl>

        {/* ── Risk + confidence ───────────────────────────────────────────────── */}
        <section className={`grid items-start gap-6 ${SHOW_SAMPLE_EVIDENCE ? 'lg:grid-cols-[minmax(0,1fr)_360px]' : ''}`}>
          <Card>
            <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
                  Risk Summary
                </div>
                {SHOW_SAMPLE_EVIDENCE ? (
                  <>
                    <SampleBadge />
                    <h2 className="mt-2 text-lg font-semibold text-slate-900 dark:text-white">
                      Multiple uncommon similarities were detected.
                    </h2>
                    <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600 dark:text-slate-400">
                      This case was flagged based on multiple independent signals. It is recommended
                      for manual review, not treated as a misconduct conclusion.
                    </p>
                  </>
                ) : (
                  <>
                    <h2 className="mt-2 text-lg font-semibold text-slate-900 dark:text-white">
                      {priorityLabel} priority case flagged for review.
                    </h2>
                    <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600 dark:text-slate-400">
                      This case was flagged by the analysis that created it. It is recommended for manual
                      review, not treated as a misconduct conclusion.
                    </p>
                  </>
                )}
              </div>
              <RiskBadge value={badgeValue} label={`${priorityLabel} priority`} />
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <RiskMetric label="Priority" value={priorityLabel} tone={priorityTone} />
              <RiskMetric
                label="Confidence"
                value={confidencePct !== null ? `${confidencePct}%` : '—'}
                tone="slate"
              />
              <RiskMetric label="Linked results" value={linkedResults !== null ? linkedResults : '—'} tone="blue" />
            </div>
          </Card>

          {SHOW_SAMPLE_EVIDENCE && (
            <Card className="h-full gap-5 lg:gap-6">
              <SampleBadge />
              <div className="flex items-center gap-2 text-base font-semibold text-slate-900 dark:text-white">
                <ShieldCheck size={17} className="text-blue-600 dark:text-blue-400" aria-hidden="true" />
                Confidence Basis
              </div>
              <p className="text-sm leading-6 text-slate-600 dark:text-slate-400">
                Confidence derived from 4 independent signals after starter code and common
                assignment patterns were excluded.
              </p>
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
                Similar code structure detected between student submissions.
              </div>
            </Card>
          )}
        </section>

        {/* ── Evidence ────────────────────────────────────────────────────────── */}
        {SHOW_SAMPLE_EVIDENCE ? (
          <>
            <Card>
              <div className="flex flex-col gap-5 lg:gap-6">
                <SampleBadge />
                <CardHeader
                  title="Why This Case Was Flagged"
                  description="Plain-language evidence for instructor review."
                />
                <div className="grid gap-4 md:grid-cols-2">
                  {[
                    'Same unusual recursive decomposition',
                    'Identical edge-case handling',
                    'Renamed variables but same structure',
                    'Matching helper function logic',
                    'Similarity exceeds course baseline',
                  ].map((reason) => (
                    <div key={reason} className="flex gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-900">
                      <SearchCheck size={18} className="mt-0.5 shrink-0 text-blue-600 dark:text-blue-400" aria-hidden="true" />
                      <div className="text-sm font-medium text-slate-800 dark:text-slate-200">{reason}</div>
                    </div>
                  ))}
                </div>
              </div>
            </Card>

            <Card>
              <div className="flex flex-col gap-5 lg:gap-6">
                <SampleBadge />
                <CardHeader
                  title="Compare Code"
                  description="Matching regions are highlighted. Starter code is greyed out and excluded from the risk summary."
                />
                <div className="grid items-start gap-6 xl:grid-cols-2">
                  <CodePanel
                    title="Student A"
                    code={`def tree_score(node):
    if node is None:
        return 0

    left_total = tree_score(node.left)
    right_total = tree_score(node.right)

    if node.value < 0:
        return max(left_total, right_total)

    if left_total > right_total:
        return left_total + node.value

    return right_total + node.value`}
                    panelRef={leftRef}
                    onScroll={() => syncScroll(leftRef, rightRef)}
                  />
                  <CodePanel
                    title="Student B"
                    code={`def calculate_tree(current):
    if current is None:
        return 0

    first_branch = calculate_tree(current.left)
    second_branch = calculate_tree(current.right)

    if current.value < 0:
        return max(first_branch, second_branch)

    if first_branch > second_branch:
        return first_branch + current.value

    return second_branch + current.value`}
                    panelRef={rightRef}
                    onScroll={() => syncScroll(rightRef, leftRef)}
                  />
                </div>
              </div>
            </Card>
          </>
        ) : (
          <Card>
            <div className="flex flex-col gap-3">
              <CardHeader
                title="Evidence"
                description="Matched code, flagged reasons and history for this case."
              />
              <p className="text-sm leading-6 text-slate-600 dark:text-slate-400">
                Detailed evidence isn’t shown on this page yet.{' '}
                {linkedResults
                  ? `This case links to ${linkedResults} analysis ${linkedResults === 1 ? 'result' : 'results'}; review the matches there before deciding.`
                  : 'Review the original analysis results before deciding.'}
              </p>
            </div>
          </Card>
        )}

        {/* ── History / context / actions ─────────────────────────────────────── */}
        <section className={`grid items-start gap-6 ${SHOW_SAMPLE_EVIDENCE ? 'lg:grid-cols-3' : ''}`}>
          {SHOW_SAMPLE_EVIDENCE && (
            <>
              <Card className="h-full gap-5 lg:gap-6">
                <SampleBadge />
                <CardHeader title="Previous History" description="Historical context, not a standalone conclusion." />
                <div className="flex flex-col gap-4">
                  <EvidenceRow
                    icon={History}
                    title="Similar to Winter 2025 submission set."
                    detail="Prior-term match is structural and excludes starter code."
                  />
                  <EvidenceRow
                    icon={ShieldCheck}
                    title="No prior confirmed violation for either student."
                    detail="Department record check returned no prior case history."
                  />
                </div>
              </Card>

              <Card className="h-full gap-5 lg:gap-6">
                <SampleBadge />
                <CardHeader title="Context Notes" description="False-positive controls applied before ranking." />
                <div className="flex flex-col gap-4">
                  {[
                    'Starter template overlap excluded.',
                    'Instructor-provided tests and LMS packaging files ignored.',
                    'Common course solution patterns discounted before ranking.',
                  ].map((note) => (
                    <EvidenceRow key={note} icon={FileText} title={note} detail="Applied automatically." />
                  ))}
                </div>
              </Card>
            </>
          )}

          <Card className="gap-5 lg:gap-6">
            <CardHeader title="Decision Actions" description="Keep the review outcome simple and auditable." />
            <div className="flex flex-col gap-5">
              {/* Assign Reviewer */}
              <div className="space-y-2">
                <label htmlFor="assign-reviewer" className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
                  Assign Reviewer
                </label>
                <div className="flex gap-2">
                  <select
                    id="assign-reviewer"
                    className="h-10 flex-1 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-800 dark:bg-slate-900 dark:text-white"
                    value={investigator?.id || ''}
                    disabled={isBusy}
                    onChange={(e) => handleAssign(e.target.value)}
                  >
                    <option value="">{pendingAction === 'assign' ? 'Assigning…' : 'Select reviewer...'}</option>
                    {/* Keep the current reviewer selectable even if /api/users didn't return them. */}
                    {investigator && !users.some((u) => u.id === investigator.id) && (
                      <option value={investigator.id}>{investigator.name}</option>
                    )}
                    {users.map((user) => (
                      <option key={user.id} value={user.id}>
                        {user.name || user.email}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="grid gap-2 md:grid-cols-2">
                <ActionButton
                  icon={CheckCircle2}
                  disabled={isBusy || status === 'UNDER_REVIEW'}
                  onClick={() =>
                    changeStatus(
                      'review',
                      'UNDER_REVIEW',
                      'Case marked for review.',
                      'Couldn’t update the case status. Please try again.'
                    )
                  }
                >
                  Mark for Review
                </ActionButton>
                <ActionButton
                  variant="secondary"
                  icon={AlertTriangle}
                  disabled={isBusy || status === 'ESCALATED'}
                  onClick={() =>
                    changeStatus(
                      'escalate',
                      'ESCALATED',
                      'Case escalated.',
                      'Couldn’t escalate the case. Please try again.'
                    )
                  }
                >
                  Needs More Evidence
                </ActionButton>
                <ActionButton
                  variant="secondary"
                  icon={XCircle}
                  disabled={isBusy || status === 'CLOSED'}
                  onClick={handleDismiss}
                >
                  Dismiss
                </ActionButton>
                <ActionButton variant="secondary" icon={Download} disabled={isBusy} onClick={handleExport}>
                  {pendingAction === 'export' ? 'Exporting…' : 'Export JSON'}
                </ActionButton>
              </div>

              {actionsNotice && <NoticeBanner notice={actionsNotice} />}
            </div>
          </Card>
        </section>

        {/* ── Notes ───────────────────────────────────────────────────────────── */}
        <Card className="gap-5 lg:gap-6">
          <CardHeader title="Notes" description="Reviewer notes are kept with the case audit trail." />
          <div className="flex flex-col gap-5">
            {/* Existing Comments */}
            <div className="max-h-60 space-y-3 overflow-y-auto" tabIndex={0} aria-label="Reviewer notes">
              {comments.length > 0 ? (
                comments.map((comment) => (
                  <div key={comment.id} className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm dark:border-slate-800 dark:bg-slate-900">
                    {/* Was always "Instructor"; now the author's name when it's known. */}
                    <div className="mb-1 font-medium text-slate-700 dark:text-slate-300">{authorName(comment.user_id)}</div>
                    <div className="whitespace-pre-wrap text-slate-600 dark:text-slate-400">{comment.body}</div>
                    <div className="mt-1 text-xs text-slate-400 dark:text-slate-500">{formatDateTime(comment.created_at)}</div>
                  </div>
                ))
              ) : (
                <div className="px-5 py-14 text-center">
                  <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-slate-100 text-slate-500 dark:bg-slate-900 dark:text-slate-400">
                    <MessageSquare size={22} aria-hidden="true" />
                  </div>
                  <h3 className="mt-4 text-base font-semibold text-slate-900 dark:text-white">No notes yet</h3>
                  <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500 dark:text-slate-400">
                    Add your first note below.
                  </p>
                </div>
              )}
            </div>

            {/* Add Note Form */}
            <div>
              <label htmlFor="case-note" className="mb-1.5 flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-300">
                <MessageSquare size={16} aria-hidden="true" />
                Add Instructor Note
              </label>
              <textarea
                id="case-note"
                value={noteText}
                onChange={(e) => setNoteText(e.target.value)}
                onKeyDown={(e) => {
                  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                    e.preventDefault();
                    handleSaveNote();
                  }
                }}
                placeholder="Enter your notes for this case..."
                rows={4}
                className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white dark:placeholder:text-slate-500"
              />
              {/* The button used to sit inside the <label>, which made the whole label a click target for it. */}
              <div className="mt-2 flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  disabled={isBusy || !noteText.trim()}
                  onClick={handleSaveNote}
                  className="inline-flex h-10 items-center gap-2 rounded-xl bg-blue-600 px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {pendingAction === 'note' ? (
                    <>
                      <Loader2 size={14} className="animate-spin" aria-hidden="true" />
                      Saving...
                    </>
                  ) : (
                    'Save Note'
                  )}
                </button>
                <span className="text-xs text-slate-500 dark:text-slate-400">Ctrl/⌘ + Enter to save</span>
              </div>
              {notesNotice && (
                <div className="mt-3">
                  <NoticeBanner notice={notesNotice} />
                </div>
              )}
            </div>
          </div>
        </Card>
      </div>
    </DashboardLayout>
  );
}

// ─── Small components ──────────────────────────────────────────────────────────

function NoticeBanner({ notice }: { notice: Notice }) {
  const styles: Record<Notice['tone'], string> = {
    success: 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-300',
    error: 'border-red-200 bg-red-50 text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300',
    warning: 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-300',
  };
  const Icon = notice.tone === 'success' ? CheckCircle2 : AlertTriangle;

  return (
    <div
      role={notice.tone === 'error' ? 'alert' : 'status'}
      className={`flex items-start gap-3 rounded-2xl border px-4 py-3 text-sm ${styles[notice.tone]}`}
    >
      <Icon size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
      <span>{notice.text}</span>
    </div>
  );
}

function SampleBadge() {
  return (
    <span className="inline-flex w-fit items-center rounded-full bg-amber-100 px-2.5 py-1 text-xs font-semibold text-amber-800 dark:bg-amber-500/15 dark:text-amber-300">
      Sample data — not from this case
    </span>
  );
}

// <dl> children must be dt/dd groups (these were plain divs). dt comes first in the DOM;
// `order` keeps the value visually above the label.
function HeaderMetric({ value, label }: { value: string | number; label: string }) {
  return (
    <div className="flex flex-col rounded-lg border border-slate-200 bg-slate-50 px-3 py-3 dark:border-slate-800 dark:bg-slate-900">
      <dt className="order-2 mt-1 leading-5">{label}</dt>
      <dd className="order-1 text-lg font-semibold text-slate-900 dark:text-white">{value}</dd>
    </div>
  );
}

function RiskMetric({
  label,
  value,
  tone,
}: {
  label: string;
  value: string | number;
  tone: 'red' | 'blue' | 'slate';
}) {
  const tones = {
    red: 'text-red-700 bg-red-50 border-red-100 dark:text-red-300 dark:bg-red-500/10 dark:border-red-500/20',
    blue: 'text-blue-700 bg-blue-50 border-blue-100 dark:text-blue-300 dark:bg-blue-500/10 dark:border-blue-500/20',
    slate: 'text-slate-800 bg-slate-50 border-slate-200 dark:text-slate-300 dark:bg-slate-800 dark:border-slate-700',
  };

  return (
    <div className={`rounded-xl border p-4 ${tones[tone]}`}>
      <div className="text-sm font-medium opacity-80">{label}</div>
      <div className="mt-2 text-2xl font-semibold">{value}</div>
    </div>
  );
}

function CodePanel({
  title,
  code,
  panelRef,
  onScroll,
}: {
  title: string;
  code: string;
  panelRef: Ref<HTMLDivElement>;
  onScroll: () => void;
}) {
  const highlightedLines = new Set([5, 6, 8, 11, 13]);
  const starterLines = new Set([1, 2]);

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950">
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3 dark:border-slate-800">
        <div className="text-sm font-semibold text-slate-900 dark:text-white">{title}</div>
        <div className="flex items-center gap-2 text-xs font-medium text-slate-500 dark:text-slate-400">
          <Clock3 size={14} aria-hidden="true" />
          Synchronized scroll
        </div>
      </div>
      <div className="border-b border-slate-200 bg-slate-50 px-4 py-2 text-xs font-medium text-slate-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
        Unrelated code collapsed. Starter code greyed out.
      </div>
      {/* Focusable so keyboard users can scroll it; the <pre> wrapper held <div>s, which is invalid. */}
      <div
        ref={panelRef}
        onScroll={onScroll}
        role="region"
        tabIndex={0}
        aria-label={`${title} code`}
        className="max-h-[620px] overflow-auto bg-slate-950 py-3 text-sm text-slate-100"
      >
        <div className="min-w-full font-mono leading-6">
          {code.split('\n').map((line, index) => {
            const lineNumber = index + 1;
            const highlighted = highlightedLines.has(lineNumber);
            const starter = starterLines.has(lineNumber);
            return (
              <div
                key={lineNumber}
                className={`grid grid-cols-[52px_1fr] px-3 ${
                  highlighted ? 'bg-red-500/15 ring-1 ring-inset ring-red-400/30' : ''
                } ${starter ? 'bg-slate-800 text-slate-500' : ''}`}
              >
                <span className="select-none pr-3 text-right text-slate-500">{lineNumber}</span>
                <code className="whitespace-pre">{line || ' '}</code>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function EvidenceRow({
  icon: Icon,
  title,
  detail,
}: {
  icon: ComponentType<{ size?: number; className?: string }>;
  title: string;
  detail: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-900">
      <div className="flex gap-3">
        <Icon size={17} className="mt-0.5 shrink-0 text-blue-600 dark:text-blue-400" />
        <div>
          <div className="text-sm font-semibold text-slate-900 dark:text-white">{title}</div>
          <div className="mt-1 text-sm leading-5 text-slate-500 dark:text-slate-400">{detail}</div>
        </div>
      </div>
    </div>
  );
}
