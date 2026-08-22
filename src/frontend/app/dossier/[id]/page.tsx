'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { apiClient } from '@/lib/apiClient';
import {
  AlertCircle,
  ArrowLeft,
  Bot,
  ClipboardCheck,
  FileDown,
  GitCompare,
  Globe,
  HelpCircle,
  Loader2,
  ShieldAlert,
  ShieldCheck,
  ShieldQuestion,
} from 'lucide-react';

interface EvidenceItem {
  type: string;
  severity: string;
  title: string;
  detail: string;
}

interface VivaOutcome {
  outcome: string;
  notes: string | null;
  conducted_at: string | null;
}

interface StudentDossier {
  student: string;
  band: string;
  ai_probability: number | null;
  ai_confidence: number | null;
  peer_max_similarity: number | null;
  peer_partner: string | null;
  web_max_similarity: number | null;
  web_best_match_url: string | null;
  web_best_match_source: string | null;
  evidence: EvidenceItem[];
  viva_questions: string[];
  viva_outcome: VivaOutcome | null;
}

interface DossierPayload {
  job_id: string;
  generated_at: string;
  coverage: { ai_detection: boolean; web_analysis: boolean; pairwise: boolean };
  students: StudentDossier[];
}

const bandStyles: Record<string, { label: string; className: string; icon: typeof ShieldCheck }> = {
  high: {
    label: 'High concern',
    className: 'bg-red-50 text-red-700 border-red-200',
    icon: ShieldAlert,
  },
  medium: {
    label: 'Needs review',
    className: 'bg-amber-50 text-amber-700 border-amber-200',
    icon: ShieldQuestion,
  },
  low: {
    label: 'Low concern',
    className: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    icon: ShieldCheck,
  },
};

const severityDot: Record<string, string> = {
  high: 'bg-red-500',
  medium: 'bg-amber-500',
  low: 'bg-emerald-500',
};

const typeIcon: Record<string, typeof Bot> = {
  ai_detection: Bot,
  peer_similarity: GitCompare,
  web_provenance: Globe,
};

const outcomeLabels: Record<string, string> = {
  authorship_confirmed: 'Authorship confirmed',
  concerns_unresolved: 'Concerns unresolved',
  breach_identified: 'Breach identified',
  inconclusive: 'Inconclusive',
};

const outcomeStyles: Record<string, string> = {
  authorship_confirmed: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  concerns_unresolved: 'bg-amber-50 text-amber-700 border-amber-200',
  breach_identified: 'bg-red-50 text-red-700 border-red-200',
  inconclusive: 'bg-slate-100 text-slate-600 border-slate-200',
};

function pct(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return `${Math.round(Number(value) * 100)}%`;
}

export default function EvidenceDossierPage() {
  const { id } = useParams();
  const [dossier, setDossier] = useState<DossierPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [outcomeDrafts, setOutcomeDrafts] = useState<
    Record<string, { outcome: string; notes: string }>
  >({});
  const [savingStudent, setSavingStudent] = useState('');

  const draftFor = (student: StudentDossier) =>
    outcomeDrafts[student.student] ?? {
      outcome: student.viva_outcome?.outcome ?? '',
      notes: student.viva_outcome?.notes ?? '',
    };

  const saveOutcome = async (
    student: StudentDossier,
    draft: { outcome: string; notes: string },
  ) => {
    if (!draft.outcome || !id) return;
    setSavingStudent(student.student);
    try {
      const conductedAt = new Date().toISOString();
      await apiClient.put(`/api/job/${id}/viva`, {
        submission_name: student.student,
        outcome: draft.outcome,
        notes: draft.notes || null,
        conducted_at: conductedAt,
      });
      setDossier((prev) =>
        prev
          ? {
              ...prev,
              students: prev.students.map((s) =>
                s.student === student.student
                  ? {
                      ...s,
                      viva_outcome: {
                        outcome: draft.outcome,
                        notes: draft.notes || null,
                        conducted_at: conductedAt,
                      },
                    }
                  : s,
              ),
            }
          : prev,
      );
    } catch (err) {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
          'Failed to save viva outcome.',
      );
    } finally {
      setSavingStudent('');
    }
  };

  useEffect(() => {
    if (!id) return;
    apiClient
      .get(`/api/job/${id}/dossier`)
      .then((res) => {
        setDossier(res.data);
        setError('');
      })
      .catch((err) => {
        setError(err?.response?.data?.detail || 'Failed to load evidence dossier.');
        setDossier(null);
      })
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex min-h-[60vh] items-center justify-center gap-3 text-slate-500">
          <Loader2 size={18} className="animate-spin" />
          Building evidence dossier...
        </div>
      </DashboardLayout>
    );
  }

  if (error || !dossier) {
    return (
      <DashboardLayout>
        <div className="px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <div className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
            <AlertCircle size={16} className="mt-0.5 shrink-0" />
            {error || 'Dossier unavailable.'}
          </div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
              Evidence Dossier
            </h1>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              Job {dossier.job_id} · {dossier.students.length} student
              {dossier.students.length === 1 ? '' : 's'} · one fused view of AI detection,
              peer similarity and public-source matches.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <a
              href={`/dossier/${dossier.job_id}/download-pdf`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              <FileDown size={14} />
              Download PDF
            </a>
            <Link
              href={`/results/${dossier.job_id}`}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              <ArrowLeft size={14} />
              Back to results
            </Link>
          </div>
        </div>

        <div className="mb-6 flex flex-wrap gap-2 text-xs">
          {(
            [
              ['AI detection', dossier.coverage.ai_detection],
              ['Pairwise similarity', dossier.coverage.pairwise],
              ['Web provenance', dossier.coverage.web_analysis],
            ] as [string, boolean][]
          ).map(([label, covered]) => (
            <span
              key={label}
              className={`rounded-full border px-2.5 py-1 ${
                covered
                  ? 'border-sky-200 bg-sky-50 text-sky-700'
                  : 'border-slate-200 bg-slate-50 text-slate-400'
              }`}
            >
              {covered ? '✓' : '—'} {label}
            </span>
          ))}
        </div>

        {dossier.students.length === 0 ? (
          <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-900">
            No evidence recorded for this job.
          </div>
        ) : (
          <div className="space-y-4">
            {dossier.students.map((student) => {
              const band = bandStyles[student.band] || bandStyles.low;
              const BandIcon = band.icon;
              const draft = draftFor(student);
              return (
                <div
                  key={student.student}
                  className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-sm font-semibold text-slate-900 dark:text-slate-100">
                        {student.student}
                      </span>
                      <span
                        className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${band.className}`}
                      >
                        <BandIcon size={12} />
                        {band.label}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-4 text-xs text-slate-500 dark:text-slate-400">
                      <span>AI: <strong>{pct(student.ai_probability)}</strong></span>
                      <span>
                        Peer: <strong>{pct(student.peer_max_similarity)}</strong>
                        {student.peer_partner ? ` (${student.peer_partner})` : ''}
                      </span>
                      <span>
                        Web: <strong>{pct(student.web_max_similarity)}</strong>
                        {student.web_best_match_source
                          ? ` (${student.web_best_match_source})`
                          : ''}
                      </span>
                    </div>
                  </div>

                  {student.evidence.length > 0 && (
                    <ul className="mt-4 space-y-2">
                      {student.evidence.map((item, index) => {
                        const Icon = typeIcon[item.type] || HelpCircle;
                        return (
                          <li
                            key={index}
                            className="flex items-start gap-3 rounded-xl bg-slate-50 px-3 py-2 text-sm dark:bg-slate-800"
                          >
                            <Icon size={15} className="mt-0.5 shrink-0 text-slate-400" />
                            <div>
                              <div className="flex items-center gap-2">
                                <span
                                  className={`h-1.5 w-1.5 rounded-full ${
                                    severityDot[item.severity] || 'bg-slate-400'
                                  }`}
                                />
                                <span className="font-medium text-slate-800 dark:text-slate-200">
                                  {item.title}
                                </span>
                              </div>
                              {item.detail && (
                                <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                                  {item.detail}
                                </p>
                              )}
                            </div>
                          </li>
                        );
                      })}
                    </ul>
                  )}

                  {student.viva_questions.length > 0 && (
                    <div className="mt-4 rounded-xl border border-indigo-100 bg-indigo-50/60 p-4 dark:border-indigo-900/50 dark:bg-indigo-950/30">
                      <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-indigo-700 dark:text-indigo-300">
                        <HelpCircle size={13} />
                        Suggested viva questions
                      </div>
                      <ol className="list-decimal space-y-1.5 pl-5 text-sm text-slate-700 dark:text-slate-300">
                        {student.viva_questions.map((question, index) => (
                          <li key={index}>{question}</li>
                        ))}
                      </ol>
                    </div>
                  )}

                  {student.viva_outcome && (
                    <div
                      className={`mt-4 rounded-xl border px-3 py-2 text-sm ${
                        outcomeStyles[student.viva_outcome.outcome] ||
                        outcomeStyles.inconclusive
                      }`}
                    >
                      <span className="inline-flex items-center gap-1.5 font-medium">
                        <ClipboardCheck size={14} />
                        Viva outcome: {outcomeLabels[student.viva_outcome.outcome] ||
                          student.viva_outcome.outcome}
                        {student.viva_outcome.conducted_at &&
                          ` · ${new Date(
                            student.viva_outcome.conducted_at,
                          ).toLocaleString()}`}
                      </span>
                      {student.viva_outcome.notes && (
                        <p className="mt-1 text-xs opacity-80">
                          {student.viva_outcome.notes}
                        </p>
                      )}
                    </div>
                  )}

                  <div className="mt-4 flex flex-wrap items-center gap-2">
                    <select
                      value={draft.outcome}
                      onChange={(e) =>
                        setOutcomeDrafts((prev) => ({
                          ...prev,
                          [student.student]: { ...draft, outcome: e.target.value },
                        }))
                      }
                      className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-sm text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
                      aria-label={`Viva outcome for ${student.student}`}
                    >
                      <option value="">Record viva outcome…</option>
                      {Object.entries(outcomeLabels).map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </select>
                    <input
                      value={draft.notes}
                      onChange={(e) =>
                        setOutcomeDrafts((prev) => ({
                          ...prev,
                          [student.student]: { ...draft, notes: e.target.value },
                        }))
                      }
                      placeholder="Interview notes (optional)"
                      className="min-w-[12rem] flex-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-sm text-slate-700 placeholder:text-slate-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
                    />
                    <button
                      onClick={() => saveOutcome(student, draft)}
                      disabled={!draft.outcome || savingStudent === student.student}
                      className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-40 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-300"
                    >
                      {savingStudent === student.student ? 'Saving…' : 'Save outcome'}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        <p className="mt-6 text-xs text-slate-400 dark:text-slate-500">
          Evidence and questions are decision support for a human reviewer, never proof
          of misconduct on their own.
        </p>
      </div>
    </DashboardLayout>
  );
}
