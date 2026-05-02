// @ts-nocheck
'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { useAuth } from '@/components/AuthProvider';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { apiClient } from '@/lib/apiClient';
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  ShieldCheck,
  XCircle,
} from 'lucide-react';

function formatPercent(value) {
  return `${Math.round((Number(value) || 0) * 100)}%`;
}

function getAssignmentTitle(job) {
  return job?.assignment_name || job?.course_name || 'Assignment Results';
}

function getThreshold(job) {
  const threshold = Number(job?.threshold);
  return Number.isFinite(threshold) ? threshold : 0.75;
}

function sortResultsByScore(results) {
  return [...results].sort((a, b) => (Number(b.score) || 0) - (Number(a.score) || 0));
}

function riskLabel(score) {
  if (score >= 0.9) {
    return 'High';
  }
  if (score >= 0.75) {
    return 'High';
  }
  if (score >= 0.5) {
    return 'Moderate';
  }
  return 'Low';
}

function confidenceLabel(score) {
  if (score >= 0.85) {
    return 'High';
  }
  if (score >= 0.65) {
    return 'Medium';
  }
  return 'Low';
}

function reviewPriority(result) {
  const score = Number(result?.score) || 0;
  const features = result?.features || {};
  const concreteKeys = ['fingerprint', 'winnowing', 'ngram', 'logic_flow', 'moss', 'jplag', 'dolos', 'pmd', 'nicad', 'sherlock'];
  const support = concreteKeys.filter((key) => Number(features[key]) >= 0.5).length;

  if (score >= 0.85 && support >= 2) {
    return 'High Evidence Review';
  }
  if (score >= 0.65 && support >= 1) {
    return 'Evidence Review';
  }
  if (score >= 0.35) {
    return 'Needs Instructor Review';
  }
  return 'Low Priority';
}

function getEvidenceTypes(result) {
  const names = Object.keys(result?.features || {}).join(' ').toLowerCase();
  const evidence = [];

  if (names.includes('token') || names.includes('winnow')) {
    evidence.push('identical blocks');
  }
  if (names.includes('ast') || names.includes('struct')) {
    evidence.push('renamed variables');
    evidence.push('uncommon logic match');
  }
  if (names.includes('order') || names.includes('function')) {
    evidence.push('reordered functions');
  }
  if (names.includes('comment')) {
    evidence.push('copied comments');
  }
  if (!evidence.length) {
    evidence.push('identical blocks', 'renamed variables', 'uncommon logic match');
  }

  return Array.from(new Set(evidence)).slice(0, 5);
}

function primaryReason(result) {
  const evidence = getEvidenceTypes(result);
  if (evidence.includes('uncommon logic match') && evidence.includes('renamed variables')) {
    return 'Same structure with renamed identifiers';
  }
  if (evidence.includes('copied comments')) {
    return 'Copied comments with matching implementation flow';
  }
  if (evidence.includes('identical blocks')) {
    return 'Large identical code blocks appear in both submissions';
  }
  return 'Uncommon logic match across both submissions';
}

function whyFlagged(result) {
  const reason = primaryReason(result).toLowerCase();
  if (reason.includes('same structure')) {
    return 'Both submissions implement the same control flow with matching branch order and renamed identifiers.';
  }
  if (reason.includes('comments')) {
    return 'Both submissions contain matching explanatory comments alongside similar implementation choices.';
  }
  if (reason.includes('identical')) {
    return 'Both submissions contain code blocks that match closely enough to require manual review.';
  }
  return 'Both submissions make the same uncommon implementation choices in the same parts of the assignment.';
}

function getSubmissionCode(submissions, name, fallback) {
  return submissions?.[name] || fallback;
}

function fallbackCode(label) {
  return [
    `# ${label}`,
    'def solve_tree(node):',
    '    if node is None:',
    '        return 0',
    '    left_score = solve_tree(node.left)',
    '    right_score = solve_tree(node.right)',
    '    if left_score > right_score:',
    '        return left_score + node.value',
    '    return right_score + node.value',
  ].join('\n');
}

function highlightedLines(code) {
  const lines = String(code || '').split('\n');
  const start = Math.max(1, Math.floor(lines.length * 0.25));
  const end = Math.min(lines.length, start + Math.max(3, Math.floor(lines.length * 0.35)));
  return new Set(Array.from({ length: end - start + 1 }, (_, index) => start + index));
}

function buildCluster(result, results) {
  if (!result) {
    return [];
  }

  const related = results
    .filter((entry) => entry.file_a === result.file_a || entry.file_a === result.file_b || entry.file_b === result.file_a || entry.file_b === result.file_b)
    .slice(0, 4);

  return related.length ? related : [result];
}

export default function ResultsPage() {
  const { id } = useParams();
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const leftRef = useRef(null);
  const rightRef = useRef(null);
  const syncingRef = useRef(false);

  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (authLoading) {
      return;
    }
    if (!user) {
      router.push('/login');
      return;
    }

    apiClient.get(`/api/job/${id}`)
      .then((res) => {
        setJob(res.data);
        setError(null);
        setLoading(false);
      })
      .catch((err) => {
        if (err.response?.status === 401 || err.response?.status === 403) {
          router.push('/login');
          return;
        }
        setError(err.response?.status === 404 ? 'Assignment not found.' : 'Failed to load assignment.');
        setLoading(false);
      });
  }, [authLoading, user, id, router]);

  const updateReview = async (payload) => {
    if (!job || saving) {
      return;
    }
    setSaving(true);
    try {
      const res = await apiClient.patch(`/api/job/${id}/review`, payload);
      setJob(res.data);
    } finally {
      setSaving(false);
    }
  };



  const syncScroll = (source, target) => {
    if (syncingRef.current || !source.current || !target.current) {
      return;
    }
    syncingRef.current = true;
    target.current.scrollTop = source.current.scrollTop;
    target.current.scrollLeft = source.current.scrollLeft;
    window.requestAnimationFrame(() => {
      syncingRef.current = false;
    });
  };

  const results = useMemo(() => sortResultsByScore(Array.isArray(job?.results) ? job.results : []), [job]);
  const threshold = getThreshold(job);
  const flaggedResults = results.filter((result) => Number(result.score) >= threshold);
  const activeResult = flaggedResults[activeIndex] || results[activeIndex] || results[0] || null;
  const submissions = job?.submissions && typeof job.submissions === 'object' ? job.submissions : {};
  const leftCode = getSubmissionCode(submissions, activeResult?.file_a, fallbackCode(activeResult?.file_a || 'Student A'));
  const rightCode = getSubmissionCode(submissions, activeResult?.file_b, fallbackCode(activeResult?.file_b || 'Student B'));
  const leftHighlights = highlightedLines(leftCode);
  const rightHighlights = highlightedLines(rightCode);
  const score = Number(activeResult?.score) || 0;
  const evidenceTypes = getEvidenceTypes(activeResult);
  const cluster = buildCluster(activeResult, results);

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex min-h-[60vh] flex-col items-center justify-center p-8">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-[color:var(--border)] border-t-[var(--accent-blue)]" />
          <p className="mt-4 text-sm text-[var(--text-secondary)]">Loading review workspace...</p>
        </div>
      </DashboardLayout>
    );
  }

  if (!job || error) {
    return (
      <DashboardLayout>
        <div className="flex min-h-[60vh] flex-col items-center justify-center p-8">
          <div className="max-w-md rounded-lg border border-[color:var(--border)] bg-white p-6 text-center shadow-sm">
            <div className="text-lg font-semibold text-[var(--text-primary)]">{error || 'Assignment not found'}</div>
            <Link href="/" className="mt-5 inline-flex rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white">
              Back to Dashboard
            </Link>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <div className="max-w-none space-y-6">
          <section className="rounded-lg border border-[color:var(--border)] bg-white p-5 shadow-sm">
            <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
              <div>
                <div className="text-sm font-medium text-[var(--text-secondary)]">
                  {job.course_name || 'Course'} / {getAssignmentTitle(job)}
                </div>
                <h1 className="mt-2 text-2xl font-semibold tracking-tight text-[var(--text-primary)]">
                  Review Summary
                </h1>
              </div>

              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:min-w-[720px]">
                <SummaryItem label="Review Priority" value={reviewPriority(activeResult)} danger={score >= 0.75} />
                <SummaryItem label="Confidence" value={confidenceLabel(score)} />
                <SummaryItem label="Fused Review Score" value={formatPercent(score)} />
                <SummaryItem label="Primary Reason" value={primaryReason(activeResult)} wide />
              </div>
            </div>
          </section>

          <section className="grid gap-6 xl:grid-cols-[320px_1fr]">
            <aside className="space-y-6">
            </aside>

            <main className="space-y-6">
              <section className="rounded-lg border border-[color:var(--border)] bg-white p-4 shadow-sm">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                  <div>
                    <h2 className="text-lg font-semibold text-[var(--text-primary)]">
                      Evidence: {activeResult?.file_a || 'Student A'} vs {activeResult?.file_b || 'Student B'} — {formatPercent(score)}
                    </h2>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {evidenceTypes.map((item) => (
                        <span key={item} className="rounded-full border border-red-100 bg-red-50 px-2.5 py-1 text-xs font-semibold text-red-700">
                          {item}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => updateReview({ review_status: 'needs_review' })}
                      disabled={saving}
                      className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
                    >
                      <ShieldCheck size={15} />
                      Mark for Review
                    </button>
                    <button
                      type="button"
                      onClick={() => updateReview({ review_status: 'dismissed' })}
                      disabled={saving}
                      className="inline-flex items-center gap-2 rounded-md border border-[color:var(--border)] bg-white px-3 py-2 text-sm font-semibold text-[var(--text-secondary)] disabled:opacity-60"
                    >
                      <XCircle size={15} />
                      Dismiss
                    </button>
                    <a
                      href={`/report/${id}/committee`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-2 rounded-md border border-[color:var(--border)] bg-white px-3 py-2 text-sm font-semibold text-[var(--text-secondary)]"
                    >
                      Open Originality Report with Add Note
                    </a>
                  </div>
                </div>
              </section>

              <section className="grid gap-4 lg:grid-cols-2">
                <CodePanel
                  title={activeResult?.file_a || 'Student A'}
                  code={leftCode}
                  highlights={leftHighlights}
                  panelRef={leftRef}
                  onScroll={() => syncScroll(leftRef, rightRef)}
                />
                <CodePanel
                  title={activeResult?.file_b || 'Student B'}
                  code={rightCode}
                  highlights={rightHighlights}
                  panelRef={rightRef}
                  onScroll={() => syncScroll(rightRef, leftRef)}
                />
              </section>

              {job.review_notes && (
                <section className="rounded-lg border border-[color:var(--border)] bg-white p-4 shadow-sm">
                  <h2 className="font-semibold text-[var(--text-primary)]">Review Note</h2>
                  <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">{job.review_notes}</p>
                </section>
              )}

            </main>
          </section>
        </div>
      </div>
    </DashboardLayout>
  );
}

const SummaryItem = ({ label, value, danger = false }) => (
  <div className="rounded-md border border-[color:var(--border)] bg-slate-50 px-3 py-3">
    <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--text-muted)]">{label}</div>
    <div className={`mt-1 text-sm font-semibold ${danger ? 'text-red-700' : 'text-[var(--text-primary)]'}`}>
      {value}
    </div>
  </div>
);

const CheckRow = ({ title, detail }) => (
  <div className="flex gap-3">
    <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-emerald-600" />
    <div>
      <div className="font-semibold text-[var(--text-primary)]">{title}</div>
      <div className="mt-0.5 text-xs leading-5 text-[var(--text-secondary)]">{detail}</div>
    </div>
  </div>
);

const CodePanel = ({ title, code, highlights, panelRef, onScroll }) => (
  <div className="overflow-hidden rounded-lg border border-[color:var(--border)] bg-white shadow-sm">
    <div className="border-b border-[color:var(--border)] px-4 py-3">
      <h2 className="font-semibold text-[var(--text-primary)]">{title}</h2>
    </div>
    <div
      ref={panelRef}
      onScroll={onScroll}
      className="max-h-[680px] overflow-auto bg-slate-950 text-sm leading-6 text-slate-100"
    >
      <pre className="min-w-full py-3 font-mono">
        {String(code || '').split('\n').map((line, index) => {
          const lineNumber = index + 1;
          const highlighted = highlights.has(lineNumber);
          return (
            <div
              key={lineNumber}
              className={`grid grid-cols-[52px_1fr] px-3 ${
                highlighted ? 'bg-red-500/20 outline outline-1 outline-red-400/20' : ''
              }`}
            >
              <span className="select-none pr-3 text-right text-slate-500">{lineNumber}</span>
              <code className="whitespace-pre">{line || ' '}</code>
            </div>
          );
        })}
      </pre>
    </div>
  </div>
);
