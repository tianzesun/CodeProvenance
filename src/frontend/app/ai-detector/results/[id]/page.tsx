// @ts-nocheck — TODO: add proper types (tracked in types/api.ts)
'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { apiClient } from '@/lib/apiClient';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import {
  AlertCircle,
  ArrowLeft,
  Bot,
  ChevronDown,
  ChevronUp,
  Download,
  FileCode2,
  Loader2,
  Printer,
  ShieldAlert,
  ShieldCheck,
  ShieldX,
  Info,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

function formatPercent(value) {
  return `${Math.round((Number(value) || 0) * 100)}%`;
}

function getCreatedAt(value) {
  if (!value) return 'Unknown time';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);
}

function riskTone(score) {
  if (score >= 0.7) return { border: 'border-red-200', bg: 'bg-red-50', text: 'text-red-700', badge: 'bg-red-100 text-red-800', bar: 'bg-red-500' };
  if (score >= 0.4) return { border: 'border-amber-200', bg: 'bg-amber-50', text: 'text-amber-700', badge: 'bg-amber-100 text-amber-800', bar: 'bg-amber-500' };
  return { border: 'border-emerald-200', bg: 'bg-emerald-50', text: 'text-emerald-700', badge: 'bg-emerald-100 text-emerald-800', bar: 'bg-emerald-500' };
}

function RiskIcon({ score, size = 16 }) {
  if (score >= 0.7) return <ShieldX size={size} className="text-red-600" />;
  if (score >= 0.4) return <ShieldAlert size={size} className="text-amber-600" />;
  return <ShieldCheck size={size} className="text-emerald-600" />;
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
};

function SignalBar({ name, value, label }) {
  const pct = Math.round((Number(value) || 0) * 100);
  const tone = riskTone(value);
  const [showTip, setShowTip] = useState(false);
  const desc = SIGNAL_DESCRIPTIONS[name] || '';

  return (
    <div className="group relative">
      <div className="flex items-center justify-between gap-2 text-xs">
        <div className="flex items-center gap-1.5 text-slate-600 font-medium">
          {label || SIGNAL_LABELS[name] || name}
          {desc && (
            <button
              type="button"
              onMouseEnter={() => setShowTip(true)}
              onMouseLeave={() => setShowTip(false)}
              className="relative text-slate-300 hover:text-slate-500"
              aria-label={`Learn more about ${label || SIGNAL_LABELS[name] || name}`}
            >
              <Info size={11} />
            </button>
          )}
        </div>
        <span className={`font-bold ${tone.text}`}>{pct}%</span>
      </div>
      <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-slate-100">
        <div
          className={`h-full rounded-full transition-all duration-500 ${tone.bar}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {showTip && desc && (
        <div className="absolute bottom-full left-0 z-50 mb-2 w-72 rounded-xl border border-slate-200 bg-white p-3 text-xs text-slate-600 shadow-xl">
          <div className="font-semibold text-slate-700 mb-1">{label || SIGNAL_LABELS[name] || name}</div>
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
        <span className="text-slate-500">Amber lines matched LLM fingerprints</span>
      </div>
      <div className="overflow-x-auto bg-slate-900">
        <table className="w-full border-collapse font-mono text-[11px] leading-5">
          <tbody>
            {lines.map((ln) => (
              <tr
                key={ln.line}
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
  if (!regions || regions.length === 0) return null;

  const reasonLabels = {
    low_perplexity: 'Low Perplexity',
    high_uniformity: 'High Uniformity',
  };

  return (
    <div>
      <div className="mb-3 text-xs font-bold uppercase tracking-widest text-slate-400">
        Flagged Regions ({regions.length})
      </div>
      <div className="space-y-2">
        {regions.map((region, idx) => (
          <div key={idx} className="rounded-lg border border-indigo-100 bg-indigo-50 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="rounded-md bg-indigo-100 px-2 py-0.5 font-mono text-[11px] font-semibold text-indigo-700">
                  Lines {region.start_line}–{region.end_line}
                </span>
                <span className={`rounded-full px-2 py-0.5 text-[11px] font-bold ${
                  region.severity === 'high' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'
                }`}>
                  {region.severity}
                </span>
                <span className="text-xs font-semibold capitalize text-indigo-800">
                  {reasonLabels[region.reason] || region.reason.replace(/_/g, ' ')}
                </span>
              </div>
            </div>
            {region.detail && (
              <div className="mt-1.5 text-xs text-indigo-700/80">{region.detail}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function SubmissionCard({ entry }) {
  const [expanded, setExpanded] = useState(false);
  const prob = Number(entry.ai_probability) || 0;
  const conf = Number(entry.confidence) || 0;
  const tone = riskTone(prob);
  const signals = entry.signals || {};
  const signalLabels = entry.signal_labels || {};
  const indicators = entry.indicators || [];
  const snippet = entry.annotated_snippet || [];
  const hasSnippet = snippet.length > 0;
  const metrics = entry.code_metrics || {};
  const patterns = entry.evidence_patterns || {};

  return (
    <div className={`rounded-2xl border ${tone.border} overflow-hidden`}>
      {/* Header row */}
      <div className={`${tone.bg} px-5 py-4`}>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex flex-wrap items-center gap-2">
            <RiskIcon score={prob} size={18} />
            <span className="font-semibold text-slate-900">{entry.name}</span>
            <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${tone.badge}`}>
              {entry.status}
            </span>
            {entry.language && (
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-500">
                {entry.language}
              </span>
            )}
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right">
              <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Assistance Probability</div>
              <div className={`text-2xl font-black ${tone.text}`}>{formatPercent(prob)}</div>
            </div>
            <div className="text-right">
              <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Confidence</div>
              <div className="text-2xl font-black text-slate-700">{formatPercent(conf)}</div>
            </div>
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              className="ml-2 flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-500 transition hover:bg-slate-50"
              aria-label={expanded ? 'Collapse' : 'Expand'}
            >
              {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>
          </div>
        </div>

        {/* Indicator pills */}
        {indicators.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {indicators.map((ind) => (
              <span
                key={ind}
                className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-600"
              >
                {ind}
              </span>
            ))}
          </div>
        )}

        {entry.error && (
          <div className="mt-2 text-xs text-red-600">
            {typeof entry.error === 'string' ? entry.error : (entry.error?.message || 'An error occurred')}
          </div>
        )}
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t border-slate-100 bg-white px-5 py-5 space-y-6">
          {/* Code Metrics */}
          {Object.keys(metrics).length > 0 && (
            <div>
              <div className="mb-3 text-xs font-bold uppercase tracking-widest text-slate-400">
                Code Analysis Metrics
              </div>
              <div className="grid gap-2 sm:grid-cols-2 text-sm">
                <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
                  <div className="text-xs text-slate-500">Total Lines</div>
                  <div className="mt-1 text-lg font-semibold text-slate-900">{metrics.total_lines}</div>
                </div>
                <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
                  <div className="text-xs text-slate-500">Function Definitions</div>
                  <div className="mt-1 text-lg font-semibold text-slate-900">{metrics.functions}</div>
                </div>
                <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
                  <div className="text-xs text-slate-500">Type Hints</div>
                  <div className="mt-1 text-lg font-semibold text-slate-900">{metrics.type_hints}</div>
                </div>
                <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
                  <div className="text-xs text-slate-500">Documentation Ratio</div>
                  <div className="mt-1 text-lg font-semibold text-slate-900">{Math.round((metrics.docstring_ratio || 0) * 100)}%</div>
                </div>
                <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
                  <div className="text-xs text-slate-500">Comment Ratio</div>
                  <div className="mt-1 text-lg font-semibold text-slate-900">{Math.round((metrics.comment_ratio || 0) * 100)}%</div>
                </div>
                <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
                  <div className="text-xs text-slate-500">Average Line Length</div>
                  <div className="mt-1 text-lg font-semibold text-slate-900">{metrics.average_line_length} chars</div>
                </div>
              </div>
            </div>
          )}

          {/* Evidence Patterns */}
          {Object.keys(patterns).length > 0 && (
            <div>
              <div className="mb-3 text-xs font-bold uppercase tracking-widest text-slate-400">
                AI-Specific Patterns Detected
              </div>
              <div className="space-y-2">
                {Object.entries(patterns).map(([patternType, patternList]) => (
                  <div key={patternType} className="rounded-lg border border-amber-100 bg-amber-50 p-3">
                    <div className="flex items-center justify-between">
                      <div className="text-sm font-semibold text-amber-900 capitalize">
                        {patternType.replace(/_/g, ' ')}
                      </div>
                      <span className="rounded-full bg-amber-200 px-2 py-0.5 text-xs font-bold text-amber-900">
                        {Array.isArray(patternList) ? patternList.length : 0}
                      </span>
                    </div>
                    {Array.isArray(patternList) && patternList.length > 0 && (
                      <div className="mt-2 space-y-1 text-xs text-amber-800">
                        {patternList.slice(0, 3).map((p, idx) => (
                          <div key={idx} className="font-mono text-[11px]">
                            Line {p.line}: <span className="text-amber-700">{p.text}</span>
                          </div>
                        ))}
                        {Array.isArray(patternList) && patternList.length > 3 && (
                          <div className="text-amber-700">+{patternList.length - 3} more</div>
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
              <div className="mb-3 text-xs font-bold uppercase tracking-widest text-slate-400">
                Detection Signal Analysis
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                {Object.entries(signals).map(([key, val]) => (
                  <SignalBar
                    key={key}
                    name={key}
                    value={val}
                    label={signalLabels[key] || SIGNAL_LABELS[key] || key}
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
              <div className="mb-3 text-xs font-bold uppercase tracking-widest text-slate-400">
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

export default function AIDetectorReportPage() {
  const { id } = useParams();
  const router = useRouter();
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    apiClient
      .get(`/api/job/${id}`)
      .then((res) => {
        if (res.data?.job_type && res.data.job_type !== 'ai_detector' && !res.data?.ai_detection) {
          router.replace(`/results/${id}`);
          return;
        }
        setJob(res.data);
        setError('');
      })
      .catch((err) => {
        setError(err?.response?.data?.detail || 'Failed to load AI Detector report.');
        setJob(null);
      })
      .finally(() => setLoading(false));
  }, [id, router]);

  const ai = job?.ai_detection || {};
  const submissions = useMemo(() => (Array.isArray(ai.submissions) ? ai.submissions : []), [ai.submissions]);
  const highestScore = Number(ai.highest_score) || 0;
  const overallTone = riskTone(highestScore);

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex min-h-[60vh] items-center justify-center gap-3 text-slate-500">
          <Loader2 size={18} className="animate-spin" />
          Loading AI Detector report...
        </div>
      </DashboardLayout>
    );
  }

  if (error) {
    return (
      <DashboardLayout>
        <div className="px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <div className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
            <AlertCircle size={16} className="mt-0.5 shrink-0" />
            {error}
          </div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <div className="space-y-6">

          {/* Header card */}
          <section className="theme-card-strong rounded-[30px] overflow-hidden">
            <div className="theme-section-line px-6 py-5 lg:px-7">
              <Link
                href="/ai-detector"
                className="mb-5 inline-flex items-center gap-2 text-sm font-semibold text-blue-600"
              >
                <ArrowLeft size={15} />
                Academic Integrity Assessment
              </Link>
              <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
                <div>
                  <div className="inline-flex items-center gap-2 rounded-full border border-blue-600/10 bg-blue-600/[0.06] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--accent-blue)]">
                    <Bot size={13} />
                    AI-Generated Code Analysis Report
                  </div>
                  <h1 className="font-display mt-4 text-3xl font-semibold tracking-tight text-[var(--text-primary)] sm:text-4xl">
                    {job.assignment_name || 'AI-Generated Code Analysis Report'}
                  </h1>
                  <p className="mt-3 text-sm leading-7 text-[var(--text-secondary)]">
                    {job.course_name || 'Course'} &middot; {getCreatedAt(job.created_at)}
                  </p>
                </div>
                <div className="no-print flex flex-wrap items-center gap-3">
                  <a
                    href={`/api/report/${id}/ai-originality-pdf`}
                    className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
                  >
                    <Download size={16} />
                    Download PDF Report
                  </a>
                  <button
                    type="button"
                    onClick={() => window.print()}
                    className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
                  >
                    <Printer size={16} />
                    Print Report
                  </button>
                  <div
                    className={`inline-flex items-center gap-2 rounded-2xl border px-4 py-3 text-sm font-semibold ${overallTone.border} ${overallTone.bg} ${overallTone.text}`}
                  >
                    <RiskIcon score={highestScore} size={16} />
                    Highest {formatPercent(highestScore)}
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* Key Findings and Distribution - side by side */}
          <section className="grid gap-4 lg:grid-cols-2">
            {/* Key Findings Section */}
            {submissions.length > 0 && (
              <section className="rounded-2xl bg-white shadow-sm ring-1 ring-slate-200">
                <div className="border-b border-slate-100 px-5 py-4">
                  <div className="text-sm font-semibold text-slate-900">Key Findings</div>
                  <div className="mt-1 text-xs text-slate-500">
                    Summary of assistance indicators across submissions
                  </div>
                </div>
                <div className="p-5">
                  <div className="grid gap-4 sm:grid-cols-3 text-sm">
                    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                      <div className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1">
                        Highest Probability
                      </div>
                      <div className={`mt-1 text-lg font-bold ${riskTone(submissions.reduce((max, s) => 
                        (s.ai_probability || 0) > (max.ai_probability || 0) ? s : max, 
                        { ai_probability: 0 }).ai_probability || 0) >= 0.7 ? 'text-red-700' : 
                        submissions.reduce((max, s) => 
                        (s.ai_probability || 0) > (max.ai_probability || 0) ? s : max, 
                        { ai_probability: 0 }).ai_probability || 0 >= 0.4 ? 'text-amber-700' : 'text-emerald-700'}`}>
                        {formatPercent(submissions.reduce((max, s) => 
                          (s.ai_probability || 0) > (max.ai_probability || 0) ? s : max, 
                          { ai_probability: 0 }).ai_probability || 0)}
                      </div>
                      {ai.calibration_confidence !== undefined && (
                        <div className="mt-1 text-xs text-slate-500">
                          Calibration confidence: {Math.round((ai.calibration_confidence || 0) * 100)}%
                        </div>
                      )}
                    </div>
                    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                      <div className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1">
                        Most Indicative Signal
                      </div>
                      <div className="font-medium text-slate-900">
                        {ai.highest_signal || 'Pattern Analysis'}
                      </div>
                      <div className="mt-1 text-xs text-slate-500">
                        {(ai.highest_signal_value * 100 || 0).toFixed(1)}% confidence
                      </div>
                    </div>
                    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                      <div className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1">
                        Recommended Action
                      </div>
                      <div className="font-medium text-slate-900">
                        {highestScore >= 0.7 ? 'Schedule Review' : 
                         highestScore >= 0.4 ? 'Monitor' : 'No Action'}
                      </div>
                      <div className="mt-1 text-xs text-slate-500">
                        {highestScore >= 0.7 ? 'High assistance probability' : 
                         highestScore >= 0.4 ? 'Review recommended' : 'Within normal range'}
                      </div>
                    </div>
                  </div>
                </div>
              </section>
            )}

            {/* Distribution Bar */}
            {ai.distribution && (
              <DistributionBarSection distribution={ai.distribution} total={ai.total_files || submissions.length} />
            )}
          </section>

          {/* Submission evidence */}
          <section>
            <div className="mb-4 flex items-center justify-between gap-4">
              <div>
                <div className="text-sm font-semibold text-slate-900">Submission Analysis</div>
                <div className="mt-1 text-xs text-slate-500">
                  Detailed evidence for each submission. AI detection scores serve as review signals — not standalone misconduct determinations.
                </div>
              </div>
            </div>
            <div className="space-y-4">
              {submissions.map((entry) => (
                <SubmissionCard key={entry.name} entry={entry} />
              ))}
              {submissions.length === 0 && (
                <div className="rounded-2xl border border-slate-200 bg-white px-5 py-8 text-sm text-slate-500">
                  No AI detection evidence was stored for this assessment.
                </div>
              )}
            </div>
          </section>
        </div>
      </div>
    </DashboardLayout>
  );
}

function DistributionBarSection({ distribution, total }) {
  const low = Number(distribution.low) || 0;
  const medium = Number(distribution.medium) || 0;
  const high = Number(distribution.high) || 0;
  const t = Math.max(1, total);

  return (
    <section className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
      <div className="mb-3 text-xs font-bold uppercase tracking-widest text-slate-400">Assistance Probability Distribution</div>
      <div className="flex h-4 overflow-hidden rounded-full">
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
      <div className="mt-3 flex gap-5 text-xs text-slate-500">
        <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-red-500" />{high} High</span>
        <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-amber-400" />{medium} Medium</span>
        <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />{low} Low</span>
      </div>
    </section>
  );
}
