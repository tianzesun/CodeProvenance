// @ts-nocheck — TODO: add proper types (tracked in types/api.ts)

'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { PageHeader } from '@/components/saas/SaaSPrimitives';
import { apiClient } from '@/lib/apiClient';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import {
  AlertCircle,
  AlertTriangle,
  ChevronDown,
  ChevronLeft,
  ChevronUp,
  Download,
  Loader2,
  Printer,
  Search,
  ShieldAlert,
  ShieldCheck,
  ShieldX,
  Info,
} from 'lucide-react';
import { useEffect, useId, useMemo, useState } from 'react';

// ── Helpers ────────────────────────────────────────────────────────────────

const REFERENCE_HEADERS = ['x-correlation-id', 'x-request-id'];

/** Generic, status-keyed text; the server's own wording is not shown. A correlation id is appended when sent. */
function describeError(err, fallback) {
  const status = typeof err?.response?.status === 'number' ? err.response.status : undefined;
  const headers = err?.response?.headers || {};
  const reference = REFERENCE_HEADERS.map((name) => headers[name]).find((v) => typeof v === 'string' && v);

  let message = fallback;
  if (status === 401) message = 'Your session has expired. Please sign in again.';
  else if (status === 403) message = 'You don’t have access to this report.';
  else if (status === 404) message = 'This report could not be found.';

  return reference ? `${message} (Reference: ${reference})` : message;
}

function num(value) {
  if (value === null || value === undefined || value === '') return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

const clamp01 = (value) => Math.max(0, Math.min(1, num(value) ?? 0));

function formatPercent(value) {
  return `${Math.round(clamp01(value) * 100)}%`;
}

/** Whole percent, with a decimal under 10% so a small rate doesn't read as "0%". */
function pctSmart(value) {
  const n = num(value);
  if (n === null) return null;
  const p = n * 100;
  return p > 0 && Number(p.toFixed(1)) < 10 ? `${p.toFixed(1)}%` : `${Math.round(p)}%`;
}

function getCreatedAt(value) {
  if (!value) return 'Unknown time';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Unknown time';
  const sameYear = date.getFullYear() === new Date().getFullYear();
  return new Intl.DateTimeFormat('en-US', {
    year: sameYear ? undefined : 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);
}

function bandOf(score) {
  if (score >= 0.7) return 'high';
  if (score >= 0.4) return 'medium';
  return 'low';
}

function riskTone(score) {
  if (score >= 0.7) return { border: 'border-red-200 dark:border-red-500/20', bg: 'bg-red-50 dark:bg-red-500/10', text: 'text-red-700 dark:text-red-300', badge: 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300', bar: 'bg-red-500' };
  if (score >= 0.4) return { border: 'border-amber-200 dark:border-amber-500/20', bg: 'bg-amber-50 dark:bg-amber-500/10', text: 'text-amber-700 dark:text-amber-300', badge: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300', bar: 'bg-amber-500' };
  return { border: 'border-emerald-200 dark:border-emerald-500/20', bg: 'bg-emerald-50 dark:bg-emerald-500/10', text: 'text-emerald-700 dark:text-emerald-300', badge: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300', bar: 'bg-emerald-500' };
}

function RiskIcon({ score, size = 16 }) {
  if (score >= 0.7) return <ShieldX size={size} className="text-red-600" aria-hidden="true" />;
  if (score >= 0.4) return <ShieldAlert size={size} className="text-amber-600" aria-hidden="true" />;
  return <ShieldCheck size={size} className="text-emerald-600" aria-hidden="true" />;
}

const SIGNAL_LABELS = {
  perplexity: 'Token Entropy',
  burstiness: 'Code Burstiness',
  stylometry: 'Style Profile',
  pattern_library: 'LLM Fingerprints',
  structural_entropy: 'AST Uniformity',
  vocabulary_richness: 'Vocabulary Diversity',
  whitespace_rhythm: 'Whitespace Rhythm',
  docstring_density: 'Docstring Density',
  binoculars: 'Binoculars Detection',
  ast: 'AST Structure',
};

const SIGNAL_DESCRIPTIONS = {
  perplexity: 'Token Entropy: measures unpredictability/diversity of token usage; unusual patterns may indicate assistance.',
  burstiness: 'Code Burstiness: measures variation in code structure; lower uniformity may suggest assistance.',
  stylometry: 'Style Profile: compares code style consistency; consistent patterns may indicate assistance.',
  pattern_library: 'LLM Fingerprints: detects recurring patterns that may indicate assistance.',
  structural_entropy: 'AST Uniformity: measures structural repetition; more repetition may suggest assistance.',
  vocabulary_richness: 'Vocabulary Diversity: lower diversity may signal repetitive assistance.',
  whitespace_rhythm: 'Whitespace Rhythm: formatting regularity; highly regular patterns may indicate assistance.',
  docstring_density: 'Docstring Density: measures documentation presence. Not an assistance signal alone, but helps in combination.',
  binoculars: 'Binoculars Detection: divergence-based detector; low values may indicate assistance.',
  ast: 'AST Structure: measures uniformity of the abstract syntax tree; very regular structure may indicate assistance.',
};

const PAGE_STEP = 25;
const IN_PROGRESS = ['processing', 'queued', 'pending', 'running'];
const MAX_POLL_MS = 15 * 60 * 1000;

function hasBinoculars(entry) {
  return entry?.method === 'binoculars' || entry?.layers?.binoculars?.available === true;
}

// The tooltip used to open only on mouse hover, so it was unreachable by keyboard and on touch screens.
function SignalBar({ name, value, label, interpretation }) {
  const pct = Math.round(clamp01(value) * 100);
  const tone = riskTone(clamp01(value));
  const [showTip, setShowTip] = useState(false);
  const tipId = useId();
  const desc = interpretation || SIGNAL_DESCRIPTIONS[name] || '';
  const title = label || SIGNAL_LABELS[name] || name;

  return (
    <div className="group relative">
      <div className="flex items-center justify-between gap-2 text-xs">
        <div className="flex items-center gap-1.5 text-slate-600 font-medium dark:text-slate-400">
          {title}
          {desc && (
            <button
              type="button"
              onMouseEnter={() => setShowTip(true)}
              onMouseLeave={() => setShowTip(false)}
              onFocus={() => setShowTip(true)}
              onBlur={() => setShowTip(false)}
              onClick={() => setShowTip((v) => !v)}
              onKeyDown={(e) => { if (e.key === 'Escape') setShowTip(false); }}
              aria-expanded={showTip}
              aria-describedby={showTip ? tipId : undefined}
              className="relative text-slate-400 transition hover:text-slate-600 dark:hover:text-slate-200"
              aria-label={`Learn more about ${title}`}
            >
              <Info size={11} aria-hidden="true" />
            </button>
          )}
        </div>
        <span className={`font-bold ${tone.text}`}>{pct}%</span>
      </div>
      <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800" aria-hidden="true">
        <div
          className={`h-full rounded-full transition-all duration-500 ${tone.bar}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {showTip && desc && (
        <div id={tipId} role="tooltip" className="absolute bottom-full left-0 z-50 mb-2 w-72 rounded-xl border border-slate-200 bg-white p-3 text-xs text-slate-600 shadow-xl dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
          <div className="mb-1 font-semibold text-slate-700 dark:text-white">{title}</div>
          <div>{desc}</div>
        </div>
      )}
    </div>
  );
}

function CodeSnippet({ lines }) {
  if (!lines || lines.length === 0) return null;
  return (
    <div className="overflow-hidden rounded-xl border border-slate-800">
      <div className="flex items-center justify-between bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-300">
        <span>Code Preview</span>
        <span className="text-slate-400">Amber lines matched LLM fingerprints</span>
      </div>
      <div className="overflow-x-auto bg-slate-900" role="region" tabIndex={0} aria-label="Annotated code">
        <table className="w-full border-collapse font-mono text-[11px] leading-5">
          <tbody>
            {lines.map((ln, index) => (
              <tr
                key={`${ln.line}-${index}`}
                className={ln.flagged ? 'bg-amber-950/60' : ''}
              >
                <td
                  className={`w-10 select-none border-r border-slate-700 px-2 py-0.5 text-right align-top ${ln.flagged ? 'bg-amber-900/40 text-amber-400' : 'bg-slate-800/60 text-slate-500'
                    }`}
                >
                  {ln.line}
                </td>
                <td
                  className={`whitespace-pre-wrap break-all px-3 py-0.5 align-top ${ln.flagged ? 'text-amber-100' : 'text-slate-300'
                    }`}
                >
                  {ln.text}
                  {ln.flagged && <span className="sr-only"> (matched an LLM fingerprint)</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function FlaggedRegions({ regions }) {
  if (!Array.isArray(regions) || regions.length === 0) return null;

  const reasonLabels = {
    low_perplexity: 'Low Perplexity',
    high_uniformity: 'High Uniformity',
  };

  return (
    <div>
      <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
        Flagged Regions ({regions.length})
      </div>
      <div className="space-y-2">
        {regions.map((region, idx) => (
          <div key={idx} className="rounded-2xl border border-indigo-100 bg-indigo-50 p-3 dark:border-indigo-500/20 dark:bg-indigo-500/10">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="rounded-md bg-indigo-100 px-2 py-0.5 font-mono text-[11px] font-semibold text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300">
                  Lines {region.start_line}–{region.end_line}
                </span>
                <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                  region.severity === 'high'
                    ? 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300'
                    : 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300'
                }`}>
                  {region.severity}
                </span>
                {/* region.reason was read with .replace() directly, which crashed the page when it was missing. */}
                <span className="text-xs font-semibold capitalize text-indigo-800 dark:text-indigo-300">
                  {reasonLabels[region.reason] || String(region.reason || 'Flagged').replace(/_/g, ' ')}
                </span>
              </div>
            </div>
            {region.detail && (
              <div className="mt-1.5 text-xs text-indigo-700/80 dark:text-indigo-300/80">{region.detail}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function MetricTile({ label, value }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-900">
      <div className="text-xs text-slate-500 dark:text-slate-400">{label}</div>
      <div className="mt-1 text-lg font-semibold text-slate-900 dark:text-white">{value}</div>
    </div>
  );
}

function SubmissionCard({ entry, expanded, onToggle }) {
  const prob = entry._prob;
  const conf = clamp01(entry.confidence);
  const tone = riskTone(prob);
  const signals = entry.signals || {};
  const signalLabels = entry.signal_labels || {};
  const signalInterpretations = entry.signal_interpretations || {};
  const indicators = Array.isArray(entry.indicators) ? entry.indicators : [];
  const snippet = Array.isArray(entry.annotated_snippet) ? entry.annotated_snippet : [];
  const hasSnippet = snippet.length > 0;
  const metrics = entry.code_metrics || {};
  const patterns = entry.evidence_patterns || {};
  const method = entry.method || 'heuristic';
  const methodLabel =
    method === 'binoculars'
      ? 'Binoculars + heuristics'
      : method === 'ml'
        ? 'Classifier + heuristics'
        : 'Heuristic-only';
  const panelId = `submission-${entry._key}`;
  const metric = (value, suffix = '') => (num(value) === null ? '—' : `${value}${suffix}`);

  return (
    <div className={`rounded-3xl border ${tone.border} overflow-hidden bg-white shadow-sm dark:bg-slate-950`}>
      {/* Header row */}
      <div className={`${tone.bg} px-5 py-4`}>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex flex-wrap items-center gap-2">
            <RiskIcon score={prob} size={18} />
            <span className="font-semibold text-slate-900 dark:text-white">{entry.name || 'Unnamed submission'}</span>
            <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${tone.badge}`}>
              {entry.status}
            </span>
            {entry.language && (
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                {entry.language}
              </span>
            )}
            <span
              className="rounded-full bg-blue-100 px-2.5 py-1 text-xs font-semibold text-blue-700 dark:bg-blue-500/15 dark:text-blue-300"
              title={entry.model || methodLabel}
            >
              {methodLabel}
            </span>
            {/* The "Binoculars not installed" warning badge that repeated on every card is now one notice
                at the top of the page. */}
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right">
              {/* "Probability" implied a calibrated likelihood; this is a screening score. */}
              <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">Assistance Score</div>
              <div className={`text-2xl font-semibold ${tone.text}`}>{formatPercent(prob)}</div>
            </div>
            <div className="text-right">
              <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">Confidence</div>
              <div className="text-2xl font-semibold text-slate-700 dark:text-white">{formatPercent(conf)}</div>
            </div>
            <button
              type="button"
              onClick={onToggle}
              aria-expanded={expanded}
              aria-controls={panelId}
              className="ml-2 flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-500 transition hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400 dark:hover:bg-slate-800"
              aria-label={`${expanded ? 'Collapse' : 'Expand'} details for ${entry.name || 'submission'}`}
            >
              {expanded ? <ChevronUp size={16} aria-hidden="true" /> : <ChevronDown size={16} aria-hidden="true" />}
            </button>
          </div>
        </div>

        {/* Two bare percentages read as two failures. Say what each one is, and that a low
            pair means "look elsewhere", not "cleared" — the detector misses assisted code. */}
        <p className="mt-3 text-xs leading-relaxed text-slate-600 dark:text-slate-400">
          <span className="font-medium text-slate-700 dark:text-slate-300">Assistance Score</span> is a
          screening signal that this file is worth a closer read.{' '}
          <span className="font-medium text-slate-700 dark:text-slate-300">Confidence</span> is how strongly
          the underlying signals agree with each other — a low pair here means the evidence is weak, not that
          the code was cleared.
        </p>

        {/* Indicator pills */}
        {indicators.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {indicators.map((ind, i) => (
              <span
                key={`${ind}-${i}`}
                className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400"
              >
                {ind}
              </span>
            ))}
          </div>
        )}

        {entry.error && (
          <div role="alert" className="mt-2 text-xs text-red-700 dark:text-red-400">
            {typeof entry.error === 'string' ? entry.error : (entry.error?.message || 'An error occurred')}
          </div>
        )}
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div id={panelId} className="border-t border-slate-200 bg-white px-5 py-5 space-y-6 dark:border-slate-800 dark:bg-slate-950">
          {/* Code Metrics */}
          {Object.keys(metrics).length > 0 && (
            <div>
              <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
                Code Analysis Metrics
              </div>
              <div className="grid gap-2 sm:grid-cols-2 text-sm">
                <MetricTile label="Total Lines" value={metric(metrics.total_lines)} />
                <MetricTile label="Function Definitions" value={metric(metrics.functions)} />
                <MetricTile label="Type Hints" value={metric(metrics.type_hints)} />
                <MetricTile label="Documentation Ratio" value={`${Math.round(clamp01(metrics.docstring_ratio) * 100)}%`} />
                <MetricTile label="Comment Ratio" value={`${Math.round(clamp01(metrics.comment_ratio) * 100)}%`} />
                <MetricTile label="Average Line Length" value={metric(metrics.average_line_length, ' chars')} />
              </div>
            </div>
          )}

          {/* Evidence Patterns */}
          {Object.keys(patterns).length > 0 && (
            <div>
              <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
                AI-Specific Patterns Detected
              </div>
              <div className="space-y-2">
                {Object.entries(patterns).map(([patternType, patternList]) => (
                  <div key={patternType} className="rounded-2xl border border-amber-100 bg-amber-50 p-3 dark:border-amber-500/20 dark:bg-amber-500/10">
                    <div className="flex items-center justify-between">
                      <div className="text-sm font-semibold text-amber-900 capitalize dark:text-amber-300">
                        {patternType.replace(/_/g, ' ')}
                      </div>
                      <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-semibold text-amber-700 dark:bg-amber-500/15 dark:text-amber-300">
                        {Array.isArray(patternList) ? patternList.length : 0}
                      </span>
                    </div>
                    {Array.isArray(patternList) && patternList.length > 0 && (
                      <div className="mt-2 space-y-1 text-xs text-amber-800 dark:text-amber-300">
                        {patternList.slice(0, 3).map((p, idx) => (
                          <div key={idx} className="font-mono text-[11px]">
                            Line {p?.line}: <span className="text-amber-700 dark:text-amber-300">{p?.text}</span>
                          </div>
                        ))}
                        {patternList.length > 3 && (
                          <div className="text-amber-700 dark:text-amber-300">+{patternList.length - 3} more</div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Signal breakdown */}
          {Object.keys(signals).length > 0 && (
            <div>
              <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
                Detection Signal Analysis
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                {Object.entries(signals).map(([key, val]) => (
                  <SignalBar
                    key={key}
                    name={key}
                    value={val}
                    label={signalLabels[key] || SIGNAL_LABELS[key] || key}
                    interpretation={signalInterpretations[key] || ''}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Flagged regions (low perplexity / uniform code) */}
          <FlaggedRegions regions={entry.flagged_regions} />

          {/* Code snippet */}
          {hasSnippet && (
            <div>
              <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
                Annotated Code (First 60 Lines)
              </div>
              <CodeSnippet lines={snippet} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function DistributionBarSection({ distribution, total }) {
  const low = Math.max(0, num(distribution.low) ?? 0);
  const medium = Math.max(0, num(distribution.medium) ?? 0);
  const high = Math.max(0, num(distribution.high) ?? 0);
  // If the counts add up to more than the stated total (files that failed to score, for instance), the segments
  // used to overflow the bar. The larger of the two is used as the whole.
  const t = Math.max(1, num(total) ?? 0, low + medium + high);

  return (
    <section className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950">
      <h2 className="mb-3 text-lg font-semibold text-slate-900 dark:text-white">Assistance Score Distribution</h2>
      <div
        className="flex h-4 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800"
        role="img"
        aria-label={`${high} high, ${medium} medium and ${low} low out of ${t} submissions`}
      >
        {high > 0 && (
          <div className="bg-red-500 transition-all" style={{ width: `${(high / t) * 100}%` }} title={`High: ${high}`} />
        )}
        {medium > 0 && (
          <div className="bg-amber-400 transition-all" style={{ width: `${(medium / t) * 100}%` }} title={`Medium: ${medium}`} />
        )}
        {low > 0 && (
          <div className="bg-emerald-400 transition-all" style={{ width: `${(low / t) * 100}%` }} title={`Low: ${low}`} />
        )}
      </div>
      <div className="mt-3 flex flex-wrap gap-5 text-xs text-slate-600 dark:text-slate-400">
        <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-red-500" aria-hidden="true" />{high} High</span>
        <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-amber-400" aria-hidden="true" />{medium} Medium</span>
        <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-emerald-400" aria-hidden="true" />{low} Low</span>
      </div>
    </section>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────

export default function AIDetectorReportPage() {
  const params = useParams();
  const id = Array.isArray(params?.id) ? params.id[0] : params?.id;
  const encId = encodeURIComponent(id || '');
  const router = useRouter();
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const [fpBaseline, setFpBaseline] = useState(null);

  const [query, setQuery] = useState('');
  const [bandFilter, setBandFilter] = useState('all');
  const [order, setOrder] = useState('score');
  const [visibleCount, setVisibleCount] = useState(PAGE_STEP);
  const [expandedKeys, setExpandedKeys] = useState(() => new Set());

  useEffect(() => {
    const controller = new AbortController();
    apiClient
      .get('/api/ai-detect/accuracy', { signal: controller.signal })
      .then((res) => {
        if (!controller.signal.aborted && res.data?.human_fp_baseline?.corpora) {
          setFpBaseline(res.data.human_fp_baseline);
        }
      })
      .catch(() => {
        /* the measured numbers are optional context, never a page error */
      });
    return () => controller.abort();
  }, []);

  // Polling used to be a setInterval that ran every 2 seconds for as long as the page was open, even after the
  // report had loaded or failed, and overlapping requests could pile up. It now chains one request at a time, stops at
  // a final state, tolerates a couple of failed requests, and gives up after 15 minutes.
  useEffect(() => {
    if (!id) {
      setError('This page needs a report id.');
      setLoading(false);
      return undefined;
    }

    let cancelled = false;
    let timer = null;
    let failures = 0;
    let delay = 2000;
    const startedAt = Date.now();
    const controller = new AbortController();
    setLoading(true);
    setError('');

    const tick = async () => {
      try {
        const res = await apiClient.get(`/api/job/${encId}`, { signal: controller.signal });
        if (cancelled) return;
        failures = 0;
        const data = res.data;
        if (!data || typeof data !== 'object') throw new Error('empty response');

        if (data.job_type && data.job_type !== 'ai_detector' && !data.ai_detection) {
          router.replace(`/results/${encId}`);
          return;
        }
        if (data.status === 'failed') {
          setError('AI detection failed for this job. Please try again from the assessment page.');
          setJob(null);
          setLoading(false);
          return;
        }
        if (IN_PROGRESS.includes(data.status)) {
          if (Date.now() - startedAt > MAX_POLL_MS) {
            setError('This analysis is taking longer than expected. Check back later, or start it again.');
            setLoading(false);
            return;
          }
          delay = Math.min(delay + 500, 5000);
          timer = setTimeout(tick, delay);
          return;
        }
        setJob(data);
        setError('');
        setLoading(false);
      } catch (err) {
        if (cancelled || controller.signal.aborted) return;
        failures += 1;
        const status = err?.response?.status;
        if ([401, 403, 404].includes(status) || failures >= 3) {
          setError(describeError(err, 'Failed to load the AI Detector report.'));
          setJob(null);
          setLoading(false);
          return;
        }
        timer = setTimeout(tick, 3000);
      }
    };

    tick();
    return () => {
      cancelled = true;
      controller.abort();
      if (timer) clearTimeout(timer);
    };
  }, [id, encId, router, attempt]);

  const ai = job?.ai_detection || {};

  const allSubmissions = useMemo(
    () => (Array.isArray(ai.submissions) ? ai.submissions : [])
      .filter((entry) => entry && typeof entry === 'object')
      .map((entry, index) => ({ ...entry, _key: `${index}`, _prob: clamp01(entry.ai_probability) })),
    [ai.submissions],
  );

  const topSubmission = useMemo(
    () => allSubmissions.reduce((max, s) => (s._prob > (max?._prob ?? -1) ? s : max), null),
    [allSubmissions],
  );

  // One source for "highest": the detector's own figure if it reported one, otherwise the highest submission.
  // The header used one number and the Key Findings card another, computed separately.
  const highestScore = num(ai.highest_score) !== null ? clamp01(ai.highest_score) : (topSubmission?._prob ?? 0);
  const overallTone = riskTone(highestScore);

  const withoutBinoculars = allSubmissions.filter((s) => !hasBinoculars(s)).length;

  const shownSubmissions = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = allSubmissions.filter((s) => {
      if (bandFilter !== 'all' && bandOf(s._prob) !== bandFilter) return false;
      if (q && !String(s.name || '').toLowerCase().includes(q)) return false;
      return true;
    });
    if (order === 'name') return [...list].sort((a, b) => String(a.name || '').localeCompare(String(b.name || ''), undefined, { numeric: true }));
    if (order === 'score') return [...list].sort((a, b) => b._prob - a._prob);
    return list;
  }, [allSubmissions, query, bandFilter, order]);

  const toggleKey = (key) => {
    setExpandedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const expandAll = () => setExpandedKeys(new Set(shownSubmissions.slice(0, visibleCount).map((s) => s._key)));
  const collapseAll = () => setExpandedKeys(new Set());

  // The cards are collapsed by default, so "Print" produced a report with no evidence in it.
  const printReport = () => {
    setVisibleCount(Math.max(visibleCount, shownSubmissions.length));
    setExpandedKeys(new Set(shownSubmissions.map((s) => s._key)));
    setTimeout(() => window.print(), 150);
  };

  const studentCorpus = fpBaseline?.corpora?.kaggle_student_code;
  const fpHigh = pctSmart(studentCorpus?.['fp_at_0.70']);
  const fpMedium = pctSmart(studentCorpus?.['fp_at_0.40']);

  if (loading) {
    return (
      <DashboardLayout>
        <div className="theme-page-container space-y-6">
          <div
            aria-hidden="true"
            className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-950"
          >
            <div className="h-4 w-36 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
            <div className="mt-3 h-10 w-72 animate-pulse rounded-2xl bg-slate-200 dark:bg-slate-800" />
            <div className="mt-4 h-4 w-52 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
            <div className="mt-6 h-9 w-full animate-pulse rounded-xl bg-slate-200 dark:bg-slate-800" />
          </div>
          <p role="status" className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
            <Loader2 size={16} className="animate-spin" aria-hidden="true" />
            Analyzing submissions — this can take up to a minute for large batches...
          </p>
        </div>
      </DashboardLayout>
    );
  }

  if (error || !job) {
    return (
      <DashboardLayout>
        <div className="theme-page-container space-y-6">
          <div
            role="alert"
            className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300"
          >
            <AlertCircle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
            <span className="flex-1">{error || 'This report is unavailable.'}</span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => setAttempt((n) => n + 1)}
              className="inline-flex h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
            >
              Try again
            </button>
            <Link href="/ai-detector" className="theme-link inline-flex items-center gap-2 text-sm font-semibold">
              <ChevronLeft size={15} aria-hidden="true" />
              Back to Academic Integrity Assessment
            </Link>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  const topLabel = ai.highest_signal ? (SIGNAL_LABELS[ai.highest_signal] || String(ai.highest_signal).replace(/_/g, ' ')) : 'Pattern Analysis';
  const topSignalValue = num(ai.highest_signal_value);
  const calibration = num(ai.calibration_confidence);
  const visible = shownSubmissions.slice(0, visibleCount);

  // Review priority (a triage order). This was "Recommended Action: Schedule Review / Monitor / No Action",
  // which told the reader what to do from the score alone, and "No Action — Within normal range" offered false
  // reassurance, since the detector misses assisted code too.
  const priority = highestScore >= 0.7 ? 'Higher' : highestScore >= 0.4 ? 'Moderate' : 'Lower';

  return (
    <DashboardLayout>
      <div className="theme-page-container space-y-6">
        {/* Always shown. It used to appear only when the accuracy endpoint answered, and the endpoint can be
            restricted, so some users never saw the caveat. */}
        <div role="note" className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-300">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
          <span>
            {fpHigh !== null && fpMedium !== null ? (
              <>
                Measured on real student code: this detector flags {fpHigh} of human novice submissions at the high
                band and {fpMedium} at the medium band.{' '}
              </>
            ) : null}
            AI-detection scores can be wrong in both directions. Scores below are screening signals for a human
            conversation — never proof.
          </span>
        </div>

        {withoutBinoculars > 0 && (
          <div role="note" className="flex items-start gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400">
            <Info size={16} className="mt-0.5 shrink-0 text-slate-400" aria-hidden="true" />
            <span>
              {withoutBinoculars === allSubmissions.length ? 'All' : `${withoutBinoculars} of ${allSubmissions.length}`} submissions were
              scored without the Binoculars zero-shot layer (it is not installed), so those results come from statistical
              signals and, where available, the trained classifier rather than the full ensemble.
            </span>
          </div>
        )}

        {/* Back link kept as its own block above the canonical PageHeader. */}
        <Link href="/ai-detector" className="theme-link inline-flex items-center gap-2 text-sm font-semibold">
          <ChevronLeft size={15} aria-hidden="true" />
          Academic Integrity Assessment
        </Link>

        <PageHeader
          eyebrow="AI Detection"
          eyebrowStyle="badge"
          title={job.assignment_name || job.course_name || 'AI Detection Report'}
          description={getCreatedAt(job.created_at)}
          action={
            <div className="no-print flex flex-wrap items-center gap-2">
              <div
                className={`inline-flex items-center gap-2 rounded-full px-2.5 py-1 text-xs font-semibold ${overallTone.badge}`}
              >
                <RiskIcon score={highestScore} size={14} />
                Highest {formatPercent(highestScore)}
              </div>
              <a
                href={`/report/${encId}/ai-originality-pdf`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
              >
                <Download size={16} aria-hidden="true" />
                Download PDF Report
              </a>
              <button
                type="button"
                onClick={printReport}
                className="inline-flex h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
              >
                <Printer size={16} aria-hidden="true" />
                Print Report
              </button>
            </div>
          }
        />

        {/* Key Findings and Distribution - side by side */}
        <section className="grid gap-4 lg:grid-cols-2">
          {/* Key Findings Section */}
          {allSubmissions.length > 0 && (
            <section className="rounded-[28px] border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
              <div className="border-b border-slate-200 px-5 py-4 dark:border-slate-800">
                <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Key Findings</h2>
                <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  Summary of assistance indicators across submissions
                </div>
              </div>
              <div className="p-5">
                <div className="grid gap-4 sm:grid-cols-3 text-sm">
                  <div className="rounded-[24px] border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-950">
                    <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
                      Highest Score
                    </div>
                    {/* The colour here came from an expression where an object was compared with 0.7 and `||`
                        bound tighter than `>=`, so it was amber for any non-zero score. It now follows the score. */}
                    <div className={`mt-1 text-lg font-bold ${riskTone(highestScore).text}`}>
                      {formatPercent(highestScore)}
                    </div>
                    {topSubmission?.name && (
                      <div className="mt-1 truncate text-xs text-slate-500 dark:text-slate-400" title={topSubmission.name}>{topSubmission.name}</div>
                    )}
                    {calibration !== null && (
                      <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                        Calibration confidence: {Math.round(clamp01(calibration) * 100)}%
                      </div>
                    )}
                  </div>
                  <div className="rounded-[24px] border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-950">
                    <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
                      Most Indicative Signal
                    </div>
                    <div className="font-medium text-slate-900 dark:text-white">{topLabel}</div>
                    {topSignalValue !== null && topSignalValue > 0 && (
                      <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                        {(clamp01(topSignalValue) * 100).toFixed(1)}% signal strength
                      </div>
                    )}
                  </div>
                  <div className="rounded-[24px] border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-950">
                    <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
                      Review Priority
                    </div>
                    <div className="font-medium text-slate-900 dark:text-white">{priority}</div>
                    <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                      Triage order only. A lower score does not rule out assistance.
                    </div>
                  </div>
                </div>
              </div>
            </section>
          )}

          {/* Distribution Bar */}
          {ai.distribution && (
            <DistributionBarSection distribution={ai.distribution} total={ai.total_files || allSubmissions.length} />
          )}
        </section>

        {/* Submission evidence */}
        <section>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Submission Analysis</h2>
              <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                Detailed evidence for each submission. AI detection scores serve as review signals — not standalone misconduct determinations.
              </div>
            </div>
            {allSubmissions.length > 0 && (
              <div className="no-print flex items-center gap-3 text-sm font-semibold">
                <button type="button" onClick={expandAll} className="text-blue-600 hover:underline dark:text-blue-400">Expand all</button>
                <button type="button" onClick={collapseAll} className="text-slate-500 hover:underline dark:text-slate-400">Collapse all</button>
              </div>
            )}
          </div>

          {allSubmissions.length > 1 && (
            <div className="no-print mb-4 flex flex-wrap items-center gap-2">
              <div role="group" aria-label="Filter by score band" className="flex flex-wrap gap-2">
                {[['all', 'All'], ['high', 'High'], ['medium', 'Medium'], ['low', 'Low']].map(([key, label]) => (
                  <button
                    key={key}
                    type="button"
                    aria-pressed={bandFilter === key}
                    onClick={() => { setBandFilter(key); setVisibleCount(PAGE_STEP); }}
                    className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition ${bandFilter === key ? 'border-blue-600 bg-blue-600 text-white' : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400 dark:hover:bg-slate-800'}`}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <label className="relative ml-auto block">
                <Search
                  size={16}
                  aria-hidden="true"
                  className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                />
                <input
                  type="search"
                  name="submission-search"
                  autoComplete="off"
                  value={query}
                  onChange={(e) => { setQuery(e.target.value); setVisibleCount(PAGE_STEP); }}
                  placeholder="Search submissions"
                  aria-label="Search submissions"
                  className="h-10 w-40 rounded-xl border border-slate-200 bg-white pl-9 pr-4 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white dark:placeholder:text-slate-500"
                />
              </label>
              <div className="relative">
                <select
                  value={order}
                  onChange={(e) => setOrder(e.target.value)}
                  aria-label="Order submissions"
                  className="h-10 appearance-none rounded-xl border border-slate-200 bg-white pl-4 pr-9 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white"
                >
                  <option value="score">Highest score first</option>
                  <option value="name">Name</option>
                  <option value="reported">As reported</option>
                </select>
                <ChevronDown
                  size={14}
                  aria-hidden="true"
                  className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400"
                />
              </div>
            </div>
          )}

          <p role="status" className="sr-only">{shownSubmissions.length} of {allSubmissions.length} submissions shown</p>

          <div className="space-y-4">
            {visible.map((entry) => (
              <SubmissionCard
                key={entry._key}
                entry={entry}
                expanded={expandedKeys.has(entry._key)}
                onToggle={() => toggleKey(entry._key)}
              />
            ))}
            {shownSubmissions.length > visibleCount && (
              <button
                type="button"
                onClick={() => setVisibleCount((n) => n + PAGE_STEP)}
                className="no-print inline-flex h-10 w-full items-center justify-center rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
              >
                Show more ({shownSubmissions.length - visibleCount} remaining)
              </button>
            )}
            {allSubmissions.length === 0 && (
              <div className="rounded-[28px] border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
                <div className="px-5 py-16 text-center">
                  <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-slate-100 text-slate-500 dark:bg-slate-900 dark:text-slate-400">
                    <Info size={22} aria-hidden="true" />
                  </div>
                  <h3 className="mt-4 text-base font-semibold text-slate-900 dark:text-white">
                    No detection evidence
                  </h3>
                  <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500 dark:text-slate-400">
                    No AI detection evidence was stored for this assessment.
                  </p>
                </div>
              </div>
            )}
            {allSubmissions.length > 0 && shownSubmissions.length === 0 && (
              <div className="rounded-[28px] border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
                <div className="px-5 py-16 text-center">
                  <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-slate-100 text-slate-500 dark:bg-slate-900 dark:text-slate-400">
                    <Search size={22} aria-hidden="true" />
                  </div>
                  <h3 className="mt-4 text-base font-semibold text-slate-900 dark:text-white">
                    No matching submissions
                  </h3>
                  <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500 dark:text-slate-400">
                    No submissions match the current filters.
                  </p>
                </div>
              </div>
            )}
          </div>
        </section>
      </div>
    </DashboardLayout>
  );
}
