// @ts-nocheck
'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { useAuth } from '@/components/AuthProvider';
import { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import axios from 'axios';
import {
  BarChart3, Loader2, Trophy, FileUp, X, AlertCircle,
  Zap, Target, Layers, TrendingUp, CheckCircle2, ChevronDown, ChevronUp,
  Download, Play, FlaskConical, FileText, Square, Check,
  ChevronRight, UploadCloud, Database, Settings2, ClipboardList, Plus,
  GitCompare,
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from 'recharts';

const API = process.env.NEXT_PUBLIC_API_URL || '';

// ── Tool definitions with full UI metadata ──────────────────────────────
const TOOLS = [
  {
    id: 'integritydesk',
    name: 'IntegrityDesk',
    color: '#7C3AED',
    bgLight: 'bg-violet-50',
    textColor: 'text-violet-700',
    ring: 'ring-violet-500',
    gradient: 'from-violet-500 to-violet-700',
    engines: ['AST', 'Embedding', 'Execution', 'Fingerprint', 'N-gram'],
    desc: 'Full multi-engine fusion: AST, UniXcoder embeddings, execution similarity, and winnowing.',
    status: 'Ready to run',
  },
  {
    id: 'moss',
    name: 'MOSS',
    color: '#0369A1',
    bgLight: 'bg-sky-50',
    textColor: 'text-sky-700',
    ring: 'ring-sky-500',
    gradient: 'from-sky-500 to-sky-700',
    engines: ['Fingerprint', 'Token'],
    desc: "Stanford's canonical academic plagiarism detector using k-gram fingerprinting.",
    status: 'Ready to run',
  },
  {
    id: 'jplag',
    name: 'JPlag',
    color: '#B45309',
    bgLight: 'bg-amber-50',
    textColor: 'text-amber-700',
    ring: 'ring-amber-500',
    gradient: 'from-amber-500 to-amber-700',
    engines: ['Token', 'AST'],
    desc: 'AST-based plagiarism detector widely used in academic settings. Supports 10+ languages.',
    status: 'Ready to run',
  },
  {
    id: 'dolos',
    name: 'Dolos',
    color: '#047857',
    bgLight: 'bg-emerald-50',
    textColor: 'text-emerald-700',
    ring: 'ring-emerald-500',
    gradient: 'from-emerald-500 to-emerald-700',
    engines: ['AST', 'Fingerprint'],
    desc: 'Modern AST + fingerprint tool from University of Ghent. Produces a pairwise similarity matrix.',
    status: 'Ready to run',
  },
  {
    id: 'nicad',
    name: 'NiCad',
    color: '#9D174D',
    bgLight: 'bg-pink-50',
    textColor: 'text-pink-700',
    ring: 'ring-pink-500',
    gradient: 'from-pink-500 to-pink-700',
    engines: ['Clone', 'Text'],
    desc: 'Clone detector using text normalisation and differencing. Strong on near-miss (Type 3) clones.',
    status: 'Ready to run',
  },
  {
    id: 'pmd',
    name: 'PMD-CPD',
    color: '#374151',
    bgLight: 'bg-slate-50',
    textColor: 'text-slate-700',
    ring: 'ring-slate-500',
    gradient: 'from-slate-500 to-slate-700',
    engines: ['Token', 'Duplication'],
    desc: 'Copy-Paste Detector from the PMD project. Fast token-based duplication finder.',
    status: 'Ready to run',
  },
  {
    id: 'sherlock',
    name: 'Sherlock',
    color: '#065F46',
    bgLight: 'bg-teal-50',
    textColor: 'text-teal-700',
    ring: 'ring-teal-500',
    gradient: 'from-teal-500 to-teal-700',
    engines: ['Token'],
    desc: 'Classical token-based plagiarism detector from University of Sydney.',
    status: 'Setup needed',
    runnable: false,
  },
  {
    id: 'sim',
    name: 'SIM',
    color: '#6B21A8',
    bgLight: 'bg-purple-50',
    textColor: 'text-purple-700',
    ring: 'ring-purple-500',
    gradient: 'from-purple-500 to-purple-700',
    engines: ['Text'],
    desc: 'Classical similarity detector by Dick Grune. Historical baseline for multi-language comparison.',
    status: 'Ready to run',
  },
];

// ── FIX #1: Merge API availability data with full TOOLS metadata ──────────
function mergeToolsWithAvailability(apiTools = []) {
  if (!apiTools.length) return TOOLS;
  return TOOLS.map(toolDef => {
    const apiTool = apiTools.find(t => t.id === toolDef.id);
    if (!apiTool) return { ...toolDef, available: false };
    return { ...toolDef, available: apiTool.available !== false, status: apiTool.status || toolDef.status };
  });
}

// ── Dataset category metadata ──────────────────────────────────────────────
const DATASET_CATEGORY_META = {
  guided: {
    label: 'Quick Check',
    eyebrow: 'Fastest way to validate tools',
    badgeClass: 'bg-violet-100 text-violet-700',
    accentClass: 'text-violet-600',
    panelClass: 'border-violet-200 bg-violet-50/70',
    summaryLabel: 'Quick check',
  },
  preset: {
    label: 'Preset Dataset',
    eyebrow: 'Standardized benchmark data',
    badgeClass: 'bg-emerald-100 text-emerald-700',
    accentClass: 'text-emerald-600',
    panelClass: 'border-emerald-200 bg-emerald-50/70',
    summaryLabel: 'Preset dataset',
  },
  demo: {
    label: 'Demo Dataset',
    eyebrow: 'Reusable classroom-style demo',
    badgeClass: 'bg-blue-100 text-blue-700',
    accentClass: 'text-blue-600',
    panelClass: 'border-blue-200 bg-blue-50/70',
    summaryLabel: 'Demo dataset',
  },
};

const PRESET_DATASET_META = {
  clough_stevenson_style: {
    order: 5, presetCategory: 'Controlled plagiarism corpus', badgeLabel: 'Gold Standard',
    eyebrow: 'Controlled original-vs-plagiarized benchmark',
    summary: 'Balanced exact, renamed, restructured, semantic, and hard-negative code pairs',
  },
  conplag_classroom_java: {
    order: 10, presetCategory: 'Classroom-style', badgeLabel: 'Classroom Java',
    eyebrow: 'Best Java submission corpus', summary: 'Assignment-grouped Java submissions with labels',
  },
  kaggle_student_code: {
    order: 20, presetCategory: 'Classroom-style', badgeLabel: 'Classroom Python',
    eyebrow: 'Best Python submission smoke test', summary: 'Lightweight student-style Python submission set',
  },
  'IR-Plag-Dataset': {
    order: 30, presetCategory: 'Research benchmark', badgeLabel: 'Research Benchmark',
    eyebrow: 'Focused Java plagiarism cases', summary: 'Smaller Java plagiarism dataset for targeted checks',
  },
  human_eval: {
    order: 40, presetCategory: 'Programming-task benchmark', badgeLabel: 'Programming Tasks',
    eyebrow: 'Python code-task benchmark', summary: 'Task-based Python benchmark, not classroom submissions',
  },
  mbpp: {
    order: 50, presetCategory: 'Programming-task benchmark', badgeLabel: 'Programming Tasks',
    eyebrow: 'Short-form Python task coverage', summary: 'Python programming task benchmark, not classroom submissions',
  },
  codesearchnet: {
    order: 60, presetCategory: 'Large-scale technical corpus', badgeLabel: 'Technical Corpus',
    eyebrow: 'Large-scale mixed-language stress test', summary: 'Use for scale and variety rather than classroom realism',
  },
  codexglue_clone: {
    order: 70, presetCategory: 'Research benchmark', badgeLabel: 'Research Benchmark',
    eyebrow: 'Large labeled clone-pair benchmark', summary: 'Good for clone-pair stress testing in Java',
  },
  codexglue_defect: {
    order: 80, presetCategory: 'Research benchmark', badgeLabel: 'Research Benchmark',
    eyebrow: 'C code technical benchmark', summary: 'Useful for stress testing, less classroom-like',
  },
};

// ── Pure helpers ───────────────────────────────────────────────────────────
function getPresetDatasetMeta(dataset) {
  if (!dataset || dataset.is_demo || dataset.cases) return null;
  return PRESET_DATASET_META[dataset.id] || null;
}

function getDatasetCategory(dataset) {
  if (!dataset) return null;
  if (dataset.datasetType) return dataset.datasetType;
  if (dataset.cases) return 'guided';
  return dataset.is_demo ? 'demo' : 'preset';
}

function getDatasetCategoryMeta(dataset) {
  const category = getDatasetCategory(dataset);
  return category ? DATASET_CATEGORY_META[category] : null;
}

function formatDatasetDate(value) {
  if (!value) return 'Recently created';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric' }).format(parsed);
}

function summarizeDataset(dataset) {
  if (!dataset) return '';
  if (dataset.cases) return `${dataset.cases.length} guided scenarios`;
  if (dataset.is_demo) {
    const sizeLabel = dataset.size || 'Custom size';
    const similarityLabel = dataset.similarity_type ? dataset.similarity_type.replaceAll('_', ' ') : 'Classroom-style patterns';
    return `${sizeLabel} • ${similarityLabel}`;
  }
  const sizeLabel = dataset.size || 'Benchmark scale';
  const languageLabel = dataset.language ? dataset.language.toUpperCase() : 'Mixed';
  const presetMeta = getPresetDatasetMeta(dataset);
  if (presetMeta?.presetCategory) return `${presetMeta.presetCategory} • ${languageLabel} • ${sizeLabel}`;
  return `${languageLabel} • ${sizeLabel}`;
}

function formatBenchmarkQuality(quality) {
  if (!quality) return null;
  const level = ['gold_standard', 'controlled_gold_standard', 'gold_standard_external'].includes(quality.certification_level)
    ? 'Gold-standard controlled benchmark'
    : quality.certification_level === 'controlled_internal_ready'
      ? 'Controlled internal benchmark'
      : 'Labeled benchmark';
  return `${level} • ${Number(quality.score_percent || 0).toFixed(0)}% quality gates`;
}

function sortDatasets(datasets, demo = false) {
  const items = [...datasets];
  if (demo) return items.sort((a, b) => (Date.parse(b.created_at || '') || 0) - (Date.parse(a.created_at || '') || 0));
  return items.sort((a, b) => {
    const aOrder = getPresetDatasetMeta(a)?.order ?? 9999;
    const bOrder = getPresetDatasetMeta(b)?.order ?? 9999;
    return aOrder !== bOrder ? aOrder - bOrder : (a.name || '').localeCompare(b.name || '');
  });
}

function buildDatasetLibrary(benchmarkDatasets = []) {
  const presetDatasets = sortDatasets(benchmarkDatasets.filter(d => !d.is_demo).map(d => ({ ...d, datasetType: 'preset' })));
  const demoDatasets = sortDatasets(benchmarkDatasets.filter(d => d.is_demo).map(d => ({ ...d, datasetType: 'demo' })), true);
  return { presetDatasets, demoDatasets, allDatasets: [...presetDatasets, ...demoDatasets] };
}

function formatDelta(value, lowerIsBetter = false) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return 'N/A';
  const numeric = Number(value);
  const adjusted = lowerIsBetter ? -numeric : numeric;
  const sign = adjusted > 0 ? '+' : '';
  return `${sign}${(adjusted * 100).toFixed(1)}%`;
}

function deltaTone(value, lowerIsBetter = false) {
  const numeric = Number(value || 0);
  if (Math.abs(numeric) < 0.0001) return 'text-slate-500 bg-slate-100';
  const improved = lowerIsBetter ? numeric < 0 : numeric > 0;
  return improved ? 'text-emerald-700 bg-emerald-50' : 'text-rose-700 bg-rose-50';
}

function formatChartPercent(value) { return `${Number(value || 0).toFixed(1)}%`; }
function formatMetric(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return 'N/A';
  return Number(value).toFixed(3);
}

function formatEngineContribution(contribution = {}) {
  const entries = Object.entries(contribution || {})
    .filter(([, value]) => typeof value === 'number' && value > 0).slice(0, 3);
  if (!entries.length) return 'N/A';
  return entries.map(([name, value]) => `${name}: ${(Number(value) * 100).toFixed(0)}%`).join(', ');
}

function formatPanMetricValue(metric) {
  if (metric.value === null || metric.value === undefined || Number.isNaN(Number(metric.value))) return 'N/A';
  if (metric.format === 'seconds') return `${Number(metric.value).toFixed(3)}s`;
  if (metric.format === 'plain') return Number(metric.value).toFixed(3);
  return `${(Number(metric.value) * 100).toFixed(1)}%`;
}

function metricBarWidth(metric) {
  const v = Math.max(0, Math.min(1, Number(metric.value || 0)));
  if (metric.mode === 'runtime') return `${Math.max(8, Math.min(100, (2 - Math.min(v * 10, 2)) / 2 * 100))}%`;
  if (metric.mode === 'lower') return `${Math.max(8, Math.min(100, (1 - v) * 100))}%`;
  if (metric.mode === 'granularity') {
    const distance = Math.min(1, Math.abs(v - 1));
    return `${Math.max(8, Math.min(100, (1 - distance) * 100))}%`;
  }
  return `${Math.max(8, Math.min(100, v * 100))}%`;
}

function metricTone(score, mode = 'higher') {
  if (mode === 'lower') { if (score <= 0.05) return 'good'; if (score <= 0.15) return 'watch'; return 'bad'; }
  if (mode === 'granularity') { if (score <= 1.05) return 'good'; if (score <= 1.2) return 'watch'; return 'bad'; }
  if (mode === 'runtime') { if (score <= 0.5) return 'good'; if (score <= 2) return 'watch'; return 'bad'; }
  if (score >= 0.9) return 'good'; if (score >= 0.75) return 'watch'; return 'bad';
}

function metricToneClasses(tone) {
  if (tone === 'good') return { border: 'border-emerald-200', bg: 'bg-emerald-50', text: 'text-emerald-700', bar: 'bg-emerald-500', badge: 'bg-emerald-100 text-emerald-700', label: 'Strong' };
  if (tone === 'watch') return { border: 'border-amber-200', bg: 'bg-amber-50', text: 'text-amber-700', bar: 'bg-amber-500', badge: 'bg-amber-100 text-amber-700', label: 'Needs attention' };
  return { border: 'border-red-200', bg: 'bg-red-50', text: 'text-red-700', bar: 'bg-red-500', badge: 'bg-red-100 text-red-700', label: 'Optimization priority' };
}

function buildPanFeedback(row) {
  if (!row) return [];
  const suggestions = [];
  if (row.precision < 0.85) suggestions.push({ title: 'Precision is the main problem', detail: 'False positives are too high. Raise the final decision threshold, increase weight on exact/token/AST agreement, and reduce broad semantic-only matches until negatives are cleaner.' });
  if (row.recall < 0.85) suggestions.push({ title: 'Recall is missing true plagiarism', detail: 'Lower the candidate threshold, enable semantic or embedding retrieval for obfuscated clones, and make sure renamed/type-3/type-4 pairs enter the candidate pool before reranking.' });
  if (row.f1Score < 0.85) suggestions.push({ title: 'F1 needs threshold calibration', detail: 'Sweep thresholds on the labeled PAN set and choose the point that maximizes F1 before tuning individual engine weights.' });
  if (row.granularity > 1.2) suggestions.push({ title: 'Granularity suggests over-splitting', detail: 'Merge overlapping or adjacent detections from the same file pair and prefer one coherent evidence span over many tiny fragments.' });
  if (row.top10Retrieval < 0.9) suggestions.push({ title: 'Top-10 retrieval is weak', detail: 'The highest-ranked results are still noisy. Improve cheap lexical/AST retrieval, apply stricter negative filters before ranking, then rerank top candidates with heavier engines.' });
  if ((row.top20Retrieval ?? 0) < 0.95) suggestions.push({ title: 'Top-20 retrieval still loses positives', detail: 'The first page of candidates is not clean enough. Tune ranking with precision@20/PR-AUC so true plagiarism consistently appears above negatives.' });
  if (row.falsePositiveRate > 0.1) suggestions.push({ title: 'False positive rate is too high', detail: 'Add stricter negative filters for boilerplate, templates, and common starter code. Require agreement between at least two independent engines before high-risk classification.' });
  if (row.aucPr < 0.85) suggestions.push({ title: 'Ranking quality is weak', detail: 'AUC-PR below target means true plagiarism is not consistently ranked above negatives. Tune fusion weights with PR-AUC/PlagDet as objectives, not average similarity.' });
  if (row.engineContributionText !== 'N/A') suggestions.push({ title: 'Use contribution balance to guide engine weights', detail: `Current top contributors are ${row.engineContributionText}. If one engine dominates, run ablations and reduce its weight when it causes false positives.` });
  if (row.avgRuntimeSeconds > 2) suggestions.push({ title: 'Runtime is expensive', detail: 'Cache tokenization/AST parsing, use cheap lexical retrieval first, run embeddings only on shortlisted candidates, and avoid all-pairs heavy scoring for large classes.' });
  if (!suggestions.length) suggestions.push({ title: 'PAN metrics look balanced', detail: 'Keep this engine mix as the baseline. Next improvements should be validated with harder obfuscation sets and a larger negative corpus.' });
  return suggestions;
}

function buildPanMetricDiagnostics(row) {
  if (!row) return [];
  const scoreDiagnostics = row.scoreDiagnostics || {};
  const hasLabelConflict = Boolean(scoreDiagnostics.label_conflict);
  const metrics = [
    { key: 'plagdet', label: 'PlagDet', value: row.plagdet, mode: 'higher', target: 'Target >= 90%', why: row.plagdet < 0.75 ? 'The primary PAN score is low.' : row.plagdet < 0.9 ? 'Usable but still room to improve.' : 'Strong primary PAN score.', action: row.plagdet < 0.9 ? 'Optimize threshold and fusion weights against PlagDet directly.' : 'Freeze as baseline.' },
    { key: 'precision', label: 'Precision', value: row.precision, mode: 'higher', target: 'Target >= 90%', why: hasLabelConflict ? 'Label conflict: some negatives score as high as positives.' : row.precision < 0.75 ? 'Too many clean pairs flagged as plagiarism.' : row.precision < 0.9 ? 'False positives still elevated.' : 'False positives under control.', action: hasLabelConflict ? 'Inspect high-scoring negatives and fix labels before threshold tuning.' : row.precision < 0.9 ? 'Raise threshold and require engine agreement before high-confidence flags.' : 'Keep current precision guardrails.' },
    { key: 'recall', label: 'Recall', value: row.recall, mode: 'higher', target: 'Target >= 90%', why: row.recall < 0.75 ? 'Too many plagiarism pairs missed.' : row.recall < 0.9 ? 'Some true plagiarism below decision boundary.' : 'Finding nearly all labeled pairs.', action: row.recall < 0.9 ? 'Lower candidate threshold and strengthen renamed/structural clone handling.' : 'Preserve candidate recall path while tuning precision.' },
    { key: 'f1', label: 'F1 Score', value: row.f1Score, mode: 'higher', target: 'Target >= 90%', why: row.f1Score < 0.75 ? 'Precision/recall tradeoff not calibrated.' : row.f1Score < 0.9 ? 'Close but threshold not at best operating point.' : 'Well balanced.', action: row.f1Score < 0.9 ? 'Run threshold sweep, keep the threshold that maximizes F1.' : 'Use this F1 as acceptance baseline.' },
    { key: 'granularity', label: 'Granularity', value: row.granularity, mode: 'granularity', format: 'plain', target: 'Target close to 1.000', why: row.granularity > 1.2 ? 'Splitting single case into too many fragments.' : row.granularity > 1.05 ? 'Slight fragmentation.' : 'Detections consolidated cleanly.', action: row.granularity > 1.05 ? 'Merge adjacent/overlapping evidence before scoring.' : 'Keep one coherent detection per true pair.' },
    { key: 'auc_pr', label: 'AUC-PR', value: row.aucPr, mode: 'higher', target: 'Target >= 90%', why: row.aucPr < 0.75 ? 'True plagiarism not consistently ranked above negatives.' : row.aucPr < 0.9 ? 'Ranking decent but vulnerable.' : 'Ranking separates positives from negatives well.', action: row.aucPr < 0.9 ? 'Tune fusion weights with PR-AUC and add harder negatives.' : 'Validate on larger negative corpus.' },
    { key: 'fpr', label: 'False Positive Rate', value: row.falsePositiveRate, mode: 'lower', target: 'Target <= 5%', why: row.falsePositiveRate > 0.15 ? 'Too many non-plagiarized pairs flagged.' : row.falsePositiveRate > 0.05 ? 'Manageable but worth reducing.' : 'Negative pairs filtered cleanly.', action: row.falsePositiveRate > 0.05 ? 'Add boilerplate suppression and require multi-engine agreement.' : 'Keep current negative filters.' },
    { key: 'top10', label: 'Top-10 Retrieval', value: row.top10Retrieval, mode: 'higher', target: 'Target >= 90%', why: hasLabelConflict ? 'True pairs pushed down by label conflicts.' : row.top10Retrieval < 0.75 ? 'Top-ranked results mostly not true positives.' : row.top10Retrieval < 0.9 ? 'Some true pairs ranked too low.' : 'Candidate stage surfacing true positives early.', action: hasLabelConflict ? 'Fix pair labels before re-running retrieval metrics.' : row.top10Retrieval < 0.9 ? 'Tune with precision@10 and PR-AUC.' : 'Use as baseline for speed optimizations.' },
    { key: 'runtime', label: 'Avg Runtime', value: row.avgRuntimeSeconds, mode: 'runtime', format: 'seconds', target: 'Target <= 0.5s / pair', why: row.avgRuntimeSeconds > 2 ? 'Too slow for iterative benchmark work.' : row.avgRuntimeSeconds > 0.5 ? 'Acceptable for small evaluations.' : 'Healthy for rapid optimization loops.', action: row.avgRuntimeSeconds > 0.5 ? 'Cache parsing, run cheap retrieval first, reserve embeddings for shortlisted pairs.' : 'Keep speed guardrails while improving accuracy.' },
  ];
  return metrics.map(metric => ({ ...metric, tone: metricTone(Number(metric.value || 0), metric.mode) }));
}

// ── ToolBadge ──────────────────────────────────────────────────────────────
function ToolBadge({ toolId, compact = false }) {
  const tool = TOOLS.find(t => t.id === toolId);
  if (!tool) return (
    <span className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600">
      <span className="h-2.5 w-2.5 rounded-full bg-slate-400" />{toolId}
    </span>
  );
  return (
    <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 ${compact ? 'text-[11px]' : 'text-xs'} font-semibold ${tool.bgLight} ${tool.textColor} border-current/10`}>
      <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: tool.color }} />{tool.name}
    </span>
  );
}

// ── Tooltip components ─────────────────────────────────────────────────────
function PairScoreTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const rows = payload.filter(e => typeof e.value === 'number').sort((a, b) => Number(b.value) - Number(a.value));
  return (
    <div className="min-w-[220px] rounded-2xl border border-slate-200 bg-white/95 p-4 shadow-2xl shadow-slate-900/10 backdrop-blur">
      <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">File Pair</div>
      <div className="mt-1 text-sm font-semibold text-slate-900">{label}</div>
      <div className="mt-3 space-y-2">
        {rows.map(entry => (
          <div key={entry.dataKey} className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2 min-w-0">
              <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: entry.color || '#94a3b8' }} />
              <span className="truncate text-xs font-medium text-slate-600">{TOOLS.find(t => t.id === entry.dataKey)?.name || entry.name}</span>
            </div>
            <span className="text-xs font-semibold text-slate-900">{formatChartPercent(entry.value)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function LeaderboardTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload;
  if (!row) return null;
  const tool = TOOLS.find(t => t.id === row.id);
  return (
    <div className="min-w-[240px] rounded-2xl border border-slate-200 bg-white/95 p-4 shadow-2xl shadow-slate-900/10 backdrop-blur">
      <div className="flex items-center gap-2">
        <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: row.color }} />
        <div className="text-sm font-semibold text-slate-900">{row.name}</div>
      </div>
      {tool?.desc && <div className="mt-2 text-xs leading-5 text-slate-500">{tool.desc}</div>}
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
        {[['Average', row.average], ['Peak', row.peak], ['Lowest', row.minimum], ['Spread', row.spread]].map(([lbl, val]) => (
          <div key={lbl} className="rounded-xl bg-slate-50 px-3 py-2">
            <div className="text-slate-400">{lbl}</div>
            <div className="mt-1 font-semibold text-slate-900">{formatChartPercent(val)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── StepIndicator ──────────────────────────────────────────────────────────
function StepIndicator({ steps, currentStep, completedSteps }) {
  return (
    <div className="flex items-center">
      {steps.map((step, idx) => {
        const isCompleted = completedSteps.includes(idx);
        const isCurrent = currentStep === idx;
        const isLast = idx === steps.length - 1;
        return (
          <div key={idx} className="flex items-center flex-1 last:flex-none">
            <div className={`flex items-center gap-2.5 px-3 py-2 rounded-xl transition-all duration-300 ${isCurrent ? 'bg-slate-900 shadow-lg' : isCompleted ? 'bg-emerald-50 border border-emerald-200' : 'bg-white border border-slate-200'}`}>
              <div className={`w-6 h-6 rounded-full flex items-center justify-center font-bold shrink-0 text-[11px] transition-all duration-300 ${isCurrent ? 'bg-white/20 text-white' : isCompleted ? 'bg-emerald-500 text-white' : 'bg-slate-100 text-slate-400'}`}>
                {isCompleted ? <Check size={12} /> : idx + 1}
              </div>
              <div>
                <div className={`text-[11px] font-bold uppercase tracking-wide transition-colors ${isCurrent ? 'text-white' : isCompleted ? 'text-emerald-700' : 'text-slate-400'}`}>{step.label}</div>
                <div className={`text-[10px] mt-0.5 hidden sm:block transition-colors ${isCurrent ? 'text-slate-300' : isCompleted ? 'text-emerald-500' : 'text-slate-400'}`}>{step.subtitle}</div>
              </div>
            </div>
            {!isLast && (
              <div className={`h-px flex-1 mx-1.5 transition-all duration-500 ${completedSteps.includes(idx) ? 'bg-emerald-300' : 'bg-slate-200'}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── RunConfigBar — sticky summary shown during step 2+ ─────────────────────
function RunConfigBar({ selectedTools, selectedDataset, uploadMode, files, benchmarkDatasets, modeName, modeColor }) {
  const { allDatasets } = useMemo(() => buildDatasetLibrary(benchmarkDatasets), [benchmarkDatasets]);
  const activeDataset = allDatasets.find(d => d.id === selectedDataset);
  const toolNames = selectedTools.slice(0, 3).map(id => TOOLS.find(t => t.id === id)?.name || id);
  const extraTools = selectedTools.length - 3;
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm text-sm">
      <span className={`rounded-full px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide ${modeColor}`}>{modeName}</span>
      <div className="flex items-center gap-1.5 text-slate-600">
        <Settings2 size={13} className="text-slate-400" />
        <span className="font-medium">{toolNames.join(', ')}{extraTools > 0 ? ` +${extraTools}` : ''}</span>
      </div>
      <div className="h-3.5 w-px bg-slate-200" />
      <div className="flex items-center gap-1.5 text-slate-600">
        <Database size={13} className="text-slate-400" />
        <span className="font-medium">{uploadMode === 'builtin' ? (activeDataset?.name || 'No dataset') : `${files.length} file${files.length !== 1 ? 's' : ''}`}</span>
      </div>
    </div>
  );
}

// ── Tool loading skeleton ──────────────────────────────────────────────────
function ToolSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 xl:grid-cols-4 gap-3">
      {Array.from({ length: 7 }).map((_, i) => (
        <div key={i} className="p-4 rounded-xl border-2 border-slate-200 bg-white animate-pulse">
          <div className="w-9 h-9 rounded-lg bg-slate-200 mb-3" />
          <div className="h-4 bg-slate-200 rounded-lg w-3/4 mb-2" />
          <div className="h-3 bg-slate-100 rounded-lg w-1/2 mb-3" />
          <div className="flex gap-1.5">
            <div className="h-5 w-12 bg-slate-100 rounded-full" />
            <div className="h-5 w-10 bg-slate-100 rounded-full" />
          </div>
        </div>
      ))}
    </div>
  );
}

// ── DatasetCard ────────────────────────────────────────────────────────────
function DatasetCard({ dataset, isActive, onSelect, disabled = false }) {
  const categoryMeta = getDatasetCategoryMeta(dataset);
  const presetMeta = getPresetDatasetMeta(dataset);
  const badgeLabel = presetMeta?.badgeLabel || categoryMeta?.label;
  const eyebrow = presetMeta?.eyebrow || categoryMeta?.eyebrow;
  const secondarySummary = presetMeta?.summary;
  const qualityLabel = formatBenchmarkQuality(dataset.benchmark_quality);
  return (
    <button
      disabled={disabled}
      onClick={() => { if (!disabled) onSelect(dataset.id); }}
      className={`group relative rounded-2xl border-2 p-4 text-left transition-all duration-200 ${disabled ? 'cursor-not-allowed border-slate-200 bg-slate-50 opacity-60' : isActive ? 'border-slate-900 bg-slate-900 text-white shadow-lg shadow-slate-900/15' : 'border-slate-200 bg-white hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-md'}`}
    >
      {isActive && <div className="absolute right-3 top-3"><CheckCircle2 size={16} className="text-white" /></div>}
      <div className="flex items-start justify-between gap-3">
        <div className="text-2xl">{dataset.icon}</div>
        <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${isActive ? 'bg-white/15 text-white' : categoryMeta?.badgeClass}`}>{badgeLabel}</span>
      </div>
      <div className={`mt-4 text-[11px] font-semibold uppercase tracking-[0.18em] ${isActive ? 'text-slate-300' : 'text-slate-400'}`}>{eyebrow}</div>
      <div className={`mt-2 text-base font-semibold ${isActive ? 'text-white' : 'text-slate-900'}`}>{dataset.name}</div>
      <div className={`mt-2 text-sm leading-6 ${isActive ? 'text-slate-200' : 'text-slate-500'}`}>{dataset.desc}</div>
      {secondarySummary && <div className={`mt-2 text-xs leading-5 ${isActive ? 'text-slate-300' : 'text-slate-400'}`}>{secondarySummary}</div>}
      {qualityLabel && (
        <div className={`mt-3 flex items-start gap-2 rounded-xl px-3 py-2 text-xs leading-5 ${isActive ? 'bg-white/10 text-slate-100' : 'bg-emerald-50 text-emerald-700'}`}>
          <ClipboardList size={14} className="mt-0.5 shrink-0" /><span>{qualityLabel}</span>
        </div>
      )}
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${isActive ? 'bg-white/10 text-white' : 'bg-slate-100 text-slate-600'}`}>{summarizeDataset(dataset)}</span>
        {dataset.created_by && <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${isActive ? 'bg-white/10 text-white' : 'bg-slate-100 text-slate-600'}`}>{dataset.created_by}</span>}
        {dataset.has_ground_truth && <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${isActive ? 'bg-white/10 text-white' : 'bg-emerald-50 text-emerald-700'}`}>Labeled</span>}
      </div>
    </button>
  );
}

// ── Step 1: Tool Selection ─────────────────────────────────────────────────
function ToolSelectionStep({ tools, selectedTools, setSelectedTools, onNext, loading, error, benchmarkMode }) {
  const runnableTools = tools.filter(t => t.available !== false && t.runnable !== false);
  const integrityDeskTool = tools.find(t => t.id === 'integritydesk');
  const isImproveMode = benchmarkMode === 'development';
  const integrityDeskReady = Boolean(integrityDeskTool && integrityDeskTool.available !== false && integrityDeskTool.runnable !== false);

  useEffect(() => {
    if (!isImproveMode) return;
    if (!integrityDeskReady) return;
    if (selectedTools.length === 1 && selectedTools[0] === 'integritydesk') return;
    setSelectedTools(['integritydesk']);
  }, [integrityDeskReady, isImproveMode, selectedTools, setSelectedTools]);

  const toggleTool = (tool) => {
    if (tool.available === false || tool.runnable === false) return;
    setSelectedTools(prev => prev.includes(tool.id) ? prev.filter(t => t !== tool.id) : [...prev, tool.id]);
  };

  if (benchmarkMode === 'comparison') {
    return (
      <div>
        <div className="mb-6">
          <h2 className="font-semibold text-slate-900 flex items-center gap-2">
            <Settings2 size={18} className="text-violet-500" />Select Detection Tools
          </h2>
          <div className="flex items-center gap-3 mt-3">
            <span className={`text-sm font-semibold px-3 py-1.5 rounded-lg transition-all ${selectedTools.length > 0 ? 'bg-violet-50 text-violet-700' : 'bg-slate-100 text-slate-400'}`}>
              {selectedTools.length} / {runnableTools.length} selected
            </span>
            <div className="flex gap-1">
              <button onClick={() => setSelectedTools(runnableTools.map(t => t.id))} className="text-xs font-medium text-slate-500 hover:text-slate-700 px-3 py-1.5 rounded-lg hover:bg-slate-50 transition-colors">Select All</button>
              <button onClick={() => setSelectedTools([])} className="text-xs font-medium text-slate-500 hover:text-slate-700 px-3 py-1.5 rounded-lg hover:bg-slate-50 transition-colors">Clear</button>
            </div>
          </div>
        </div>

        <div>
          {error && (
            <div className="mb-5 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 flex items-center gap-2">
              <AlertCircle size={14} className="shrink-0" />{error}
            </div>
          )}

          {loading ? <ToolSkeleton /> : (
            <div className="grid grid-cols-1 md:grid-cols-3 xl:grid-cols-4 gap-3">
              {tools.map(tool => {
                const isSelected = selectedTools.includes(tool.id);
                const canRun = tool.available !== false && tool.runnable !== false;
                return (
                  <button key={tool.id} onClick={() => toggleTool(tool)} disabled={!canRun}
                    className={`relative p-4 rounded-xl border-2 text-left transition-all duration-200 group ${!canRun ? 'border-slate-200 bg-slate-50 opacity-70 cursor-not-allowed' : isSelected ? `border-transparent ring-2 ${tool.ring} ring-offset-2 ${tool.bgLight} scale-[1.02]` : 'border-slate-200 hover:border-slate-300 bg-white hover:shadow-sm hover:-translate-y-0.5'}`}>
                    {isSelected && <div className="absolute top-2 right-2 animate-in zoom-in-50 duration-150"><CheckCircle2 size={16} className={tool.textColor} /></div>}
                    <div className={`w-9 h-9 rounded-lg bg-gradient-to-br ${tool.gradient} flex items-center justify-center mb-3 shadow-sm transition-shadow ${isSelected ? 'shadow-md' : ''}`}>
                      <Zap size={16} className="text-white" />
                    </div>
                    <div className="font-semibold text-sm text-slate-900">{tool.name}</div>
                    <div className={`mt-1 text-[11px] font-semibold ${canRun ? 'text-emerald-600' : 'text-amber-600'}`}>{tool.status || (canRun ? 'Ready to run' : 'Setup needed')}</div>
                    <div className="mt-1 flex flex-wrap gap-1.5">
                      {(tool.engines || []).slice(0, 3).map(engine => (
                        <span key={engine} className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${isSelected ? 'border-current/20 bg-white/70' : 'border-slate-200 bg-slate-50 text-slate-500'}`}>{engine}</span>
                      ))}
                    </div>
                    <div className="text-xs text-slate-400 mt-2 line-clamp-2">{tool.desc}</div>
                  </button>
                );
              })}
            </div>
          )}

          <div className="flex justify-end mt-6">
            <button onClick={onNext} disabled={selectedTools.length === 0 || (isImproveMode && !integrityDeskReady)}
              className="flex items-center gap-2 px-6 py-3 bg-slate-900 hover:bg-slate-800 disabled:bg-slate-200 disabled:text-slate-400 text-white font-semibold rounded-xl transition-all shadow-lg shadow-slate-900/15 hover:shadow-xl disabled:shadow-none">
              Continue to Dataset <ChevronRight size={18} />
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="px-6 py-5 border-b border-slate-100 flex items-center justify-between">
        <h2 className="font-semibold text-slate-900 flex items-center gap-2">
          <Settings2 size={18} className="text-violet-500" />{isImproveMode ? 'IntegrityDesk Benchmark Setup' : 'Select Detection Tools'}
        </h2>
        <div className="flex items-center gap-3">
          <span className={`text-sm font-semibold px-3 py-1.5 rounded-lg transition-all ${selectedTools.length > 0 ? 'bg-violet-50 text-violet-700' : 'bg-slate-100 text-slate-400'}`}>
            {selectedTools.length} / {runnableTools.length} selected
          </span>
          {!isImproveMode && (
            <div className="flex gap-1">
              <button onClick={() => setSelectedTools(runnableTools.map(t => t.id))} className="text-xs font-medium text-slate-500 hover:text-slate-700 px-3 py-1.5 rounded-lg hover:bg-slate-50 transition-colors">Select All</button>
              <button onClick={() => setSelectedTools([])} className="text-xs font-medium text-slate-500 hover:text-slate-700 px-3 py-1.5 rounded-lg hover:bg-slate-50 transition-colors">Clear</button>
            </div>
          )}
        </div>
      </div>

      <div className="p-6">
        {error && (
          <div className="mb-5 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 flex items-center gap-2">
            <AlertCircle size={14} className="shrink-0" />{error}
          </div>
        )}

        {loading ? <ToolSkeleton /> : isImproveMode ? (
          <div className="overflow-hidden rounded-[28px] border border-violet-200 bg-gradient-to-br from-violet-50 via-fuchsia-50 to-rose-50 shadow-[0_24px_80px_-48px_rgba(124,58,237,0.45)]">
            <div className="grid gap-0 lg:grid-cols-[minmax(0,1.2fr)_320px]">
              <div className="p-6 lg:p-7">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="inline-flex items-center gap-2 rounded-full bg-white/80 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-violet-700 shadow-sm">
                      <Zap size={12} />
                      IntegrityDesk Optimization Path
                    </div>
                    <h3 className="mt-4 text-2xl font-bold tracking-tight text-slate-950">IntegrityDesk is the only tool used in this workflow</h3>
                    <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-700">
                      Improve IntegrityDesk is a focused benchmark loop for your own detector. Run labeled tests,
                      inspect per-run F1 / Precision / Recall / FPR, and use the threshold and error analysis to decide what to change next.
                    </p>
                  </div>
                  <div className="rounded-2xl bg-white/85 px-4 py-3 text-right shadow-sm">
                    <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Workflow scope</div>
                    <div className="mt-1 text-sm font-semibold text-slate-900">Locked to IntegrityDesk</div>
                  </div>
                </div>

                <div className="mt-6 grid gap-3 md:grid-cols-3">
                  {[
                    'Get per-run F1, Precision, Recall, and False Positive Rate',
                    'Tune the operating threshold on labeled benchmark data',
                    'Review the misses and false alarms blocking improvement',
                  ].map(item => (
                    <div key={item} className="rounded-2xl border border-white/70 bg-white/80 px-4 py-4 text-sm font-medium leading-6 text-slate-700 shadow-sm">
                      {item}
                    </div>
                  ))}
                </div>

                {!integrityDeskReady && (
                  <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 flex items-start gap-2">
                    <AlertCircle size={14} className="mt-0.5 shrink-0" />
                    IntegrityDesk is not currently available in this environment, so this workflow cannot run yet.
                  </div>
                )}
              </div>

              <div className="border-t border-violet-100/80 bg-slate-950 px-6 py-6 text-slate-100 lg:border-l lg:border-t-0">
                <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-400">Selected engine</div>
                <div className="mt-4 rounded-[24px] border border-white/10 bg-white/5 p-5">
                  <div className="flex items-start gap-3">
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500 to-violet-700 shadow-lg shadow-violet-900/30">
                      <Zap size={18} className="text-white" />
                    </div>
                    <div className="min-w-0">
                      <div className="text-lg font-semibold text-white">IntegrityDesk</div>
                      <div className="mt-1 text-sm leading-6 text-slate-300">
                        {integrityDeskTool?.desc || 'Multi-engine internal detector'}
                      </div>
                    </div>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {(integrityDeskTool?.engines || ['AST', 'Embedding', 'Execution']).slice(0, 5).map(engine => (
                      <span key={engine} className="rounded-full border border-white/10 bg-white/10 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-200">
                        {engine}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="mt-4 rounded-2xl bg-white/5 px-4 py-4 text-sm leading-6 text-slate-300">
                  External tools like MOSS, JPlag, and Dolos are still useful in <span className="font-semibold text-white">Compare Against Other Tools</span>,
                  but they are not part of the IntegrityDesk improvement loop.
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 xl:grid-cols-4 gap-3">
            {tools.map(tool => {
              const isSelected = selectedTools.includes(tool.id);
              const canRun = tool.available !== false && tool.runnable !== false;
              return (
                <button key={tool.id} onClick={() => toggleTool(tool)} disabled={!canRun}
                  className={`relative p-4 rounded-xl border-2 text-left transition-all duration-200 group ${!canRun ? 'border-slate-200 bg-slate-50 opacity-70 cursor-not-allowed' : isSelected ? `border-transparent ring-2 ${tool.ring} ring-offset-2 ${tool.bgLight} scale-[1.02]` : 'border-slate-200 hover:border-slate-300 bg-white hover:shadow-sm hover:-translate-y-0.5'}`}>
                  {isSelected && <div className="absolute top-2 right-2 animate-in zoom-in-50 duration-150"><CheckCircle2 size={16} className={tool.textColor} /></div>}
                  <div className={`w-9 h-9 rounded-lg bg-gradient-to-br ${tool.gradient} flex items-center justify-center mb-3 shadow-sm transition-shadow ${isSelected ? 'shadow-md' : ''}`}>
                    <Zap size={16} className="text-white" />
                  </div>
                  <div className="font-semibold text-sm text-slate-900">{tool.name}</div>
                  <div className={`mt-1 text-[11px] font-semibold ${canRun ? 'text-emerald-600' : 'text-amber-600'}`}>{tool.status || (canRun ? 'Ready to run' : 'Setup needed')}</div>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    {(tool.engines || []).slice(0, 3).map(engine => (
                      <span key={engine} className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${isSelected ? 'border-current/20 bg-white/70' : 'border-slate-200 bg-slate-50 text-slate-500'}`}>{engine}</span>
                    ))}
                  </div>
                  <div className="text-xs text-slate-400 mt-2 line-clamp-2">{tool.desc}</div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      <div className="px-6 pb-6 flex justify-end">
        <button onClick={onNext} disabled={selectedTools.length === 0 || (isImproveMode && !integrityDeskReady)}
          className="flex items-center gap-2 px-6 py-3 bg-slate-900 hover:bg-slate-800 disabled:bg-slate-200 disabled:text-slate-400 text-white font-semibold rounded-xl transition-all shadow-lg shadow-slate-900/15 hover:shadow-xl disabled:shadow-none">
          Continue to Dataset <ChevronRight size={18} />
        </button>
      </div>
    </div>
  );
}

// ── Step 2: Dataset Selection ──────────────────────────────────────────────
function DatasetStep({ selectedDataset, setSelectedDataset, uploadMode, setUploadMode, files, setFiles, benchmarkDatasets, canManageDemoDatasets, onBack, onNext }) {
  const [libraryFilter, setLibraryFilter] = useState('all');
  const [languageFilter, setLanguageFilter] = useState('all');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [creatingDataset, setCreatingDataset] = useState(false);
  const [createError, setCreateError] = useState('');
  const [datasetForm, setDatasetForm] = useState({ name: '', description: '', language: 'python', numFiles: 10, similarityType: 'type1_exact' });

  const handleDatasetFormChange = useCallback((field, value) => setDatasetForm(prev => ({ ...prev, [field]: value })), []);

  const createDemoDataset = async (event) => {
    event.preventDefault();
    setCreatingDataset(true);
    setCreateError('');
    try {
      await axios.post(`${API}/api/admin/create-demo-dataset`, datasetForm, { withCredentials: true });
      setShowCreateModal(false);
      setDatasetForm({ name: '', description: '', language: 'python', numFiles: 10, similarityType: 'type1_exact' });
    } catch (err) {
      setCreateError(err?.response?.data?.error || 'Failed to create dataset. Please try again.');
    } finally {
      setCreatingDataset(false);
    }
  };

  const closeModal = () => { setShowCreateModal(false); setCreateError(''); setDatasetForm({ name: '', description: '', language: 'python', numFiles: 10, similarityType: 'type1_exact' }); };
  const handleDrop = useCallback(e => { e.preventDefault(); setFiles(Array.from(e.dataTransfer.files)); }, [setFiles]);

  const { presetDatasets, demoDatasets, allDatasets } = useMemo(() => buildDatasetLibrary(benchmarkDatasets), [benchmarkDatasets]);
  const availableLanguages = useMemo(() => {
    const langs = new Set(allDatasets.map(d => d.language?.toLowerCase() || 'mixed').filter(Boolean));
    return Array.from(langs).sort();
  }, [allDatasets]);

  const visibleLibraryDatasets = allDatasets.filter(dataset => {
    if (libraryFilter === 'preset') return dataset.datasetType === 'preset';
    if (libraryFilter === 'demo') return dataset.datasetType === 'demo';
    return true;
  }).filter(dataset => {
    if (languageFilter === 'all') return true;
    return dataset.language?.toLowerCase() === languageFilter.toLowerCase();
  });

  const activeDataset = allDatasets.find(d => d.id === selectedDataset);
  const activeDatasetMeta = getDatasetCategoryMeta(activeDataset);
  const activePresetMeta = getPresetDatasetMeta(activeDataset);
  const hasZipUpload = files.some(f => f.name?.toLowerCase().endsWith('.zip'));
  const canProceed = uploadMode === 'builtin' ? !!selectedDataset : hasZipUpload || files.length >= 2;

  return (
    <div className="space-y-5">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-5 border-b border-slate-100">
          <h2 className="font-semibold text-slate-900 flex items-center gap-2"><Database size={18} className="text-violet-500" />Choose What To Benchmark</h2>
          <p className="text-sm text-slate-500 mt-0.5">Select a reusable dataset for tool comparison, or upload your own files.</p>
        </div>

        <div className="flex border-b border-slate-100">
          {[{ id: 'builtin', label: 'Dataset Library', icon: FlaskConical }, { id: 'upload', label: 'Upload Files or ZIP', icon: FileUp }].map(({ id, label, icon: Icon }) => (
            <button key={id} onClick={() => { setUploadMode(id); setFiles([]); if (id !== 'builtin') setSelectedDataset(null); }}
              className={`flex items-center gap-2 px-5 py-3.5 text-sm font-medium border-b-2 transition-colors ${uploadMode === id ? 'border-violet-500 text-violet-700 bg-violet-50/50' : 'border-transparent text-slate-500 hover:text-slate-700'}`}>
              <Icon size={15} />{label}
            </button>
          ))}
        </div>

        <div className="p-6">
          {uploadMode === 'builtin' && (
            <div className="space-y-6">
              <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-5">
                <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
                  <div className="flex items-center gap-1">
                    {[{ id: 'all', label: 'All', count: allDatasets.length }, { id: 'preset', label: 'Preset', count: presetDatasets.length }, { id: 'demo', label: 'Demo', count: demoDatasets.length }].map(filter => (
                      <button key={filter.id} onClick={() => setLibraryFilter(filter.id)}
                        className={`rounded-full px-3 py-1.5 text-xs font-semibold transition ${libraryFilter === filter.id ? 'bg-slate-900 text-white' : 'border border-slate-200 bg-white text-slate-600 hover:border-slate-300'}`}>
                        {filter.label} ({filter.count})
                      </button>
                    ))}
                  </div>
                  {availableLanguages.length > 0 && (
                    <div className="flex items-center gap-1 flex-wrap">
                      <button onClick={() => setLanguageFilter('all')} className={`rounded-full px-3 py-1.5 text-xs font-semibold transition ${languageFilter === 'all' ? 'bg-slate-900 text-white' : 'border border-slate-200 bg-white text-slate-600 hover:border-slate-300'}`}>All Languages</button>
                      {availableLanguages.map(lang => (
                        <button key={lang} onClick={() => setLanguageFilter(lang)} className={`rounded-full px-3 py-1.5 text-xs font-semibold transition capitalize ${languageFilter === lang ? 'bg-slate-900 text-white' : 'border border-slate-200 bg-white text-slate-600 hover:border-slate-300'}`}>{lang}</button>
                      ))}
                    </div>
                  )}
                </div>
                {visibleLibraryDatasets.length > 0 || (libraryFilter === 'demo' && canManageDemoDatasets) ? (
                  <div className="grid gap-4 grid-cols-1 md:grid-cols-2 xl:grid-cols-3">
                    {visibleLibraryDatasets.map(dataset => (
                      <DatasetCard key={dataset.id} dataset={dataset} isActive={selectedDataset === dataset.id} onSelect={setSelectedDataset} />
                    ))}
                    {canManageDemoDatasets && libraryFilter !== 'preset' && (
                      <button onClick={() => setShowCreateModal(true)}
                        className="relative rounded-2xl border-2 border-dashed border-slate-300 p-4 text-left transition-all duration-200 bg-slate-50 hover:border-blue-400 hover:bg-blue-50/70 flex flex-col items-center justify-center min-h-[200px]">
                        <div className="w-12 h-12 rounded-full bg-blue-100 flex items-center justify-center mb-3"><Plus size={24} className="text-blue-600" /></div>
                        <div className="text-base font-semibold text-slate-700">Create Demo Dataset</div>
                        <div className="text-sm text-slate-500 mt-1">Generate a new synthetic benchmark dataset</div>
                      </button>
                    )}
                  </div>
                ) : (
                  <div className="mt-5 rounded-2xl border border-dashed border-slate-300 bg-white px-5 py-6">
                    <div className="text-sm font-semibold text-slate-900">{libraryFilter === 'demo' ? 'No demo datasets yet' : 'No datasets match this filter'}</div>
                    <div className="mt-2 text-sm leading-6 text-slate-500">{libraryFilter === 'demo' ? 'Preset datasets are ready to use now.' : 'Try another filter or switch to Upload Your Own.'}</div>
                  </div>
                )}
              </div>

              {activeDataset && activeDatasetMeta && (
                <div className={`rounded-2xl border p-5 ${activeDatasetMeta.panelClass}`}>
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Selected dataset</p>
                      <div className="mt-2 flex items-center gap-3">
                        <span className="text-2xl">{activeDataset.icon}</span>
                        <div>
                          <div className="text-lg font-semibold text-slate-900">{activeDataset.name}</div>
                          <div className="text-sm text-slate-600">{activePresetMeta?.presetCategory || activeDatasetMeta.label}</div>
                        </div>
                      </div>
                    </div>
                    <span className={`rounded-full px-3 py-1 text-xs font-semibold ${activeDatasetMeta.badgeClass}`}>{activePresetMeta?.badgeLabel || activeDatasetMeta.summaryLabel}</span>
                  </div>
                  <div className="mt-4 text-sm leading-6 text-slate-600">{activeDataset.desc}</div>
                  {activePresetMeta?.summary && <div className="mt-3 text-sm text-slate-500">{activePresetMeta.summary}</div>}

                  {activeDataset.benchmark_quality && (
                    <div className="mt-4 rounded-2xl border border-emerald-200 bg-white p-4">
                      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                        <div>
                          <div className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-600">Benchmark Quality Certificate</div>
                          <div className="mt-2 text-sm leading-6 text-slate-600">{activeDataset.benchmark_quality.pair_count} labeled pairs, {activeDataset.benchmark_quality.positive_pairs} positives, {activeDataset.benchmark_quality.negative_pairs} negatives, {activeDataset.benchmark_quality.hard_negative_pairs} hard negatives.</div>
                        </div>
                        <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700">{Number(activeDataset.benchmark_quality.score_percent || 0).toFixed(0)}% gates passed</span>
                      </div>
                      <div className="mt-3 grid gap-2 md:grid-cols-2">
                        {(activeDataset.benchmark_quality.gates || []).map(gate => (
                          <div key={gate.id} className="flex items-start gap-2 rounded-xl bg-slate-50 px-3 py-2.5">
                            <CheckCircle2 size={15} className={gate.passed ? 'mt-0.5 shrink-0 text-emerald-600' : 'mt-0.5 shrink-0 text-amber-600'} />
                            <div className="min-w-0">
                              <div className="text-xs font-semibold text-slate-800">{gate.label}</div>
                              <div className="text-xs leading-5 text-slate-500">{gate.value} · {gate.target}</div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {activeDataset.cases ? (
                    <div className="mt-5 grid md:grid-cols-3 gap-2">
                      {activeDataset.cases.map(tc => (
                        <div key={tc.id} className="flex items-center gap-2 bg-white rounded-lg border border-slate-200 px-3 py-2.5">
                          <div className={`w-2 h-2 rounded-full shrink-0 ${tc.expected >= 0.9 ? 'bg-red-500' : tc.expected >= 0.7 ? 'bg-amber-500' : tc.expected >= 0.4 ? 'bg-yellow-500' : 'bg-emerald-500'}`} />
                          <div className="min-w-0">
                            <div className="text-xs font-semibold text-slate-800 truncate">{tc.label}</div>
                            <div className="text-xs text-slate-400">~{(tc.expected * 100).toFixed(0)}% expected</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="mt-5 grid grid-cols-2 md:grid-cols-4 gap-3">
                      {[
                        { label: 'Language', value: activeDataset.language || 'Mixed' },
                        { label: activeDataset.is_demo ? 'Files' : 'Size', value: activeDataset.size || 'Unknown' },
                        { label: activeDataset.is_demo ? 'Created' : 'Use', value: activeDataset.is_demo ? formatDatasetDate(activeDataset.created_at) : (activePresetMeta?.presetCategory || activeDataset.similarity_type || 'Standard') },
                        { label: activeDataset.is_demo ? 'Created By' : 'Source', value: activeDataset.created_by || 'System' },
                      ].map(({ label, value }) => (
                        <div key={label} className="bg-white rounded-lg border border-slate-200 px-3 py-2.5 text-center">
                          <div className={`text-lg font-bold ${activeDatasetMeta.accentClass}`}>{value}</div>
                          <div className="text-xs text-slate-500">{label}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {uploadMode === 'upload' && (
            <div>
              <div onDrop={handleDrop} onDragOver={e => e.preventDefault()} onClick={() => document.getElementById('file-input').click()}
                className="border-2 border-dashed border-slate-300 rounded-2xl p-10 text-center cursor-pointer hover:border-violet-400 hover:bg-violet-50/30 transition-all group">
                <input id="file-input" type="file" className="hidden" multiple
                  accept=".zip,.py,.java,.c,.cpp,.h,.hpp,.js,.ts,.jsx,.tsx,.go,.rs,.rb,.php,.cs,.kt,.swift,.scala,.r,.m,.sql,.sh,.bash"
                  onChange={e => setFiles(Array.from(e.target.files))} />
                <UploadCloud size={40} className="mx-auto text-slate-300 group-hover:text-violet-400 transition-colors mb-4" />
                <p className="font-semibold text-slate-600 mb-1">Drop source files or a ZIP archive here</p>
                <p className="text-sm text-slate-400">Upload 2 or more source files, or a single ZIP for one-off comparison</p>
                <div className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm text-slate-600 group-hover:border-violet-300 transition-colors">
                  <FileUp size={14} />Browse files
                </div>
              </div>
              {files.length > 0 && (
                <div className="mt-4 bg-slate-50 rounded-xl border border-slate-200 divide-y divide-slate-100 overflow-hidden">
                  {files.map((f, i) => (
                    <div key={i} className="flex items-center gap-3 px-4 py-2.5 group/file hover:bg-white transition-colors">
                      <div className="w-6 h-6 rounded-md bg-emerald-100 flex items-center justify-center shrink-0"><FileUp size={12} className="text-emerald-600" /></div>
                      <span className="text-sm font-medium text-slate-700 truncate flex-1">{f.name}</span>
                      <span className="text-xs text-slate-400 shrink-0">{(f.size / 1024).toFixed(1)} KB</span>
                      <button onClick={() => setFiles(files.filter((_, j) => j !== i))} className="opacity-0 group-hover/file:opacity-100 text-slate-300 hover:text-red-500 transition-all"><X size={14} /></button>
                    </div>
                  ))}
                </div>
              )}
              {files.length === 1 && !hasZipUpload && (
                <p className="text-xs text-amber-600 mt-2 flex items-center gap-1.5"><AlertCircle size={13} /> Upload at least 2 source files, or use a ZIP archive</p>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center justify-between">
        <button onClick={onBack} className="flex items-center gap-2 px-5 py-2.5 bg-white border border-slate-200 text-slate-600 hover:text-slate-800 font-medium rounded-xl hover:border-slate-300 transition-all text-sm">← Back</button>
        <button onClick={onNext} disabled={!canProceed}
          className="flex items-center gap-2 px-6 py-3 bg-slate-900 hover:bg-slate-800 disabled:bg-slate-200 disabled:text-slate-400 text-white font-semibold rounded-xl transition-all shadow-lg shadow-slate-900/15 hover:shadow-xl disabled:shadow-none">
          <Play size={18} />Start Benchmark
        </button>
      </div>

      {/* Create Demo Dataset Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-[30px] shadow-2xl max-w-3xl w-full p-8 animate-in zoom-in-95 fade-in duration-200">
            <div className="flex items-start justify-between mb-6">
              <div>
                <div className="inline-flex items-center gap-2 rounded-full border border-emerald-600/10 bg-emerald-600/[0.06] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-emerald-600 mb-3">
                  <Database size={14} />Dataset Tools
                </div>
                <h3 className="text-2xl font-semibold text-slate-900">Demo dataset creation</h3>
                <p className="mt-2 text-sm text-slate-600 max-w-xl">Generate synthetic datasets with controlled similarity patterns for testing.</p>
              </div>
              <button onClick={closeModal} className="p-2 hover:bg-slate-100 rounded-xl transition text-slate-500">✕</button>
            </div>
            {createError && (
              <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 flex items-center gap-2">
                <AlertCircle size={14} className="shrink-0" />{createError}
              </div>
            )}
            <form className="space-y-6 mt-2" onSubmit={createDemoDataset}>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Dataset Name</label>
                  <input type="text" value={datasetForm.name} onChange={e => handleDatasetFormChange('name', e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                    placeholder="my_test_dataset" required />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Programming Language</label>
                  <select value={datasetForm.language} onChange={e => handleDatasetFormChange('language', e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500">
                    <option value="python">Python</option><option value="java">Java</option>
                    <option value="javascript">JavaScript</option><option value="cpp">C++</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Description</label>
                <input type="text" value={datasetForm.description} onChange={e => handleDatasetFormChange('description', e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                  placeholder="Dataset for testing plagiarism detection" />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Number of Files</label>
                  <input type="number" min="5" max="100" value={datasetForm.numFiles} onChange={e => handleDatasetFormChange('numFiles', parseInt(e.target.value) || 10)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Similarity Type</label>
                  <select value={datasetForm.similarityType} onChange={e => handleDatasetFormChange('similarityType', e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500">
                    <option value="type1_exact">Type 1 — Exact Copy</option>
                    <option value="type2_renamed">Type 2 — Renamed Identifiers</option>
                    <option value="type3_modified">Type 3 — Modified Structure</option>
                    <option value="type4_semantic">Type 4 — Semantic Equivalence</option>
                    <option value="token_similarity">Token-Level Similarity</option>
                    <option value="structural_similarity">Structural Similarity</option>
                    <option value="semantic_similarity">Semantic Similarity</option>
                  </select>
                </div>
              </div>
              <div className="mt-8 flex justify-end gap-3">
                <button type="button" onClick={closeModal} className="px-5 py-3 text-slate-700 hover:bg-slate-100 rounded-xl transition font-medium">Cancel</button>
                <button type="submit" disabled={creatingDataset || !datasetForm.name.trim()}
                  className="px-8 py-3 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 text-white rounded-xl transition flex items-center gap-3 font-semibold min-w-[200px] justify-center">
                  {creatingDataset ? (<><Loader2 size={18} className="animate-spin" />Generating…</>) : 'Create Demo Dataset'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Step 3: Run ────────────────────────────────────────────────────────────
function RunStep({ selectedTools, selectedDataset, uploadMode, files, benchmarkDatasets, selectedPreset, benchmarkMode, autoStart = false, onBack, onComplete }) {
  const { token } = useAuth();
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState('');
  const [progressPct, setProgressPct] = useState(0);
  const [error, setError] = useState('');
  const requestControllerRef = useRef(null);
  const autoStartedRef = useRef(false);

  const { allDatasets } = useMemo(() => buildDatasetLibrary(benchmarkDatasets), [benchmarkDatasets]);
  const activeDataset = allDatasets.find(d => d.id === selectedDataset);
  const activeDatasetMeta = activeDataset ? getDatasetCategoryMeta(activeDataset) : null;
  const hasZipUpload = files.some(f => f.name?.toLowerCase().endsWith('.zip'));
  const benchmarkType = benchmarkMode === 'development' || benchmarkMode === 'calibration'
    ? 'pan_optimization'
    : 'tool_comparison';

  const run = async () => {
    requestControllerRef.current?.abort();
    const controller = new AbortController();
    requestControllerRef.current = controller;
    setError(''); setRunning(true); setProgressPct(10);
    try {
      if (uploadMode === 'builtin' && activeDataset) {
        if (activeDataset.cases) {
          const allResults = [];
          const cases = activeDataset.cases;
          for (let i = 0; i < cases.length; i++) {
            const tc = cases[i];
            setProgress(`Running "${tc.label}" (${i + 1}/${cases.length})…`);
            setProgressPct(10 + (i / cases.length) * 80);
            const blobA = new Blob([tc.codeA], { type: 'text/plain' });
            const blobB = new Blob([tc.codeB], { type: 'text/plain' });
            const formData = new FormData();
            formData.append('files', new File([blobA], `${tc.id}_a.py`));
            formData.append('files', new File([blobB], `${tc.id}_b.py`));
            formData.append('benchmark_type', benchmarkType);
            if (selectedPreset?.id) formData.append('preset_id', selectedPreset.id);
            selectedTools.forEach(t => formData.append('tools', t));
            try {
              const res = await axios.post(`${API}/api/benchmark`, formData, { withCredentials: true, signal: controller.signal });
              allResults.push({ testCase: tc, ...res.data });
            } catch (err) { if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') break; }
          }
          if (allResults.length > 0) {
            setProgressPct(100); setProgress('Complete!');
            const merged = { ...allResults[0], pair_results: allResults.flatMap(r => r.pair_results || []) };
            setTimeout(() => onComplete({ ...merged, datasetName: activeDataset.name, runAt: new Date().toISOString() }), 400);
          }
        } else {
          setProgress('Loading dataset…'); setProgressPct(30);
          const formData = new FormData();
          selectedTools.forEach(t => formData.append('tools', t));
          formData.append('dataset', activeDataset.id);
          formData.append('benchmark_type', benchmarkType);
          if (selectedPreset?.id) formData.append('preset_id', selectedPreset.id);
          setProgress(benchmarkType === 'pan_optimization' ? 'Running IntegrityDesk benchmark…' : 'Running multi-tool comparison…');
          setProgressPct(50);
          const res = await axios.post(`${API}/api/benchmark`, formData, { withCredentials: true, signal: controller.signal });
          setProgressPct(100); setProgress('Complete!');
          onComplete({ ...res.data, datasetName: activeDataset.name, runAt: new Date().toISOString() });
        }
      } else {
        setProgress('Uploading files…'); setProgressPct(20);
        const formData = new FormData();
        files.forEach(f => formData.append('files', f));
        formData.append('benchmark_type', benchmarkType);
        if (selectedPreset?.id) formData.append('preset_id', selectedPreset.id);
        selectedTools.forEach(t => formData.append('tools', t));
        setProgress(benchmarkType === 'pan_optimization' ? 'Running IntegrityDesk benchmark…' : 'Running analysis across all selected tools…');
        setProgressPct(50);
        const res = await axios.post(`${API}/api/benchmark`, formData, { withCredentials: true, signal: controller.signal });
        setProgressPct(100); setProgress('Complete!');
        setTimeout(() => onComplete({ ...res.data, runAt: new Date().toISOString() }), 400);
      }
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') setProgress('Run cancelled');
      else setError(err.response?.data?.error || err.message || 'Benchmark failed. Please try again.');
    } finally {
      if (requestControllerRef.current === controller) requestControllerRef.current = null;
      setRunning(false);
    }
  };

  useEffect(() => {
    if (!autoStart || autoStartedRef.current) return;
    autoStartedRef.current = true;
    const timer = window.setTimeout(() => run(), 0);
    return () => window.clearTimeout(timer);
  }, [autoStart]);

  useEffect(() => {
    return () => requestControllerRef.current?.abort();
  }, []);

  const stop = () => { requestControllerRef.current?.abort(); setRunning(false); setProgress('Cancelling run…'); setProgressPct(0); };

  return (
    <div className="space-y-5">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <h2 className="font-semibold text-slate-900 flex items-center gap-2 mb-5"><ClipboardList size={18} className="text-violet-500" />Benchmark Configuration</h2>
        <div className="grid md:grid-cols-2 gap-4">
          <div className="bg-slate-50 rounded-xl p-4 border border-slate-100">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Tools</p>
            <div className="flex flex-wrap gap-1.5">
              {selectedTools.slice(0, 6).map(id => { const t = TOOLS.find(x => x.id === id); return t ? <span key={id} className={`text-xs font-medium px-2.5 py-1 rounded-lg ${t.bgLight} ${t.textColor}`}>{t.name}</span> : null; })}
              {selectedTools.length > 6 && <span className="text-xs font-medium px-2.5 py-1 rounded-lg bg-slate-200 text-slate-600">+{selectedTools.length - 6} more</span>}
            </div>
          </div>
          <div className="bg-slate-50 rounded-xl p-4 border border-slate-100">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Dataset</p>
            {uploadMode === 'builtin' ? (
              <><p className="font-semibold text-slate-800 text-sm">{activeDataset?.name || 'Unknown'}</p><p className="text-xs text-slate-500 mt-1">{activeDataset?.cases?.length ? `${activeDataset.cases.length} guided scenarios` : activeDatasetMeta?.label || 'Dataset library'}</p></>
            ) : (
              <><p className="font-semibold text-slate-800 text-sm">{files.length} uploaded file{files.length !== 1 ? 's' : ''}</p><p className="text-xs text-slate-500 mt-1">{hasZipUpload ? 'ZIP archive' : 'Direct file upload'}</p></>
            )}
          </div>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        {error && (
          <div className="mb-4 flex items-start gap-3 p-4 bg-red-50 border border-red-100 rounded-xl">
            <AlertCircle size={18} className="text-red-500 mt-0.5 shrink-0" />
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}
        {running && (
          <div className="mb-5">
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-medium text-slate-700 flex items-center gap-2"><Loader2 size={15} className="text-violet-600 animate-spin" />{progress}</p>
              <span className="text-sm font-bold text-violet-600">{Math.round(progressPct)}%</span>
            </div>
            <div className="h-2.5 bg-slate-100 rounded-full overflow-hidden">
              <div className="h-full bg-gradient-to-r from-violet-500 to-blue-500 rounded-full transition-all duration-500" style={{ width: `${progressPct}%` }} />
            </div>
          </div>
        )}
        <div className="flex items-center gap-3">
          {!running ? (
            <button onClick={run} className="flex-1 flex items-center justify-center gap-3 py-4 bg-slate-900 hover:bg-slate-800 text-white font-bold rounded-xl transition-all shadow-lg shadow-slate-900/15 hover:shadow-xl text-base">
              <Play size={20} />Run Again
            </button>
          ) : (
            <button onClick={stop} className="flex-1 flex items-center justify-center gap-3 py-4 bg-red-500 hover:bg-red-600 text-white font-bold rounded-xl transition-all shadow-lg shadow-red-500/25 text-base">
              <Square size={18} />Stop
            </button>
          )}
        </div>
      </div>

      <div className="flex items-center justify-between">
        <button onClick={onBack} disabled={running} className="flex items-center gap-2 px-5 py-2.5 bg-white border border-slate-200 text-slate-600 hover:text-slate-800 font-medium rounded-xl hover:border-slate-300 transition-all text-sm disabled:opacity-50">← Back</button>
      </div>
    </div>
  );
}

// ── Step 4: Report ─────────────────────────────────────────────────────────
function ReportStep({ results, onRestart, benchmarkMode }) {
  const [expandedPairs, setExpandedPairs] = useState({});
  const [currentPage, setCurrentPage] = useState(1);
  const [pdfDownloading, setPdfDownloading] = useState(false);
  const [pdfError, setPdfError] = useState('');

  const { tool_scores, pair_results } = results;
  const itemsPerPage = 50;
  const totalPairs = (pair_results || []).length;
  const totalPages = Math.max(1, Math.ceil(totalPairs / itemsPerPage));
  const pageStart = (currentPage - 1) * itemsPerPage;
  const pageEnd = Math.min(pageStart + itemsPerPage, totalPairs);
  const visiblePairResults = (pair_results || []).slice(pageStart, pageEnd);

  const activeTools = Object.keys(tool_scores || {}).length
    ? Object.keys(tool_scores || {})
    : Array.from(new Set((pair_results || []).flatMap(pair => (pair.tool_results || []).map(e => e.tool))));

  const chartData = (pair_results || []).map(pair => {
    const d = { pair: pair.label };
    activeTools.forEach(t => { const tr = pair.tool_results?.find(r => r.tool === t); d[t] = tr ? Math.round(tr.score * 1000) / 10 : 0; });
    return d;
  });

  const panEvaluationRows = Object.entries(results.evaluation || {})
    .filter(([, metrics]) => metrics && !metrics.error)
    .map(([toolId, metrics]) => {
      const toolInfo = TOOLS.find(t => t.id === toolId);
      const toolScoreMeta = results.tool_scores?.[toolId] || {};
      const f1Score = metrics.f1_score ?? metrics.best_f1 ?? 0;
      const plagdet = metrics.plagdet ?? f1Score;
      return {
        toolId, name: toolInfo?.name || metrics.tool || toolId,
        precision: Number(metrics.precision || 0), recall: Number(metrics.recall || 0),
        f1Score: Number(f1Score || 0), granularity: Number(metrics.granularity || 1),
        plagdet: Number(plagdet || 0), aucPr: Number(metrics.auc_pr ?? metrics.pr_auc ?? 0),
        falsePositiveRate: Number(metrics.false_positive_rate || 0),
        top10Retrieval: Number(metrics.top_10_retrieval || 0), top20Retrieval: Number(metrics.top_20_retrieval || 0),
        avgRuntimeSeconds: Number(metrics.avg_runtime_seconds ?? toolScoreMeta.avg_runtime_seconds ?? 0),
        nPositives: Number(metrics.n_positives || 0), nNegatives: Number(metrics.n_negatives || 0),
        engineContribution: metrics.engine_contribution || {},
        engineContributionText: formatEngineContribution(metrics.engine_contribution || {}),
        scoreDiagnostics: metrics.score_diagnostics || {}, threshold: metrics.best_threshold,
        fixedThreshold: metrics.fixed_threshold, fixedThresholdMetrics: metrics.fixed_threshold_metrics || {},
        confidenceIntervals: metrics.confidence_intervals || {}, splitProtocol: metrics.split_protocol || {},
        metricIntegrity: metrics.metric_integrity || {},
      };
    }).sort((a, b) => b.plagdet - a.plagdet);

  const topPanResult = panEvaluationRows[0] || null;
  const integrityDeskPanResult = panEvaluationRows.find(r => r.toolId === 'integritydesk') || null;
  const productPanResult = integrityDeskPanResult || topPanResult;
  const panFeedback = buildPanFeedback(productPanResult);
  const panMetricDiagnostics = buildPanMetricDiagnostics(productPanResult);
  const isCalibrationReport = benchmarkMode === 'development' || benchmarkMode === 'calibration' || results.protocol === 'development_evaluation' || results.benchmark_type === 'pan_optimization' || results.benchmarkMode === 'pan_optimization' || results.benchmark_goal === 'admin_pan_optimization';
  const isRegressionReport = benchmarkMode === 'release' || benchmarkMode === 'regression' || results.protocol === 'release_check' || results.benchmark_type === 'regression_test' || results.benchmark_goal === 'locked_regression_test';
  const isFocusedMetricReport = isCalibrationReport || isRegressionReport;
  const isComparisonReport = !isFocusedMetricReport;

  const toolFailureRows = Object.entries(results.tool_scores || {}).filter(([, meta]) => meta?.error).map(([toolId, meta]) => ({ toolId, name: TOOLS.find(t => t.id === toolId)?.name || toolId, error: String(meta.error || 'Tool did not return scores.') }));

  const comparison = results.comparison || {};
  const comparisonDeltas = comparison.metrics || {};
  const qualityGates = results.quality_gates || null;

  const pairKey = (pair, idx) => `${pair.file_a || 'a'}::${pair.file_b || 'b'}::${pair.label || idx}`;
  const togglePair = (key) => setExpandedPairs(prev => ({ ...prev, [key]: !prev[key] }));

  const downloadJSON = () => {
    const blob = new Blob([JSON.stringify(results, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = `benchmark-report-${new Date().toISOString().slice(0, 10)}.json`; a.click(); URL.revokeObjectURL(url);
  };

  const downloadCSV = () => {
    const rows = [['Pair', 'File A', 'File B', ...activeTools.map(id => TOOLS.find(t => t.id === id)?.name || id), 'Max', 'Min']];
    (pair_results || []).forEach(pair => {
      const scores = activeTools.map(t => { const tr = pair.tool_results?.find(r => r.tool === t); return tr ? (tr.score * 100).toFixed(1) : 'N/A'; });
      const numScores = scores.filter(s => s !== 'N/A').map(Number);
      rows.push([pair.label, pair.file_a || '', pair.file_b || '', ...scores, numScores.length ? Math.max(...numScores).toFixed(1) : 'N/A', numScores.length ? Math.min(...numScores).toFixed(1) : 'N/A']);
    });
    const csv = rows.map(r => r.map(c => `"${c}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = `benchmark-report-${new Date().toISOString().slice(0, 10)}.csv`; a.click(); URL.revokeObjectURL(url);
  };

  const downloadPDF = async () => {
    try {
      setPdfDownloading(true); setPdfError('');
      const res = await axios.post(`${API}/api/benchmark/export-pdf`, results, { responseType: 'blob', withCredentials: true });
      const blob = new Blob([res.data], { type: res.headers['content-type'] || 'application/pdf' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = url; a.download = `benchmark-report-${new Date().toISOString().slice(0, 10)}.pdf`; a.click(); URL.revokeObjectURL(url);
    } catch { setPdfError('Could not export the benchmark report as PDF. Please try again.'); }
    finally { setPdfDownloading(false); }
  };

  const metricIntegrity = productPanResult?.metricIntegrity || {};
  const fixedThresholdMetrics = productPanResult?.fixedThresholdMetrics || {};
  const confidenceIntervals = productPanResult?.confidenceIntervals || {};
  const splitProtocol = productPanResult?.splitProtocol || {};
  const metricWarnings = metricIntegrity.warnings || [];
  const decisionThreshold = Number(productPanResult?.threshold ?? productPanResult?.fixedThreshold ?? 0.5);
  const labeledPairAudit = (pair_results || [])
    .map((pair) => {
      if (pair.ground_truth_label === undefined || pair.ground_truth_label === null) return null;
      const toolResult = (pair.tool_results || []).find(tr => tr.tool === productPanResult?.toolId);
      if (!toolResult || typeof toolResult.score !== 'number') return null;
      const actual = Number(pair.ground_truth_label) >= 2;
      const predicted = Number(toolResult.score) >= decisionThreshold;
      return { ...pair, score: Number(toolResult.score), actual, predicted };
    })
    .filter(Boolean);
  const localConfusion = labeledPairAudit.reduce((acc, pair) => {
    if (pair.actual && pair.predicted) acc.tp += 1;
    else if (!pair.actual && pair.predicted) acc.fp += 1;
    else if (!pair.actual && !pair.predicted) acc.tn += 1;
    else acc.fn += 1;
    return acc;
  }, { tp: 0, fp: 0, tn: 0, fn: 0 });
  const heldoutConfusion = metricIntegrity.heldout_confusion_matrix || {};
  const confusion = labeledPairAudit.length ? localConfusion : {
    tp: Number(heldoutConfusion.tp || 0),
    fp: Number(heldoutConfusion.fp || 0),
    tn: Number(heldoutConfusion.tn || 0),
    fn: Number(heldoutConfusion.fn || 0),
  };
  const falsePositiveExamples = labeledPairAudit.filter(pair => !pair.actual && pair.predicted).sort((a, b) => b.score - a.score).slice(0, 3);
  const falseNegativeExamples = labeledPairAudit.filter(pair => pair.actual && !pair.predicted).sort((a, b) => a.score - b.score).slice(0, 3);
  const heldoutSize = Number(splitProtocol.holdout_size || 0);
  const hasHoldout = splitProtocol.protocol === 'deterministic_stratified_calibration_holdout';
  const hasConfidenceInterval = Boolean(confidenceIntervals.available && confidenceIntervals.f1);
  const trustLevel = hasHoldout && hasConfidenceInterval && heldoutSize >= 20
    ? { label: 'Strong', className: 'bg-emerald-100 text-emerald-700', description: 'Held-out labels and confidence intervals are available.' }
    : hasHoldout
      ? { label: 'Moderate', className: 'bg-amber-100 text-amber-700', description: 'Held-out labels are used, but the sample is small or intervals are unavailable.' }
      : { label: 'Limited', className: 'bg-rose-100 text-rose-700', description: 'No separate holdout was available; treat this as a smoke test, not a certification.' };

  return (
    <div className="space-y-6">
      {/* Report header */}
      <div className="bg-gradient-to-r from-slate-900 to-slate-800 rounded-2xl p-5 flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center"><FileText size={20} className="text-white" /></div>
          <div>
            <p className="font-bold text-white">{results.datasetName || 'Benchmark'} {isRegressionReport ? 'Release Check Report' : isCalibrationReport ? 'IntegrityDesk Improvement Report' : 'Tool Comparison Report'}</p>
            <p className="text-sm text-slate-400 mt-0.5">Generated {results.runAt ? new Date(results.runAt).toLocaleString() : 'just now'}</p>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button onClick={downloadPDF} disabled={pdfDownloading}
            className="flex items-center gap-2 px-4 py-2.5 bg-white hover:bg-slate-100 disabled:bg-white/50 text-slate-900 font-semibold rounded-xl transition-all text-sm">
            <Download size={15} />{pdfDownloading ? 'Preparing…' : 'PDF'}
          </button>
          <button onClick={downloadCSV} className="flex items-center gap-2 px-4 py-2.5 bg-white/10 hover:bg-white/20 border border-white/20 text-white font-semibold rounded-xl transition-all text-sm"><Download size={15} />CSV</button>
          <button onClick={downloadJSON} className="flex items-center gap-2 px-4 py-2.5 bg-white/10 hover:bg-white/20 border border-white/20 text-white font-semibold rounded-xl transition-all text-sm"><Download size={15} />JSON</button>
          <button onClick={onRestart} className="flex items-center gap-2 px-4 py-2.5 bg-white/10 hover:bg-white/20 border border-white/20 text-white font-semibold rounded-xl transition-all text-sm">New Benchmark</button>
        </div>
      </div>

      {pdfError && <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 flex items-center gap-2"><AlertCircle size={14} className="shrink-0" />{pdfError}</div>}

      {/* Comparison delta banner */}
      {false && comparison.has_previous && (
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Compared With Previous Run</div>
              <div className="mt-1 text-sm text-slate-600">Previous job {comparison.previous_job_id} · {comparison.previous_run_at ? new Date(comparison.previous_run_at).toLocaleString() : 'earlier run'}</div>
            </div>
            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">Same workflow/dataset</span>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {[['Precision', 'precision', false], ['F1 Score', 'f1_score', false], ['PlagDet', 'plagdet', false], ['False Positive Rate', 'false_positive_rate', true]].map(([label, key, lowerIsBetter]) => (
              <div key={key} className="rounded-xl border border-slate-100 bg-slate-50 p-4">
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</div>
                <div className={`mt-2 inline-flex rounded-full px-2.5 py-1 text-sm font-bold ${deltaTone(comparisonDeltas[key], lowerIsBetter)}`}>{formatDelta(comparisonDeltas[key], lowerIsBetter)}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tool failure warnings */}
      {!isComparisonReport && toolFailureRows.length > 0 && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm leading-6 text-amber-800">
          <div className="font-semibold text-amber-900 mb-2">Some tools did not return scores:</div>
          {toolFailureRows.map(f => <div key={f.toolId}><span className="font-semibold">{f.name}:</span> {f.error}</div>)}
        </div>
      )}

      {isRegressionReport && qualityGates && (
        <div className={`rounded-2xl border p-5 shadow-sm ${qualityGates.passed ? 'border-emerald-200 bg-emerald-50' : 'border-red-200 bg-red-50'}`}>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className={`font-semibold ${qualityGates.passed ? 'text-emerald-900' : 'text-red-900'}`}>Regression Quality Gates</h2>
              <p className={`mt-1 text-sm ${qualityGates.passed ? 'text-emerald-700' : 'text-red-700'}`}>{qualityGates.summary}</p>
            </div>
            <span className={`rounded-full px-3 py-1 text-xs font-bold ${qualityGates.passed ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'}`}>{qualityGates.passed ? 'PASS' : 'FAIL'}</span>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {(qualityGates.gates || []).map(gate => (
              <div key={gate.metric} className="rounded-xl border border-white/70 bg-white/80 p-4">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">{gate.label}</div>
                  <span className={`rounded-full px-2 py-0.5 text-[11px] font-bold ${gate.passed ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'}`}>{gate.passed ? 'Pass' : 'Fail'}</span>
                </div>
                <div className="mt-2 text-2xl font-bold text-slate-900">{formatPanMetricValue({ value: gate.value })}</div>
                <div className="mt-1 text-xs text-slate-500">{gate.direction === 'min' ? 'Minimum' : 'Maximum'} {formatPanMetricValue({ value: gate.threshold })}</div>
                <div className="mt-3 text-xs leading-5 text-slate-500">{gate.reason}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* PAN scorecard */}
      {isFocusedMetricReport && productPanResult && (
        <div className="space-y-6">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-6 py-5 border-b border-slate-100">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <h2 className="font-semibold text-slate-900">Score Trust & Error Audit</h2>
                  <p className="text-sm text-slate-500 mt-0.5">Why the PAN numbers are credible, and where they should not be overclaimed.</p>
                </div>
                <span className={`w-fit rounded-full px-3 py-1 text-xs font-bold ${trustLevel.className}`}>{trustLevel.label} trust</span>
              </div>
            </div>
            <div className="grid gap-4 p-6 lg:grid-cols-4">
              <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Protocol</div>
                <div className="mt-3 text-sm font-semibold text-slate-900">{hasHoldout ? 'Stratified holdout' : 'Fallback evaluation'}</div>
                <p className="mt-2 text-sm leading-6 text-slate-600">{trustLevel.description}</p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Held-Out Labels</div>
                <div className="mt-3 text-sm leading-6 text-slate-600">{splitProtocol.holdout_positive_pairs ?? metricIntegrity.positive_pairs ?? productPanResult.nPositives ?? 0} positive pairs and {splitProtocol.holdout_negative_pairs ?? metricIntegrity.negative_pairs ?? productPanResult.nNegatives ?? 0} negative pairs.</div>
                <div className="mt-2 text-xs font-semibold text-slate-500">Total evaluated: {heldoutSize || ((confusion.tp || 0) + (confusion.fp || 0) + (confusion.tn || 0) + (confusion.fn || 0))}</div>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Threshold</div>
                <div className="mt-3 text-2xl font-bold text-slate-900">{Number.isFinite(decisionThreshold) ? decisionThreshold.toFixed(2) : 'N/A'}</div>
                <div className="mt-2 text-xs leading-5 text-slate-500">Fixed {formatMetric(productPanResult.fixedThreshold ?? productPanResult.fixed_threshold ?? 0.82)} F1: {formatMetric(metricIntegrity.fixed_threshold_f1 ?? fixedThresholdMetrics.f1_score)}. Held-out F1: {formatMetric(metricIntegrity.heldout_f1 ?? productPanResult.f1Score)}.</div>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Confidence</div>
                <div className="mt-3 text-sm font-semibold text-slate-900">{hasConfidenceInterval ? 'Bootstrap CI available' : 'CI unavailable'}</div>
                <div className="mt-2 text-xs leading-5 text-slate-500">{hasConfidenceInterval ? `95% F1 CI: ${formatMetric(confidenceIntervals.f1.ci_lower)}-${formatMetric(confidenceIntervals.f1.ci_upper)}.` : 'Use a larger labeled holdout to narrow uncertainty.'}</div>
              </div>
            </div>

            <div className="border-t border-slate-100 px-6 py-5">
              <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
                <div className="rounded-2xl border border-slate-200 overflow-hidden">
                  <div className="grid grid-cols-2 border-b border-slate-200 bg-slate-50 text-center text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                    <div className="p-3 border-r border-slate-200">Actual Positive</div>
                    <div className="p-3">Actual Negative</div>
                  </div>
                  <div className="grid grid-cols-2 text-center">
                    <div className="p-4 border-r border-b border-slate-200">
                      <div className="text-xs text-slate-500">True Positives</div>
                      <div className="mt-1 text-2xl font-bold text-emerald-600">{confusion.tp || 0}</div>
                    </div>
                    <div className="p-4 border-b border-slate-200">
                      <div className="text-xs text-slate-500">False Positives</div>
                      <div className="mt-1 text-2xl font-bold text-rose-600">{confusion.fp || 0}</div>
                    </div>
                    <div className="p-4 border-r border-slate-200">
                      <div className="text-xs text-slate-500">False Negatives</div>
                      <div className="mt-1 text-2xl font-bold text-amber-600">{confusion.fn || 0}</div>
                    </div>
                    <div className="p-4">
                      <div className="text-xs text-slate-500">True Negatives</div>
                      <div className="mt-1 text-2xl font-bold text-slate-700">{confusion.tn || 0}</div>
                    </div>
                  </div>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="rounded-2xl border border-rose-200 bg-rose-50/60 p-4">
                    <div className="font-semibold text-rose-900">False positives to inspect</div>
                    <p className="mt-1 text-xs leading-5 text-rose-700">Clean pairs scoring above threshold reduce precision.</p>
                    <div className="mt-3 space-y-2">
                      {falsePositiveExamples.length ? falsePositiveExamples.map(pair => (
                        <div key={`${pair.file_a}-${pair.file_b}`} className="rounded-xl bg-white/80 px-3 py-2 text-xs text-slate-700">
                          <div className="font-semibold text-slate-900">{pair.label}</div>
                          <div>{pair.file_a} vs {pair.file_b}</div>
                          <div className="mt-1 font-semibold text-rose-700">Score {(pair.score * 100).toFixed(1)}%</div>
                        </div>
                      )) : <div className="text-sm text-rose-700">{labeledPairAudit.length ? 'No false positives at this threshold.' : 'Pair-level labels are not attached to rows, so examples are unavailable.'}</div>}
                    </div>
                  </div>
                  <div className="rounded-2xl border border-amber-200 bg-amber-50/60 p-4">
                    <div className="font-semibold text-amber-900">False negatives to inspect</div>
                    <p className="mt-1 text-xs leading-5 text-amber-700">Plagiarized pairs scoring below threshold reduce recall.</p>
                    <div className="mt-3 space-y-2">
                      {falseNegativeExamples.length ? falseNegativeExamples.map(pair => (
                        <div key={`${pair.file_a}-${pair.file_b}`} className="rounded-xl bg-white/80 px-3 py-2 text-xs text-slate-700">
                          <div className="font-semibold text-slate-900">{pair.label}</div>
                          <div>{pair.file_a} vs {pair.file_b}</div>
                          <div className="mt-1 font-semibold text-amber-700">Score {(pair.score * 100).toFixed(1)}%</div>
                        </div>
                      )) : <div className="text-sm text-amber-700">{labeledPairAudit.length ? 'No false negatives at this threshold.' : 'Pair-level labels are not attached to rows, so examples are unavailable.'}</div>}
                    </div>
                  </div>
                </div>
              </div>
              {metricWarnings.length > 0 && (
                <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-800">{metricWarnings.map(warning => <div key={warning}>{warning}</div>)}</div>
              )}
            </div>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-6 py-5 border-b border-slate-100">
              <h2 className="font-semibold text-slate-900">PAN Evaluation Scorecard</h2>
              <p className="text-sm text-slate-500 mt-0.5">Focused on {productPanResult.name} — threshold: {typeof productPanResult.threshold === 'number' ? productPanResult.threshold.toFixed(2) : 'N/A'}</p>
            </div>
            <div className="grid gap-4 p-6 md:grid-cols-2 xl:grid-cols-3">
              {panMetricDiagnostics.map(metric => {
                const tone = metricToneClasses(metric.tone);
                return (
                  <div key={metric.key} className={`rounded-2xl border ${tone.border} ${tone.bg} p-5`}>
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{metric.label}</div>
                        <div className={`mt-2 text-3xl font-bold ${tone.text}`}>{formatPanMetricValue(metric)}</div>
                      </div>
                      <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${tone.badge}`}>{tone.label}</span>
                    </div>
                    <div className="mt-4 h-2 rounded-full bg-white/70">
                      <div className={`h-full rounded-full ${tone.bar}`} style={{ width: metricBarWidth(metric) }} />
                    </div>
                    <div className="mt-3 text-xs font-semibold text-slate-500">{metric.target}</div>
                    <div className="mt-4"><div className="text-sm font-semibold text-slate-900">Why it matters</div><p className="mt-1 text-sm leading-6 text-slate-600">{metric.why}</p></div>
                    <div className="mt-4"><div className="text-sm font-semibold text-slate-900">Next action</div><p className="mt-1 text-sm leading-6 text-slate-600">{metric.action}</p></div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-6 py-5 border-b border-slate-100">
              <h2 className="font-semibold text-slate-900">Engine Tuning Feedback</h2>
              <p className="text-sm text-slate-500 mt-0.5">Concrete optimization guidance for the next source-code iteration.</p>
            </div>
            <div className="grid gap-3 p-6 md:grid-cols-2">
              {panFeedback.map(item => (
                <div key={item.title} className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                  <div className="font-semibold text-slate-900">{item.title}</div>
                  <div className="mt-2 text-sm leading-6 text-slate-600">{item.detail}</div>
                </div>
              ))}
            </div>
          </div>

        </div>
      )}

      {/* Charts */}
      {isComparisonReport && chartData.length > 0 && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-6 py-5 border-b border-slate-100">
            <h2 className="font-semibold text-slate-900">Pair-by-Pair Scores</h2>
            <p className="text-sm text-slate-500 mt-0.5">How each tool scored every tested file pair.</p>
            <div className="mt-4 flex flex-wrap gap-2">{activeTools.map(toolId => <ToolBadge key={toolId} toolId={toolId} compact />)}</div>
          </div>
          <div className="p-6 h-[420px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="pair" tick={{ fontSize: 11, fill: '#64748b' }} />
                <YAxis tick={{ fontSize: 11, fill: '#64748b' }} domain={[0, 100]} />
                <Tooltip content={<PairScoreTooltip />} cursor={{ fill: 'rgba(148,163,184,0.08)' }} />
                {activeTools.map(tool => <Bar key={tool} dataKey={tool} fill={TOOLS.find(t => t.id === tool)?.color ?? '#94a3b8'} radius={[4, 4, 0, 0]} name={TOOLS.find(t => t.id === tool)?.name || tool} />)}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Detailed pair results */}
      {isComparisonReport && (pair_results?.length || 0) > 0 && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-6 py-5 border-b border-slate-100">
            <h2 className="font-semibold text-slate-900">Detailed Pair Results</h2>
            <p className="text-sm text-slate-500 mt-0.5">Click any pair to expand individual tool scores</p>
          </div>

          <div className="hidden lg:grid px-6 py-3 bg-slate-50/80 text-[11px] uppercase tracking-wider text-slate-400 font-semibold"
            style={{ gridTemplateColumns: `2fr repeat(${activeTools.length}, 1fr) 60px 60px 70px` }}>
            <div>File Pair</div>
            {activeTools.map(tool => (
              <div key={tool} className="text-center flex items-center justify-center gap-1.5">
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: TOOLS.find(t => t.id === tool)?.color ?? '#94a3b8' }} />
                {TOOLS.find(t => t.id === tool)?.name || tool}
              </div>
            ))}
            <div className="text-center">Max</div>
            <div className="text-center">Min</div>
            <div className="text-center">Spread</div>
          </div>

          <div className="divide-y divide-slate-50">
            {visiblePairResults.map((pair, idx) => {
              const key = pairKey(pair, pageStart + idx);
              const isExpanded = !!expandedPairs[key];
              const scores = activeTools.map(t => { const tr = pair.tool_results?.find(r => r.tool === t); return tr ? tr.score : null; });
              const valid = scores.filter(s => s !== null);
              const maxScore = valid.length ? Math.max(...valid) : 0;
              const minScore = valid.length ? Math.min(...valid) : 0;
              const spread = maxScore - minScore;
              const riskColor = maxScore >= 0.9 ? 'bg-red-500' : maxScore >= 0.75 ? 'bg-amber-500' : maxScore >= 0.5 ? 'bg-yellow-500' : 'bg-emerald-500';

              return (
                <div key={key}>
                  <button onClick={() => togglePair(key)}
                    className="w-full px-6 py-4 hover:bg-slate-50/50 transition-colors text-left hidden lg:grid items-center"
                    style={{ gridTemplateColumns: `2fr repeat(${activeTools.length}, 1fr) 60px 60px 70px` }}>
                    <div className="flex items-center gap-3">
                      <div className={`w-2 h-8 rounded-full ${riskColor}`} />
                      <div>
                        <div className="text-sm font-semibold text-slate-900">{pair.label}</div>
                        <div className="text-xs text-slate-400">{pair.file_a} vs {pair.file_b}</div>
                      </div>
                      {isExpanded ? <ChevronUp size={14} className="text-slate-400 ml-2" /> : <ChevronDown size={14} className="text-slate-400 ml-2" />}
                    </div>
                    {activeTools.map((tool, ti) => (
                      <div key={tool} className="text-center">
                        {scores[ti] !== null ? (
                          <span className={`inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-bold ${tool === 'integritydesk' ? 'bg-blue-50 text-blue-700' : 'bg-slate-50 text-slate-600'}`}>{(scores[ti] * 100).toFixed(1)}%</span>
                        ) : <span className="text-xs text-slate-300">N/A</span>}
                      </div>
                    ))}
                    <div className="text-center text-xs font-bold text-red-600">{(maxScore * 100).toFixed(0)}%</div>
                    <div className="text-center text-xs font-bold text-emerald-600">{(minScore * 100).toFixed(0)}%</div>
                    <div className={`text-center text-xs font-bold ${spread >= 0.3 ? 'text-red-600' : 'text-emerald-600'}`}>{(spread * 100).toFixed(0)}%</div>
                  </button>

                  <button onClick={() => togglePair(key)} className="lg:hidden w-full px-4 py-3 hover:bg-slate-50/50 text-left flex items-center gap-3">
                    <div className={`w-2 h-8 rounded-full shrink-0 ${riskColor}`} />
                    <div className="flex-1">
                      <div className="text-sm font-semibold text-slate-900">{pair.label}</div>
                      <div className="text-xs text-slate-400">Max: {(maxScore * 100).toFixed(0)}% · Min: {(minScore * 100).toFixed(0)}%</div>
                    </div>
                    {isExpanded ? <ChevronUp size={14} className="text-slate-400" /> : <ChevronDown size={14} className="text-slate-400" />}
                  </button>

                  {isExpanded && (
                    <div className="px-6 pb-5 bg-slate-50/50">
                      <div className="grid md:grid-cols-2 gap-3 mt-3">
                        {(pair.tool_results || []).map(tr => {
                          const toolInfo = TOOLS.find(t => t.id === tr.tool);
                          if (!toolInfo) return null;
                          return (
                            <div key={tr.tool} className="bg-white rounded-xl border border-slate-200 p-4">
                              <div className="flex items-center justify-between mb-3">
                                <div className="flex items-center gap-2">
                                  <div className={`w-7 h-7 rounded-lg bg-gradient-to-br ${toolInfo.gradient} flex items-center justify-center`}><Zap size={13} className="text-white" /></div>
                                  <span className="text-sm font-semibold text-slate-900">{toolInfo.name}</span>
                                </div>
                                <span className={`text-lg font-bold ${toolInfo.textColor}`}>{(tr.score * 100).toFixed(1)}%</span>
                              </div>
                              <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                                <div className="h-full rounded-full transition-all duration-500" style={{ width: `${tr.score * 100}%`, background: `linear-gradient(90deg, ${toolInfo.color}, ${toolInfo.color}dd)` }} />
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {totalPairs > itemsPerPage && (
            <div className="flex flex-col gap-3 border-t border-slate-100 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
              <div className="text-xs font-medium text-slate-500">Showing {pageStart + 1}–{pageEnd} of {totalPairs} pairs</div>
              <div className="flex items-center gap-2">
                <button onClick={() => setCurrentPage(p => Math.max(1, p - 1))} disabled={currentPage === 1}
                  className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">Previous</button>
                <span className="min-w-[88px] text-center text-xs font-semibold text-slate-500">Page {currentPage} of {totalPages}</span>
                <button onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))} disabled={currentPage === totalPages}
                  className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">Next</button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Benchmark mode definitions ─────────────────────────────────────────────
const BENCHMARK_MODES = [
  {
    id: 'development',
    icon: Zap,
    eyebrow: 'IntegrityDesk optimization',
    label: 'Improve IntegrityDesk',
    tagline: 'Run labeled tests, inspect per-run F1 / Precision / Recall / FPR, and keep improving IntegrityDesk.',
    description: 'Run IntegrityDesk on labeled benchmark data, tune the threshold, and inspect the misses and false alarms that are blocking quality.',
    bestFor: 'Best for improving your own detector',
    outputs: ['Per-run F1 / Precision / Recall / FPR', 'Best threshold', 'Top misses and false alarms'],
    accent: 'from-violet-500 via-fuchsia-500 to-rose-400',
    accentBg: 'bg-violet-600',
    accentSoft: 'bg-violet-100 text-violet-700',
    border: 'border-violet-200',
    activeBg: 'bg-violet-600',
    detailNote: 'A single-tool IntegrityDesk scorecard with threshold tuning and concrete next steps for improving quality.',
  },
  {
    id: 'comparison',
    icon: GitCompare,
    eyebrow: 'Competitive benchmark',
    label: 'Compare Against Other Tools',
    tagline: 'Run IntegrityDesk beside MOSS, JPlag, Dolos, and others on the same benchmark to prove it wins.',
    description: 'Compare multiple detectors on the same labeled dataset and see where IntegrityDesk wins or loses on F1, precision, recall, and false positive rate.',
    bestFor: 'Best for proving IntegrityDesk is better',
    outputs: ['Per-tool F1 / Precision / Recall / FPR', 'Leaderboard ranking', 'Speed vs quality tradeoffs'],
    accent: 'from-sky-500 via-cyan-500 to-emerald-400',
    accentBg: 'bg-sky-600',
    accentSoft: 'bg-sky-100 text-sky-700',
    border: 'border-sky-200',
    activeBg: 'bg-sky-600',
    detailNote: 'A ranked multi-tool leaderboard showing whether IntegrityDesk beats the external baselines on the same benchmark data.',
  },
];

// ── Shared Workbench ───────────────────────────────────────────────────────
export function BenchmarkWorkbench({ modeScope = 'benchmark' }: { modeScope?: 'benchmark' | 'comparison' }) {
  const { user, loading: authLoading } = useAuth();
  const availableModes = useMemo(
    () => BENCHMARK_MODES.filter(mode => (modeScope === 'comparison' ? mode.id === 'comparison' : mode.id === 'development')),
    [modeScope]
  );
  const [activeModeId, setActiveModeId] = useState(modeScope === 'comparison' ? 'comparison' : 'development');
  const [step, setStep] = useState(0);
  const [completedSteps, setCompletedSteps] = useState([]);
  const [selectedTools, setSelectedTools] = useState([]);
  const [selectedDataset, setSelectedDataset] = useState(null);
  const [uploadMode, setUploadMode] = useState('builtin');
  const [files, setFiles] = useState([]);
  const [benchmarkDatasets, setBenchmarkDatasets] = useState([]);
  const [rawApiTools, setRawApiTools] = useState([]);
  const [toolsLoading, setToolsLoading] = useState(true);
  const [toolsError, setToolsError] = useState('');
  const [results, setResults] = useState(null);

  // FIX: Merge API availability with full TOOLS metadata
  const availableTools = useMemo(() => mergeToolsWithAvailability(rawApiTools), [rawApiTools]);

  useEffect(() => {
    if (authLoading || !user) return;
    setToolsLoading(true);
    axios.get(`${API}/api/benchmark-tools`, { withCredentials: true })
      .then(res => { if (res.data?.tools) setRawApiTools(res.data.tools); })
      .catch(() => {
        setToolsError('Unable to confirm installed benchmark tools. Showing last known tool set.');
        // On error: show all TOOLS as available (except explicitly non-runnable)
        setRawApiTools(TOOLS.map(t => ({ id: t.id, available: t.runnable !== false })));
      })
      .finally(() => setToolsLoading(false));
    axios.get(`${API}/api/benchmark-datasets`, { withCredentials: true })
      .then(res => { if (res.data?.datasets) setBenchmarkDatasets(res.data.datasets); })
      .catch(() => { });
  }, [authLoading, user]);

  const activeMode = availableModes.find(m => m.id === activeModeId) || availableModes[0];

  useEffect(() => {
    const nextModeId = modeScope === 'comparison' ? 'comparison' : 'development';
    if (activeModeId === nextModeId) return;
    setActiveModeId(nextModeId);
    setStep(0);
    setCompletedSteps([]);
    setResults(null);
    setSelectedTools([]);
    setSelectedDataset(null);
    setFiles([]);
  }, [activeModeId, modeScope]);

  const switchMode = (modeId) => {
    setActiveModeId(modeId);
    // FIX: also reset wizard state on mode switch
    setStep(0);
    setCompletedSteps([]);
    setResults(null);
    setSelectedTools([]);
    setSelectedDataset(null);
    setFiles([]);
  };

  const goToStep = (next, currentCompleted) => {
    setCompletedSteps(prev => [...new Set([...prev, currentCompleted])]);
    setStep(next);
    // Scroll step content into view smoothly
    setTimeout(() => document.getElementById('step-content')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
  };

  const restart = () => { setStep(0); setCompletedSteps([]); setResults(null); };

  const STEPS = [
    { label: 'Tools', subtitle: 'Choose what to run' },
    { label: 'Dataset', subtitle: 'Pick or upload data' },
    { label: 'Run', subtitle: 'Execute benchmark' },
    { label: 'Report', subtitle: 'View results' },
  ];

  return (
    <DashboardLayout requiredRole={modeScope === 'benchmark' ? 'admin' : undefined}>
      <div className={`px-4 py-6 sm:px-6 lg:px-8 lg:py-8 max-w-none`}>
        <div className="space-y-6">

          {/* ── Page header ─────────────────────────────────────────────── */}
          {modeScope !== 'comparison' && (
            <div className="flex flex-col gap-4 mb-1 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-3 mb-1">
                <div className="w-9 h-9 rounded-xl bg-slate-900 flex items-center justify-center shadow-lg shrink-0">
                  <FlaskConical size={18} className="text-white" />
                </div>
                <div>
                  <h1 className="text-xl font-bold text-slate-900 tracking-tight">
                    IntegrityDesk Benchmark
                  </h1>
                  <p className="text-sm text-slate-500">
                    Admin-only benchmark workspace for improving IntegrityDesk on labeled benchmark data.
                  </p>
                </div>
              </div>
              <div className="flex-1 sm:max-w-sm md:max-w-md lg:max-w-lg">
                <StepIndicator steps={STEPS} currentStep={step} completedSteps={completedSteps} />
              </div>
            </div>
          )}
          {modeScope === 'comparison' && (
            <div className="flex flex-col gap-4 mb-1 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-slate-900 flex items-center justify-center shadow-lg shrink-0">
                  <GitCompare size={18} className="text-white" />
                </div>
                <div>
                  <h1 className="text-xl font-bold text-slate-900 tracking-tight">
                    Compare Tools
                  </h1>
                  <p className="text-sm text-slate-500">
                    Compare IntegrityDesk against external detection tools on the same benchmark data.
                  </p>
                </div>
              </div>
              <div className="flex-1 sm:max-w-sm md:max-w-md lg:max-w-lg">
                <StepIndicator steps={STEPS} currentStep={step} completedSteps={completedSteps} />
              </div>
            </div>
          )}

          {/* ── Mode selector ────────────────────────────────────────────── */}
          {availableModes.length > 1 && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {availableModes.map(mode => {
              const Icon = mode.icon;
              const isActive = activeModeId === mode.id;
              return (
                <button key={mode.id} onClick={() => switchMode(mode.id)}
                  className={`group relative rounded-2xl border-2 p-5 text-left transition-all duration-200 ${isActive ? 'border-slate-900 bg-slate-900 shadow-xl shadow-slate-900/15' : 'border-slate-200 bg-white hover:border-slate-300 hover:-translate-y-0.5 hover:shadow-md'}`}>
                  {isActive && (
                    <div className="absolute inset-0 rounded-2xl overflow-hidden pointer-events-none">
                      <div className={`absolute inset-0 bg-gradient-to-br ${mode.accent} opacity-10`} />
                    </div>
                  )}
                  <div className="flex items-start justify-between gap-3">
                    <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${mode.accent} flex items-center justify-center shadow-md shrink-0`}>
                      <Icon size={18} className="text-white" />
                    </div>
                    {isActive && <span className="rounded-full bg-white/20 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-white">Selected</span>}
                  </div>
                  <div className={`mt-4 text-[11px] font-semibold uppercase tracking-[0.18em] ${isActive ? 'text-slate-400' : 'text-slate-400'}`}>{mode.eyebrow}</div>
                  <div className={`mt-1 text-base font-bold ${isActive ? 'text-white' : 'text-slate-900'}`}>{mode.label}</div>
                  <p className={`mt-2 text-sm leading-5 ${isActive ? 'text-slate-300' : 'text-slate-500'}`}>{mode.description}</p>
                  <div className="mt-4 flex flex-wrap gap-1.5">
                    {mode.outputs.map(o => (
                      <span key={o} className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${isActive ? 'bg-white/10 text-slate-200' : 'bg-slate-100 text-slate-600'}`}>{o}</span>
                    ))}
                  </div>
                </button>
              );
            })}
          </div>
          )}

          {/* ── Step wizard ─────────────────────────────────────────────── */}
          <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
            {/* Run config summary bar — visible in steps 1+ */}
            {step >= 1 && step < 3 && (
              <div className="px-5 py-3 bg-slate-50/70 border-b border-slate-100">
                <RunConfigBar
                  selectedTools={selectedTools}
                  selectedDataset={selectedDataset}
                  uploadMode={uploadMode}
                  files={files}
                  benchmarkDatasets={benchmarkDatasets}
                  modeName={activeMode.label}
                  modeColor={activeMode.accentSoft}
                />
              </div>
            )}

            {/* Step content */}
            <div id="step-content" className="p-5 sm:p-6">
              {step === 0 && (
                <ToolSelectionStep
              tools={availableTools}
              selectedTools={selectedTools}
              setSelectedTools={setSelectedTools}
              loading={toolsLoading}
              error={toolsError}
              benchmarkMode={activeModeId}
              onNext={() => goToStep(1, 0)}
            />
              )}
              {step === 1 && (
                <DatasetStep
                  selectedDataset={selectedDataset}
                  setSelectedDataset={setSelectedDataset}
                  uploadMode={uploadMode}
                  setUploadMode={setUploadMode}
                  files={files}
                  setFiles={setFiles}
                  benchmarkDatasets={benchmarkDatasets}
                  canManageDemoDatasets={user?.role === 'admin'}
                  onBack={() => setStep(0)}
                  onNext={() => goToStep(2, 1)}
                />
              )}
              {step === 2 && (
                <RunStep
                  selectedTools={selectedTools}
                  selectedDataset={selectedDataset}
                  uploadMode={uploadMode}
                  files={files}
                  benchmarkDatasets={benchmarkDatasets}
                  selectedPreset={null}
                  benchmarkMode={activeModeId}
                  autoStart
                  onBack={() => setStep(1)}
                  onComplete={data => { setResults(data); goToStep(3, 2); }}
                />
              )}
              {step === 3 && results && (
                <ReportStep results={results} onRestart={restart} benchmarkMode={activeModeId} />
              )}
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

// ── Route Page ─────────────────────────────────────────────────────────────
export default function BenchmarkPage() {
  return <BenchmarkWorkbench modeScope="benchmark" />;
}
