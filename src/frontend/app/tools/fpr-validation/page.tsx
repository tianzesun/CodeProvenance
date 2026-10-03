'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { Modal, PageHeader } from '@/components/saas/SaaSPrimitives';
import { useState, useEffect, useCallback, useRef } from 'react';
import { apiClient } from '@/lib/apiClient';
import {
  AlertCircle,
  CheckCircle2,
  ClipboardList,
  FileText,
  Loader2,
  Play,
  Printer,
  Trash2,
  UploadCloud,
  X,
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceArea,
} from 'recharts';

// ─── Types ─────────────────────────────────────────────────────────────────────

interface RecommendationItem {
  threshold: number;
  fpr: number;
  type: string;
  title: string;
  advice: string;
}

interface FprRow {
  threshold: number;
  fpr: number;
  fpr_percent: number;
  label: string;
  flagged_pairs: number;
}

interface FprResult {
  num_submissions: number;
  num_pairs: number;
  mean_score: number;
  max_score: number;
  fpr_table: FprRow[];
  score_histogram: Array<{ bin: string; count: number }>;
  recommendation: string; // legacy
  recommendations: RecommendationItem[];
  overall_assessment: string;
  suggested_actions: string[];
}

interface FprRunSummary {
  id: string;
  name: string;
  created_at: string;
  num_submissions: number | null;
  num_pairs: number | null;
  recommended_threshold: number | null;
  fpr_at_recommended_threshold: number | null;
  is_certified: boolean;
  status: string;
}

// ─── Constants ─────────────────────────────────────────────────────────────────

const ZONE_MIN = 0.65;
const ZONE_MAX = 0.78;
const RECOMMENDED_MIN_SUBMISSIONS = 40;
const MAX_FILES = 500;
const MAX_FILE_BYTES = 5 * 1024 * 1024;

// Same list the benchmark upload accepts. The picker only hints at types; dropped files bypass it.
const ALLOWED_EXTENSIONS = ['zip', 'txt', 'py', 'java', 'c', 'cpp', 'h', 'hpp', 'js', 'ts', 'jsx', 'tsx', 'go', 'rs', 'rb', 'php', 'cs', 'kt', 'swift', 'scala', 'r', 'm', 'sql', 'sh', 'bash'];
const ACCEPT = ALLOWED_EXTENSIONS.map((ext) => `.${ext}`).join(',');

const REFERENCE_HEADERS = ['x-correlation-id', 'x-request-id'];

// ─── Helpers ───────────────────────────────────────────────────────────────────

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
  else if (status === 403) message = 'You don’t have permission to do that. Administrator access is required.';
  else if (status === 404) message = 'That run no longer exists. Refresh the list and try again.';
  else if (status === 413) message = 'The upload is too large. Remove some files and try again.';
  else if (status === 422 || status === 400) message = 'The server couldn’t analyse those files. Check that they are readable source files.';
  else if (status === 429) message = 'Too many requests. Please wait a moment and try again.';

  return reference ? `${message} (Reference: ${reference})` : message;
}

function isCanceled(err: unknown): boolean {
  const e = err as { name?: string; code?: string } | null;
  return e?.name === 'CanceledError' || e?.code === 'ERR_CANCELED';
}

const toNumber = (value: unknown, fallback = 0): number => {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
};
const clamp01 = (value: unknown): number => Math.max(0, Math.min(1, toNumber(value)));
const asList = (value: unknown): unknown[] => (Array.isArray(value) ? value : []);
// Math.round: 0.07 * 100 is 7.000000000000001, which showed up in axis labels and "% threshold" text.
const pctInt = (fraction: number): string => `${Math.round(fraction * 100)}%`;

/** A run's result is server data (and, for saved runs, data a client once posted), so it gets a safe shape. */
function normalizeResult(raw: unknown): FprResult | null {
  if (!raw || typeof raw !== 'object') return null;
  const data = raw as Record<string, unknown>;

  const fprTable = asList(data.fpr_table)
    .filter((r): r is Record<string, unknown> => Boolean(r) && typeof r === 'object')
    .map((r) => {
      const fpr = clamp01(r.fpr);
      return {
        threshold: clamp01(r.threshold),
        fpr,
        fpr_percent: Number.isFinite(Number(r.fpr_percent)) ? Number(r.fpr_percent) : fpr * 100,
        label: String(r.label ?? ''),
        flagged_pairs: Math.max(0, Math.round(toNumber(r.flagged_pairs))),
      };
    })
    .sort((a, b) => a.threshold - b.threshold);

  return {
    num_submissions: Math.max(0, Math.round(toNumber(data.num_submissions))),
    num_pairs: Math.max(0, Math.round(toNumber(data.num_pairs))),
    mean_score: clamp01(data.mean_score),
    max_score: clamp01(data.max_score),
    fpr_table: fprTable,
    score_histogram: asList(data.score_histogram)
      .filter((h): h is Record<string, unknown> => Boolean(h) && typeof h === 'object')
      .map((h) => ({ bin: String(h.bin ?? ''), count: Math.max(0, Math.round(toNumber(h.count))) })),
    recommendation: String(data.recommendation ?? ''),
    recommendations: asList(data.recommendations)
      .filter((r): r is Record<string, unknown> => Boolean(r) && typeof r === 'object')
      .map((r) => ({
        threshold: clamp01(r.threshold),
        fpr: toNumber(r.fpr),
        type: String(r.type ?? ''),
        title: String(r.title ?? ''),
        advice: String(r.advice ?? ''),
      })),
    overall_assessment: String(data.overall_assessment ?? ''),
    suggested_actions: asList(data.suggested_actions).map(String),
  };
}

function fileExtension(name: string): string {
  const dot = name.lastIndexOf('.');
  return dot === -1 ? '' : name.slice(dot + 1).toLowerCase();
}

function fileKey(file: File): string {
  return `${file.name}:${file.size}:${file.lastModified}`;
}

function formatDateTime(value?: string | null): string {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat('en-US', { dateStyle: 'medium', timeStyle: 'short' }).format(date);
}

function fprBadgeClass(fpr: number): string {
  if (fpr <= 0.02) return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300';
  if (fpr <= 0.04) return 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-300';
  if (fpr <= 0.07) return 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300';
  return 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300';
}

/** Escapes text for HTML. The report used to interpolate server text straight into markup. */
function esc(value: unknown): string {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Builds the printable report. Every value from the result is escaped, and the document carries a
 * content-security policy that forbids scripts, so even a value that slipped through can't run: the
 * new window shares this app's origin, and recommendation text, labels and actions are loaded from
 * saved runs.
 */
function generateFprReportHtml(result: FprResult, runName: string): string {
  const dateStr = formatDateTime(new Date().toISOString());

  const fprRows = result.fpr_table
    .map(
      (row) => `
        <tr>
          <td>${esc(pctInt(row.threshold))}</td>
          <td style="font-weight: 600;">${esc(row.fpr_percent.toFixed(2))}%</td>
          <td>${esc(row.flagged_pairs)} / ${esc(result.num_pairs)}</td>
          <td>${esc(row.label)}</td>
        </tr>`
    )
    .join('');

  const recHtml =
    result.recommendations.length > 0
      ? result.recommendations
          .map(
            (rec) => `
          <div class="rec">
            <strong>${esc(rec.title)}</strong> — ${esc(pctInt(rec.threshold))} threshold (FPR: ${esc(rec.fpr.toFixed(1))}%)<br>
            <span style="color: #444;">${esc(rec.advice)}</span>
          </div>`
          )
          .join('')
      : `<p>${esc(result.recommendation)}</p>`;

  const actionsHtml = result.suggested_actions.length
    ? `<ul style="margin: 8px 0 0 20px;">${result.suggested_actions.map((a) => `<li>${esc(a)}</li>`).join('')}</ul>`
    : '';

  const histText = result.score_histogram.length
    ? result.score_histogram.map((h) => `${esc(h.bin)}: ${esc(h.count)}`).join(' | ')
    : 'N/A';

  return `<!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
        <title>Real-World FPR Validation Report</title>
        <style>
          body { font-family: system-ui, -apple-system, sans-serif; padding: 40px; line-height: 1.5; color: #222; }
          h1 { color: #0f172a; margin-bottom: 4px; }
          h2 { color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 4px; margin-top: 28px; }
          table { border-collapse: collapse; width: 100%; margin: 12px 0; }
          th, td { padding: 8px 12px; border: 1px solid #ddd; text-align: left; }
          th { background: #f8fafc; color: #64748b; }
          .rec { margin-bottom: 12px; padding: 12px; border: 1px solid #ddd; border-radius: 6px; }
          .section { margin-bottom: 24px; }
          .footer { font-size: 11px; color: #666; margin-top: 40px; border-top: 1px solid #eee; padding-top: 12px; }
        </style>
      </head>
      <body>
        <h1>Real-World FPR Validation Report</h1>
        ${runName ? `<p><strong>Run:</strong> ${esc(runName)}</p>` : ''}
        <p><strong>Generated:</strong> ${esc(dateStr)}</p>

        <div class="section">
          <h2>Summary</h2>
          <ul>
            <li><strong>Submissions analyzed:</strong> ${esc(result.num_submissions)}</li>
            <li><strong>Pairs analyzed:</strong> ${esc(result.num_pairs)}</li>
            <li><strong>Mean similarity on clean data:</strong> ${esc((result.mean_score * 100).toFixed(1))}%</li>
            <li><strong>Maximum similarity on clean data:</strong> ${esc((result.max_score * 100).toFixed(1))}%</li>
          </ul>
        </div>

        <div class="section">
          <h2>False Positive Rate by Threshold</h2>
          <table>
            <thead><tr><th>Threshold</th><th>FPR</th><th>Flagged Pairs</th><th>Assessment</th></tr></thead>
            <tbody>${fprRows}</tbody>
          </table>
        </div>

        <div class="section">
          <h2>Recommendations</h2>
          ${recHtml}
        </div>

        ${result.overall_assessment ? `
          <div class="section">
            <h2>Corpus Assessment</h2>
            <p>${esc(result.overall_assessment)}</p>
          </div>` : ''}

        ${result.suggested_actions.length ? `
          <div class="section">
            <h2>Suggested Actions</h2>
            ${actionsHtml}
          </div>` : ''}

        <div class="section">
          <h2>Similarity Score Distribution (Histogram)</h2>
          <p style="font-family: monospace; font-size: 13px; background: #f8fafc; padding: 12px; border-radius: 6px;">${histText}</p>
          <p style="font-size: 12px; color: #666;">Higher counts in lower bins (e.g. 0.0-0.1) indicate healthier clean data with fewer near-misses.</p>
        </div>

        <div class="footer">
          Generated by IntegrityDesk Real-World FPR Validation Tool<br>
          This report reflects the false positive behavior of the system on the specific clean corpus you provided.
          The estimate is only as good as that corpus: it assumes every submission in it is original work.
        </div>
      </body>
    </html>`;
}

// ─── Page ──────────────────────────────────────────────────────────────────────

export default function FprValidationPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [fileNotice, setFileNotice] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<FprResult | null>(null);
  const [activeRunName, setActiveRunName] = useState('');
  const [error, setError] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const dragDepth = useRef(0);

  // === Persistence (database-backed) ===
  const [savedRuns, setSavedRuns] = useState<FprRunSummary[]>([]);
  const [historyError, setHistoryError] = useState('');
  // The list loads on mount; without this it just popped in late with no feedback.
  const [historyLoading, setHistoryLoading] = useState(true);
  const [loadingRunId, setLoadingRunId] = useState('');
  // Designed dialogs replace the native prompt()/confirm()/alert() this tool used to open.
  const [saveModalOpen, setSaveModalOpen] = useState(false);
  const [runName, setRunName] = useState('');
  const [runNotes, setRunNotes] = useState('');
  const [savingRun, setSavingRun] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [pendingDeleteRun, setPendingDeleteRun] = useState<FprRunSummary | null>(null);
  const [deletingRun, setDeletingRun] = useState(false);
  const [deleteError, setDeleteError] = useState('');
  const [notice, setNotice] = useState('');

  // Default to focusing on the fine-tuning zone (0.65–0.78)
  const [fprView, setFprView] = useState<'all' | 'fine-tuning'>('fine-tuning');

  const loadFprHistory = useCallback(async (signal?: AbortSignal) => {
    setHistoryLoading(true);
    try {
      const res = await apiClient.get('/api/fpr-validation-runs', { signal });
      setSavedRuns(Array.isArray(res.data?.runs) ? res.data.runs : []);
      setHistoryError('');
    } catch (err) {
      if (signal?.aborted) return;
      // This used to be a console.error, so a failed load looked like "no saved runs".
      setHistoryError(describeError(err, 'Couldn’t load your saved runs.'));
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    loadFprHistory(controller.signal);
    return () => {
      controller.abort();
      abortRef.current?.abort();
    };
  }, [loadFprHistory]);

  // ── Files ────────────────────────────────────────────────────────────────────

  // Adds to the list (it replaced it, so browsing a second time discarded the first batch), skips
  // duplicates, and drops files that aren't supported source types or are too big.
  const addFiles = (incoming: FileList | File[] | null) => {
    if (!incoming) return;
    const list = Array.from(incoming);
    if (list.length === 0) return;

    const seen = new Set(files.map(fileKey));
    const accepted: File[] = [];
    const skipped: string[] = [];
    for (const file of list) {
      if (!ALLOWED_EXTENSIONS.includes(fileExtension(file.name)) || file.size > MAX_FILE_BYTES) {
        skipped.push(file.name);
      } else if (!seen.has(fileKey(file))) {
        seen.add(fileKey(file));
        accepted.push(file);
      }
    }

    let combined = [...files, ...accepted];
    let notes = '';
    if (combined.length > MAX_FILES) {
      combined = combined.slice(0, MAX_FILES);
      notes += `Only the first ${MAX_FILES} files are used. `;
    }
    if (skipped.length) {
      notes += `Skipped ${skipped.length} unsupported or oversized file${skipped.length === 1 ? '' : 's'} (${skipped.slice(0, 3).join(', ')}${skipped.length > 3 ? '…' : ''}). Files must be source code under ${Math.round(MAX_FILE_BYTES / 1024 / 1024)} MB.`;
    }

    setFiles(combined);
    setFileNotice(notes.trim());
    setResult(null);
    setActiveRunName('');
    setError('');
  };

  const reset = () => {
    abortRef.current?.abort();
    setFiles([]);
    setFileNotice('');
    setResult(null);
    setActiveRunName('');
    setError('');
    setNotice('');
  };

  // ── Analysis ─────────────────────────────────────────────────────────────────

  const runAnalysis = async () => {
    if (loading) return;
    if (files.length < 2) {
      setError('Please select at least 2 clean submissions.');
      return;
    }

    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    setError('');
    setNotice('');
    setResult(null);
    setActiveRunName('');

    const form = new FormData();
    files.forEach((f) => form.append('files', f));

    try {
      const res = await apiClient.post('/api/benchmark/real-fpr', form, { signal: controller.signal });
      const normalized = normalizeResult(res.data);
      if (!normalized || normalized.fpr_table.length === 0) {
        setError('The analysis returned no threshold data. Check that the files are readable source files and try again.');
      } else {
        setResult(normalized);
      }
    } catch (err) {
      if (isCanceled(err)) {
        setNotice('Analysis cancelled.');
      } else {
        setError(describeError(err, 'Failed to compute the false positive rate. Please try again.'));
      }
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
      setLoading(false);
    }
  };

  // ── Saved runs ───────────────────────────────────────────────────────────────

  const openSaveModal = () => {
    const stamp = new Intl.DateTimeFormat('en-CA').format(new Date());
    setRunName(`FPR Run - ${stamp}`);
    setRunNotes('');
    setSaveError('');
    setNotice('');
    setSaveModalOpen(true);
  };

  const closeSaveModal = () => {
    if (savingRun) return;
    setSaveModalOpen(false);
  };

  const saveCurrentRun = async () => {
    const name = runName.trim();
    if (!result || !name || savingRun) return;

    setSavingRun(true);
    setSaveError('');
    try {
      await apiClient.post('/api/fpr-validation-runs', {
        name,
        result,
        notes: runNotes.trim(),
      });
      setNotice(`Saved “${name}”.`);
      setActiveRunName(name);
      setSaveModalOpen(false);
      await loadFprHistory(); // refresh list
    } catch (err) {
      // Shown inside the dialog. It went to the page behind it, where it couldn't be seen.
      setSaveError(describeError(err, 'Failed to save the run. Please try again.'));
    } finally {
      setSavingRun(false);
    }
  };

  const loadSavedRun = async (runSummary: FprRunSummary) => {
    if (loadingRunId) return;
    setLoadingRunId(runSummary.id);
    setError('');
    setNotice('');
    try {
      const res = await apiClient.get(`/api/fpr-validation-runs/${encodeURIComponent(runSummary.id)}`);
      const normalized = normalizeResult(res.data?.result);
      if (!normalized) throw new Error('missing result');
      setResult(normalized);
      setActiveRunName(String(res.data?.name ?? runSummary.name));
      setFiles([]);
      setFileNotice('');
    } catch (err) {
      setError(describeError(err, 'Failed to load that run.'));
    } finally {
      setLoadingRunId('');
    }
  };

  const deleteSavedRun = async () => {
    const pending = pendingDeleteRun;
    if (!pending || deletingRun) return;

    setDeletingRun(true);
    setDeleteError('');
    try {
      await apiClient.delete(`/api/fpr-validation-runs/${encodeURIComponent(pending.id)}`);
      setPendingDeleteRun(null);
      setNotice(`Deleted “${pending.name}”.`);
      await loadFprHistory();
    } catch (err) {
      setDeleteError(describeError(err, 'Failed to delete the run. Please try again.'));
    } finally {
      setDeletingRun(false);
    }
  };

  // ── Report ───────────────────────────────────────────────────────────────────

  const printReport = () => {
    if (!result) return;
    const printWindow = window.open('', '_blank');
    if (!printWindow) {
      setError('The report window was blocked. Allow pop-ups for this site and try again.');
      return;
    }
    try {
      printWindow.opener = null;
    } catch {
      /* some browsers don't allow it */
    }
    printWindow.document.open();
    printWindow.document.write(generateFprReportHtml(result, activeRunName));
    printWindow.document.close();
    // Printing straight after close() could print an empty page.
    setTimeout(() => {
      printWindow.focus();
      printWindow.print();
    }, 300);
  };

  // ── Derived ──────────────────────────────────────────────────────────────────

  const chartData = result?.fpr_table.map((row) => ({
    threshold: row.threshold,
    fpr: Math.round(row.fpr * 10000) / 100,
  })) || [];

  const chartDomain: [number, number] = chartData.length
    ? [chartData[0].threshold, chartData[chartData.length - 1].threshold]
    : [0, 1];

  const chartSummary = result && result.fpr_table.length
    ? `False positive rate by similarity threshold: ${result.fpr_table[0].fpr_percent.toFixed(1)}% at ${pctInt(result.fpr_table[0].threshold)} falling to ${result.fpr_table[result.fpr_table.length - 1].fpr_percent.toFixed(1)}% at ${pctInt(result.fpr_table[result.fpr_table.length - 1].threshold)}.`
    : '';

  const histogramMax = Math.max(1, ...(result?.score_histogram.map((h) => h.count) ?? [1]));

  return (
    <DashboardLayout requiredRole="admin">
      <div className="theme-page-container space-y-6">
        <PageHeader
          eyebrow="Engine & R&D"
          eyebrowStyle="badge"
          title="Real-World FPR Validation"
          description="Measure actual false positive risk on your own clean student data"
          action={
            <button
              type="button"
              onClick={reset}
              className="theme-button-secondary inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50"
            >
              Reset
            </button>
          }
        />

        <div className="overflow-hidden rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950">
          <div className="mb-4">
            <p className="text-sm leading-6 text-slate-600 dark:text-slate-400">
              Upload known-clean submissions (no plagiarism) to see the real-world false positive rate
              your students would experience at different similarity thresholds.
            </p>
          </div>

          {/* Drag & Drop + File List */}
          <div
            onDragEnter={() => {
              dragDepth.current += 1;
              setIsDragging(true);
            }}
            onDragOver={(e) => e.preventDefault()}
            onDragLeave={() => {
              // dragleave also fires when crossing a child element, which made the highlight flicker.
              dragDepth.current = Math.max(0, dragDepth.current - 1);
              if (dragDepth.current === 0) setIsDragging(false);
            }}
            onDrop={(e) => {
              e.preventDefault();
              dragDepth.current = 0;
              setIsDragging(false);
              addFiles(e.dataTransfer.files);
            }}
            className="mb-4"
          >
            {/* sr-only instead of display:none, so the picker can be reached and opened from the keyboard. */}
            <input
              type="file"
              multiple
              accept={ACCEPT}
              onChange={(e) => {
                addFiles(e.target.files);
                e.target.value = '';
              }}
              className="peer sr-only"
              id="fpr-files"
            />
            <label
              htmlFor="fpr-files"
              className={`block cursor-pointer border-2 border-dashed rounded-2xl p-8 text-center transition-all peer-focus-visible:ring-2 peer-focus-visible:ring-blue-500/50 peer-focus-visible:ring-offset-2 ${
                isDragging
                  ? 'border-blue-500 bg-blue-50 dark:border-blue-500 dark:bg-blue-500/10'
                  : 'border-slate-300 bg-white hover:border-blue-400 dark:border-slate-700 dark:bg-slate-900 dark:hover:border-blue-500'
              }`}
            >
              <div className="flex flex-col items-center justify-center">
                <UploadCloud size={32} className="text-blue-600 mb-3" aria-hidden="true" />
                <div className="font-medium text-slate-900 dark:text-white">
                  Drop clean submissions here
                </div>
                <div className="text-sm text-slate-600 mt-1 dark:text-slate-400">
                  or <span className="underline">click to browse</span>
                </div>
                <p className="text-xs text-slate-500 mt-3 max-w-[260px] dark:text-slate-400">
                  Recommended: {RECOMMENDED_MIN_SUBMISSIONS}+ real student submissions from past semesters with no plagiarism
                </p>
              </div>
            </label>
          </div>

          {fileNotice && (
            <p
              role="status"
              className="mb-4 flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-300"
            >
              <AlertCircle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
              {fileNotice}
            </p>
          )}

          {/* Selected Files List */}
          {files.length > 0 && (
            <div className="mb-6">
              <div className="flex items-center justify-between mb-2 px-1">
                <div className="text-sm font-medium text-slate-700 dark:text-slate-300">
                  Selected files ({files.length})
                </div>
                <button
                  type="button"
                  onClick={reset}
                  className="text-xs font-medium text-slate-500 transition hover:text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50 dark:text-slate-400 dark:hover:text-slate-200"
                >
                  Clear all
                </button>
              </div>

              <div className="max-h-48 overflow-auto rounded-2xl border border-slate-200 bg-white divide-y divide-slate-200 dark:divide-slate-800 dark:border-slate-800 dark:bg-slate-900">
                {files.map((file, index) => (
                  <div
                    key={`${fileKey(file)}-${index}`}
                    className="flex items-center justify-between px-4 py-2.5 text-sm transition-colors hover:bg-slate-50 dark:hover:bg-slate-800"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center flex-shrink-0 dark:bg-slate-800">
                        <FileText size={16} className="text-slate-500 dark:text-slate-400" aria-hidden="true" />
                      </div>
                      <div className="min-w-0">
                        <div className="truncate font-medium text-slate-900 dark:text-white">{file.name}</div>
                        <div className="text-xs text-slate-500 dark:text-slate-400">
                          {(file.size / 1024).toFixed(1)} KB
                        </div>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        const newFiles = files.filter((_, i) => i !== index);
                        setFiles(newFiles);
                        if (newFiles.length === 0) {
                          setResult(null);
                        }
                      }}
                      className="ml-2 rounded-md p-2 text-slate-400 transition hover:bg-red-50 hover:text-red-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50 dark:hover:bg-slate-800 dark:hover:text-red-400"
                      aria-label={`Remove ${file.name}`}
                    >
                      <X size={16} aria-hidden="true" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="flex flex-wrap gap-3">
            {!loading ? (
              <button
                type="button"
                onClick={runAnalysis}
                disabled={files.length < 2}
                className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50 disabled:opacity-50"
              >
                <Play size={16} aria-hidden="true" />
                Run Real-World FPR Analysis
              </button>
            ) : (
              <button
                type="button"
                onClick={() => abortRef.current?.abort()}
                className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-6 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
              >
                <Loader2 className="animate-spin" size={16} aria-hidden="true" />
                Analyzing… Cancel
              </button>
            )}

            {result && !activeRunName && (
              <button
                type="button"
                onClick={openSaveModal}
                className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
              >
                Save this run
              </button>
            )}

            {result && (
              <button
                type="button"
                onClick={printReport}
                className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
              >
                <Printer size={16} aria-hidden="true" />
                {/* It opens the browser's print dialog (choose "Save as PDF"); it doesn't download a PDF. */}
                Print / Save as PDF
              </button>
            )}
          </div>

          {error && (
            <div
              role="alert"
              className="mt-4 flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300"
            >
              <AlertCircle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
              <span>{error}</span>
            </div>
          )}
          {notice && (
            <div
              role="status"
              className="mt-4 flex items-start gap-3 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-300"
            >
              <CheckCircle2 size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
              <span>{notice}</span>
            </div>
          )}
        </div>

        {/* Saved Runs History */}
        {historyError && (
          <div
            role="alert"
            className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300"
          >
            <AlertCircle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
            <span className="flex-1">{historyError}</span>
            <button
              type="button"
              onClick={() => loadFprHistory()}
              className="ml-auto inline-flex h-9 shrink-0 items-center rounded-xl border border-red-200 bg-white px-3 text-sm font-semibold text-red-700 transition hover:bg-red-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50 dark:border-red-500/30 dark:bg-slate-950 dark:text-red-300 dark:hover:bg-red-500/10"
            >
              Retry
            </button>
          </div>
        )}
        {historyLoading && !historyError && savedRuns.length === 0 && (
          <div
            role="status"
            className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400"
          >
            <Loader2 size={16} className="animate-spin" aria-hidden="true" />
            Loading saved runs…
          </div>
        )}
        {savedRuns.length > 0 && (
          <div>
            <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold text-slate-900 dark:text-white">
              <ClipboardList size={18} className="text-slate-400 dark:text-slate-500" aria-hidden="true" /> Previous Real-World FPR Validations
            </h2>
            <ul className="space-y-2">
              {savedRuns.map((run) => (
                <li
                  key={run.id}
                  className="flex items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 transition-colors hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-950 dark:hover:bg-slate-900/50"
                >
                  <div className="min-w-0">
                    <div className="font-medium text-slate-900 truncate dark:text-white">{run.name}</div>
                    <div className="text-xs text-slate-500 dark:text-slate-400">
                      {formatDateTime(run.created_at)}
                      {run.num_submissions !== null && run.num_submissions !== undefined ? ` • ${run.num_submissions} submissions` : ''}
                      {run.num_pairs !== null && run.num_pairs !== undefined ? ` • ${run.num_pairs} pairs` : ''}
                      {/* These two fields were in the data but never shown. */}
                      {run.recommended_threshold !== null && run.recommended_threshold !== undefined
                        ? ` • recommended ${pctInt(run.recommended_threshold)}`
                        : ''}
                      {run.fpr_at_recommended_threshold !== null && run.fpr_at_recommended_threshold !== undefined
                        ? ` (FPR ${(run.fpr_at_recommended_threshold * 100).toFixed(1)}%)`
                        : ''}
                    </div>
                  </div>
                  <div className="flex shrink-0 gap-2">
                    <button
                      type="button"
                      onClick={() => loadSavedRun(run)}
                      disabled={Boolean(loadingRunId)}
                      aria-label={`Load ${run.name}`}
                      className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-3 py-1.5 text-sm font-semibold text-white transition hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50 disabled:opacity-50"
                    >
                      {loadingRunId === run.id && <Loader2 size={16} className="animate-spin" aria-hidden="true" />}
                      {loadingRunId === run.id ? 'Loading…' : 'Load'}
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setDeleteError('');
                        setPendingDeleteRun(run);
                      }}
                      aria-label={`Delete ${run.name}`}
                      className="inline-flex items-center gap-1.5 rounded-xl border border-red-200 bg-white px-3 py-1.5 text-sm font-medium text-red-600 transition hover:bg-red-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50 dark:border-red-500/30 dark:bg-slate-950 dark:text-red-400 dark:hover:bg-red-500/10"
                    >
                      Delete
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}

        {result && (
          <div className="space-y-6">
            {activeRunName && (
              <p className="text-sm text-slate-600 dark:text-slate-400">
                Showing saved run: <strong>{activeRunName}</strong>
              </p>
            )}

            {result.num_submissions < RECOMMENDED_MIN_SUBMISSIONS && (
              <p role="note" className="flex items-start gap-2 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-300">
                <AlertCircle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
                This run used {result.num_submissions} submission{result.num_submissions === 1 ? '' : 's'}. Rates measured on fewer than{' '}
                {RECOMMENDED_MIN_SUBMISSIONS} are noisy, so treat the thresholds below as a rough guide, not a setting to apply as-is.
                The estimate also assumes every submission uploaded is original work.
              </p>
            )}

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { label: 'Submissions', value: result.num_submissions },
                { label: 'Pairs Analyzed', value: result.num_pairs },
                { label: 'Mean Similarity', value: `${(result.mean_score * 100).toFixed(1)}%` },
                { label: 'Max Similarity', value: `${(result.max_score * 100).toFixed(1)}%` },
              ].map((stat) => (
                <div
                  key={stat.label}
                  className="rounded-3xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-950"
                >
                  <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
                    {stat.label}
                  </div>
                  <div className="mt-2 text-3xl font-bold text-slate-900 dark:text-white">{stat.value}</div>
                </div>
              ))}
            </div>

            {/* FPR Curve */}
            <div className="rounded-3xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-950">
              <h2 className="mb-4 text-lg font-semibold text-slate-900 dark:text-white">False Positive Rate Curve</h2>
              <div className="h-72" role="img" aria-label={chartSummary}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    {/* A numeric axis: with the default category axis the highlighted zone only appeared
                        if 0.65 and 0.78 happened to be exact thresholds, and the labels showed floating-point noise. */}
                    <XAxis
                      dataKey="threshold"
                      type="number"
                      domain={chartDomain}
                      tickFormatter={(v: number) => pctInt(v)}
                    />
                    <YAxis tickFormatter={(v: number) => `${Math.round(v * 10) / 10}%`} />
                    <Tooltip
                      formatter={(value: number) => [`${value}%`, 'False positive rate']}
                      labelFormatter={(label: number) => `Threshold ${pctInt(label)}`}
                    />

                    {/* Highlight the dense fine-tuning zone (0.65 – 0.78) */}
                    <ReferenceArea
                      x1={ZONE_MIN}
                      x2={ZONE_MAX}
                      fill="#2563eb"
                      fillOpacity={0.08}
                      stroke="#2563eb"
                      strokeOpacity={0.3}
                    />

                    <Line type="monotone" dataKey="fpr" stroke="#2563eb" strokeWidth={3} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Detailed Table with Fine-tuning Zone Focus (default) */}
            <div className="overflow-hidden rounded-3xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-6 py-4 dark:border-slate-800">
                <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
                  False Positive Rate at Different Thresholds
                </h2>

                {/* View toggle - defaults to Fine-tuning Zone */}
                <div
                  role="group"
                  aria-label="Threshold range"
                  className="flex rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-sm dark:border-slate-800 dark:bg-slate-900"
                >
                  <button
                    type="button"
                    aria-pressed={fprView === 'fine-tuning'}
                    onClick={() => setFprView('fine-tuning')}
                    className={`rounded-md px-3 py-1 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50 ${fprView === 'fine-tuning' ? 'bg-white font-medium text-blue-600 shadow dark:bg-slate-950 dark:text-blue-400' : 'text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800'}`}
                  >
                    Fine-tuning Zone (0.65–0.78)
                  </button>
                  <button
                    type="button"
                    aria-pressed={fprView === 'all'}
                    onClick={() => setFprView('all')}
                    className={`rounded-md px-3 py-1 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50 ${fprView === 'all' ? 'bg-white font-medium text-blue-600 shadow dark:bg-slate-950 dark:text-blue-400' : 'text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800'}`}
                  >
                    All Thresholds
                  </button>
                </div>
              </div>

              {(() => {
                const zoneRows = result.fpr_table.filter((r) => r.threshold >= ZONE_MIN && r.threshold <= ZONE_MAX);
                // If the run has no rows in the zone, show everything instead of an empty table.
                const showZoneOnly = fprView === 'fine-tuning' && zoneRows.length > 0;
                const tableRows = showZoneOnly ? zoneRows : result.fpr_table;

                return (
                  <>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500 dark:bg-slate-900/80 dark:text-slate-400">
                          <tr>
                            <th scope="col" className="text-left px-6 py-3">Threshold</th>
                            <th scope="col" className="text-left px-6 py-3">FPR</th>
                            <th scope="col" className="text-left px-6 py-3">Flagged Pairs</th>
                            <th scope="col" className="text-left px-6 py-3">Assessment</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                          {tableRows.map((row) => {
                            const isDenseZone = row.threshold >= ZONE_MIN && row.threshold <= ZONE_MAX;
                            // "Recommended" used to be the lowest-FPR row in the zone. FPR only falls as the
                            // threshold rises, so that was always the least sensitive threshold. Rows are now
                            // tagged from the recommendations the analysis itself returned.
                            const rec = result.recommendations.find((r) => Math.abs(r.threshold - row.threshold) < 0.005);

                            return (
                              <tr
                                key={row.threshold}
                                className={`hover:bg-slate-50 dark:hover:bg-slate-900/50 ${isDenseZone ? 'bg-blue-50/70 dark:bg-blue-500/10' : ''} ${rec ? 'ring-1 ring-blue-400' : ''}`}
                              >
                                <td className="px-6 py-3 font-mono">
                                  {pctInt(row.threshold)}
                                  {isDenseZone && (
                                    <span className="ml-2 rounded-full bg-slate-100 px-1.5 py-0.5 text-[11px] font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                                      Fine-tuning zone
                                    </span>
                                  )}
                                  {rec && (
                                    <span className="ml-2 rounded-full bg-blue-600 px-2 py-0.5 text-[11px] font-semibold text-white">
                                      {rec.title || 'Recommended'}
                                    </span>
                                  )}
                                </td>
                                <td className="px-6 py-3 font-semibold">{row.fpr_percent.toFixed(2)}%</td>
                                <td className="px-6 py-3 text-slate-600 dark:text-slate-400">{row.flagged_pairs} / {result.num_pairs}</td>
                                <td className="px-6 py-3">
                                  <span className={`inline-block px-3 py-1 rounded-full text-xs font-medium ${fprBadgeClass(row.fpr)}`}>
                                    {row.label}
                                  </span>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>

                    {showZoneOnly && (
                      <div className="border-t border-slate-200 bg-slate-50 px-6 py-2 text-[11px] text-slate-500 dark:border-slate-800 dark:bg-slate-900/80 dark:text-slate-400">
                        Focused on the fine-tuning zone (0.65–0.78), lowest threshold first. A higher threshold lowers the false
                        positive rate but also misses more genuine similarity, so rows are only tagged where the analysis
                        recommended them. Switch to &quot;All Thresholds&quot; for the complete view.
                      </div>
                    )}
                  </>
                );
              })()}
            </div>

            {/* Score distribution (previously only in the printed report) */}
            {result.score_histogram.length > 0 && (
              <div className="rounded-3xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-950">
                <h2 className="mb-1 text-lg font-semibold text-slate-900 dark:text-white">Similarity score distribution</h2>
                <p className="mb-4 text-xs text-slate-500 dark:text-slate-400">
                  Pairs per similarity range. More pairs in the low ranges means cleaner data with fewer near-misses.
                </p>
                <div className="space-y-2">
                  {result.score_histogram.map((bin) => (
                    <div key={bin.bin} className="flex items-center gap-3 text-sm">
                      <span className="w-24 shrink-0 font-mono text-slate-600 dark:text-slate-300">{bin.bin}</span>
                      <div className="h-3 flex-1 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800" aria-hidden="true">
                        <div className="h-full rounded-full bg-blue-600" style={{ width: `${(bin.count / histogramMax) * 100}%` }} />
                      </div>
                      <span className="w-12 shrink-0 text-right tabular-nums text-slate-900 dark:text-white">{bin.count}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Sophisticated Recommendations */}
            <div className="rounded-3xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-950">
              <h2 className="mb-4 text-lg font-semibold text-slate-900 dark:text-white">Recommended Thresholds</h2>

              {result.recommendations.length > 0 ? (
                <div className="space-y-4">
                  {result.recommendations.map((rec, idx) => (
                    <div key={`${rec.type}-${idx}`} className={`rounded-2xl border p-4 ${
                      rec.type === 'balanced' ? 'border-slate-300 bg-slate-50 dark:border-slate-700 dark:bg-slate-900' :
                      rec.type === 'very_safe' ? 'border-blue-300 bg-blue-50 dark:border-blue-500/30 dark:bg-blue-500/10' :
                      'border-amber-300 bg-amber-50 dark:border-amber-500/30 dark:bg-amber-500/10'
                    }`}>
                      <div className="flex items-center justify-between">
                        <div>
                          <span className="font-semibold text-lg">{rec.title}</span>
                          <span className="ml-3 rounded border border-slate-200 bg-white px-2 py-0.5 font-mono text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-300">
                            {pctInt(rec.threshold)} threshold
                          </span>
                        </div>
                        <div className="text-right">
                          <div className="text-sm text-slate-600 dark:text-slate-400">FPR on your data</div>
                          <div className="text-xl font-bold text-slate-900 dark:text-white">{rec.fpr.toFixed(1)}%</div>
                        </div>
                      </div>
                      <p className="mt-2 text-sm text-slate-700 dark:text-slate-300">{rec.advice}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-slate-600 dark:text-slate-400">{result.recommendation}</p>
              )}

              {/* Overall Assessment */}
              {result.overall_assessment && (
                <div className="mt-5 border-t border-slate-200 pt-5 dark:border-slate-800">
                  <div className="mb-1 font-medium text-slate-900 dark:text-white">Corpus Assessment</div>
                  <p className="text-sm text-slate-600 dark:text-slate-400">{result.overall_assessment}</p>
                </div>
              )}

              {/* Actionable Suggestions */}
              {result.suggested_actions.length > 0 && (
                <div className="mt-5 border-t border-slate-200 pt-5 dark:border-slate-800">
                  <div className="mb-2 font-medium text-slate-900 dark:text-white">Suggested Actions</div>
                  <ul className="list-inside list-disc space-y-1 text-sm text-slate-600 dark:text-slate-400">
                    {result.suggested_actions.map((action, i) => (
                      <li key={i}>{action}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Save run */}
        <Modal
          open={saveModalOpen}
          title="Save this validation run"
          description="Saved runs stay in the history list so you can revisit a threshold later."
          onClose={closeSaveModal}
          footer={
            <>
              <button
                type="button"
                onClick={closeSaveModal}
                disabled={savingRun}
                className="theme-button-secondary rounded-xl px-4 py-2 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50 disabled:opacity-60"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={saveCurrentRun}
                disabled={!runName.trim() || savingRun}
                className="rounded-xl bg-slate-950 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50 disabled:opacity-60 dark:bg-white dark:text-slate-950 dark:hover:bg-slate-200"
              >
                {savingRun ? 'Saving…' : 'Save run'}
              </button>
            </>
          }
        >
          <div className="space-y-4">
            {saveError && (
              <p role="alert" className="flex items-start gap-2 rounded-2xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300">
                <AlertCircle size={15} className="mt-0.5 shrink-0" aria-hidden="true" />
                {saveError}
              </p>
            )}
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
              Run name
              <input
                value={runName}
                onChange={(e) => setRunName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') saveCurrentRun();
                }}
                maxLength={120}
                autoComplete="off"
                autoFocus
                className="mt-1.5 w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-700 dark:bg-slate-950 dark:text-white"
              />
            </label>
            {/* `notes` was always sent as an empty string ("can be extended later"). */}
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
              Notes (optional)
              <textarea
                value={runNotes}
                onChange={(e) => setRunNotes(e.target.value)}
                rows={3}
                maxLength={1000}
                placeholder="Which course and term this corpus came from, anything unusual about it…"
                className="mt-1.5 w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-700 dark:bg-slate-950 dark:text-white"
              />
            </label>
          </div>
        </Modal>

        {/* Delete run */}
        <Modal
          open={pendingDeleteRun !== null}
          title="Delete saved run"
          onClose={() => { if (!deletingRun) setPendingDeleteRun(null); }}
          footer={
            <>
              <button
                type="button"
                onClick={() => setPendingDeleteRun(null)}
                disabled={deletingRun}
                className="theme-button-secondary rounded-xl px-4 py-2 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50 disabled:opacity-60"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={deleteSavedRun}
                disabled={deletingRun}
                className="rounded-xl bg-red-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-red-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50 disabled:opacity-60"
              >
                {deletingRun ? 'Deleting…' : 'Delete'}
              </button>
            </>
          }
        >
          <div className="flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-red-50 text-red-600 dark:bg-red-500/15 dark:text-red-300">
              <Trash2 size={18} aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-slate-900 dark:text-white">
                {pendingDeleteRun?.name}
              </p>
              <p className="mt-1 text-sm leading-6 text-slate-600 dark:text-slate-300">
                The saved threshold table is removed from your history. Re-running the
                analysis on the same files is unaffected.
              </p>
              {deleteError && (
                <p role="alert" className="mt-3 rounded-2xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300">
                  {deleteError}
                </p>
              )}
            </div>
          </div>
        </Modal>
      </div>
    </DashboardLayout>
  );
}
