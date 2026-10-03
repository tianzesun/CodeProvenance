'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { PageHeader } from '@/components/saas/SaaSPrimitives';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ChangeEvent, RefObject } from 'react';
import { useRouter } from 'next/navigation';
import { apiClient } from '@/lib/apiClient';
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  ChevronLeft,
  Code,
  FileText,
  FileUp,
  GitCompare,
  Info,
  Loader2,
  ShieldAlert,
  Trash2,
  ArrowLeftRight,
} from 'lucide-react';

// ─── Types ─────────────────────────────────────────────────────────────────────

type LineStatus = 'exact' | 'renamed' | null;
type Language = 'python' | 'java' | 'javascript' | 'c' | 'cpp' | 'other';

interface Block {
  aStart: number;
  aEnd: number;
  bStart: number;
  bEnd: number;
  status: 'exact' | 'renamed';
  lines: number;
}

interface Comparison {
  statusA: LineStatus[];
  statusB: LineStatus[];
  /** For each line, the index of the matching line in the other file (-1 when unmatched). */
  matchA: number[];
  matchB: number[];
  blocks: Block[];
  consideredA: number;
  consideredB: number;
  matched: number;
  exact: number;
  renamed: number;
  percent: number;
  truncated: boolean;
}

interface NormalizedLine {
  considered: boolean;
  rawKey: string;
  key: string;
}

// ─── Constants ─────────────────────────────────────────────────────────────────

const VERDICT_STYLES: Record<string, string> = {
  TRUE: 'bg-red-100 text-red-700 border-red-200',
  PROBABLE: 'bg-amber-100 text-amber-700 border-amber-200',
  REVIEW: 'bg-blue-100 text-blue-700 border-blue-200',
  FLAG: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  CLEAN: 'bg-emerald-100 text-emerald-700 border-emerald-200',
};

const LANGUAGES: { id: Language; label: string }[] = [
  { id: 'python', label: 'Python' },
  { id: 'java', label: 'Java' },
  { id: 'javascript', label: 'JavaScript / TypeScript' },
  { id: 'c', label: 'C' },
  { id: 'cpp', label: 'C++' },
  { id: 'other', label: 'Other' },
];

const EXTENSION_LANGUAGE: Record<string, Language> = {
  py: 'python',
  java: 'java',
  js: 'javascript',
  ts: 'javascript',
  jsx: 'javascript',
  tsx: 'javascript',
  c: 'c',
  h: 'c',
  cpp: 'cpp',
  hpp: 'cpp',
};

const KEYWORDS = new Set(
  (
    'if else elif for while do return def class import from as try except finally catch throw raise with in is not and or ' +
    'None True False null true false function var let const new this self public private protected static void int float ' +
    'double char bool boolean string long short switch case break continue default struct enum namespace using include ' +
    'lambda yield async await pass del global nonlocal assert extends implements interface package final abstract'
  ).split(' ')
);

const MAX_CODE_CHARS = 200_000;
const MAX_FILE_BYTES = 200 * 1024;
const MAX_LINES = 2500;
const MAX_BLOCKS_SHOWN = 50;

const SAMPLE_A = `def find_max(numbers):
    """Find the maximum value in a list."""
    if not numbers:
        return None
    max_val = numbers[0]
    for num in numbers:
        if num > max_val:
            max_val = num
    return max_val`;

const SAMPLE_B = `def find_maximum(values):
    """Find the maximum value in a list."""
    if not values:
        return None
    max_val = values[0]
    for val in values:
        if val > max_val:
            max_val = val
    return max_val`;

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
  else if (status === 403) message = 'You don’t have permission to generate evidence.';
  else if (status === 413) message = 'That code is too large for the evidence service. Use shorter files.';
  else if (status === 429) message = 'Too many requests. Please wait a moment and try again.';

  return reference ? `${message} (Reference: ${reference})` : message;
}

/**
 * Removes comments from each line (a small scanner that respects string literals, so a URL inside a
 * string isn't cut at the "//"). Block comments can span lines.
 */
function stripComments(lines: string[], language: Language): string[] {
  const hashComments = language === 'python' || language === 'other';
  const slashComments = language !== 'python';
  let inBlock = false;

  return lines.map((line) => {
    let out = '';
    let quote: string | null = null;
    for (let i = 0; i < line.length; i += 1) {
      const ch = line[i];
      const next = line[i + 1];

      if (inBlock) {
        if (ch === '*' && next === '/') {
          inBlock = false;
          i += 1;
        }
        continue;
      }
      if (quote) {
        out += ch;
        if (ch === '\\' && next !== undefined) {
          out += next;
          i += 1;
        } else if (ch === quote) {
          quote = null;
        }
        continue;
      }
      if (ch === '"' || ch === "'") {
        quote = ch;
        out += ch;
        continue;
      }
      if (hashComments && ch === '#') break;
      if (slashComments && ch === '/' && next === '/') break;
      if (slashComments && ch === '/' && next === '*') {
        inBlock = true;
        i += 1;
        continue;
      }
      out += ch;
    }
    return out;
  });
}

const TOKEN_PATTERN = /"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\d+(?:\.\d+)?|[A-Za-z_][A-Za-z0-9_]*|[^\sA-Za-z0-9_]/g;

/**
 * Two keys per line: `rawKey` (whitespace-collapsed text, so only a literal copy matches) and `key`
 * (identifiers, numbers and strings replaced by placeholders, so renamed variables still match).
 * Lines with no words or values (just braces or punctuation) are not "considered", otherwise every
 * closing brace would count as a match.
 */
function normalizeCode(code: string, language: Language): { lines: string[]; normalized: NormalizedLine[]; truncated: boolean } {
  const all = code.replace(/\r\n?/g, '\n').split('\n');
  const truncated = all.length > MAX_LINES;
  const lines = truncated ? all.slice(0, MAX_LINES) : all;
  const stripped = stripComments(lines, language);

  const normalized = stripped.map((text): NormalizedLine => {
    const tokens = text.match(TOKEN_PATTERN) || [];
    let meaningful = 0;
    const key = tokens
      .map((token) => {
        if (token[0] === '"' || token[0] === "'") {
          meaningful += 1;
          return 'STR';
        }
        if (/^\d/.test(token)) {
          meaningful += 1;
          return 'NUM';
        }
        if (/^[A-Za-z_]/.test(token)) {
          meaningful += 1;
          return KEYWORDS.has(token) ? token : 'ID';
        }
        return token;
      })
      .join(' ');
    return {
      considered: meaningful > 0,
      rawKey: text.trim().replace(/\s+/g, ' '),
      key,
    };
  });

  return { lines, normalized, truncated };
}

/** Longest-common-subsequence alignment of the considered lines of both files. */
function compareCode(codeA: string, codeB: string, language: Language): Comparison {
  const a = normalizeCode(codeA, language);
  const b = normalizeCode(codeB, language);

  const idxA: number[] = [];
  const idxB: number[] = [];
  a.normalized.forEach((line, i) => line.considered && idxA.push(i));
  b.normalized.forEach((line, i) => line.considered && idxB.push(i));

  const n = idxA.length;
  const m = idxB.length;
  const width = m + 1;
  const table = new Uint16Array((n + 1) * width);

  for (let i = n - 1; i >= 0; i -= 1) {
    for (let j = m - 1; j >= 0; j -= 1) {
      table[i * width + j] =
        a.normalized[idxA[i]].key === b.normalized[idxB[j]].key
          ? table[(i + 1) * width + j + 1] + 1
          : Math.max(table[(i + 1) * width + j], table[i * width + j + 1]);
    }
  }

  const statusA: LineStatus[] = new Array(a.lines.length).fill(null);
  const statusB: LineStatus[] = new Array(b.lines.length).fill(null);
  const matchA: number[] = new Array(a.lines.length).fill(-1);
  const matchB: number[] = new Array(b.lines.length).fill(-1);
  const pairs: { p: number; q: number; status: 'exact' | 'renamed' }[] = [];

  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    const lineA = a.normalized[idxA[i]];
    const lineB = b.normalized[idxB[j]];
    if (lineA.key === lineB.key) {
      const status = lineA.rawKey === lineB.rawKey ? 'exact' : 'renamed';
      statusA[idxA[i]] = status;
      statusB[idxB[j]] = status;
      matchA[idxA[i]] = idxB[j];
      matchB[idxB[j]] = idxA[i];
      pairs.push({ p: i, q: j, status });
      i += 1;
      j += 1;
    } else if (table[(i + 1) * width + j] >= table[i * width + j + 1]) {
      i += 1;
    } else {
      j += 1;
    }
  }

  const blocks: Block[] = [];
  pairs.forEach((pair, index) => {
    const last = blocks[blocks.length - 1];
    const lastPair = index > 0 ? pairs[index - 1] : undefined;
    // A block is a run of consecutive code lines (blank and brace-only lines are skipped) with one status.
    if (last && lastPair && lastPair.status === pair.status && pair.p === lastPair.p + 1 && pair.q === lastPair.q + 1) {
      last.aEnd = idxA[pair.p];
      last.bEnd = idxB[pair.q];
      last.lines += 1;
    } else {
      blocks.push({
        aStart: idxA[pair.p],
        aEnd: idxA[pair.p],
        bStart: idxB[pair.q],
        bEnd: idxB[pair.q],
        status: pair.status,
        lines: 1,
      });
    }
  });

  const exact = pairs.filter((pair) => pair.status === 'exact').length;
  const matched = pairs.length;
  const denominator = Math.max(n, m);

  return {
    statusA,
    statusB,
    matchA,
    matchB,
    blocks,
    consideredA: n,
    consideredB: m,
    matched,
    exact,
    renamed: matched - exact,
    percent: denominator > 0 ? Math.round((matched / denominator) * 100) : 0,
    truncated: a.truncated || b.truncated,
  };
}

function scrollToLine(container: HTMLElement | null, lineIndex: number) {
  if (!container) return;
  const el = container.querySelector<HTMLElement>(`[data-line="${lineIndex}"]`);
  if (!el) return;
  container.scrollTo({ top: Math.max(0, el.offsetTop - container.clientHeight / 3), behavior: 'smooth' });
}

/** The engine's evidence response has no documented shape, so show whatever lists of items it carries. */
function extractEvidenceSections(data: unknown): { title: string; items: { title: string; score: number | null; text: string }[] }[] {
  if (!data || typeof data !== 'object') return [];
  const sections: { title: string; items: { title: string; score: number | null; text: string }[] }[] = [];

  for (const [key, value] of Object.entries(data as Record<string, unknown>)) {
    if (!Array.isArray(value) || value.length === 0 || typeof value[0] !== 'object' || value[0] === null) continue;

    const items = value.slice(0, 50).map((raw, index) => {
      const item = raw as Record<string, unknown>;
      const titleSource = item.name ?? item.label ?? item.title ?? item.function ?? item.type;
      const scoreSource = item.score ?? item.similarity ?? item.confidence;
      const textSource = item.description ?? item.explanation ?? item.summary ?? item.detail;
      const scoreNumber = typeof scoreSource === 'number' && Number.isFinite(scoreSource) ? scoreSource : null;
      return {
        title: typeof titleSource === 'string' && titleSource ? titleSource : `Item ${index + 1}`,
        score: scoreNumber === null ? null : Math.round((scoreNumber <= 1 ? scoreNumber * 100 : scoreNumber) * 10) / 10,
        text: typeof textSource === 'string' ? textSource : '',
      };
    });
    sections.push({ title: key.replace(/_/g, ' '), items });
  }
  return sections;
}

// ─── Components ────────────────────────────────────────────────────────────────

function VerdictBadge({ v }: { v: string }) {
  const Icon = v === 'CLEAN' ? CheckCircle2 : v === 'TRUE' || v === 'PROBABLE' ? ShieldAlert : Info;
  return (
    <span
      aria-label={`Verdict: ${v}`}
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm font-semibold ${VERDICT_STYLES[v] || VERDICT_STYLES.REVIEW}`}
    >
      <Icon size={14} aria-hidden="true" />
      {v}
    </span>
  );
}

function CodePane({
  title,
  prefix,
  lines,
  statuses,
  containerRef,
  onScroll,
  onLineClick,
}: {
  title: string;
  prefix: string;
  lines: string[];
  statuses: LineStatus[];
  containerRef: RefObject<HTMLDivElement | null>;
  onScroll: () => void;
  onLineClick: (index: number) => void;
}) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-200 bg-slate-50 flex items-center gap-2">
        <FileText size={16} className="text-slate-500" aria-hidden="true" />
        <span className="font-medium text-slate-700">{title}</span>
        <span className="text-xs text-slate-500 ml-auto">{lines.length} lines</span>
      </div>
      <div
        ref={containerRef}
        onScroll={onScroll}
        role="region"
        tabIndex={0}
        aria-label={`${title} code`}
        className="relative max-h-[28rem] overflow-auto py-2 font-mono text-sm"
      >
        {lines.map((line, index) => {
          const status = statuses[index];
          return (
            <div
              key={index}
              data-line={index}
              id={`${prefix}-line-${index}`}
              onClick={status ? () => onLineClick(index) : undefined}
              title={status ? (status === 'exact' ? 'Identical line: click to find its match' : 'Same structure, different names: click to find its match') : undefined}
              className={`grid grid-cols-[3rem_1fr] border-l-4 ${
                status === 'exact'
                  ? 'cursor-pointer border-red-400 bg-red-50'
                  : status === 'renamed'
                    ? 'cursor-pointer border-amber-400 bg-amber-50'
                    : 'border-transparent'
              }`}
            >
              <span className="select-none pr-3 text-right text-xs leading-6 text-slate-400">{index + 1}</span>
              <code className="whitespace-pre-wrap break-words leading-6 text-slate-800">
                {line || ' '}
                {status && <span className="sr-only"> ({status === 'exact' ? 'identical line' : 'renamed match'})</span>}
              </code>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Page ──────────────────────────────────────────────────────────────────────

export default function EvidenceViewerPage() {
  const router = useRouter();

  // No code is pre-filled or auto-run. The page used to load a hard-coded sample on every visit and
  // show a made-up verdict (PROBABLE, 87%) and made-up "matched functions" next to it.
  const [codeA, setCodeA] = useState('');
  const [codeB, setCodeB] = useState('');
  const [language, setLanguage] = useState<Language>('python');
  const [view, setView] = useState<'edit' | 'compare'>('edit');
  const [isSample, setIsSample] = useState(false);
  const [inputNotice, setInputNotice] = useState('');
  const [syncScroll, setSyncScroll] = useState(true);

  // Verdict and score only come from an analysis, so they are only shown when a results page passes them.
  const [verdict, setVerdict] = useState<string | null>(null);
  const [score, setScore] = useState<number | null>(null);

  const [serverLoading, setServerLoading] = useState(false);
  const [serverError, setServerError] = useState('');
  const [serverData, setServerData] = useState<unknown>(null);

  const leftRef = useRef<HTMLDivElement | null>(null);
  const rightRef = useRef<HTMLDivElement | null>(null);
  const syncing = useRef(false);
  const fileInputA = useRef<HTMLInputElement | null>(null);
  const fileInputB = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const v = (params.get('verdict') || '').toUpperCase();
    if (Object.prototype.hasOwnProperty.call(VERDICT_STYLES, v)) setVerdict(v);
    const rawScore = Number(params.get('score'));
    if (params.get('score') !== null && Number.isFinite(rawScore) && rawScore >= 0 && rawScore <= 100) {
      setScore(rawScore > 1 ? rawScore / 100 : rawScore);
    }
  }, []);

  const hasBoth = codeA.trim() !== '' && codeB.trim() !== '';

  const comparison = useMemo(
    () => (view === 'compare' && hasBoth ? compareCode(codeA, codeB, language) : null),
    [view, hasBoth, codeA, codeB, language]
  );
  const linesA = useMemo(() => codeA.replace(/\r\n?/g, '\n').split('\n').slice(0, MAX_LINES), [codeA]);
  const linesB = useMemo(() => codeB.replace(/\r\n?/g, '\n').split('\n').slice(0, MAX_LINES), [codeB]);

  const goBack = () => {
    if (window.history.length > 1) router.back();
    else router.push('/history');
  };

  const loadSample = () => {
    setCodeA(SAMPLE_A);
    setCodeB(SAMPLE_B);
    setLanguage('python');
    setIsSample(true);
    setInputNotice('');
    setServerData(null);
    setServerError('');
  };

  const clearAll = () => {
    setCodeA('');
    setCodeB('');
    setIsSample(false);
    setInputNotice('');
    setView('edit');
    setServerData(null);
    setServerError('');
  };

  const swap = () => {
    setCodeA(codeB);
    setCodeB(codeA);
  };

  const handleFile = async (event: ChangeEvent<HTMLInputElement>, target: 'a' | 'b') => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    if (file.size > MAX_FILE_BYTES) {
      setInputNotice(`“${file.name}” is larger than ${Math.round(MAX_FILE_BYTES / 1024)} KB. Use a smaller file.`);
      return;
    }
    try {
      const text = await file.text();
      if (text.length > MAX_CODE_CHARS) {
        setInputNotice(`“${file.name}” is too long to compare here.`);
        return;
      }
      if (target === 'a') setCodeA(text);
      else setCodeB(text);
      const ext = file.name.split('.').pop()?.toLowerCase() || '';
      if (EXTENSION_LANGUAGE[ext]) setLanguage(EXTENSION_LANGUAGE[ext]);
      setIsSample(false);
      setInputNotice('');
    } catch {
      setInputNotice('That file couldn’t be read.');
    }
  };

  const onCodeChange = (target: 'a' | 'b', value: string) => {
    if (target === 'a') setCodeA(value);
    else setCodeB(value);
    setIsSample(false);
    setServerData(null);
  };

  const syncFrom = (source: RefObject<HTMLDivElement | null>, other: RefObject<HTMLDivElement | null>) => {
    if (!syncScroll || syncing.current || !source.current || !other.current) return;
    syncing.current = true;
    other.current.scrollTop = source.current.scrollTop;
    requestAnimationFrame(() => {
      syncing.current = false;
    });
  };

  // Jumping scrolls each pane to its own line, so scroll-sync is paused while that animation runs.
  const jumpTo = (aLine: number, bLine: number) => {
    syncing.current = true;
    scrollToLine(leftRef.current, aLine);
    scrollToLine(rightRef.current, bLine);
    window.setTimeout(() => {
      syncing.current = false;
    }, 600);
  };

  const findCounterpart = (from: 'a' | 'b', index: number) => {
    if (!comparison) return;
    const partner = from === 'a' ? comparison.matchA[index] : comparison.matchB[index];
    if (partner === undefined || partner < 0) return;
    if (from === 'a') jumpTo(index, partner);
    else jumpTo(partner, index);
  };

  const requestEngineEvidence = useCallback(async () => {
    if (!hasBoth || serverLoading) return;
    setServerLoading(true);
    setServerError('');
    try {
      // verdict / confidence keep the defaults this page always used when it has no analysis to quote.
      const response = await apiClient.post('/api/evidence-view/generate', {
        code_a: codeA,
        code_b: codeB,
        verdict: verdict ?? 'REVIEW',
        confidence: score ?? 0.5,
        explanation: score !== null ? `Similarity score: ${(score * 100).toFixed(1)}%` : 'Evidence requested from the Evidence Viewer.',
      });
      setServerData(response.data ?? {});
    } catch (err) {
      setServerError(describeError(err, 'Failed to generate the evidence view. Please try again.'));
    } finally {
      setServerLoading(false);
    }
  }, [hasBoth, serverLoading, codeA, codeB, verdict, score]);

  const evidenceSections = useMemo(() => extractEvidenceSections(serverData), [serverData]);
  const serverId =
    serverData && typeof serverData === 'object' && typeof (serverData as { id?: unknown }).id === 'string'
      ? (serverData as { id: string }).id
      : null;

  return (
    <DashboardLayout>
      <div className="theme-page-container">
        <div className="mb-4">
          <button
            type="button"
            onClick={goBack}
            className="theme-link mb-4 flex items-center gap-2 text-sm font-semibold"
          >
            <ChevronLeft size={16} aria-hidden="true" />
            Back
          </button>
        </div>

        <PageHeader
          eyebrow="Evidence"
          eyebrowStyle="badge"
          title="Evidence Viewer"
          description="Compare two submissions side by side and see which lines match, including lines that only differ by renamed variables."
          action={
            verdict || score !== null ? (
              <div className="flex items-center gap-3">
                {verdict && <VerdictBadge v={verdict} />}
                {score !== null && (
                  <span className="text-sm font-medium text-[var(--text-secondary)]">
                    Analysis score: {(score * 100).toFixed(1)}%
                  </span>
                )}
              </div>
            ) : null
          }
        />

        <p className="mb-4 flex items-start gap-2 text-sm text-slate-600">
          <Info size={16} className="mt-0.5 shrink-0 text-slate-400" aria-hidden="true" />
          <span>
            Matching is calculated in your browser and the code stays on this page unless you choose “Get engine evidence”.
            Highlights are a reading aid. They are not the detection engine’s score, and similarity alone does not show misconduct.
          </span>
        </p>

        {/* Mode + controls */}
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <div role="group" aria-label="Viewer mode" className="inline-flex rounded-xl bg-slate-100 p-1">
            {(['edit', 'compare'] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                aria-pressed={view === mode}
                disabled={mode === 'compare' && !hasBoth}
                onClick={() => setView(mode)}
                className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${
                  view === mode ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
                }`}
              >
                {mode === 'edit' ? <Code size={15} aria-hidden="true" /> : <GitCompare size={15} aria-hidden="true" />}
                {mode === 'edit' ? 'Edit code' : 'Compare'}
              </button>
            ))}
          </div>

          <label className="flex items-center gap-2 text-sm text-slate-600">
            <span>Language</span>
            <select
              value={language}
              onChange={(event) => setLanguage(event.target.value as Language)}
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            >
              {LANGUAGES.map((lang) => (
                <option key={lang.id} value={lang.id}>
                  {lang.label}
                </option>
              ))}
            </select>
          </label>

          <div className="ml-auto flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={swap}
              disabled={!codeA && !codeB}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              <ArrowLeftRight size={14} aria-hidden="true" /> Swap A and B
            </button>
            <button
              type="button"
              onClick={loadSample}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Load sample
            </button>
            <button
              type="button"
              onClick={clearAll}
              disabled={!codeA && !codeB}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              <Trash2 size={14} aria-hidden="true" /> Clear
            </button>
          </div>
        </div>

        {isSample && (
          <div role="status" className="mb-4 flex items-start gap-2 rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">
            <Info size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
            Sample code loaded. It is made-up example code, not a real submission.
          </div>
        )}
        {inputNotice && (
          <div role="alert" className="mb-4 flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
            {inputNotice}
          </div>
        )}

        {/* ── Edit mode ── */}
        {view === 'edit' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {([
              { id: 'a' as const, title: 'Submission A', value: codeA, input: fileInputA },
              { id: 'b' as const, title: 'Submission B', value: codeB, input: fileInputB },
            ]).map((pane) => (
              <div key={pane.id} className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
                <div className="px-4 py-3 border-b border-slate-200 bg-slate-50 flex items-center gap-2">
                  <FileText size={16} className="text-slate-500" aria-hidden="true" />
                  <label htmlFor={`code-${pane.id}`} className="font-medium text-slate-700">{pane.title}</label>
                  <button
                    type="button"
                    onClick={() => pane.input.current?.click()}
                    className="ml-auto inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-slate-600 hover:bg-slate-50"
                  >
                    <FileUp size={13} aria-hidden="true" /> Load file
                  </button>
                  <input
                    ref={pane.input}
                    type="file"
                    accept=".py,.java,.js,.ts,.jsx,.tsx,.c,.h,.cpp,.hpp,.cs,.go,.rs,.rb,.php,.kt,.swift,.txt"
                    className="hidden"
                    onChange={(event) => handleFile(event, pane.id)}
                  />
                </div>
                <textarea
                  id={`code-${pane.id}`}
                  value={pane.value}
                  onChange={(event) => onCodeChange(pane.id, event.target.value)}
                  maxLength={MAX_CODE_CHARS}
                  spellCheck={false}
                  placeholder="Paste code here, or use Load file"
                  className="block h-80 w-full resize-y border-0 p-4 font-mono text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-500/20"
                />
              </div>
            ))}
          </div>
        )}

        {/* ── Compare mode ── */}
        {view === 'compare' && comparison && (
          <>
            <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
              {[
                { label: 'Line match', value: `${comparison.percent}%`, sub: `${comparison.matched} of ${Math.max(comparison.consideredA, comparison.consideredB)} code lines` },
                { label: 'Identical lines', value: String(comparison.exact), sub: 'Same text on both sides' },
                { label: 'Renamed matches', value: String(comparison.renamed), sub: 'Same structure, different names' },
                { label: 'Matched blocks', value: String(comparison.blocks.length), sub: 'Runs of consecutive lines' },
              ].map((stat) => (
                <div key={stat.label} className="rounded-2xl border border-slate-200 bg-white p-4">
                  <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">{stat.label}</div>
                  <div className="mt-1 text-2xl font-bold text-slate-900">{stat.value}</div>
                  <div className="mt-0.5 text-xs text-slate-500">{stat.sub}</div>
                </div>
              ))}
            </div>

            <div className="mb-3 flex flex-wrap items-center gap-4 text-xs text-slate-600">
              <span className="inline-flex items-center gap-1.5"><span className="h-3 w-3 rounded border-l-4 border-red-400 bg-red-50" aria-hidden="true" /> Identical line</span>
              <span className="inline-flex items-center gap-1.5"><span className="h-3 w-3 rounded border-l-4 border-amber-400 bg-amber-50" aria-hidden="true" /> Renamed match</span>
              <label className="ml-auto inline-flex items-center gap-2">
                <input type="checkbox" checked={syncScroll} onChange={(event) => setSyncScroll(event.target.checked)} className="h-4 w-4 rounded border-slate-300" />
                Scroll both panes together
              </label>
            </div>

            {comparison.truncated && (
              <p role="status" className="mb-3 text-xs text-amber-700">Only the first {MAX_LINES.toLocaleString('en-US')} lines of each file are compared.</p>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <CodePane
                title="Submission A"
                prefix="a"
                lines={linesA}
                statuses={comparison.statusA}
                containerRef={leftRef}
                onScroll={() => syncFrom(leftRef, rightRef)}
                onLineClick={(index) => findCounterpart('a', index)}
              />
              <CodePane
                title="Submission B"
                prefix="b"
                lines={linesB}
                statuses={comparison.statusB}
                containerRef={rightRef}
                onScroll={() => syncFrom(rightRef, leftRef)}
                onLineClick={(index) => findCounterpart('b', index)}
              />
            </div>

            {/* Keyboard-friendly list of the matches */}
            <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-4">
              <h2 className="text-lg font-semibold text-slate-900">Matched blocks</h2>
              {comparison.blocks.length === 0 ? (
                <p className="mt-2 text-sm text-slate-500">No matching lines were found between these two files.</p>
              ) : (
                <ul className="mt-3 space-y-2">
                  {comparison.blocks.slice(0, MAX_BLOCKS_SHOWN).map((block, index) => (
                    <li key={`${block.aStart}-${block.bStart}-${index}`} className="flex flex-wrap items-center gap-3 rounded-lg bg-slate-50 p-3 text-sm">
                      <span
                        className={`rounded px-2 py-0.5 text-xs font-semibold ${
                          block.status === 'exact' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'
                        }`}
                      >
                        {block.status === 'exact' ? 'Identical' : 'Renamed'}
                      </span>
                      <span className="text-slate-700">
                        A lines {block.aStart + 1}{block.aEnd !== block.aStart ? `–${block.aEnd + 1}` : ''}
                        {' ↔ '}
                        B lines {block.bStart + 1}{block.bEnd !== block.bStart ? `–${block.bEnd + 1}` : ''}
                      </span>
                      <span className="text-xs text-slate-500">{block.lines} code line{block.lines === 1 ? '' : 's'}</span>
                      <button
                        type="button"
                        onClick={() => jumpTo(block.aStart, block.bStart)}
                        className="ml-auto rounded-lg border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                      >
                        Show
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              {comparison.blocks.length > MAX_BLOCKS_SHOWN && (
                <p className="mt-3 text-xs text-slate-500">Showing the first {MAX_BLOCKS_SHOWN} of {comparison.blocks.length} blocks.</p>
              )}
            </div>
          </>
        )}

        {/* ── Engine evidence ── */}
        <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-4">
          <div className="flex flex-wrap items-center gap-3">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">Engine evidence</h2>
              <p className="text-sm text-slate-500">Ask the detection service for its own evidence on this pair. This sends both code samples to the server.</p>
            </div>
            <button
              type="button"
              onClick={requestEngineEvidence}
              disabled={!hasBoth || serverLoading}
              className="ml-auto inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-50"
            >
              {serverLoading && <Loader2 size={16} className="animate-spin" aria-hidden="true" />}
              {serverLoading ? 'Requesting…' : 'Get engine evidence'}
            </button>
          </div>

          {serverError && (
            <div role="alert" className="mt-4 flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              <AlertCircle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
              {serverError}
            </div>
          )}

          {serverData !== null && !serverError && (
            <div className="mt-4 space-y-4" aria-live="polite">
              {evidenceSections.length === 0 ? (
                <p className="text-sm text-slate-600">
                  The service returned an evidence record{serverId ? ` (${serverId})` : ''} with no matched elements to display.
                </p>
              ) : (
                evidenceSections.map((section) => (
                  <div key={section.title}>
                    <h3 className="mb-2 font-medium capitalize text-slate-800">{section.title}</h3>
                    <div className="space-y-2">
                      {section.items.map((item, index) => (
                        <div key={`${item.title}-${index}`} className="rounded-lg bg-slate-50 p-3">
                          <div className="flex items-center justify-between gap-3">
                            <span className="font-medium text-slate-800">{item.title}</span>
                            {item.score !== null && (
                              <span className="rounded bg-emerald-100 px-2 py-1 text-xs font-semibold text-emerald-700">{item.score}%</span>
                            )}
                          </div>
                          {item.text && <p className="mt-2 text-sm text-slate-600">{item.text}</p>}
                        </div>
                      ))}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
