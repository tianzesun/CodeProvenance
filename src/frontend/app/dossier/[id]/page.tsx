'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { Modal, PageHeader } from '@/components/saas/SaaSPrimitives';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { apiClient } from '@/lib/apiClient';
import {
  AlertCircle,
  ArrowLeft,
  Bot,
  CheckCircle2,
  ClipboardCheck,
  ExternalLink,
  FileDown,
  GitCompare,
  Globe,
  HelpCircle,
  Loader2,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  ShieldQuestion,
} from 'lucide-react';

// ─── Types ─────────────────────────────────────────────────────────────────────

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

interface Draft {
  outcome: string;
  notes: string;
  /** datetime-local value (local time), e.g. 2026-10-02T14:30 */
  conductedAt: string;
}

type BandFilter = 'all' | 'high' | 'medium' | 'low';
type SortOrder = 'concern' | 'name' | 'reported';

// ─── Constants ─────────────────────────────────────────────────────────────────

const bandStyles: Record<string, { label: string; className: string; icon: typeof ShieldCheck }> = {
  high: {
    label: 'High concern',
    className:
      'border-red-200 bg-red-50 text-red-700 dark:border-red-500/25 dark:bg-red-500/15 dark:text-red-300',
    icon: ShieldAlert,
  },
  medium: {
    label: 'Needs review',
    className:
      'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/25 dark:bg-amber-500/15 dark:text-amber-300',
    icon: ShieldQuestion,
  },
  low: {
    label: 'Low concern',
    className:
      'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/25 dark:bg-emerald-500/15 dark:text-emerald-300',
    icon: ShieldCheck,
  },
};

// An unknown band used to fall back to "Low concern", which is a reassuring label for something unrated.
const unratedBand = {
  label: 'Not rated',
  className: 'border-slate-200 bg-slate-100 text-slate-600 dark:border-slate-800 dark:bg-slate-800 dark:text-slate-300',
  icon: HelpCircle,
};

const BAND_RANK: Record<string, number> = { high: 0, medium: 1, low: 2 };

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
  authorship_confirmed:
    'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/25 dark:bg-emerald-500/15 dark:text-emerald-300',
  concerns_unresolved:
    'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/25 dark:bg-amber-500/15 dark:text-amber-300',
  breach_identified:
    'border-red-200 bg-red-50 text-red-700 dark:border-red-500/25 dark:bg-red-500/15 dark:text-red-300',
  inconclusive:
    'border-slate-200 bg-slate-100 text-slate-600 dark:border-slate-800 dark:bg-slate-800 dark:text-slate-300',
};

const PAGE_STEP = 25;
const MAX_NOTES = 2000;
const FIELD =
  'rounded-xl border border-slate-200 bg-white px-2.5 py-1.5 text-sm text-slate-700 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white';

// ─── Helpers ───────────────────────────────────────────────────────────────────

const REFERENCE_HEADERS = ['x-correlation-id', 'x-request-id'];

/** Generic, status-keyed text; a correlation id is appended when the backend sends one. */
function describeError(error: unknown, fallback: string): string {
  const response = (error as { response?: { status?: unknown; headers?: unknown } } | null)?.response;
  const status = typeof response?.status === 'number' ? response.status : undefined;
  const headers = (response?.headers ?? {}) as Record<string, unknown>;
  const reference = REFERENCE_HEADERS.map((name) => headers[name]).find(
    (value): value is string => typeof value === 'string' && value.length > 0
  );

  let message = fallback;
  if (status === 401) message = 'Your session has expired. Please sign in again.';
  else if (status === 403) message = 'You don’t have permission to do that.';
  else if (status === 404) message = 'This job or dossier could not be found.';
  else if (status === 409) message = 'This record was changed by someone else. Refresh the page and try again.';
  else if (status === 429) message = 'Too many requests. Please wait a moment and try again.';

  return reference ? `${message} (Reference: ${reference})` : message;
}

function pct(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return `${Math.round(Number(value) * 100)}%`;
}

function formatDateTime(value?: string | null): string {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat('en-US', { dateStyle: 'medium', timeStyle: 'short' }).format(date);
}

/** ISO timestamp -> value for <input type="datetime-local"> in the user's own time zone. */
function toLocalInput(iso?: string | null): string {
  const date = iso ? new Date(iso) : new Date();
  if (Number.isNaN(date.getTime())) return '';
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

/** Only http(s) links from the report are rendered as links. */
function safeHref(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return (url.protocol === 'http:' || url.protocol === 'https:') && url.hostname ? url.toString() : null;
  } catch {
    return null;
  }
}

function maxSignal(student: StudentDossier): number {
  const values = [student.ai_probability, student.peer_max_similarity, student.web_max_similarity]
    .map((v) => (v === null || v === undefined ? NaN : Number(v)))
    .filter((v) => Number.isFinite(v));
  return values.length ? Math.max(...values) : -1;
}

function normalizeDossier(raw: unknown): DossierPayload | null {
  const data = raw as Partial<DossierPayload> | null;
  if (!data || typeof data !== 'object') return null;
  const students = Array.isArray(data.students) ? data.students : [];
  return {
    job_id: String(data.job_id ?? ''),
    generated_at: String(data.generated_at ?? ''),
    coverage: {
      ai_detection: Boolean(data.coverage?.ai_detection),
      web_analysis: Boolean(data.coverage?.web_analysis),
      pairwise: Boolean(data.coverage?.pairwise),
    },
    students: students.map((s) => ({
      ...s,
      student: String(s?.student ?? 'Unnamed submission'),
      band: String(s?.band ?? ''),
      evidence: Array.isArray(s?.evidence) ? s.evidence : [],
      viva_questions: Array.isArray(s?.viva_questions) ? s.viva_questions : [],
      viva_outcome: s?.viva_outcome ?? null,
    })) as StudentDossier[],
  };
}

// ─── Page ──────────────────────────────────────────────────────────────────────

export default function EvidenceDossierPage() {
  const params = useParams<{ id: string | string[] }>();
  const id = Array.isArray(params?.id) ? params.id[0] : params?.id;

  const [dossier, setDossier] = useState<DossierPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [savingStudent, setSavingStudent] = useState('');
  const [saveErrors, setSaveErrors] = useState<Record<string, string>>({});
  const [savedFlash, setSavedFlash] = useState<Record<string, boolean>>({});
  const [confirming, setConfirming] = useState<{ student: StudentDossier; draft: Draft } | null>(null);

  const [bandFilter, setBandFilter] = useState<BandFilter>('all');
  const [query, setQuery] = useState('');
  const [order, setOrder] = useState<SortOrder>('concern');
  const [visibleCount, setVisibleCount] = useState(PAGE_STEP);
  const requestIdRef = useRef(0);

  // ── Loading ──────────────────────────────────────────────────────────────────

  const loadDossier = useCallback(async (signal?: AbortSignal, background = false) => {
    if (!id) return;
    const requestId = ++requestIdRef.current;
    if (background) setRefreshing(true);
    try {
      const res = await apiClient.get(`/api/job/${encodeURIComponent(id)}/dossier`, { signal });
      if (requestId !== requestIdRef.current) return;
      const normalized = normalizeDossier(res.data);
      if (!normalized) throw new Error('bad payload');
      setDossier(normalized);
      setLoadError('');
    } catch (err) {
      if (signal?.aborted || requestId !== requestIdRef.current) return;
      // A failed refresh keeps the dossier on screen.
      setLoadError(describeError(err, 'Failed to load the evidence dossier.'));
    } finally {
      if (requestId === requestIdRef.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, [id]);

  useEffect(() => {
    // With no id the page used to sit on "Building evidence dossier..." forever.
    if (!id) {
      setLoading(false);
      setLoadError('This page needs a job id.');
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    loadDossier(controller.signal);
    return () => controller.abort();
  }, [id, reloadKey, loadDossier]);

  // ── Drafts ───────────────────────────────────────────────────────────────────

  const savedDraft = (student: StudentDossier): Draft => ({
    outcome: student.viva_outcome?.outcome ?? '',
    notes: student.viva_outcome?.notes ?? '',
    conductedAt: student.viva_outcome?.conducted_at ? toLocalInput(student.viva_outcome.conducted_at) : '',
  });

  const draftFor = (student: StudentDossier): Draft => drafts[student.student] ?? savedDraft(student);

  const isDirty = (student: StudentDossier): boolean => {
    const draft = drafts[student.student];
    if (!draft) return false;
    const saved = savedDraft(student);
    return draft.outcome !== saved.outcome || draft.notes.trim() !== saved.notes.trim() || draft.conductedAt !== saved.conductedAt;
  };

  const anyDirty = dossier?.students.some(isDirty) ?? false;

  // Unsaved interview notes would be lost on reload or navigation.
  useEffect(() => {
    if (!anyDirty) return;
    const handler = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [anyDirty]);

  const updateDraft = (student: StudentDossier, patch: Partial<Draft>) => {
    setDrafts((prev) => {
      const current = prev[student.student] ?? savedDraft(student);
      const next = { ...current, ...patch };
      // Picking an outcome fills in the interview time, which the user can then correct.
      if (patch.outcome && !next.conductedAt) next.conductedAt = toLocalInput(null);
      return { ...prev, [student.student]: next };
    });
    setSavedFlash((prev) => ({ ...prev, [student.student]: false }));
    setSaveErrors((prev) => ({ ...prev, [student.student]: '' }));
  };

  // ── Saving ───────────────────────────────────────────────────────────────────

  const performSave = async (student: StudentDossier, draft: Draft) => {
    if (!id || savingStudent) return;
    const conducted = new Date(draft.conductedAt);
    setSavingStudent(student.student);
    setSaveErrors((prev) => ({ ...prev, [student.student]: '' }));
    try {
      // The interview time used to be set to "now" on every save, which overwrote the real date
      // whenever an outcome or its notes were edited later.
      const conductedAt = conducted.toISOString();
      await apiClient.put(`/api/job/${encodeURIComponent(id)}/viva`, {
        submission_name: student.student,
        outcome: draft.outcome,
        notes: draft.notes.trim() || null,
        conducted_at: conductedAt,
      });
      setDossier((prev) =>
        prev
          ? {
              ...prev,
              students: prev.students.map((s) =>
                s.student === student.student
                  ? { ...s, viva_outcome: { outcome: draft.outcome, notes: draft.notes.trim() || null, conducted_at: conductedAt } }
                  : s
              ),
            }
          : prev
      );
      // The saved record is now the source of truth for this card.
      setDrafts((prev) => {
        const next = { ...prev };
        delete next[student.student];
        return next;
      });
      setSavedFlash((prev) => ({ ...prev, [student.student]: true }));
    } catch (err) {
      // Shown on the card. It used to replace the whole dossier with an error screen and drop every draft.
      setSaveErrors((prev) => ({ ...prev, [student.student]: describeError(err, 'Failed to save the viva outcome. Your entry is still here.') }));
    } finally {
      setSavingStudent('');
    }
  };

  const requestSave = (student: StudentDossier) => {
    const draft = draftFor(student);
    if (!draft.outcome) return;

    const conducted = new Date(draft.conductedAt);
    if (!draft.conductedAt || Number.isNaN(conducted.getTime())) {
      setSaveErrors((prev) => ({ ...prev, [student.student]: 'Enter the date and time the viva took place.' }));
      return;
    }
    if (conducted.getTime() > Date.now() + 5 * 60 * 1000) {
      setSaveErrors((prev) => ({ ...prev, [student.student]: 'The viva time can’t be in the future.' }));
      return;
    }

    const existing = student.viva_outcome?.outcome;
    // A breach finding, or replacing a recorded outcome, is a formal change to the record.
    if (draft.outcome === 'breach_identified' || (existing && existing !== draft.outcome)) {
      setConfirming({ student, draft });
      return;
    }
    performSave(student, draft);
  };

  // ── Derived list ─────────────────────────────────────────────────────────────

  const bandCounts = useMemo(() => {
    const counts: Record<BandFilter, number> = { all: 0, high: 0, medium: 0, low: 0 };
    for (const s of dossier?.students ?? []) {
      counts.all += 1;
      if (s.band === 'high' || s.band === 'medium' || s.band === 'low') counts[s.band] += 1;
    }
    return counts;
  }, [dossier]);

  const shownStudents = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = (dossier?.students ?? []).filter((s) => {
      if (bandFilter !== 'all' && s.band !== bandFilter) return false;
      if (q && !s.student.toLowerCase().includes(q) && !(s.peer_partner || '').toLowerCase().includes(q)) return false;
      return true;
    });
    if (order === 'name') return [...list].sort((a, b) => a.student.localeCompare(b.student, undefined, { numeric: true }));
    if (order === 'concern') {
      return [...list].sort(
        (a, b) =>
          (BAND_RANK[a.band] ?? 3) - (BAND_RANK[b.band] ?? 3) ||
          maxSignal(b) - maxSignal(a) ||
          a.student.localeCompare(b.student, undefined, { numeric: true })
      );
    }
    return list;
  }, [dossier, bandFilter, query, order]);

  // ── Views ────────────────────────────────────────────────────────────────────

  if (loading && !dossier) {
    return (
      <DashboardLayout>
        <div className="theme-page-container space-y-6">
          <div role="status" className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950">
            <span className="sr-only">Building evidence dossier...</span>
            <div className="h-5 w-28 animate-pulse rounded-full bg-slate-200 dark:bg-slate-800" />
            <div className="mt-4 h-10 w-72 animate-pulse rounded-2xl bg-slate-200 dark:bg-slate-800" />
            <div className="mt-3 h-4 w-[28rem] max-w-full animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="rounded-[24px] border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950"
              >
                <div className="h-4 w-24 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
                <div className="mt-4 h-9 w-16 animate-pulse rounded-xl bg-slate-200 dark:bg-slate-800" />
              </div>
            ))}
          </div>
        </div>
      </DashboardLayout>
    );
  }

  if (!dossier) {
    return (
      <DashboardLayout>
        <div className="theme-page-container space-y-6">
          <div role="alert" className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300">
            <AlertCircle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
            <span className="flex-1">{loadError || 'Dossier unavailable.'}</span>
            <button
              type="button"
              onClick={() => setReloadKey((k) => k + 1)}
              className="inline-flex h-9 shrink-0 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
            >
              Try again
            </button>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  const encodedJobId = encodeURIComponent(dossier.job_id);
  const incompleteCoverage = !dossier.coverage.ai_detection || !dossier.coverage.pairwise || !dossier.coverage.web_analysis;
  const generated = formatDateTime(dossier.generated_at);

  return (
    <DashboardLayout>
      <div className="theme-page-container space-y-6">
        <PageHeader
          eyebrow="Dossier"
          eyebrowStyle="badge"
          title="Evidence Dossier"
          description={`Job ${dossier.job_id} · ${dossier.students.length} student${dossier.students.length === 1 ? '' : 's'}${generated ? ` · generated ${generated}` : ''}`}
          action={
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => loadDossier(undefined, true)}
                disabled={refreshing}
                className="inline-flex h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
              >
                <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} aria-hidden="true" />
                {refreshing ? 'Refreshing…' : 'Refresh'}
              </button>
              <a
                href={`/report/${encodedJobId}/download-pdf`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
              >
                <FileDown size={14} aria-hidden="true" />
                Download PDF
              </a>
              <Link
                href={`/results/${encodedJobId}`}
                className="inline-flex h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
              >
                <ArrowLeft size={14} aria-hidden="true" />
                Back to results
              </Link>
            </div>
          }
        />

        {loadError && (
          <div role="alert" className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300">
            <AlertCircle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
            {loadError} Showing the last loaded dossier.
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          {(
            [
              ['AI detection', dossier.coverage.ai_detection],
              ['Pairwise similarity', dossier.coverage.pairwise],
              ['Web provenance', dossier.coverage.web_analysis],
            ] as [string, boolean][]
          ).map(([label, covered]) => (
            <span
              key={label}
              className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${covered
                ? 'bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300'
                : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300'
                }`}
            >
              <span aria-hidden="true">{covered ? '✓' : '—'}</span> {label}
              <span className="sr-only">{covered ? ' was analysed' : ' was not analysed'}</span>
            </span>
          ))}
        </div>

        {incompleteCoverage && (
          <p role="note" className="text-xs text-amber-700 dark:text-amber-400">
            Not every analysis ran for this job. A concern band reflects only the analyses that did, so “Low concern” does
            not mean the missing checks were clear.
          </p>
        )}

        {/* Filters */}
        {dossier.students.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <div role="group" aria-label="Filter by concern" className="flex flex-wrap gap-2">
              {(
                [
                  ['all', 'All'],
                  ['high', 'High concern'],
                  ['medium', 'Needs review'],
                  ['low', 'Low concern'],
                ] as [BandFilter, string][]
              ).map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  aria-pressed={bandFilter === key}
                  onClick={() => { setBandFilter(key); setVisibleCount(PAGE_STEP); }}
                  className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition ${bandFilter === key
                    ? 'border-slate-900 bg-slate-900 text-white dark:border-slate-100 dark:bg-slate-100 dark:text-slate-900'
                    : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800'
                    }`}
                >
                  {label} ({bandCounts[key]})
                </button>
              ))}
            </div>
            <label className="ml-auto flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-500 transition focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900">
              <Search size={14} aria-hidden="true" />
              <input
                type="search"
                name="student-search"
                autoComplete="off"
                value={query}
                onChange={(e) => { setQuery(e.target.value); setVisibleCount(PAGE_STEP); }}
                placeholder="Search students"
                aria-label="Search students"
                className="w-40 bg-transparent text-slate-900 placeholder:text-slate-400 focus:outline-none dark:text-white dark:placeholder:text-slate-500"
              />
            </label>
            <select
              value={order}
              onChange={(e) => setOrder(e.target.value as SortOrder)}
              aria-label="Order students"
              className={FIELD}
            >
              <option value="concern">Highest concern first</option>
              <option value="name">Name</option>
              <option value="reported">As reported</option>
            </select>
          </div>
        )}

        <p role="status" className="sr-only">{shownStudents.length} of {dossier.students.length} students shown</p>

        {dossier.students.length === 0 ? (
          <div className="overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
            <div className="px-5 py-16 text-center">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-slate-100 text-slate-500 dark:bg-slate-900 dark:text-slate-400">
                <ClipboardCheck size={22} aria-hidden="true" />
              </div>
              <h3 className="mt-4 text-base font-semibold text-slate-900 dark:text-white">
                No evidence recorded
              </h3>
              <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500 dark:text-slate-400">
                No evidence recorded for this job.
              </p>
            </div>
          </div>
        ) : shownStudents.length === 0 ? (
          <div className="overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
            <div className="px-5 py-16 text-center">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-slate-100 text-slate-500 dark:bg-slate-900 dark:text-slate-400">
                <Search size={22} aria-hidden="true" />
              </div>
              <h3 className="mt-4 text-base font-semibold text-slate-900 dark:text-white">
                No students match the current filters
              </h3>
              <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500 dark:text-slate-400">
                Try a different search or concern filter to see more students.
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {shownStudents.slice(0, visibleCount).map((student, studentIndex) => {
              const band = bandStyles[student.band] || unratedBand;
              const BandIcon = band.icon;
              const draft = draftFor(student);
              const dirty = isDirty(student);
              const saving = savingStudent === student.student;
              const webHref = safeHref(student.web_best_match_url);
              const webHost = webHref ? new URL(webHref).hostname : '';
              const saveError = saveErrors[student.student];
              const outcomeId = `outcome-${studentIndex}`;
              return (
                <section
                  key={`${student.student}-${studentIndex}`}
                  aria-label={`Evidence for ${student.student}`}
                  className="relative flex h-full flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md dark:border-slate-800 dark:bg-slate-950"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <h2 className="text-lg font-semibold tracking-tight text-slate-900 dark:text-white">
                        {student.student}
                      </h2>
                      <span
                        className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${band.className}`}
                      >
                        <BandIcon size={12} aria-hidden="true" />
                        {band.label}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-4 text-xs text-slate-500 dark:text-slate-400">
                      <span>
                        AI: <strong>{pct(student.ai_probability)}</strong>
                        {student.ai_confidence !== null && student.ai_confidence !== undefined
                          ? ` (confidence ${pct(student.ai_confidence)})`
                          : ''}
                      </span>
                      <span>
                        Peer: <strong>{pct(student.peer_max_similarity)}</strong>
                        {student.peer_partner ? ` (${student.peer_partner})` : ''}
                      </span>
                      <span>
                        Web: <strong>{pct(student.web_max_similarity)}</strong>
                        {student.web_best_match_source ? ` (${student.web_best_match_source})` : ''}
                      </span>
                    </div>
                  </div>

                  {/* web_best_match_url was in the data but never shown */}
                  {webHref && (
                    <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                      Closest web match:{' '}
                      <a href={webHref} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 font-medium text-blue-600 hover:underline dark:text-blue-400">
                        {webHost}
                        <ExternalLink size={11} aria-hidden="true" />
                      </a>
                    </p>
                  )}

                  {student.evidence.length > 0 && (
                    <ul className="mt-4 space-y-2">
                      {student.evidence.map((item, index) => {
                        const Icon = typeIcon[item.type] || HelpCircle;
                        return (
                          <li
                            key={index}
                            className="flex items-start gap-3 rounded-xl bg-slate-50 px-3 py-2 text-sm dark:bg-slate-800"
                          >
                            <Icon size={15} className="mt-0.5 shrink-0 text-slate-400" aria-hidden="true" />
                            <div>
                              <div className="flex items-center gap-2">
                                <span
                                  aria-hidden="true"
                                  className={`h-1.5 w-1.5 rounded-full ${severityDot[item.severity] || 'bg-slate-400'}`}
                                />
                                <span className="sr-only">{item.severity ? `${item.severity} severity: ` : ''}</span>
                                <span className="font-medium text-slate-900 dark:text-white">{item.title}</span>
                              </div>
                              {item.detail && (
                                <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{item.detail}</p>
                              )}
                            </div>
                          </li>
                        );
                      })}
                    </ul>
                  )}

                  {student.viva_questions.length > 0 && (
                    <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-900">
                      <div className="mb-2 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
                        <HelpCircle size={13} aria-hidden="true" />
                        Suggested viva questions
                      </div>
                      <ol className="list-decimal space-y-1.5 pl-5 text-sm text-slate-700 dark:text-white">
                        {student.viva_questions.map((question, index) => (
                          <li key={index}>{question}</li>
                        ))}
                      </ol>
                    </div>
                  )}

                  {student.viva_outcome && (
                    <div
                      className={`mt-4 rounded-xl border px-3 py-2 text-sm ${outcomeStyles[student.viva_outcome.outcome] || outcomeStyles.inconclusive}`}
                    >
                      <span className="inline-flex items-center gap-1.5 font-medium">
                        <ClipboardCheck size={14} aria-hidden="true" />
                        Viva outcome: {outcomeLabels[student.viva_outcome.outcome] || student.viva_outcome.outcome}
                        {formatDateTime(student.viva_outcome.conducted_at) && ` · ${formatDateTime(student.viva_outcome.conducted_at)}`}
                      </span>
                      {student.viva_outcome.notes && (
                        <p className="mt-1 whitespace-pre-wrap text-xs opacity-80">{student.viva_outcome.notes}</p>
                      )}
                    </div>
                  )}

                  <div className="mt-4 flex flex-wrap items-center gap-2">
                    <select
                      id={outcomeId}
                      value={draft.outcome}
                      onChange={(e) => updateDraft(student, { outcome: e.target.value })}
                      className={FIELD}
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
                      type="datetime-local"
                      value={draft.conductedAt}
                      onChange={(e) => updateDraft(student, { conductedAt: e.target.value })}
                      aria-label={`When the viva with ${student.student} took place`}
                      disabled={!draft.outcome}
                      className={`${FIELD} disabled:opacity-50`}
                    />
                    <input
                      value={draft.notes}
                      onChange={(e) => updateDraft(student, { notes: e.target.value })}
                      placeholder="Interview notes (optional)"
                      aria-label={`Interview notes for ${student.student}`}
                      maxLength={MAX_NOTES}
                      autoComplete="off"
                      className={`min-w-[12rem] flex-1 ${FIELD} placeholder:text-slate-400`}
                    />
                    <button
                      type="button"
                      onClick={() => requestSave(student)}
                      disabled={!draft.outcome || !dirty || Boolean(savingStudent)}
                      className="inline-flex h-9 items-center gap-2 rounded-xl bg-blue-600 px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {saving && <Loader2 size={14} className="animate-spin" aria-hidden="true" />}
                      {saving ? 'Saving…' : 'Save outcome'}
                    </button>
                  </div>

                  {saveError && (
                    <p role="alert" className="mt-2 flex items-start gap-1.5 text-xs text-red-600 dark:text-red-400">
                      <AlertCircle size={13} className="mt-0.5 shrink-0" aria-hidden="true" />
                      {saveError}
                    </p>
                  )}
                  {savedFlash[student.student] && !dirty && (
                    <p role="status" className="mt-2 flex items-center gap-1.5 text-xs text-emerald-600 dark:text-emerald-400">
                      <CheckCircle2 size={13} aria-hidden="true" />
                      Outcome saved.
                    </p>
                  )}
                </section>
              );
            })}
            {shownStudents.length > visibleCount && (
              <button
                type="button"
                onClick={() => setVisibleCount((n) => n + PAGE_STEP)}
                className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
              >
                Show more ({shownStudents.length - visibleCount} remaining)
              </button>
            )}
          </div>
        )}

        <p className="text-xs text-slate-500 dark:text-slate-400">
          Evidence and questions are decision support for a human reviewer, never proof
          of misconduct on their own.
        </p>
      </div>

      {/* Formal outcomes are confirmed before they are written to the record. */}
      <Modal
        open={confirming !== null}
        title="Record this outcome?"
        description="This is saved to the job’s record and replaces any outcome already recorded for this student."
        onClose={() => { if (!savingStudent) setConfirming(null); }}
        footer={(
          <>
            <button
              type="button"
              onClick={() => setConfirming(null)}
              disabled={Boolean(savingStudent)}
              className="inline-flex h-10 items-center justify-center rounded-xl border border-slate-200 px-4 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-60 dark:border-slate-800 dark:text-slate-200 dark:hover:bg-slate-900"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={Boolean(savingStudent)}
              onClick={async () => {
                if (!confirming) return;
                const { student, draft } = confirming;
                await performSave(student, draft);
                setConfirming(null);
              }}
              className="inline-flex h-10 items-center gap-2 rounded-xl bg-slate-950 px-4 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:opacity-60 dark:bg-white dark:text-slate-950"
            >
              {savingStudent && <Loader2 size={14} className="animate-spin" aria-hidden="true" />}
              Record outcome
            </button>
          </>
        )}
      >
        {confirming && (
          <p className="text-sm leading-6 text-slate-600 dark:text-slate-400">
            <strong className="font-semibold text-slate-800 dark:text-white">{outcomeLabels[confirming.draft.outcome] || confirming.draft.outcome}</strong>
            {' '}for <span className="font-mono">{confirming.student.student}</span>
            {confirming.student.viva_outcome && confirming.student.viva_outcome.outcome !== confirming.draft.outcome
              ? `, replacing “${outcomeLabels[confirming.student.viva_outcome.outcome] || confirming.student.viva_outcome.outcome}”`
              : ''}
            . A viva outcome is a human decision; the report’s evidence on its own does not establish misconduct.
          </p>
        )}
      </Modal>
    </DashboardLayout>
  );
}
