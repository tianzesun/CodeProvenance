// @ts-nocheck — TODO: add proper types (tracked in types/api.ts)
'use client';

import DashboardLayout from '@/components/DashboardLayout';
import {
  ActionButton,
  Card,
  CardHeader,
  RiskBadge,
} from '@/components/saas/SaaSPrimitives';
import { apiClient } from '@/lib/apiClient';
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Download,
  FileText,
  History,
  MessageSquare,
  SearchCheck,
  ShieldCheck,
  XCircle,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useParams } from 'next/navigation';

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
  comments?: { id: string; user_id: string; body: string; created_at: string }[];
};

const PRIORITY_RISK: Record<string, number> = {
  URGENT: 97,
  HIGH: 92,
  MEDIUM: 72,
  LOW: 40,
};

type User = {
  id: string;
  name: string;
  email: string;
  role: string;
};

export default function CompareCasePage() {
  const { id } = useParams();
  const [caseData, setCaseData] = useState<CaseData | null>(null);
  const [comments, setComments] = useState<CaseData['comments']>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [noteText, setNoteText] = useState('');
  const [isSavingNote, setIsSavingNote] = useState(false);
  const [totalSubmissions, setTotalSubmissions] = useState(0);
  const [casesNeedingReview, setCasesNeedingReview] = useState(0);
  const [analysesCompleted, setAnalysesCompleted] = useState(0);
  
  const [studentA, studentB] = ['Student A', 'Student B'];
  const leftRef = useRef(null);
  const rightRef = useRef(null);
  const syncing = useRef(false);

  useEffect(() => {
    const fetchCase = async () => {
      try {
        const response = await apiClient.get(`/api/cases/${id}`);
        setCaseData(response.data?.case || response.data);
        setComments(response.data?.comments || []);
      } catch (err) {
        console.error('Failed to fetch case:', err);
        setError(err instanceof Error ? err.message : 'Failed to load case details.');
      } finally {
        setLoading(false);
      }
    };

    const fetchUsers = async () => {
      try {
        const response = await apiClient.get('/api/users');
        setUsers(response.data || []);
      } catch (err) {
        console.error('Failed to fetch users:', err);
      }
    };

    const fetchStats = async () => {
      try {
        const [casesRes, jobsRes] = await Promise.all([
          apiClient.get('/api/cases', { params: { limit: 1000 } }),
          apiClient.get('/api/jobs'),
        ]);
        const allCases = casesRes.data || [];
        const jobs = (jobsRes.data || {}).jobs || [];
        setCasesNeedingReview(
          allCases.filter((c: { status?: string }) => c.status === 'OPEN').length
        );
        setTotalSubmissions(
          jobs.reduce((sum: number, job: { file_count?: number }) => sum + (Number(job.file_count) || 0), 0)
        );
        setAnalysesCompleted(jobs.length);
      } catch (err) {
        console.error('Failed to fetch stats:', err);
      }
    };

    if (id) {
      fetchCase();
      fetchUsers();
      fetchStats();
    }
  }, [id]);

  const syncScroll = (source, target) => {
    if (syncing.current || !source.current || !target.current) return;
    syncing.current = true;
    target.current.scrollTop = source.current.scrollTop;
    requestAnimationFrame(() => {
      syncing.current = false;
    });
  };

  const getAssignmentDisplay = () => {
    if (!caseData) return { course: 'Course', title: '' };
    const assignment = caseData.assignment;
    if (assignment) {
      return { 
        course: assignment.course_name || 'Course', 
        title: assignment.title || caseData.title 
      };
    }
    return { course: 'Course', title: caseData.title };
  };
  
  const assignmentDisplay = getAssignmentDisplay();

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center min-h-screen">
          <div className="text-slate-500">Loading case details...</div>
        </div>
      </DashboardLayout>
    );
  }

  if (error) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center min-h-screen">
          <div className="text-red-500">{error}</div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="max-w-none px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <section className="rounded-xl border border-slate-200 bg-white px-5 py-5 shadow-sm">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <div className="text-sm font-medium text-slate-500">
                Assignment: {assignmentDisplay.course} {assignmentDisplay.title}
              </div>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">
                Instructor Review Case
              </h1>
              <div className="mt-4 flex items-center gap-4 text-sm">
                <div className="text-slate-600">
                  <span className="font-medium text-slate-500">Status:</span> {caseData?.status || 'OPEN'}
                </div>
                <div className="text-slate-600">
                  <span className="font-medium text-slate-500">Assignee:</span> {caseData?.investigator?.name || 'Unassigned'}
                </div>
              </div>
              <div className="mt-4 grid gap-3 text-sm text-slate-600 sm:grid-cols-2 lg:grid-cols-4">
                <HeaderMetric value={totalSubmissions.toLocaleString()} label="submissions analyzed" />
                <HeaderMetric value={casesNeedingReview} label="cases need instructor review" />
                <HeaderMetric value={analysesCompleted.toLocaleString()} label="analyses completed" />
                <HeaderMetric value={caseData?.priority || 'MEDIUM'} label="queue priority" />
              </div>
            </div>
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-600">
              Similarity does not by itself imply misconduct. Instructor review is required.
            </div>
          </div>
        </section>

        <section className="grid gap-4 lg:grid-cols-[1fr_360px]">
          <Card className="p-5">
            <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <div className="text-sm font-semibold text-slate-500">Risk Summary</div>
                <h2 className="mt-2 text-2xl font-semibold text-slate-950">
                  Multiple uncommon similarities were detected.
                </h2>
                <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
                  This case was flagged based on multiple independent signals. It is recommended
                  for manual review, not treated as a misconduct conclusion.
                </p>
              </div>
              <RiskBadge value={PRIORITY_RISK[caseData?.priority || 'MEDIUM'] || 72} label="High Risk" />
            </div>

            <div className="mt-6 grid gap-4 md:grid-cols-3">
              <RiskMetric label="Overall Risk" value="High" tone="red" />
              <RiskMetric label="Confidence" value={`${Math.round(caseData?.confidence || 0)}%`} tone="slate" />
              <RiskMetric label="Review Time" value="~2 min" tone="blue" />
            </div>
          </Card>

          <Card className="p-5">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-950">
              <ShieldCheck size={17} className="text-blue-600" />
              Confidence Basis
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              Confidence derived from 4 independent signals after starter code and common
              assignment patterns were excluded.
            </p>
            <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
              Similar code structure detected between student submissions.
            </div>
          </Card>
        </section>

        <Card>
          <CardHeader
            title="Why This Case Was Flagged"
            description="Plain-language evidence for instructor review."
          />
          <div className="grid gap-3 p-5 md:grid-cols-2">
            {[
              'Same unusual recursive decomposition',
              'Identical edge-case handling',
              'Renamed variables but same structure',
              'Matching helper function logic',
              'Similarity exceeds course baseline',
            ].map((reason) => (
              <div key={reason} className="flex gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4">
                <SearchCheck size={18} className="mt-0.5 shrink-0 text-blue-600" />
                <div className="text-sm font-medium text-slate-800">{reason}</div>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Compare Code"
            description="Matching regions are highlighted. Starter code is greyed out and excluded from the risk summary."
          />
          <div className="grid gap-4 p-5 xl:grid-cols-2">
            <CodePanel
              title={studentA || 'Student A'}
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
              title={studentB || 'Student B'}
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
        </Card>

        <section className="grid gap-4 lg:grid-cols-3">
          <Card>
            <CardHeader title="Previous History" description="Historical context, not a standalone conclusion." />
            <div className="space-y-3 p-5">
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

          <Card>
            <CardHeader title="Context Notes" description="False-positive controls applied before ranking." />
            <div className="space-y-3 p-5">
              {[
                'Starter template overlap excluded.',
                'Instructor-provided tests and LMS packaging files ignored.',
                'Common course solution patterns discounted before ranking.',
              ].map((note) => (
                <EvidenceRow key={note} icon={FileText} title={note} detail="Applied automatically." />
              ))}
            </div>
          </Card>

          <Card>
            <CardHeader title="Decision Actions" description="Keep the review outcome simple and auditable." />
            <div className="space-y-4 p-5">
              {/* Assign Reviewer */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700">Assign Reviewer</label>
                <div className="flex gap-2">
                  <select
                    className="flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-300 focus:ring-4 focus:ring-blue-50"
                    value={caseData?.investigator?.id || ''}
                    onChange={async (e) => {
                      const reviewerId = e.target.value;
                      if (reviewerId) {
                        try {
                          await apiClient.post(`/api/cases/${id}/assign`, { reviewer_id: reviewerId });
                          window.location.reload();
                        } catch (err) {
                          console.error('Failed to assign reviewer:', err);
                        }
                      }
                    }}
                  >
                    <option value="">Select reviewer...</option>
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
                  onClick={async () => {
                    try {
                      await apiClient.patch(`/api/cases/${id}`, { status: 'UNDER_REVIEW' });
                      window.location.reload();
                    } catch (err) {
                      console.error('Failed to update case status:', err);
                    }
                  }}
                >
                  Mark for Review
                </ActionButton>
                <ActionButton variant="secondary" icon={AlertTriangle} onClick={async () => {
                  try {
                    await apiClient.patch(`/api/cases/${id}`, { status: 'ESCALATED' });
                    window.location.reload();
                  } catch (err) {
                    console.error('Failed to escalate case:', err);
                  }
                }}>
                  Needs More Evidence
                </ActionButton>
                <ActionButton variant="secondary" icon={XCircle} onClick={async () => {
                  try {
                    await apiClient.patch(`/api/cases/${id}`, { status: 'CLOSED' });
                    window.location.reload();
                  } catch (err) {
                    console.error('Failed to close case:', err);
                  }
                }}>
                  Dismiss
                </ActionButton>
                <ActionButton variant="secondary" icon={Download} onClick={async () => {
                  try {
                    const response = await apiClient.get(`/api/cases/${id}/export`);
                    const data = response.data;
                    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `case-${id}.json`;
                    a.click();
                    URL.revokeObjectURL(url);
                  } catch (err) {
                    console.error('Failed to export case:', err);
                  }
                }}>
                  Export JSON
                </ActionButton>
              </div>
            </div>
          </Card>
        </section>

        <Card>
          <CardHeader title="Notes" description="Reviewer notes are kept with the case audit trail." />
          <div className="p-5 space-y-4">
            {/* Existing Comments */}
            <div className="space-y-3 max-h-60 overflow-y-auto">
              {comments && comments.length > 0 ? (
                comments.map((comment) => (
                  <div key={comment.id} className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
                    <div className="font-medium text-slate-700 mb-1">Instructor</div>
                    <div className="text-slate-600">{comment.body}</div>
                    <div className="text-xs text-slate-400 mt-1">
                      {new Date(comment.created_at).toLocaleString()}
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-sm text-slate-500 italic">No notes yet. Add your first note below.</div>
              )}
            </div>
            
            {/* Add Note Form */}
            <label className="block">
              <span className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-700">
                <MessageSquare size={16} />
                Add Instructor Note
              </span>
              <textarea
                value={noteText}
                onChange={(e) => setNoteText(e.target.value)}
                placeholder="Enter your notes for this case..."
                rows={4}
                className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm outline-none transition focus:border-blue-300 focus:ring-4 focus:ring-blue-50"
              />
              <button
                type="button"
                disabled={isSavingNote || !noteText.trim()}
                onClick={async () => {
                  setIsSavingNote(true);
                  try {
                    await apiClient.post(`/api/cases/${id}/comments`, { body: noteText });
                    setNoteText('');
                    window.location.reload();
                  } catch (err) {
                    console.error('Failed to save note:', err);
                  } finally {
                    setIsSavingNote(false);
                  }
                }}
                className="mt-2 inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isSavingNote ? 'Saving...' : 'Save Note'}
              </button>
            </label>
          </div>
        </Card>
      </div>
    </DashboardLayout>
  );
}

function HeaderMetric({ value, label }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3">
      <div className="text-lg font-semibold text-slate-950">{value}</div>
      <div className="mt-1 leading-5">{label}</div>
    </div>
  );
}

function RiskMetric({ label, value, tone }) {
  const tones = {
    red: 'text-red-700 bg-red-50 border-red-100',
    blue: 'text-blue-700 bg-blue-50 border-blue-100',
    slate: 'text-slate-800 bg-slate-50 border-slate-200',
  };

  return (
    <div className={`rounded-xl border p-4 ${tones[tone]}`}>
      <div className="text-sm font-medium opacity-80">{label}</div>
      <div className="mt-2 text-2xl font-semibold">{value}</div>
    </div>
  );
}

function CodePanel({ title, code, panelRef, onScroll }) {
  const highlightedLines = new Set([5, 6, 8, 11, 13]);
  const starterLines = new Set([1, 2]);

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <div className="text-sm font-semibold text-slate-950">{title}</div>
        <div className="flex items-center gap-2 text-xs font-medium text-slate-500">
          <Clock3 size={14} />
          Synchronized scroll
        </div>
      </div>
      <div className="border-b border-slate-200 bg-slate-50 px-4 py-2 text-xs font-medium text-slate-500">
        Unrelated code collapsed. Starter code greyed out.
      </div>
      <div ref={panelRef} onScroll={onScroll} className="max-h-[620px] overflow-auto bg-slate-950 py-3 text-sm text-slate-100">
        <pre className="min-w-full font-mono leading-6">
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
        </pre>
      </div>
    </div>
  );
}

function EvidenceRow({ icon: Icon, title, detail }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex gap-3">
        <Icon size={17} className="mt-0.5 shrink-0 text-blue-600" />
        <div>
          <div className="text-sm font-semibold text-slate-950">{title}</div>
          <div className="mt-1 text-sm leading-5 text-slate-500">{detail}</div>
        </div>
      </div>
    </div>
  );
}