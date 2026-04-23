// @ts-nocheck
'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { useAuth } from '@/components/AuthProvider';
import { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import axios from 'axios';
import Link from 'next/link';
import {
  BarChart3, Loader2, Trophy, FileUp, X, AlertCircle,
  Zap, Target, Layers, TrendingUp, CheckCircle2, ChevronDown, ChevronUp,
  Download, Play, FlaskConical, FileText, ArrowRight, Square, Check,
  ChevronRight, UploadCloud, Database, Settings2, ClipboardList, Plus,
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from 'recharts';

const API = process.env.NEXT_PUBLIC_API_URL || '';

const TOOLS = [];

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
    order: 5,
    presetCategory: 'Controlled plagiarism corpus',
    badgeLabel: 'Gold Standard',
    eyebrow: 'Controlled original-vs-plagiarized benchmark',
    summary: 'Balanced exact, renamed, restructured, semantic, and hard-negative code pairs',
  },
  conplag_classroom_java: {
    order: 10,
    presetCategory: 'Classroom-style',
    badgeLabel: 'Classroom Java',
    eyebrow: 'Best Java submission corpus',
    summary: 'Assignment-grouped Java submissions with labels',
  },
  kaggle_student_code: {
    order: 20,
    presetCategory: 'Classroom-style',
    badgeLabel: 'Classroom Python',
    eyebrow: 'Best Python submission smoke test',
    summary: 'Lightweight student-style Python submission set',
  },
  'IR-Plag-Dataset': {
    order: 30,
    presetCategory: 'Research benchmark',
    badgeLabel: 'Research Benchmark',
    eyebrow: 'Focused Java plagiarism cases',
    summary: 'Smaller Java plagiarism dataset for targeted checks',
  },
  human_eval: {
    order: 40,
    presetCategory: 'Programming-task benchmark',
    badgeLabel: 'Programming Tasks',
    eyebrow: 'Python code-task benchmark',
    summary: 'Task-based Python benchmark, not classroom submissions',
  },
  mbpp: {
    order: 50,
    presetCategory: 'Programming-task benchmark',
    badgeLabel: 'Programming Tasks',
    eyebrow: 'Short-form Python task coverage',
    summary: 'Python programming task benchmark, not classroom submissions',
  },
  codesearchnet: {
    order: 60,
    presetCategory: 'Large-scale technical corpus',
    badgeLabel: 'Technical Corpus',
    eyebrow: 'Large-scale mixed-language stress test',
    summary: 'Use for scale and variety rather than classroom realism',
  },
  codexglue_clone: {
    order: 70,
    presetCategory: 'Research benchmark',
    badgeLabel: 'Research Benchmark',
    eyebrow: 'Large labeled clone-pair benchmark',
    summary: 'Good for clone-pair stress testing in Java',
  },
  codexglue_defect: {
    order: 80,
    presetCategory: 'Research benchmark',
    badgeLabel: 'Research Benchmark',
    eyebrow: 'C code technical benchmark',
    summary: 'Useful for stress testing, less classroom-like',
  },
};

const BENCHMARK_MODES = {
  pan_optimization: {
    label: 'PAN Optimization',
    audience: 'Admin / Developer',
    title: 'Build the strongest detector',
    description: 'Use labeled benchmark data to optimize Precision, Recall, F1, Granularity, and PlagDet.',
  },
  tool_comparison: {
    label: 'Tool Comparison',
    audience: 'Professor',
    title: 'Compare against external tools',
    description: 'Run IntegrityDesk beside MOSS, Dolos, JPlag, NiCad, and other tools for competitive proof.',
  },
};

function getPresetDatasetMeta(dataset) {
  if (!dataset || dataset.is_demo || dataset.cases) {
    return null;
  }

  return PRESET_DATASET_META[dataset.id] || null;
}

function getDatasetCategory(dataset) {
  if (!dataset) {
    return null;
  }

  if (dataset.datasetType) {
    return dataset.datasetType;
  }

  if (dataset.cases) {
    return 'guided';
  }

  return dataset.is_demo ? 'demo' : 'preset';
}

function getDatasetCategoryMeta(dataset) {
  const category = getDatasetCategory(dataset);
  return category ? DATASET_CATEGORY_META[category] : null;
}

function formatDatasetDate(value) {
  if (!value) {
    return 'Recently created';
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(parsed);
}

function summarizeDataset(dataset) {
  if (!dataset) {
    return '';
  }

  if (dataset.cases) {
    return `${dataset.cases.length} guided scenarios`;
  }

  if (dataset.is_demo) {
    const sizeLabel = dataset.size || 'Custom size';
    const similarityLabel = dataset.similarity_type
      ? dataset.similarity_type.replaceAll('_', ' ')
      : 'Classroom-style patterns';
    return `${sizeLabel} • ${similarityLabel}`;
  }

  const sizeLabel = dataset.size || 'Benchmark scale';
  const languageLabel = dataset.language ? dataset.language.toUpperCase() : 'Mixed';
  const presetMeta = getPresetDatasetMeta(dataset);
  if (presetMeta?.presetCategory) {
    return `${presetMeta.presetCategory} • ${languageLabel} • ${sizeLabel}`;
  }
  return `${languageLabel} • ${sizeLabel}`;
}

function formatBenchmarkQuality(quality) {
  if (!quality) {
    return null;
  }

  const level = quality.certification_level === 'gold_standard'
    ? 'Gold-standard controlled benchmark'
    : 'Labeled benchmark';
  return `${level} • ${Number(quality.score_percent || 0).toFixed(0)}% quality gates`;
}

function sortDatasets(datasets, demo = false) {
  const items = [...datasets];
  if (demo) {
    return items.sort((a, b) => {
      const aTime = Date.parse(a.created_at || '') || 0;
      const bTime = Date.parse(b.created_at || '') || 0;
      return bTime - aTime;
    });
  }

  return items.sort((a, b) => {
    const aMeta = getPresetDatasetMeta(a);
    const bMeta = getPresetDatasetMeta(b);
    const aOrder = aMeta?.order ?? 9999;
    const bOrder = bMeta?.order ?? 9999;
    if (aOrder !== bOrder) {
      return aOrder - bOrder;
    }
    return (a.name || '').localeCompare(b.name || '');
  });
}

function buildDatasetLibrary(benchmarkDatasets = []) {
  const presetDatasets = sortDatasets(
    benchmarkDatasets.filter(d => !d.is_demo).map(d => ({ ...d, datasetType: 'preset' }))
  );
  const demoDatasets = sortDatasets(
    benchmarkDatasets.filter(d => d.is_demo).map(d => ({ ...d, datasetType: 'demo' })),
    true
  );

  return {
    presetDatasets,
    demoDatasets,
    allDatasets: [...presetDatasets, ...demoDatasets],
  };
}

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
      onClick={() => {
        if (!disabled) onSelect(dataset.id);
      }}
      className={`relative rounded-2xl border-2 p-4 text-left transition-all duration-200 ${disabled
        ? 'cursor-not-allowed border-slate-200 bg-slate-50 opacity-60'
        : isActive
        ? 'border-slate-900 bg-slate-900 text-white shadow-lg shadow-slate-900/10'
        : 'border-slate-200 bg-white hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-md'
        }`}
    >
      {isActive && (
        <div className="absolute right-3 top-3">
          <CheckCircle2 size={16} className="text-white" />
        </div>
      )}
      <div className="flex items-start justify-between gap-3">
        <div className="text-2xl">{dataset.icon}</div>
        <span
          className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${isActive ? 'bg-white/15 text-white' : categoryMeta?.badgeClass
            }`}
        >
          {badgeLabel}
        </span>
      </div>
      <div className={`mt-4 text-[11px] font-semibold uppercase tracking-[0.18em] ${isActive ? 'text-slate-300' : 'text-slate-400'
        }`}>
        {eyebrow}
      </div>
      <div className={`mt-2 text-base font-semibold ${isActive ? 'text-white' : 'text-slate-900'}`}>
        {dataset.name}
      </div>
      <div className={`mt-2 text-sm leading-6 ${isActive ? 'text-slate-200' : 'text-slate-500'}`}>
        {dataset.desc}
      </div>
      {secondarySummary && (
        <div className={`mt-2 text-xs leading-5 ${isActive ? 'text-slate-300' : 'text-slate-400'}`}>
          {secondarySummary}
        </div>
      )}
      {qualityLabel && (
        <div className={`mt-3 flex items-start gap-2 rounded-xl px-3 py-2 text-xs leading-5 ${isActive ? 'bg-white/10 text-slate-100' : 'bg-emerald-50 text-emerald-700'
          }`}>
          <ClipboardList size={14} className="mt-0.5 shrink-0" />
          <span>{qualityLabel}</span>
        </div>
      )}
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <span
          className={`rounded-full px-2.5 py-1 text-xs font-medium ${isActive ? 'bg-white/10 text-white' : 'bg-slate-100 text-slate-600'
            }`}
        >
          {summarizeDataset(dataset)}
        </span>
        {dataset.created_by && (
          <span
            className={`rounded-full px-2.5 py-1 text-xs font-medium ${isActive ? 'bg-white/10 text-white' : 'bg-slate-100 text-slate-600'
              }`}
          >
            {dataset.created_by}
          </span>
        )}
        {dataset.has_ground_truth && (
          <span
            className={`rounded-full px-2.5 py-1 text-xs font-semibold ${isActive ? 'bg-white/10 text-white' : 'bg-emerald-50 text-emerald-700'
              }`}
          >
            Labeled
          </span>
        )}
      </div>
    </button>
  );
}

function formatChartPercent(value) {
  return `${Number(value || 0).toFixed(1)}%`;
}

function formatMetric(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return 'N/A';
  }
  return Number(value).toFixed(3);
}

function formatRuntime(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return 'N/A';
  }
  return Number(value).toFixed(2);
}

function formatDelta(value, lowerIsBetter = false) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return 'N/A';
  }
  const numeric = Number(value);
  const direction = numeric > 0 ? '+' : '';
  const display = lowerIsBetter ? numeric * 100 : numeric * 100;
  return `${direction}${display.toFixed(1)}%`;
}

function deltaTone(value, lowerIsBetter = false) {
  const numeric = Number(value || 0);
  if (Math.abs(numeric) < 0.0001) return 'text-slate-500 bg-slate-100';
  const improved = lowerIsBetter ? numeric < 0 : numeric > 0;
  return improved ? 'text-emerald-700 bg-emerald-50' : 'text-rose-700 bg-rose-50';
}

function formatEngineContribution(contribution = {}) {
  const entries = Object.entries(contribution || {})
    .filter(([, value]) => typeof value === 'number' && value > 0)
    .slice(0, 3);

  if (!entries.length) {
    return 'N/A';
  }

  return entries
    .map(([name, value]) => `${name}: ${(Number(value) * 100).toFixed(0)}%`)
    .join(', ');
}

function ToolBadge({ toolId, compact = false }) {
  const tool = TOOLS.find((entry) => entry.id === toolId);

  if (!tool) {
    return (
      <span className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600">
        <span className="h-2.5 w-2.5 rounded-full bg-slate-400" />
        {toolId}
      </span>
    );
  }

  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 ${compact ? 'text-[11px]' : 'text-xs'
        } font-semibold ${tool.bgLight} ${tool.textColor} border-current/10`}
    >
      <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: tool.color }} />
      {tool.name}
    </span>
  );
}

function PairScoreTooltip({ active, payload, label }) {
  if (!active || !payload?.length) {
    return null;
  }

  const rows = payload
    .filter((entry) => typeof entry.value === 'number')
    .sort((a, b) => Number(b.value) - Number(a.value));

  return (
    <div className="min-w-[220px] rounded-2xl border border-slate-200 bg-white/95 p-4 shadow-2xl shadow-slate-900/10 backdrop-blur">
      <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">File Pair</div>
      <div className="mt-1 text-sm font-semibold text-slate-900">{label}</div>
      <div className="mt-3 space-y-2">
        {rows.map((entry) => (
          <div key={entry.dataKey} className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2 min-w-0">
              <span
                className="h-2.5 w-2.5 shrink-0 rounded-full"
                style={{ backgroundColor: entry.color || '#94a3b8' }}
              />
              <span className="truncate text-xs font-medium text-slate-600">
                {TOOLS.find((tool) => tool.id === entry.dataKey)?.name || entry.name}
              </span>
            </div>
            <span className="text-xs font-semibold text-slate-900">{formatChartPercent(entry.value)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function LeaderboardTooltip({ active, payload }) {
  if (!active || !payload?.length) {
    return null;
  }

  const toolId = payload[0]?.payload?.id;
  const tool = TOOLS.find((entry) => entry.id === toolId);
  const row = payload[0]?.payload;

  if (!row) {
    return null;
  }

  return (
    <div className="min-w-[240px] rounded-2xl border border-slate-200 bg-white/95 p-4 shadow-2xl shadow-slate-900/10 backdrop-blur">
      <div className="flex items-center gap-2">
        <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: row.color }} />
        <div className="text-sm font-semibold text-slate-900">{row.name}</div>
      </div>
      {tool?.desc && <div className="mt-2 text-xs leading-5 text-slate-500">{tool.desc}</div>}
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <div className="rounded-xl bg-slate-50 px-3 py-2">
          <div className="text-slate-400">Average</div>
          <div className="mt-1 font-semibold text-slate-900">{formatChartPercent(row.average)}</div>
        </div>
        <div className="rounded-xl bg-slate-50 px-3 py-2">
          <div className="text-slate-400">Peak</div>
          <div className="mt-1 font-semibold text-slate-900">{formatChartPercent(row.peak)}</div>
        </div>
        <div className="rounded-xl bg-slate-50 px-3 py-2">
          <div className="text-slate-400">Lowest</div>
          <div className="mt-1 font-semibold text-slate-900">{formatChartPercent(row.minimum)}</div>
        </div>
        <div className="rounded-xl bg-slate-50 px-3 py-2">
          <div className="text-slate-400">Spread</div>
          <div className="mt-1 font-semibold text-slate-900">{formatChartPercent(row.spread)}</div>
        </div>
      </div>
    </div>
  );
}

function buildPanFeedback(row) {
  if (!row) return [];

  const suggestions = [];
  if (row.precision < 0.85) {
    suggestions.push({
      title: 'Precision is the main problem',
      detail: 'False positives are too high. Raise the final decision threshold, increase weight on exact/token/AST agreement, and reduce broad semantic-only matches until negatives are cleaner.',
    });
  }
  if (row.recall < 0.85) {
    suggestions.push({
      title: 'Recall is missing true plagiarism',
      detail: 'Lower the candidate threshold, enable semantic or embedding retrieval for obfuscated clones, and make sure renamed/type-3/type-4 pairs enter the candidate pool before reranking.',
    });
  }
  if (row.f1Score < 0.85) {
    suggestions.push({
      title: 'F1 needs threshold calibration',
      detail: 'Sweep thresholds on the labeled PAN set and choose the point that maximizes F1 before tuning individual engine weights.',
    });
  }
  if (row.granularity > 1.2) {
    suggestions.push({
      title: 'Granularity suggests over-splitting',
      detail: 'Merge overlapping or adjacent detections from the same file pair and prefer one coherent evidence span over many tiny fragments.',
    });
  }
  if (row.top10Retrieval < 0.9) {
    suggestions.push({
      title: 'Top-10 retrieval is weak',
      detail: 'The highest-ranked results are still noisy. Improve cheap lexical/AST retrieval, apply stricter negative filters before ranking, then rerank top candidates with heavier engines.',
    });
  }
  if (row.top20Retrieval < 0.95) {
    suggestions.push({
      title: 'Top-20 retrieval still loses positives',
      detail: 'The first page of candidates is not clean enough. Tune ranking with precision@20/PR-AUC so true plagiarism consistently appears above negatives.',
    });
  }
  if (row.falsePositiveRate > 0.1) {
    suggestions.push({
      title: 'False positive rate is too high',
      detail: 'Add stricter negative filters for boilerplate, templates, and common starter code. Require agreement between at least two independent engines before high-risk classification.',
    });
  }
  if (row.aucPr < 0.85) {
    suggestions.push({
      title: 'Ranking quality is weak',
      detail: 'AUC-PR below target means true plagiarism is not consistently ranked above negatives. Tune fusion weights with PR-AUC/PlagDet as objectives, not average similarity.',
    });
  }
  if (row.engineContributionText !== 'N/A') {
    suggestions.push({
      title: 'Use contribution balance to guide engine weights',
      detail: `Current top contributors are ${row.engineContributionText}. If one engine dominates, run ablations and reduce its weight when it causes false positives.`,
    });
  }
  if (row.avgRuntimeSeconds > 2) {
    suggestions.push({
      title: 'Runtime is expensive',
      detail: 'Cache tokenization/AST parsing, use cheap lexical retrieval first, run embeddings only on shortlisted candidates, and avoid all-pairs heavy scoring for large classes.',
    });
  }
  if (!suggestions.length) {
    suggestions.push({
      title: 'PAN metrics look balanced',
      detail: 'Keep this engine mix as the baseline. Next improvements should be validated with harder obfuscation sets and a larger negative corpus.',
    });
  }
  return suggestions;
}

function metricTone(score, mode = 'higher') {
  if (mode === 'lower') {
    if (score <= 0.05) return 'good';
    if (score <= 0.15) return 'watch';
    return 'bad';
  }
  if (mode === 'granularity') {
    if (score <= 1.05) return 'good';
    if (score <= 1.2) return 'watch';
    return 'bad';
  }
  if (mode === 'runtime') {
    if (score <= 0.5) return 'good';
    if (score <= 2) return 'watch';
    return 'bad';
  }
  if (score >= 0.9) return 'good';
  if (score >= 0.75) return 'watch';
  return 'bad';
}

function metricToneClasses(tone) {
  if (tone === 'good') {
    return {
      border: 'border-emerald-200',
      bg: 'bg-emerald-50',
      text: 'text-emerald-700',
      bar: 'bg-emerald-500',
      badge: 'bg-emerald-100 text-emerald-700',
      label: 'Strong',
    };
  }
  if (tone === 'watch') {
    return {
      border: 'border-amber-200',
      bg: 'bg-amber-50',
      text: 'text-amber-700',
      bar: 'bg-amber-500',
      badge: 'bg-amber-100 text-amber-700',
      label: 'Needs attention',
    };
  }
  return {
    border: 'border-red-200',
    bg: 'bg-red-50',
    text: 'text-red-700',
    bar: 'bg-red-500',
    badge: 'bg-red-100 text-red-700',
    label: 'Optimization priority',
  };
}

function formatPanMetricValue(metric) {
  if (metric.value === null || metric.value === undefined || Number.isNaN(Number(metric.value))) {
    return 'N/A';
  }
  if (metric.format === 'seconds') {
    return `${Number(metric.value).toFixed(3)}s`;
  }
  if (metric.format === 'plain') {
    return Number(metric.value).toFixed(3);
  }
  return `${(Number(metric.value) * 100).toFixed(1)}%`;
}

function metricBarWidth(metric) {
  if (metric.mode === 'runtime') {
    return `${Math.max(8, Math.min(100, (2 - Math.min(Number(metric.value || 0), 2)) / 2 * 100))}%`;
  }
  if (metric.mode === 'lower') {
    return `${Math.max(8, Math.min(100, (1 - Number(metric.value || 0)) * 100))}%`;
  }
  if (metric.mode === 'granularity') {
    const distance = Math.min(1, Math.abs(Number(metric.value || 1) - 1));
    return `${Math.max(8, Math.min(100, (1 - distance) * 100))}%`;
  }
  return `${Math.max(8, Math.min(100, Number(metric.value || 0) * 100))}%`;
}

function buildPanMetricDiagnostics(row) {
  if (!row) return [];

  const scoreDiagnostics = row.scoreDiagnostics || {};
  const hasLabelConflict = Boolean(scoreDiagnostics.label_conflict);
  const metrics = [
    {
      key: 'plagdet',
      label: 'PlagDet',
      value: row.plagdet,
      mode: 'higher',
      target: 'Target >= 90%',
      why: row.plagdet < 0.75
        ? 'The primary PAN score is low, so the detector is not yet balancing recall, precision, and detection granularity well enough for trustworthy benchmark progress.'
        : row.plagdet < 0.9
          ? 'The primary PAN score is usable but still leaves measurable room in either classification balance or evidence consolidation.'
          : 'The primary PAN score is strong; protect this as the baseline while testing harder plagiarism transformations.',
      action: row.plagdet < 0.9
        ? 'Optimize threshold and fusion weights against PlagDet directly, then rerun synthetic_small and one harder dataset before accepting the change.'
        : 'Freeze this configuration as the current benchmark baseline and compare every future engine change against it.',
    },
    {
      key: 'precision',
      label: 'Precision',
      value: row.precision,
      mode: 'higher',
      target: 'Target >= 90%',
      why: hasLabelConflict
        ? 'The score distribution suggests a benchmark-label conflict: some labeled negatives score as high as or higher than labeled positives, often caused by shared templates or starter-code pairs.'
        : row.precision < 0.75
        ? 'Many clean pairs are being marked as plagiarism, which will create noisy admin feedback and reduce trust in production findings.'
        : row.precision < 0.9
          ? 'False positives are still high enough to make reviewers spend time on avoidable cases.'
          : 'False positives are under control on this dataset.',
      action: hasLabelConflict
        ? 'Inspect the top high-scoring negatives and add true unrelated negative files or explicit pair metadata before using this dataset for threshold tuning.'
        : row.precision < 0.9
        ? 'Raise the decision threshold, down-weight broad semantic-only matches, and require agreement between token/AST/winnowing before high-confidence flags.'
        : 'Keep the current precision guardrails and watch whether recall improvements introduce new false positives.',
    },
    {
      key: 'recall',
      label: 'Recall',
      value: row.recall,
      mode: 'higher',
      target: 'Target >= 90%',
      why: row.recall < 0.75
        ? 'The engine is missing too many known plagiarism pairs, so the candidate generation or final threshold is too strict.'
        : row.recall < 0.9
          ? 'Some true plagiarism still falls below the decision boundary.'
          : 'The engine is finding nearly all labeled plagiarism pairs in this run.',
      action: row.recall < 0.9
        ? 'Lower the candidate threshold, widen retrieval before reranking, and strengthen renamed/structural clone handling.'
        : 'Preserve the candidate recall path while tuning precision.',
    },
    {
      key: 'f1',
      label: 'F1 Score',
      value: row.f1Score,
      mode: 'higher',
      target: 'Target >= 90%',
      why: row.f1Score < 0.75
        ? 'The precision/recall tradeoff is not calibrated; improving only one side will not be enough.'
        : row.f1Score < 0.9
          ? 'The detector is close, but the threshold is not at the best operating point yet.'
          : 'Precision and recall are well balanced for this labeled set.',
      action: row.f1Score < 0.9
        ? 'Run a threshold sweep and keep the threshold that maximizes F1, then check whether PlagDet also improves.'
        : 'Use this F1 as the acceptance baseline for source-code changes.',
    },
    {
      key: 'granularity',
      label: 'Granularity',
      value: row.granularity,
      mode: 'granularity',
      format: 'plain',
      target: 'Target close to 1.000',
      why: row.granularity > 1.2
        ? 'The detector is splitting a single plagiarism case into too many fragments, which PAN penalizes and makes feedback harder to interpret.'
        : row.granularity > 1.05
          ? 'Evidence is slightly fragmented; the score would benefit from cleaner span merging.'
          : 'Detections are consolidated cleanly for pair-level PAN scoring.',
      action: row.granularity > 1.05
        ? 'Merge adjacent or overlapping evidence from the same pair before scoring and reporting.'
        : 'Keep one coherent detection per true pair unless span-level PAN data requires finer evidence.',
    },
    {
      key: 'auc_pr',
      label: 'AUC-PR',
      value: row.aucPr,
      mode: 'higher',
      target: 'Target >= 90%',
      why: row.aucPr < 0.75
        ? 'True plagiarism is not consistently ranked above negatives, so reviewers may not see the right cases first.'
        : row.aucPr < 0.9
          ? 'Ranking quality is decent but still vulnerable when there are many negative pairs.'
          : 'Ranking separates positives from negatives well.',
      action: row.aucPr < 0.9
        ? 'Tune fusion weights with PR-AUC as an objective and add harder negative examples that look superficially similar.'
        : 'Keep this ranking profile and validate it on a larger negative corpus.',
    },
    {
      key: 'fpr',
      label: 'False Positive Rate',
      value: row.falsePositiveRate,
      mode: 'lower',
      target: 'Target <= 5%',
      why: row.falsePositiveRate > 0.15
        ? 'Too many non-plagiarized pairs are being flagged, which points to weak negative filtering or an overly permissive threshold.'
        : row.falsePositiveRate > 0.05
          ? 'False positives are manageable but still worth reducing before shipping a stricter detector.'
          : 'Negative pairs are being filtered cleanly.',
      action: row.falsePositiveRate > 0.05
        ? 'Add boilerplate/template suppression and require multi-engine agreement before high-risk classification.'
        : 'Keep current negative filters while improving recall.',
    },
    {
      key: 'top10',
      label: 'Top-10 Retrieval',
      value: row.top10Retrieval,
      mode: 'higher',
      target: 'Target >= 90%',
      why: hasLabelConflict
        ? 'True pairs are being pushed down because labeled negatives have equal or higher scores, so retrieval appears broken even when the input labels may be the weak point.'
      : row.top10Retrieval < 0.75
        ? 'The top-ranked results are not mostly true positives, so reviewers see noisy candidates first.'
        : row.top10Retrieval < 0.9
          ? 'Some true pairs appear too low in the candidate ranking.'
          : 'The candidate stage is surfacing true positives early.',
      action: hasLabelConflict
        ? 'Separate benchmark-data cleanup from engine tuning: fix pair labels/templates first, then rerun retrieval metrics.'
      : row.top10Retrieval < 0.9
        ? 'Tune retrieval ranking with precision@10 and PR-AUC, then rerank top candidates with token/AST/winnowing evidence.'
        : 'Use this retrieval setting as the baseline for speed optimizations.',
    },
    {
      key: 'runtime',
      label: 'Avg Runtime',
      value: row.avgRuntimeSeconds,
      mode: 'runtime',
      format: 'seconds',
      target: 'Target <= 0.5s / pair',
      why: row.avgRuntimeSeconds > 2
        ? 'The engine is too slow for iterative benchmark work and larger classroom datasets.'
        : row.avgRuntimeSeconds > 0.5
          ? 'Runtime is acceptable for small evaluations but may slow down larger PAN runs.'
          : 'Runtime is healthy for rapid optimization loops.',
      action: row.avgRuntimeSeconds > 0.5
        ? 'Cache parsing/tokenization, run cheap retrieval first, and reserve embeddings or heavy AST comparison for shortlisted pairs.'
        : 'Keep speed guardrails in place while improving accuracy metrics.',
    },
  ];

  return metrics.map((metric) => ({
    ...metric,
    tone: metricTone(Number(metric.value || 0), metric.mode),
  }));
}
// ── Step indicator ──────────────────────────────────────────────────────────
function StepIndicator({ steps, currentStep, completedSteps, compact = false }) {
  return (
    <div className={`flex items-center gap-0 ${compact ? '' : 'mb-8'}`}>
      {steps.map((step, idx) => {
        const isCompleted = completedSteps.includes(idx);
        const isCurrent = currentStep === idx;
        const isLast = idx === steps.length - 1;
        return (
          <div key={idx} className="flex items-center flex-1 last:flex-none">
            <div className={`flex items-center ${compact ? 'gap-2 px-3 py-2 rounded-2xl' : 'gap-3 px-4 py-3 rounded-xl'} transition-all duration-200 ${isCurrent ? 'bg-violet-600 shadow-lg shadow-violet-500/25' :
              isCompleted ? 'bg-emerald-50 border border-emerald-200' :
                'bg-white border border-slate-200'
              }`}>
              <div className={`${compact ? 'w-6 h-6 text-[11px]' : 'w-7 h-7 text-xs'} rounded-full flex items-center justify-center font-bold shrink-0 ${isCurrent ? 'bg-white/20 text-white' :
                isCompleted ? 'bg-emerald-500 text-white' :
                  'bg-slate-100 text-slate-400'
                }`}>
                {isCompleted ? <Check size={13} /> : idx + 1}
              </div>
              <div>
                <div className={`${compact ? 'text-[11px]' : 'text-xs'} font-bold uppercase tracking-wide ${isCurrent ? 'text-white' : isCompleted ? 'text-emerald-700' : 'text-slate-400'
                  }`}>{step.label}</div>
                <div className={`${compact ? 'hidden' : 'text-xs mt-0.5 hidden sm:block'} ${isCurrent ? 'text-violet-200' : isCompleted ? 'text-emerald-500' : 'text-slate-400'
                  }`}>{step.subtitle}</div>
              </div>
            </div>
            {!isLast && (
              <div className={`h-px flex-1 ${compact ? 'mx-1.5' : 'mx-2'} ${completedSteps.includes(idx) ? 'bg-emerald-300' : 'bg-slate-200'
                }`} />
            )}
          </div>
        );
      })}
    </div>
  );
}
function ToolSelectionStep({ tools, selectedTools, setSelectedTools, onNext, loading, error }) {
  const [activeEngines, setActiveEngines] = useState([]);
  const engineFilters = Array.from(new Set(tools.flatMap((tool) => tool.engines ?? []))).sort();

  const visibleTools = activeEngines.length
    ? tools.filter((tool) => activeEngines.some((engine) => tool.engines.includes(engine)))
    : tools;
  const runnableTools = tools.filter((tool) => tool.available !== false && tool.runnable !== false);

  const toggleTool = (tool) => {
    if (tool.available === false || tool.runnable === false) return;
    setSelectedTools(prev =>
      prev.includes(tool.id) ? prev.filter(t => t !== tool.id) : [...prev, tool.id]
    );
  };

  const toggleEngine = (engine) => setActiveEngines((prev) =>
    prev.includes(engine) ? prev.filter((item) => item !== engine) : [...prev, engine]
  );



  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="px-6 py-5 border-b border-slate-100 flex items-center justify-between">
        <div>
          <h2 className="font-semibold text-slate-900 flex items-center gap-2">
            <Settings2 size={18} className="text-violet-500" />
            Select Detection Tools
          </h2>
        </div>
        <div className="flex items-center gap-3">
          <span className={`text-sm font-semibold px-3 py-1.5 rounded-lg ${selectedTools.length > 0 ? 'bg-violet-50 text-violet-700' : 'bg-slate-100 text-slate-400'
            }`}>{selectedTools.length} / {runnableTools.length} selected</span>
           <div className="flex gap-1">
             <button onClick={() => setSelectedTools(runnableTools.map(t => t.id))} className="text-xs font-medium text-slate-500 hover:text-slate-700 px-3 py-1.5 rounded-lg hover:bg-slate-50 transition-colors">Select All</button>
             <button onClick={() => setSelectedTools([])} className="text-xs font-medium text-slate-500 hover:text-slate-700 px-3 py-1.5 rounded-lg hover:bg-slate-50 transition-colors">Clear</button>
           </div>
        </div>
      </div>
      <div className="p-6">
        {loading && (
          <div className="mb-5 rounded-2xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-4 py-3 text-sm text-slate-600 dark:text-slate-300">
            Checking which benchmark tools are available in this environment…
          </div>
        )}
        {error && (
          <div className="mb-5 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            {error}
          </div>
        )}

        <div className="mb-5 rounded-2xl border border-slate-200 dark:border-slate-700 bg-slate-50/70 dark:bg-slate-800/70 p-4">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
            <div className="min-w-0">
              <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Filter By Engine</div>
              <div className="mt-3 flex flex-wrap gap-2">
                {engineFilters.map((engine) => {
                  const active = activeEngines.includes(engine);
                  return (
                    <button
                      key={engine}
                      onClick={() => toggleEngine(engine)}
                      className={`rounded-full border px-3 py-1.5 text-xs font-semibold uppercase tracking-wide transition ${active
                        ? 'border-violet-500 bg-violet-600 text-white shadow-lg shadow-violet-500/20'
                        : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'
                        }`}
                    >
                      {engine}
                    </button>
                  );
                })}
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {activeEngines.length > 0 && (
                <button onClick={() => setActiveEngines([])} className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 transition hover:border-slate-300">
                  Show All Engines
                </button>
              )}
            </div>
          </div>
        </div>

        {visibleTools.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-200 dark:border-slate-600 bg-slate-50/60 dark:bg-slate-800/60 px-6 py-10 text-center">
            <div className="text-sm font-semibold text-slate-700">No tools match the selected engines.</div>
            <div className="mt-2 text-sm text-slate-500">Try clearing one or more engine filters to widen the comparison set.</div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 xl:grid-cols-4 gap-3">
            {visibleTools.map(tool => {
              const isSelected = selectedTools.includes(tool.id);
              const canRun = tool.available !== false && tool.runnable !== false;
              return (
                <button key={tool.id} onClick={() => toggleTool(tool)} disabled={!canRun}
                  className={`relative p-4 rounded-xl border-2 text-left transition-all duration-200 group ${!canRun
                    ? 'border-slate-200 bg-slate-50 opacity-70 cursor-not-allowed'
                    : isSelected
                    ? `border-transparent ring-2 ${tool.ring} ring-offset-2 ${tool.bgLight}`
                    : 'border-slate-200 hover:border-slate-300 bg-white hover:shadow-sm'
                    }`}>
                  {isSelected && (
                    <div className="absolute top-2 right-2">
                      <CheckCircle2 size={16} className={tool.textColor} />
                    </div>
                  )}
                  <div className={`w-9 h-9 rounded-lg bg-gradient-to-br ${tool.gradient} flex items-center justify-center mb-3 shadow-sm`}>
                    <Zap size={16} className="text-white" />
                  </div>
                  <div className="font-semibold text-sm text-slate-900">{tool.name}</div>
                  <div className={`mt-1 text-[11px] font-semibold ${canRun ? 'text-emerald-600' : 'text-amber-600'}`}>
                    {tool.status || (canRun ? 'Ready to run' : 'Setup needed')}
                  </div>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    {tool.engines.slice(0, 3).map((engine) => (
                      <span
                        key={engine}
                        className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${isSelected ? 'border-current/20 bg-white/70' : 'border-slate-200 bg-slate-50 text-slate-500'
                          }`}
                      >
                        {engine}
                      </span>
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
        <button onClick={onNext} disabled={selectedTools.length === 0}
          className="flex items-center gap-2 px-6 py-3 bg-violet-600 hover:bg-violet-700 disabled:bg-slate-200 disabled:text-slate-400 text-white font-semibold rounded-xl transition-all shadow-lg shadow-violet-500/25 hover:shadow-xl disabled:shadow-none">
          Continue to Dataset
          <ChevronRight size={18} />
        </button>
      </div>
    </div>
  );
}

// ── Step 2: Dataset Selection ───────────────────────────────────────────────
function DatasetStep({ selectedDataset, setSelectedDataset, uploadMode, setUploadMode, files, setFiles, benchmarkDatasets, canManageDemoDatasets, benchmarkMode, onBack, onNext }) {
  const [libraryFilter, setLibraryFilter] = useState('all');
  const [languageFilter, setLanguageFilter] = useState('all');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [creatingDataset, setCreatingDataset] = useState(false);
  const [datasetForm, setDatasetForm] = useState({
    name: '',
    description: '',
    language: 'python',
    numFiles: 10,
    similarityType: 'type1_exact',
  });

  const handleDatasetFormChange = useCallback((field: string, value: string | number) => {
    setDatasetForm(prev => ({ ...prev, [field]: value }));
  }, []);

  const createDemoDataset = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setCreatingDataset(true);

    try {
      await axios.post(`${API}/api/admin/create-demo-dataset`, datasetForm, { withCredentials: true });
      setShowCreateModal(false);
      setDatasetForm({
        name: '',
        description: '',
        language: 'python',
        numFiles: 10,
        similarityType: 'type1_exact',
      });
    } catch (error) {
      console.error('Demo dataset creation error:', error);
    } finally {
      setCreatingDataset(false);
    }
  };

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setFiles(Array.from(e.dataTransfer.files));
  }, [setFiles]);

  const handleDragOver = (e) => e.preventDefault();

  const { presetDatasets, demoDatasets, allDatasets } = useMemo(
    () => buildDatasetLibrary(benchmarkDatasets),
    [benchmarkDatasets]
  );
  const panRequiresGroundTruth = benchmarkMode === 'pan_optimization';
  const labeledDatasets = allDatasets.filter((dataset) => dataset.has_ground_truth);

  const availableLanguages = useMemo(() => {
    const langs = new Set(allDatasets.map(d => d.language?.toLowerCase() || 'mixed').filter(Boolean));
    return Array.from(langs).sort();
  }, [allDatasets]);

  const visibleLibraryDatasets = allDatasets.filter((dataset) => {
    if (panRequiresGroundTruth && !dataset.has_ground_truth) {
      return false;
    }
    if (libraryFilter === 'preset') {
      return dataset.datasetType === 'preset';
    }
    if (libraryFilter === 'demo') {
      return dataset.datasetType === 'demo';
    }
    return true;
  }).filter((dataset) => {
    if (languageFilter === 'all') return true;
    return dataset.language?.toLowerCase() === languageFilter.toLowerCase();
  });
  const activeDataset = allDatasets.find((dataset) => dataset.id === selectedDataset);
  const activeDatasetMeta = getDatasetCategoryMeta(activeDataset);
  const activePresetMeta = getPresetDatasetMeta(activeDataset);
  const hasZipUpload = files.some((file) => file.name?.toLowerCase().endsWith('.zip'));
  const canProceed = uploadMode === 'builtin'
    ? !!selectedDataset && (!panRequiresGroundTruth || activeDataset?.has_ground_truth)
    : !panRequiresGroundTruth && (hasZipUpload || files.length >= 2);

  return (
    <div className="space-y-5">
      {/* Mode tabs */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-5 border-b border-slate-100">
          <h2 className="font-semibold text-slate-900 flex items-center gap-2">
            <Database size={18} className="text-violet-500" />
            Choose What To Benchmark
          </h2>
          <p className="text-sm text-slate-500 mt-0.5">
            {benchmarkMode === 'pan_optimization'
              ? 'Choose labeled PAN-style data for detector optimization, or upload controlled test files.'
              : 'Choose a reusable dataset for tool comparison, or upload professor-facing evidence files.'}
          </p>
        </div>
        <div className="flex border-b border-slate-100">
          {[
            { id: 'builtin', label: 'Dataset Library', icon: FlaskConical },
            { id: 'upload', label: 'Upload Files or ZIP', icon: FileUp },
          ].map(({ id, label, icon: Icon }) => {
            const disabled = panRequiresGroundTruth && id === 'upload';
            return (
            <button key={id} disabled={disabled} onClick={() => { if (disabled) return; setUploadMode(id); setFiles([]); if (id !== 'builtin') setSelectedDataset(null); }}
              className={`flex items-center gap-2 px-5 py-3.5 text-sm font-medium border-b-2 transition-colors ${disabled
                ? 'cursor-not-allowed border-transparent text-slate-300'
                : uploadMode === id ? 'border-violet-500 text-violet-700 bg-violet-50/50' : 'border-transparent text-slate-500 hover:text-slate-700'
                }`}>
              <Icon size={15} />
              {label}
            </button>
            );
          })}
        </div>

        <div className="p-6">
          {panRequiresGroundTruth && (
            <div className="mb-5 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm leading-6 text-emerald-800">
              PAN Optimization uses only labeled datasets. Select a dataset with the Labeled badge to compute Precision, Recall, F1, Granularity, and PlagDet.
            </div>
          )}
          {uploadMode === 'builtin' && (
            <div className="space-y-6">
               <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-slate-50/80 dark:bg-slate-800/80 p-5">
                 <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between mb-4">
                   <div>
                     <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Dataset Library</p>
                   </div>
                 </div>

                 <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-1">
                    {[
                      { id: 'all', label: 'All', count: panRequiresGroundTruth ? labeledDatasets.length : allDatasets.length },
                      { id: 'preset', label: 'Preset', count: panRequiresGroundTruth ? presetDatasets.filter(d => d.has_ground_truth).length : presetDatasets.length },
                      { id: 'demo', label: 'Demo', count: panRequiresGroundTruth ? demoDatasets.filter(d => d.has_ground_truth).length : demoDatasets.length },
                    ].map((filter) => (
                      <button
                        key={filter.id}
                        onClick={() => setLibraryFilter(filter.id)}
                        className={`rounded-full px-3 py-1.5 text-xs font-semibold transition ${libraryFilter === filter.id
                          ? 'bg-slate-900 text-white'
                          : 'border border-slate-200 bg-white text-slate-600 hover:border-slate-300'
                          }`}
                      >
                        {filter.label} ({filter.count})
                      </button>
                    ))}
                  </div>
                  {availableLanguages.length > 0 && (
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => setLanguageFilter('all')}
                        className={`rounded-full px-3 py-1.5 text-xs font-semibold transition ${languageFilter === 'all'
                          ? 'bg-slate-900 text-white'
                          : 'border border-slate-200 bg-white text-slate-600 hover:border-slate-300'
                          }`}
                      >
                        All Languages
                      </button>
                      {availableLanguages.map(lang => (
                        <button
                          key={lang}
                          onClick={() => setLanguageFilter(lang)}
                          className={`rounded-full px-3 py-1.5 text-xs font-semibold transition capitalize ${languageFilter === lang
                            ? 'bg-slate-900 text-white'
                            : 'border border-slate-200 bg-white text-slate-600 hover:border-slate-300'
                            }`}
                        >
                          {lang}
                        </button>
                      ))}
                    </div>
                  )}
                  {!canManageDemoDatasets && (
                    <div className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-500">
                      Need another demo? Ask an administrator to create one.
                    </div>
                  )}
                </div>

                 {visibleLibraryDatasets.length > 0 || (libraryFilter === 'demo' && canManageDemoDatasets) ? (
                   <div className={`mt-5 grid gap-4 ${libraryFilter === 'demo' && visibleLibraryDatasets.length === 0 && canManageDemoDatasets ? 'grid-cols-1 md:grid-cols-1 xl:grid-cols-1 max-w-md mx-auto' : 'grid-cols-1 md:grid-cols-2 xl:grid-cols-3'}`}>
                     {visibleLibraryDatasets.map((dataset) => {
                       const isActive = selectedDataset === dataset.id;
                       return <DatasetCard key={dataset.id} dataset={dataset} isActive={isActive} onSelect={setSelectedDataset} />;
                     })}
                     {canManageDemoDatasets && libraryFilter !== 'preset' && (
                       <button
                         onClick={() => setShowCreateModal(true)}
                         className="relative rounded-2xl border-2 border-dashed border-slate-300 p-4 text-left transition-all duration-200 bg-slate-50 hover:border-blue-400 hover:bg-blue-50/70 flex flex-col items-center justify-center min-h-[200px]"
                       >
                         <div className="w-12 h-12 rounded-full bg-blue-100 flex items-center justify-center mb-3">
                           <Plus size={24} className="text-blue-600" />
                         </div>
                         <div className="text-base font-semibold text-slate-700">Create Demo Dataset</div>
                         <div className="text-sm text-slate-500 mt-1">Generate a new synthetic benchmark dataset</div>
                       </button>
                     )}
                   </div>
                 ) : (
                   <div className="mt-5 rounded-2xl border border-dashed border-slate-300 bg-white px-5 py-6">
                     <div className="text-sm font-semibold text-slate-900">
                      {libraryFilter === 'demo' ? 'No demo datasets yet' : 'No datasets match this filter'}
                     </div>
                     <div className="mt-2 text-sm leading-6 text-slate-500">
                       {panRequiresGroundTruth
                         ? 'No labeled datasets match this filter. Choose All or Preset to use Clough-Stevenson-style, synthetic, Kaggle student code, CodeXGLUE clone, or another labeled benchmark.'
                         : libraryFilter === 'demo'
                         ? 'Preset datasets are ready to use now. When you want course-specific examples, create a demo dataset and it will appear here automatically.'
                         : 'Try another filter or switch to Upload Your Own for a one-off comparison.'}
                     </div>
                   </div>
                 )}
              </div>

              {activeDataset && (
                <div className={`rounded-2xl border p-5 ${activeDatasetMeta.panelClass}`}>
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                        Selected dataset
                      </p>
                      <div className="mt-2 flex items-center gap-3">
                        <span className="text-2xl">{activeDataset.icon}</span>
                        <div>
                          <div className="text-lg font-semibold text-slate-900">{activeDataset.name}</div>
                          <div className="text-sm text-slate-600">{activePresetMeta?.presetCategory || activeDatasetMeta.label}</div>
                        </div>
                      </div>
                    </div>
                    <span className={`rounded-full px-3 py-1 text-xs font-semibold ${activeDatasetMeta.badgeClass}`}>
                      {activePresetMeta?.badgeLabel || activeDatasetMeta.summaryLabel}
                    </span>
                  </div>

                  <div className="mt-4 text-sm leading-6 text-slate-600">{activeDataset.desc}</div>
                  {activePresetMeta?.summary && (
                    <div className="mt-3 text-sm text-slate-500">{activePresetMeta.summary}</div>
                  )}
                  {activeDataset.benchmark_quality && (
                    <div className="mt-4 rounded-2xl border border-emerald-200 bg-white p-4">
                      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                        <div>
                          <div className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-600">
                            Benchmark Quality Certificate
                          </div>
                          <div className="mt-2 text-sm leading-6 text-slate-600">
                            {activeDataset.benchmark_quality.pair_count} labeled pairs,
                            {' '}{activeDataset.benchmark_quality.positive_pairs} positives,
                            {' '}{activeDataset.benchmark_quality.negative_pairs} negatives,
                            {' '}{activeDataset.benchmark_quality.hard_negative_pairs} hard negatives.
                          </div>
                        </div>
                        <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700">
                          {Number(activeDataset.benchmark_quality.score_percent || 0).toFixed(0)}% gates passed
                        </span>
                      </div>
                      <div className="mt-3 grid gap-2 md:grid-cols-2">
                        {(activeDataset.benchmark_quality.gates || []).map((gate) => (
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
                          <div className={`w-2 h-2 rounded-full shrink-0 ${tc.expected >= 0.9 ? 'bg-red-500' : tc.expected >= 0.7 ? 'bg-amber-500' : tc.expected >= 0.4 ? 'bg-yellow-500' : 'bg-emerald-500'
                            }`} />
                          <div className="min-w-0">
                            <div className="text-xs font-semibold text-slate-800 truncate">{tc.label}</div>
                            <div className="text-xs text-slate-400">~{(tc.expected * 100).toFixed(0)}% expected</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="mt-5 space-y-3">
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        <div className="bg-white rounded-lg border border-slate-200 px-3 py-2.5 text-center">
                          <div className={`text-lg font-bold ${activeDatasetMeta.accentClass}`}>{activeDataset.language || 'Mixed'}</div>
                          <div className="text-xs text-slate-500">Language</div>
                        </div>
                        <div className="bg-white rounded-lg border border-slate-200 px-3 py-2.5 text-center">
                          <div className={`text-lg font-bold ${activeDatasetMeta.accentClass}`}>{activeDataset.size || 'Unknown'}</div>
                          <div className="text-xs text-slate-500">{activeDataset.is_demo ? 'Files' : 'Size'}</div>
                        </div>
                        <div className="bg-white rounded-lg border border-slate-200 px-3 py-2.5 text-center">
                          <div className={`text-lg font-bold ${activeDatasetMeta.accentClass}`}>
                            {activeDataset.is_demo
                              ? formatDatasetDate(activeDataset.created_at)
                              : (activePresetMeta?.presetCategory || activeDataset.similarity_type || 'Standard')}
                          </div>
                          <div className="text-xs text-slate-500">{activeDataset.is_demo ? 'Created' : 'Recommended Use'}</div>
                        </div>
                        <div className="bg-white rounded-lg border border-slate-200 px-3 py-2.5 text-center">
                          <div className={`text-lg font-bold ${activeDatasetMeta.accentClass}`}>{activeDataset.created_by || 'System'}</div>
                          <div className="text-xs text-slate-500">{activeDataset.is_demo ? 'Created By' : 'Source'}</div>
                        </div>
                      </div>
                      <div className="rounded-lg border border-white/70 bg-white/80 p-3 text-sm text-slate-600">
                        {activeDataset.is_demo
                          ? 'This demo dataset was created inside the app and is meant for reusable classroom examples, workshops, and faculty demos.'
                          : 'This dataset is part of the system benchmark library and is best for larger, more standardized tool comparisons.'}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {uploadMode === 'upload' && (
            <div>
              <div
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onClick={() => document.getElementById('file-input').click()}
                className="border-2 border-dashed border-slate-300 rounded-2xl p-10 text-center cursor-pointer hover:border-violet-400 hover:bg-violet-50/30 transition-all group"
              >
                <input id="file-input" type="file" className="hidden" multiple
                  accept=".zip,.py,.java,.c,.cpp,.h,.hpp,.js,.ts,.jsx,.tsx,.go,.rs,.rb,.php,.cs,.kt,.swift,.scala,.r,.m,.sql,.sh,.bash,.zsh,.ps1,.lua,.pl,.pm,.ex,.exs,.dart,.clj,.hs,.ml,.fs,.erl,.vue,.svelte"
                  onChange={e => setFiles(Array.from(e.target.files))} />
                <UploadCloud size={40} className="mx-auto text-slate-300 group-hover:text-violet-400 transition-colors mb-4" />
                <p className="font-semibold text-slate-600 mb-1">
                  Drop source files or a ZIP archive here
                </p>
                <p className="text-sm text-slate-400">
                  Upload 2 or more source files, or a single ZIP containing source files for one-off comparison
                </p>
                <div className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm text-slate-600 group-hover:border-violet-300 transition-colors">
                  <FileUp size={14} />
                  Browse files
                </div>
              </div>

              {files.length > 0 && (
                <div className="mt-4 bg-slate-50 rounded-xl border border-slate-200 divide-y divide-slate-100 overflow-hidden">
                  {files.map((f, i) => (
                    <div key={i} className="flex items-center gap-3 px-4 py-2.5 group/file hover:bg-white transition-colors">
                      <div className="w-6 h-6 rounded-md bg-emerald-100 flex items-center justify-center shrink-0">
                        <FileUp size={12} className="text-emerald-600" />
                      </div>
                      <span className="text-sm font-medium text-slate-700 truncate flex-1">{f.name}</span>
                      <span className="text-xs text-slate-400 shrink-0">{(f.size / 1024).toFixed(1)} KB</span>
                      <button onClick={() => setFiles(files.filter((_, j) => j !== i))} className="opacity-0 group-hover/file:opacity-100 text-slate-300 hover:text-red-500 transition-all">
                        <X size={14} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              {files.length > 0 && !hasZipUpload && files.length < 2 && (
                <p className="text-xs text-amber-600 mt-2 flex items-center gap-1.5">
                  <AlertCircle size={13} /> Upload at least 2 source files, or use a ZIP archive
                </p>
              )}
              {panRequiresGroundTruth && (
                <p className="text-xs text-amber-600 mt-2 flex items-center gap-1.5">
                  <AlertCircle size={13} /> PAN metrics require labeled ground truth, so uploads are available only in Tool Comparison mode.
                </p>
              )}
            </div>
          )}
        </div>
      </div>

       <div className="flex items-center justify-between">
         <button onClick={onBack} className="flex items-center gap-2 px-5 py-2.5 bg-white border border-slate-200 text-slate-600 hover:text-slate-800 font-medium rounded-xl hover:border-slate-300 transition-all text-sm">
           ← Back
         </button>
         <button onClick={onNext} disabled={!canProceed}
           className="flex items-center gap-2 px-6 py-3 bg-violet-600 hover:bg-violet-700 disabled:bg-slate-200 disabled:text-slate-400 text-white font-semibold rounded-xl transition-all shadow-lg shadow-violet-500/25 hover:shadow-xl disabled:shadow-none">
           Ready to Run
           <ChevronRight size={18} />
         </button>
       </div>

       {/* Create Demo Dataset Modal */}
       {showCreateModal && (
         <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
           <div className="bg-white rounded-[30px] shadow-2xl max-w-3xl w-full p-8">
             <div className="flex items-start justify-between mb-6">
               <div>
                 <div className="inline-flex items-center gap-2 rounded-full border border-emerald-600/10 bg-emerald-600/[0.06] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-emerald-600 mb-3">
                   <Database size={14} />
                   Dataset Tools
                 </div>
                 <h3 className="text-2xl font-semibold text-slate-900">Demo dataset creation</h3>
                 <p className="mt-2 text-sm text-slate-600 max-w-xl">
                   Generate synthetic datasets for testing plagiarism detection algorithms. Create custom datasets with controlled similarity patterns.
                 </p>
               </div>
               <button
                 onClick={() => {
                   setShowCreateModal(false);
                   setDatasetForm({
                     name: '',
                     description: '',
                     language: 'python',
                     numFiles: 10,
                     similarityType: 'type1_exact',
                   });
                 }}
                 className="p-2 hover:bg-slate-100 rounded-xl transition text-slate-500"
               >
                 ✕
               </button>
             </div>

             <form className="space-y-6 mt-6" onSubmit={createDemoDataset}>
               <div className="grid gap-4 sm:grid-cols-2">
                 <div>
                   <label className="block text-sm font-medium text-slate-700 mb-1">Dataset Name</label>
                   <input
                     type="text"
                     value={datasetForm.name}
                     onChange={(event) => handleDatasetFormChange('name', event.target.value)}
                     className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                     placeholder="my_test_dataset"
                     required
                   />
                 </div>
                 <div>
                   <label className="block text-sm font-medium text-slate-700 mb-1">Programming Language</label>
                   <select
                     value={datasetForm.language}
                     onChange={(event) => handleDatasetFormChange('language', event.target.value)}
                     className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                   >
                     <option value="python">Python</option>
                     <option value="java">Java</option>
                     <option value="javascript">JavaScript</option>
                     <option value="cpp">C++</option>
                   </select>
                 </div>
               </div>

               <div>
                 <label className="block text-sm font-medium text-slate-700 mb-1">Description</label>
                 <input
                   type="text"
                   value={datasetForm.description}
                   onChange={(event) => handleDatasetFormChange('description', event.target.value)}
                   className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                   placeholder="Dataset for testing plagiarism detection"
                 />
               </div>

               <div className="grid gap-4 sm:grid-cols-2">
                 <div>
                   <label className="block text-sm font-medium text-slate-700 mb-1">Number of Files</label>
                   <input
                     type="number"
                     min="5"
                     max="100"
                     value={datasetForm.numFiles}
                     onChange={(event) => handleDatasetFormChange('numFiles', parseInt(event.target.value) || 10)}
                     className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                   />
                 </div>
                 <div>
                   <label className="block text-sm font-medium text-slate-700 mb-1">Similarity Type</label>
                   <select
                     value={datasetForm.similarityType}
                     onChange={(event) => handleDatasetFormChange('similarityType', event.target.value)}
                     className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                   >
                     <option value="type1_exact">Type 1 - Exact Copy</option>
                     <option value="type2_renamed">Type 2 - Renamed Identifiers</option>
                     <option value="type3_modified">Type 3 - Modified Structure</option>
                     <option value="type4_semantic">Type 4 - Semantic Equivalence</option>
                     <option value="token_similarity">Token-Level Similarity</option>
                     <option value="structural_similarity">Structural Similarity</option>
                     <option value="semantic_similarity">Semantic Similarity</option>
                   </select>
                 </div>
               </div>

               <div className="mt-8 flex justify-end gap-3">
                 <button
                   type="button"
                   onClick={() => {
                     setShowCreateModal(false);
                     setDatasetForm({
                       name: '',
                       description: '',
                       language: 'python',
                       numFiles: 10,
                       similarityType: 'type1_exact',
                     });
                   }}
                   className="px-5 py-3 text-slate-700 hover:bg-slate-100 rounded-xl transition font-medium"
                 >
                   Cancel
                 </button>
                 <button
                   type="submit"
                   disabled={creatingDataset || !datasetForm.name.trim()}
                   className="px-8 py-3 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 text-white rounded-xl transition flex items-center gap-3 font-semibold min-w-[200px] justify-center"
                 >
                   {creatingDataset ? (
                     <>
                       <Loader2 size={18} className="animate-spin" />
                       Generating code samples...
                     </>
                   ) : (
                     'Create Demo Dataset'
                   )}
                 </button>
               </div>
            </form>
          </div>
        </div>
      )}

     </div>
   );
}

// ── Step 3: Run ─────────────────────────────────────────────────────────────
function RunStep({ selectedTools, selectedDataset, uploadMode, files, benchmarkDatasets, benchmarkMode, selectedPreset, onBack, onComplete }) {
  const { token } = useAuth();
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState('');
  const [progressPct, setProgressPct] = useState(0);
  const [currentFile, setCurrentFile] = useState(null);
  const [totalFiles, setTotalFiles] = useState(null);
  const [currentFilename, setCurrentFilename] = useState(null);
  const [currentEngine, setCurrentEngine] = useState(null);
  const [error, setError] = useState('');
  const requestControllerRef = useRef(null);

  const { allDatasets } = useMemo(
    () => buildDatasetLibrary(benchmarkDatasets),
    [benchmarkDatasets]
  );
  const activeDataset = allDatasets.find((dataset) => dataset.id === selectedDataset);
  const activeDatasetMeta = activeDataset ? getDatasetCategoryMeta(activeDataset) : null;
  const hasZipUpload = files.some((file) => file.name?.toLowerCase().endsWith('.zip'));

  const createRequestOptions = () => ({
    headers: { 'Content-Type': 'multipart/form-data' },
    withCredentials: true,
    signal: requestControllerRef.current?.signal,
  });

  const run = async () => {
    requestControllerRef.current?.abort();
    const controller = new AbortController();
    requestControllerRef.current = controller;
    setError('');
    setRunning(true);
    setProgressPct(10);

    try {
      if (uploadMode === 'builtin' && activeDataset) {
        if (activeDataset.cases) {
          // Run all interactive test cases.
          const allResults = [];
          const cases = activeDataset.cases;

          for (let i = 0; i < cases.length; i++) {
            const tc = cases[i];
            setProgress(`Running "${tc.label}" (${i + 1}/${cases.length})…`);
            setProgressPct(10 + ((i / cases.length) * 80));

            const blobA = new Blob([tc.codeA], { type: 'text/plain' });
            const blobB = new Blob([tc.codeB], { type: 'text/plain' });
            const fileA = new File([blobA], `${tc.id}_a.py`);
            const fileB = new File([blobB], `${tc.id}_b.py`);

            const formData = new FormData();
            formData.append('files', fileA);
            formData.append('files', fileB);
            formData.append('benchmark_type', benchmarkMode);
            if (selectedPreset?.id) formData.append('preset_id', selectedPreset.id);
            selectedTools.forEach(t => formData.append('tools', t));

            try {
              const res = await axios.post(`${API}/api/benchmark`, formData, createRequestOptions());
              allResults.push({ testCase: tc, ...res.data });
            } catch (err) {
              if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') {
                break;
              }
              // Continue with other cases
            }
          }

          if (allResults.length > 0) {
            setProgressPct(100);
            setProgress('Complete!');
            // Merge results without mutating the original response
            const merged = { ...allResults[0], pair_results: allResults.flatMap(r => r.pair_results || []) };
            setTimeout(() => onComplete({ ...merged, datasetName: activeDataset.name, runAt: new Date().toISOString() }), 400);
          }
        } else {
          // Handle backend-provided datasets, including generated demo datasets.
          setProgress('Loading dataset...');
          setProgressPct(30);
          const formData = new FormData();
          selectedTools.forEach(t => formData.append('tools', t));
          formData.append('dataset', activeDataset.id);
          formData.append('benchmark_type', benchmarkMode);
          if (selectedPreset?.id) formData.append('preset_id', selectedPreset.id);

          try {
            setProgress('Running benchmark analysis...');
            setProgressPct(50);

            const res = await axios.post(`${API}/api/benchmark`, formData, createRequestOptions());

            setProgressPct(100);
            setProgress('Complete!');
            onComplete({ ...res.data, datasetName: activeDataset.name, runAt: new Date().toISOString() });
          } catch (err) {
            setError(err.response?.data?.error || 'Failed to run benchmark on the selected dataset');
            setProgress('Error occurred');
          }
        }
      } else {
        // Upload mode
        setProgress('Uploading files…');
        setProgressPct(20);
        const formData = new FormData();
        files.forEach(f => formData.append('files', f));
        formData.append('benchmark_type', benchmarkMode);
        if (selectedPreset?.id) formData.append('preset_id', selectedPreset.id);
        selectedTools.forEach(t => formData.append('tools', t));

        setProgress('Running analysis across all tools…');
        setProgressPct(50);
        const res = await axios.post(`${API}/api/benchmark`, formData, createRequestOptions());
        setProgressPct(100);
        setProgress('Complete!');
        setTimeout(() => onComplete({ ...res.data, runAt: new Date().toISOString() }), 400);
      }
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') {
        setProgress('Run cancelled');
      } else {
        console.error('Benchmark error:', err);
        setError(err.response?.data?.error || err.message || 'Benchmark failed. Please try again.');
      }
    } finally {
      // Only clear the ref if it matches the controller that started this invocation
      if (requestControllerRef.current === controller) {
        requestControllerRef.current = null;
      }
      setRunning(false);
    }
  };

  const stop = () => {
    requestControllerRef.current?.abort();
    setRunning(false);
    setProgress('Cancelling run…');
    setProgressPct(0);
  };

  return (
    <div className="space-y-5">
      {/* Summary card */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <h2 className="font-semibold text-slate-900 flex items-center gap-2 mb-5">
          <ClipboardList size={18} className="text-violet-500" />
          Benchmark Configuration
        </h2>
        <div className="grid md:grid-cols-2 gap-4">
          <div className="bg-slate-50 rounded-xl p-4 border border-slate-100">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Tools</p>
            <div className="flex flex-wrap gap-1.5">
              {selectedTools.slice(0, 6).map(id => {
                const t = TOOLS.find(x => x.id === id);
                return t ? (
                  <span key={id} className={`text-xs font-medium px-2.5 py-1 rounded-lg ${t.bgLight} ${t.textColor}`}>{t.name}</span>
                ) : null;
              })}
              {selectedTools.length > 6 && (
                <span className="text-xs font-medium px-2.5 py-1 rounded-lg bg-slate-200 text-slate-600">+{selectedTools.length - 6} more</span>
              )}
            </div>
          </div>
          <div className="bg-slate-50 rounded-xl p-4 border border-slate-100">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Dataset</p>
            {uploadMode === 'builtin' ? (
              <>
                <p className="font-semibold text-slate-800 text-sm">{activeDataset?.name || 'Unknown'}</p>
                <p className="text-xs text-slate-500 mt-1">
                  {activeDataset?.cases?.length
                    ? `${activeDataset.cases.length} guided scenarios`
                    : activeDatasetMeta?.label || 'Dataset library'}
                </p>
              </>
            ) : (
              <>
                <p className="font-semibold text-slate-800 text-sm">{files.length} uploaded file{files.length !== 1 ? 's' : ''}</p>
                <p className="text-xs text-slate-500 mt-1">{hasZipUpload ? 'ZIP archive or mixed upload' : 'Direct file upload'}</p>
              </>
            )}
          </div>
          {selectedPreset && (
            <div className="bg-violet-50 rounded-xl p-4 border border-violet-100 md:col-span-2">
              <p className="text-xs font-semibold text-violet-400 uppercase tracking-wider mb-2">Workflow Preset</p>
              <p className="font-semibold text-violet-900 text-sm">{selectedPreset.name}</p>
              <p className="text-xs text-violet-700 mt-1">{selectedPreset.cadence}</p>
            </div>
          )}
        </div>
      </div>

      {/* Run control */}
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
               <p className="text-sm font-medium text-slate-700 flex items-center gap-2">
                 <Loader2 size={15} className="text-violet-600 animate-spin" />
                 {progress}
               </p>
               <span className="text-sm font-bold text-violet-600">{Math.round(progressPct)}%</span>
             </div>
             <div className="h-2.5 bg-slate-100 rounded-full overflow-hidden mb-3">
               <div
                 className="h-full bg-gradient-to-r from-violet-500 to-blue-500 rounded-full transition-all duration-500"
                 style={{ width: `${progressPct}%` }}
               />
             </div>

             {/* Detailed progress counter */}
             {currentFile && totalFiles && (
               <div className="bg-slate-50 rounded-xl p-3 border border-slate-100">
                 <div className="flex items-center justify-between">
                   <div className="text-xs font-semibold text-slate-500">Processing</div>
                   <div className="text-xs font-bold text-violet-600">{currentFile} / {totalFiles}</div>
                 </div>
                 <div className="mt-1 text-sm font-medium text-slate-700 truncate">{currentFilename || 'Preparing files...'}</div>
                 {currentEngine && (
                   <div className="mt-1 text-xs text-slate-400">Running with {currentEngine}</div>
                 )}
               </div>
             )}
           </div>
         )}

        <div className="flex items-center gap-3">
          {!running ? (
            <button onClick={run}
              className="flex-1 flex items-center justify-center gap-3 py-4 bg-gradient-to-r from-violet-600 to-blue-600 hover:from-violet-700 hover:to-blue-700 text-white font-bold rounded-xl transition-all shadow-lg shadow-violet-500/25 hover:shadow-xl text-base">
              <Play size={20} />
              Start Benchmark
            </button>
          ) : (
            <button onClick={stop}
              className="flex-1 flex items-center justify-center gap-3 py-4 bg-red-500 hover:bg-red-600 text-white font-bold rounded-xl transition-all shadow-lg shadow-red-500/25 text-base">
              <Square size={18} />
              Stop
            </button>
          )}
        </div>
      </div>

      <div className="flex items-center justify-between">
        <button onClick={onBack} disabled={running} className="flex items-center gap-2 px-5 py-2.5 bg-white border border-slate-200 text-slate-600 hover:text-slate-800 font-medium rounded-xl hover:border-slate-300 transition-all text-sm disabled:opacity-50">
          ← Back
        </button>
      </div>
    </div>
  );
}

// ── Step 4: Report ──────────────────────────────────────────────────────────
function ReportStep({ results, onRestart }) {
  const [expandedPairs, setExpandedPairs] = useState({});
  const [currentPage, setCurrentPage] = useState(1);
  const [pdfDownloading, setPdfDownloading] = useState(false);
  const [pdfError, setPdfError] = useState('');
  const { tool_scores, pair_results, summary } = results;
  const itemsPerPage = 50;
  const totalPairs = (pair_results || []).length;
  const totalPages = Math.max(1, Math.ceil(totalPairs / itemsPerPage));
  const pageStart = (currentPage - 1) * itemsPerPage;
  const pageEnd = Math.min(pageStart + itemsPerPage, totalPairs);
  const visiblePairResults = (pair_results || []).slice(pageStart, pageEnd);
  const activeTools = Object.keys(tool_scores || {}).length
    ? Object.keys(tool_scores || {})
    : Array.from(new Set((pair_results || []).flatMap((pair) => (pair.tool_results || []).map((entry) => entry.tool))));

  const chartData = (pair_results || []).map(pair => {
    const d = { pair: pair.label };
    activeTools.forEach(t => {
      const tr = pair.tool_results?.find(r => r.tool === t);
      d[t] = tr ? Math.round(tr.score * 1000) / 10 : 0;
    });
    return d;
  });

  const toolLeaderboard = activeTools.map((tool) => {
    const toolInfo = TOOLS.find(t => t.id === tool);
    const scores = (pair_results || [])
      .map(pair => pair.tool_results?.find(r => r.tool === tool)?.score)
      .filter(score => typeof score === 'number');
    const average = scores.length
      ? scores.reduce((sum, score) => sum + score, 0) / scores.length
      : 0;
    const peak = scores.length ? Math.max(...scores) : 0;
    const minimum = scores.length ? Math.min(...scores) : 0;
    const spread = peak - minimum;

    return {
      id: tool,
      name: toolInfo?.name || tool,
      shortName: toolInfo?.name || tool,
      color: toolInfo?.color ?? '#94a3b8',
      average: Math.round(average * 1000) / 10,
      peak: Math.round(peak * 1000) / 10,
      minimum: Math.round(minimum * 1000) / 10,
      spread: Math.round(spread * 1000) / 10,
      pairCount: scores.length,
    };
  }).sort((a, b) => b.average - a.average);

  const leadingTool = toolLeaderboard[0] || null;
  const leadingToolInfo = leadingTool ? TOOLS.find((tool) => tool.id === leadingTool.id) : null;
  const panEvaluationRows = Object.entries(results.evaluation || {})
    .filter(([, metrics]) => metrics && !metrics.error)
    .map(([toolId, metrics]) => {
      const toolInfo = TOOLS.find((tool) => tool.id === toolId);
      const toolScoreMeta = results.tool_scores?.[toolId] || {};
      const f1Score = metrics.f1_score ?? metrics.best_f1 ?? 0;
      const plagdet = metrics.plagdet ?? f1Score;
      return {
        toolId,
        name: toolInfo?.name || metrics.tool || toolId,
        precision: Number(metrics.precision || 0),
        recall: Number(metrics.recall || 0),
        f1Score: Number(f1Score || 0),
        granularity: Number(metrics.granularity || 1),
        plagdet: Number(plagdet || 0),
        aucPr: Number(metrics.auc_pr ?? metrics.pr_auc ?? 0),
        falsePositiveRate: Number(metrics.false_positive_rate || 0),
        top10Retrieval: Number(metrics.top_10_retrieval || 0),
        top20Retrieval: Number(metrics.top_20_retrieval || 0),
        avgRuntimeSeconds: Number(metrics.avg_runtime_seconds ?? toolScoreMeta.avg_runtime_seconds ?? 0),
        engineContribution: metrics.engine_contribution || {},
        engineContributionText: formatEngineContribution(metrics.engine_contribution || {}),
        scoreDiagnostics: metrics.score_diagnostics || metrics.pan_metrics?.score_diagnostics || {},
        aiGeneratedRecall: metrics.ai_generated_recall,
        threshold: metrics.best_threshold,
      };
    })
    .sort((a, b) => b.plagdet - a.plagdet);
  const topPanResult = panEvaluationRows[0] || null;
  const integrityDeskPanResult = panEvaluationRows.find((row) => row.toolId === 'integritydesk') || null;
  const productPanResult = integrityDeskPanResult || topPanResult;
  const panFeedback = buildPanFeedback(productPanResult);
  const panMetricDiagnostics = buildPanMetricDiagnostics(productPanResult);
  const reportMode = results.benchmark_type || results.benchmarkMode || 'tool_comparison';
  const isPanOptimization = reportMode === 'pan_optimization';
  const hasGroundTruth = results.has_ground_truth !== false;
  const toolFailureRows = Object.entries(results.tool_scores || {})
    .filter(([, meta]) => meta?.error)
    .map(([toolId, meta]) => ({
      toolId,
      name: TOOLS.find((tool) => tool.id === toolId)?.name || toolId,
      error: String(meta.error || 'Tool did not return scores.'),
    }));
  const showMissingGroundTruthWarning = isPanOptimization && !hasGroundTruth;
  const showMissingPanScoresWarning = isPanOptimization && hasGroundTruth && panEvaluationRows.length === 0;
  const benchmarkSummary = results.summary || {};
  const benchmarkQuality = results.benchmark_quality || {};
  const datasetLabel = `${benchmarkSummary.dataset_name || results.datasetName || 'Dataset'} · ${benchmarkSummary.dataset_size || 0} submissions · ${benchmarkSummary.positive_pairs || 0} plagiarized pairs`;
  const optimizationLabel = `${benchmarkSummary.optimization_method || 'Threshold sweep, maximizing F1 / PlagDet'} · ${benchmarkSummary.optimization_trials || 0} trials · ${benchmarkSummary.cross_validation_folds || 1} fold`;
  const comparison = results.comparison || {};
  const comparisonDeltas = comparison.metrics || {};
  const summaryCards = [
    { icon: Layers, bg: 'bg-blue-50', color: 'text-blue-600', label: 'Tools Run', value: activeTools.length },
    { icon: Target, bg: 'bg-emerald-50', color: 'text-emerald-600', label: 'Pairs Tested', value: pair_results?.length || 0 },
    { icon: Trophy, bg: 'bg-amber-50', color: 'text-amber-600', label: 'Top Average', value: leadingTool ? `${leadingTool.average.toFixed(1)}%` : 'N/A' },
    { icon: TrendingUp, bg: 'bg-violet-50', color: 'text-violet-600', label: 'Comparison', value: 'Tools' },
  ];

  const togglePair = (idx) => setExpandedPairs(prev => ({ ...prev, [idx]: !prev[idx] }));

  const downloadJSON = () => {
    const blob = new Blob([JSON.stringify(results, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `benchmark-report-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const downloadCSV = () => {
    if (isPanOptimization && productPanResult) {
      const rows = [['Metric', 'Score', 'Status', 'Target', 'Why It Matters', 'Next Action']];
      panMetricDiagnostics.forEach(metric => {
        const tone = metricToneClasses(metric.tone);
        rows.push([
          metric.label,
          formatPanMetricValue(metric),
          tone.label,
          metric.target,
          metric.why,
          metric.action,
        ]);
      });
      const csv = rows.map(r => r.map(c => `"${String(c).replaceAll('"', '""')}"`).join(',')).join('\n');
      const blob = new Blob([csv], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `pan-optimization-report-${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      return;
    }

    const rows = [['Pair', 'File A', 'File B', ...activeTools.map(id => TOOLS.find(t => t.id === id)?.name || id), 'Max Score', 'Min Score']];
    (pair_results || []).forEach(pair => {
      const scores = activeTools.map(t => {
        const tr = pair.tool_results?.find(r => r.tool === t);
        return tr ? (tr.score * 100).toFixed(1) : 'N/A';
      });
      const numScores = scores.filter(s => s !== 'N/A').map(Number);
      rows.push([pair.label, pair.file_a || '', pair.file_b || '', ...scores,
      numScores.length ? Math.max(...numScores).toFixed(1) : 'N/A',
      numScores.length ? Math.min(...numScores).toFixed(1) : 'N/A',
      ]);
    });
    const csv = rows.map(r => r.map(c => `"${c}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `benchmark-report-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const downloadPDF = async () => {
    try {
      setPdfDownloading(true);
      setPdfError('');
      const res = await axios.post(`${API}/api/benchmark/export-pdf`, results, {
        responseType: 'blob',
      });
      const blob = new Blob([res.data], { type: res.headers['content-type'] || 'application/pdf' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `benchmark-report-${new Date().toISOString().slice(0, 10)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setPdfError('Could not export the benchmark report as PDF.');
    } finally {
      setPdfDownloading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Report header */}
      <div className="bg-gradient-to-r from-violet-50 to-blue-50 border border-violet-200 rounded-2xl p-5 flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-violet-100 flex items-center justify-center">
            <FileText size={20} className="text-violet-600" />
          </div>
          <div>
            <p className="font-bold text-violet-900">{results.datasetName || 'Benchmark'} Report</p>
            <p className="text-sm text-violet-600 mt-0.5">
              {isPanOptimization ? 'PAN optimization benchmark' : 'Professor tool comparison'} · Generated {results.runAt ? new Date(results.runAt).toLocaleString() : 'just now'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={downloadPDF} disabled={pdfDownloading}
            className="flex items-center gap-2 px-4 py-2.5 bg-slate-900 hover:bg-slate-800 disabled:bg-slate-300 text-white font-semibold rounded-xl transition-all text-sm shadow-lg shadow-slate-900/10 disabled:shadow-none">
            <Download size={15} />
            {pdfDownloading ? 'Preparing PDF…' : 'PDF'}
          </button>
          <button onClick={downloadCSV}
            className="flex items-center gap-2 px-4 py-2.5 bg-white border border-violet-200 hover:border-violet-400 text-violet-700 font-semibold rounded-xl transition-all text-sm hover:shadow-sm">
            <Download size={15} />
            CSV
          </button>
          <button onClick={downloadJSON}
            className="flex items-center gap-2 px-4 py-2.5 bg-violet-600 hover:bg-violet-700 text-white font-semibold rounded-xl transition-all text-sm shadow-lg shadow-violet-500/25">
            <Download size={15} />
            JSON
          </button>
          <button onClick={onRestart}
            className="flex items-center gap-2 px-4 py-2.5 bg-white border border-slate-200 hover:border-slate-300 text-slate-600 font-semibold rounded-xl transition-all text-sm">
            New Benchmark
          </button>
        </div>
      </div>

      {pdfError && (
        <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {pdfError}
        </div>
      )}

      {comparison.has_previous && (
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Compared With Previous Run</div>
              <div className="mt-1 text-sm text-slate-600">
                Previous job {comparison.previous_job_id} · {comparison.previous_run_at ? new Date(comparison.previous_run_at).toLocaleString() : 'earlier run'}
              </div>
            </div>
            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
              Same workflow/dataset
            </span>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {[
              ['Precision', 'precision', false],
              ['F1 Score', 'f1_score', false],
              ['PlagDet', 'plagdet', false],
              ['False Positive Rate', 'false_positive_rate', true],
            ].map(([label, key, lowerIsBetter]) => (
              <div key={key} className="rounded-xl border border-slate-100 bg-slate-50 p-4">
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</div>
                <div className={`mt-2 inline-flex rounded-full px-2.5 py-1 text-sm font-bold ${deltaTone(comparisonDeltas[key], lowerIsBetter)}`}>
                  {formatDelta(comparisonDeltas[key], lowerIsBetter)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {!isPanOptimization && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {summaryCards.map(({ icon: Icon, bg, color, label, value }) => (
            <div key={label} className="bg-white rounded-2xl border border-slate-200 p-5">
              <div className="flex items-center gap-3 mb-3">
                <div className={`w-9 h-9 rounded-xl ${bg} flex items-center justify-center`}>
                  <Icon size={18} className={color} />
                </div>
                <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">{label}</span>
              </div>
              <div className={`text-2xl font-bold ${color}`}>{value}</div>
            </div>
          ))}
        </div>
      )}

      {showMissingGroundTruthWarning && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm leading-6 text-amber-800">
          PAN metrics need labeled ground truth. Use a demo/synthetic original-vs-plagiarized dataset or a PAN-style dataset with labels to compute Precision, Recall, F1, Granularity, and PlagDet.
        </div>
      )}

      {showMissingPanScoresWarning && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm leading-6 text-amber-800">
          <div className="font-semibold text-amber-900">Ground truth labels were loaded, but no selected tool returned evaluable pair scores.</div>
          <div className="mt-1">
            Check the tool setup and rerun the benchmark. PAN metrics are computed only after a tool returns scores for labeled pairs.
          </div>
          {toolFailureRows.length > 0 && (
            <div className="mt-3 space-y-1">
              {toolFailureRows.map((failure) => (
                <div key={failure.toolId}>
                  <span className="font-semibold">{failure.name}:</span> {failure.error}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {isPanOptimization && benchmarkQuality.certification_level && (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-700">
                Benchmark Quality Certificate
              </div>
              <div className="mt-2 text-sm leading-6 text-emerald-900">
                {benchmarkQuality.pair_count} labeled pairs across {Object.keys(benchmarkQuality.transformations || {}).length} transformations,
                with {benchmarkQuality.hard_negative_pairs} hard negatives and PAN pair-level PlagDet scoring.
              </div>
            </div>
            <span className="rounded-full bg-white px-3 py-1 text-xs font-bold text-emerald-700">
              {Number(benchmarkQuality.score_percent || 0).toFixed(0)}% quality gates passed
            </span>
          </div>
        </div>
      )}

      {isPanOptimization && productPanResult && (
        <div className="space-y-6">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-6 py-5 border-b border-slate-100">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <h2 className="font-semibold text-slate-900">PAN Evaluation Scorecard</h2>
                  <p className="text-sm text-slate-500 mt-0.5">
                    Focused on product optimization for {productPanResult.name}; raw pair details and tool ranking are intentionally hidden.
                  </p>
                </div>
                <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs leading-5 text-slate-600 lg:max-w-md">
                  <div><span className="font-semibold text-slate-800">Dataset:</span> {datasetLabel}</div>
                  <div><span className="font-semibold text-slate-800">Method:</span> {optimizationLabel}</div>
                  <div><span className="font-semibold text-slate-800">Decision threshold:</span> {typeof productPanResult.threshold === 'number' ? productPanResult.threshold.toFixed(2) : 'N/A'}</div>
                </div>
              </div>
            </div>
            <div className="grid gap-4 p-6 md:grid-cols-2 xl:grid-cols-3">
              {panMetricDiagnostics.map((metric) => {
                const tone = metricToneClasses(metric.tone);
                return (
                  <div key={metric.key} className={`rounded-2xl border ${tone.border} ${tone.bg} p-5`}>
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{metric.label}</div>
                        <div className={`mt-2 text-3xl font-bold ${tone.text}`}>{formatPanMetricValue(metric)}</div>
                      </div>
                      <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${tone.badge}`}>
                        {tone.label}
                      </span>
                    </div>
                    <div className="mt-4 h-2 rounded-full bg-white/70">
                      <div className={`h-full rounded-full ${tone.bar}`} style={{ width: metricBarWidth(metric) }} />
                    </div>
                    <div className="mt-3 text-xs font-semibold text-slate-500">{metric.target}</div>
                    <div className="mt-4">
                      <div className="text-sm font-semibold text-slate-900">Why it matters</div>
                      <p className="mt-1 text-sm leading-6 text-slate-600">{metric.why}</p>
                    </div>
                    <div className="mt-4">
                      <div className="text-sm font-semibold text-slate-900">Next action</div>
                      <p className="mt-1 text-sm leading-6 text-slate-600">{metric.action}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-6 py-5 border-b border-slate-100">
            <h2 className="font-semibold text-slate-900">Engine Tuning Feedback</h2>
            <p className="text-sm text-slate-500 mt-0.5">
              Concrete optimization guidance for the next source-code iteration.
            </p>
          </div>
          <div className="grid gap-3 p-6 md:grid-cols-2">
            {panFeedback.map((item) => (
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
      {!isPanOptimization && chartData.length > 0 && (
        <div className="grid lg:grid-cols-2 gap-6">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-6 py-5 border-b border-slate-100">
              <h2 className="font-semibold text-slate-900">Pair-by-Pair Scores</h2>
              <p className="text-sm text-slate-500 mt-0.5">See how each tool scored every tested file pair.</p>
              <div className="mt-4 flex flex-wrap gap-2">
                {activeTools.map((toolId) => (
                  <ToolBadge key={toolId} toolId={toolId} compact />
                ))}
              </div>
            </div>
            <div className="p-6 h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="pair" tick={{ fontSize: 11, fill: '#64748b' }} />
                  <YAxis tick={{ fontSize: 11, fill: '#64748b' }} domain={[0, 100]} />
                  <Tooltip content={<PairScoreTooltip />} cursor={{ fill: 'rgba(148, 163, 184, 0.08)' }} />
                  {activeTools.map(tool => (
                    <Bar key={tool} dataKey={tool} fill={TOOLS.find(t => t.id === tool)?.color ?? '#94a3b8'} radius={[4, 4, 0, 0]} name={TOOLS.find(t => t.id === tool)?.name || tool} />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-6 py-5 border-b border-slate-100">
              <h2 className="font-semibold text-slate-900">Tool Leaderboard</h2>
              <p className="text-sm text-slate-500 mt-0.5">
                Average score across all tested pairs, with the top tool called out at a glance.
              </p>
            </div>
            <div className="grid gap-6 p-6 xl:grid-cols-[1.1fr_0.9fr]">
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={toolLeaderboard}
                    layout="vertical"
                    margin={{ top: 8, right: 12, left: 12, bottom: 8 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                    <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11, fill: '#64748b' }} />
                    <YAxis
                      type="category"
                      dataKey="shortName"
                      width={110}
                      tick={{ fontSize: 11, fill: '#475569' }}
                    />
                    <Tooltip content={<LeaderboardTooltip />} cursor={{ fill: 'rgba(148, 163, 184, 0.08)' }} />
                    <Bar dataKey="average" radius={[0, 10, 10, 0]} name="Average score">
                      {toolLeaderboard.map((entry) => (
                        <Cell key={entry.id} fill={entry.color} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <div className="space-y-3">
                {leadingTool && (
                  <div className="overflow-hidden rounded-2xl border border-blue-200 bg-gradient-to-br from-blue-50 to-indigo-50">
                    <div className="h-1.5 w-full bg-gradient-to-r from-blue-500 via-indigo-500 to-violet-500" />
                    <div className="p-4">
                      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-blue-600">
                        <Trophy size={14} />
                        Top Average Score
                      </div>
                      <div className="mt-3 flex items-start justify-between gap-4">
                        <div className="min-w-0">
                          <div className="text-2xl font-bold text-slate-900">{leadingTool.name}</div>
                          <div className="mt-1 text-sm text-slate-600">
                            {leadingTool.average.toFixed(1)}% average across {leadingTool.pairCount} pair{leadingTool.pairCount === 1 ? '' : 's'}
                          </div>
                        </div>
                        <ToolBadge toolId={leadingTool.id} compact />
                      </div>
                      {leadingToolInfo?.desc && (
                        <div className="mt-3 text-sm leading-6 text-slate-600">{leadingToolInfo.desc}</div>
                      )}
                      {leadingToolInfo?.engines?.length > 0 && (
                        <div className="mt-4 flex flex-wrap gap-2">
                          {leadingToolInfo.engines.slice(0, 4).map((engine) => (
                            <span
                              key={engine}
                              className="rounded-full border border-blue-200 bg-white/70 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-blue-700"
                            >
                              {engine}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {toolLeaderboard.slice(0, 4).map((tool, index) => (
                  <div key={tool.id} className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-slate-50/70 dark:bg-slate-800/70 p-4 transition hover:-translate-y-0.5 hover:border-slate-300 dark:hover:border-slate-600">
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span
                            className="inline-flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold text-white"
                            style={{ backgroundColor: tool.color }}
                          >
                            {index + 1}
                          </span>
                          <span className="truncate font-semibold text-slate-900">{tool.name}</span>
                        </div>
                        <div className="mt-2 flex flex-wrap gap-2">
                          <ToolBadge toolId={tool.id} compact />
                        </div>
                        <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-200">
                          <div
                            className="h-full rounded-full transition-all"
                            style={{ width: `${tool.average}%`, backgroundColor: tool.color }}
                          />
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-lg font-bold text-slate-900">{tool.average.toFixed(1)}%</div>
                        <div className="text-[11px] uppercase tracking-wider text-slate-400">Average</div>
                      </div>
                    </div>
                    <div className="mt-3 grid grid-cols-3 gap-2 text-xs text-slate-500">
                      <div>
                        <div className="font-semibold text-slate-700">{tool.peak.toFixed(1)}%</div>
                        <div>Peak</div>
                      </div>
                      <div>
                        <div className="font-semibold text-slate-700">{tool.minimum.toFixed(1)}%</div>
                        <div>Lowest</div>
                      </div>
                      <div>
                        <div className="font-semibold text-slate-700">{tool.spread.toFixed(1)}%</div>
                        <div>Spread</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Detailed table */}
      {!isPanOptimization && (pair_results?.length || 0) > 0 && (
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
              const pairIndex = pageStart + idx;
              const scores = activeTools.map(t => {
                const tr = pair.tool_results?.find(r => r.tool === t);
                return tr ? tr.score : null;
              });
              const valid = scores.filter(s => s !== null);
              const maxScore = valid.length ? Math.max(...valid) : 0;
              const minScore = valid.length ? Math.min(...valid) : 0;
              const spread = maxScore - minScore;
              const isExpanded = expandedPairs[pairIndex];
              const pairKey = `${pair.file_a || 'unknown-a'}::${pair.file_b || 'unknown-b'}::${pair.label || pairIndex}`;

              return (
                <div key={pairKey}>
                  <button onClick={() => togglePair(pairIndex)}
                    className="w-full px-6 py-4 hover:bg-slate-50/50 transition-colors text-left hidden lg:grid items-center"
                    style={{ gridTemplateColumns: `2fr repeat(${activeTools.length}, 1fr) 60px 60px 70px` }}>
                    <div className="flex items-center gap-3">
                      <div className={`w-2 h-8 rounded-full ${maxScore >= 0.9 ? 'bg-red-500' : maxScore >= 0.75 ? 'bg-amber-500' : maxScore >= 0.5 ? 'bg-yellow-500' : 'bg-emerald-500'}`} />
                      <div>
                        <div className="text-sm font-semibold text-slate-900">{pair.label}</div>
                        <div className="text-xs text-slate-400">{pair.file_a} vs {pair.file_b}</div>
                      </div>
                      {isExpanded ? <ChevronUp size={14} className="text-slate-400 ml-2" /> : <ChevronDown size={14} className="text-slate-400 ml-2" />}
                    </div>
                    {activeTools.map((tool, ti) => {
                      const score = scores[ti];
                      return (
                        <div key={tool} className="text-center">
                          {score !== null ? (
                            <span className={`inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-bold ${tool === 'integritydesk' ? 'bg-blue-50 text-blue-700' : 'bg-slate-50 text-slate-600'}`}>
                              {(score * 100).toFixed(1)}%
                            </span>
                          ) : <span className="text-xs text-slate-300">N/A</span>}
                        </div>
                      );
                    })}
                    <div className="text-center text-xs font-bold text-red-600">{(maxScore * 100).toFixed(0)}%</div>
                    <div className="text-center text-xs font-bold text-emerald-600">{(minScore * 100).toFixed(0)}%</div>
                    <div className={`text-center text-xs font-bold ${spread >= 0.3 ? 'text-red-600' : 'text-emerald-600'}`}>{(spread * 100).toFixed(0)}%</div>
                  </button>
                  {/* Mobile row */}
                  <button onClick={() => togglePair(pairIndex)} className="lg:hidden w-full px-4 py-3 hover:bg-slate-50/50 text-left flex items-center gap-3">
                    <div className={`w-2 h-8 rounded-full shrink-0 ${maxScore >= 0.9 ? 'bg-red-500' : maxScore >= 0.75 ? 'bg-amber-500' : maxScore >= 0.5 ? 'bg-yellow-500' : 'bg-emerald-500'}`} />
                    <div className="flex-1">
                      <div className="text-sm font-semibold text-slate-900">{pair.label}</div>
                      <div className="text-xs text-slate-400">Max: {(maxScore * 100).toFixed(0)}% · Min: {(minScore * 100).toFixed(0)}%</div>
                    </div>
                    {isExpanded ? <ChevronUp size={14} className="text-slate-400" /> : <ChevronDown size={14} className="text-slate-400" />}
                  </button>

                  {isExpanded && (
                    <div className="px-6 pb-5 bg-slate-50/50">
                      <div className="grid md:grid-cols-2 gap-3 mt-3">
                        {pair.tool_results?.map(tr => {
                          const toolInfo = TOOLS.find(t => t.id === tr.tool);
                          if (!toolInfo) return null;
                          return (
                            <div key={tr.tool} className="bg-white rounded-xl border border-slate-200 p-4">
                              <div className="flex items-center justify-between mb-3">
                                <div className="flex items-center gap-2">
                                  <div className={`w-7 h-7 rounded-lg bg-gradient-to-br ${toolInfo.gradient} flex items-center justify-center`}>
                                    <Zap size={13} className="text-white" />
                                  </div>
                                  <span className="text-sm font-semibold text-slate-900">{toolInfo.name}</span>
                                </div>
                                <span className={`text-lg font-bold ${toolInfo.textColor}`}>{(tr.score * 100).toFixed(1)}%</span>
                              </div>
                              <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                                <div className="h-full rounded-full transition-all duration-500"
                                  style={{ width: `${tr.score * 100}%`, background: `linear-gradient(90deg, ${toolInfo.color}, ${toolInfo.color}dd)` }} />
                              </div>
                              <div className="flex items-center justify-between mt-2">
                                <span className={`text-xs font-medium ${tr.score >= 0.9 ? 'text-red-600' : tr.score >= 0.75 ? 'text-amber-600' : tr.score >= 0.5 ? 'text-yellow-600' : 'text-emerald-600'}`}>
                                  {tr.score >= 0.9 ? 'Critical risk' : tr.score >= 0.75 ? 'High risk' : tr.score >= 0.5 ? 'Medium risk' : 'Low risk'}
                                </span>
                                <span className="text-xs text-slate-400">{toolInfo.desc}</span>
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
              <div className="text-xs font-medium text-slate-500">
                Showing {pageStart + 1}-{pageEnd} of {totalPairs} pairs
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
                  disabled={currentPage === 1}
                  className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Previous
                </button>
                <span className="min-w-[88px] text-center text-xs font-semibold text-slate-500">
                  Page {currentPage} of {totalPages}
                </span>
                <button
                  onClick={() => setCurrentPage((page) => Math.min(totalPages, page + 1))}
                  disabled={currentPage === totalPages}
                  className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main Page ───────────────────────────────────────────────────────────────
export default function BenchmarkPage() {
  const { user, loading: authLoading } = useAuth();
  const [step, setStep] = useState(0);
  const [completedSteps, setCompletedSteps] = useState([]);
  const [benchmarkMode, setBenchmarkMode] = useState('tool_comparison');
  const [selectedTools, setSelectedTools] = useState([]);
  const [selectedDataset, setSelectedDataset] = useState(null);
  const [uploadMode, setUploadMode] = useState('builtin');
  const [files, setFiles] = useState([]);
  const [benchmarkDatasets, setBenchmarkDatasets] = useState([]);
  const [availableTools, setAvailableTools] = useState([]);
  const [toolsLoading, setToolsLoading] = useState(true);
  const [toolsError, setToolsError] = useState('');
  const [results, setResults] = useState(null);
  const [workflowPresets, setWorkflowPresets] = useState([]);
  const [benchmarkHistory, setBenchmarkHistory] = useState([]);
  const [selectedPreset, setSelectedPreset] = useState(null);

  useEffect(() => {
    if (authLoading || !user) {
      return;
    }
    setToolsLoading(true);
    axios.get(`${API}/api/benchmark-tools`, { withCredentials: true }).then(res => {
      if (res.data?.tools) {
        setAvailableTools(res.data.tools);
      }
    }).catch(() => {
      setToolsError('Unable to confirm the installed benchmark tools. Showing the last known real-tool set.');
      setAvailableTools(TOOLS.filter((tool) => ['integritydesk', 'moss', 'jplag', 'dolos', 'nicad', 'pmd', 'sherlock'].includes(tool.id)));
    }).finally(() => {
      setToolsLoading(false);
    });
    axios.get(`${API}/api/benchmark-datasets`, { withCredentials: true }).then(res => {
      if (res.data?.datasets) setBenchmarkDatasets(res.data.datasets);
    }).catch(() => { });
    axios.get(`${API}/api/benchmark-presets`, { withCredentials: true }).then(res => {
      if (res.data?.presets) setWorkflowPresets(res.data.presets);
    }).catch(() => { });
    axios.get(`${API}/api/benchmark-history`, { withCredentials: true }).then(res => {
      if (res.data?.runs) setBenchmarkHistory(res.data.runs);
    }).catch(() => { });
  }, [authLoading, user]);

  useEffect(() => {
    if (benchmarkMode !== 'pan_optimization') {
      return;
    }

    if (uploadMode !== 'builtin') {
      setUploadMode('builtin');
      setFiles([]);
    }

    const selected = benchmarkDatasets.find((dataset) => dataset.id === selectedDataset);
    if (selected && !selected.has_ground_truth) {
      setSelectedDataset(null);
    }
  }, [benchmarkMode, uploadMode, selectedDataset, benchmarkDatasets]);

  const applyPreset = (preset) => {
    const runnableToolIds = new Set(
      availableTools
        .filter((tool) => tool.available !== false && tool.runnable !== false)
        .map((tool) => tool.id)
    );
    const toolsForPreset = (preset.runnable_tools?.length ? preset.runnable_tools : preset.tools || [])
      .filter((toolId) => runnableToolIds.has(toolId));
    setSelectedPreset(preset);
    setBenchmarkMode(preset.mode || 'pan_optimization');
    setSelectedTools(toolsForPreset);
    setUploadMode('builtin');
    setSelectedDataset(preset.dataset);
    setFiles([]);
    setStep(0);
    setCompletedSteps([]);
  };

  const goToStep = (next, currentCompleted) => {
    setCompletedSteps(prev => {
      const updated = [...new Set([...prev, currentCompleted])];
      return updated;
    });
    setStep(next);
  };

  const STEPS = [
    { label: 'Select Tools', subtitle: 'Choose what to benchmark' },
    { label: 'Dataset', subtitle: 'Pick or upload data' },
    { label: 'Run', subtitle: 'Execute the benchmark' },
    { label: 'Report', subtitle: 'View & download results' },
  ];

  const restart = () => {
    setStep(0);
    setCompletedSteps([]);
    setResults(null);
  };

  return (
    <DashboardLayout>
      <div className="px-4 py-4 lg:px-6 lg:py-6">
        {/* Header */}
        <div className="mb-8 flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-violet-600 flex items-center justify-center shadow-lg shadow-violet-500/25 shrink-0">
              <FlaskConical size={20} className="text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Benchmark Suite</h1>
            </div>
          </div>

          <div className="xl:w-[540px] xl:max-w-[48%]">
            <div className="rounded-2xl border border-slate-200 bg-white/80 p-3 shadow-sm">
              <div className="mb-2 flex items-center justify-between">
                <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Progress</div>
                <div className="text-xs font-medium text-slate-500">Step {step + 1} of {STEPS.length}</div>
              </div>
              <StepIndicator steps={STEPS} currentStep={step} completedSteps={completedSteps} compact />
            </div>
          </div>
        </div>

        {step < 3 && (
          <BenchmarkWorkflowPanel
            presets={workflowPresets}
            history={benchmarkHistory}
            selectedPreset={selectedPreset}
            onApplyPreset={applyPreset}
          />
        )}

        {step < 3 && (
          <div className="mb-6 grid gap-3 lg:grid-cols-2">
            {Object.entries(BENCHMARK_MODES).map(([modeId, mode]) => {
              const active = benchmarkMode === modeId;
              return (
                <button
                  key={modeId}
                  onClick={() => setBenchmarkMode(modeId)}
                  className={`rounded-2xl border p-4 text-left transition ${active
                    ? 'border-slate-900 bg-slate-900 text-white shadow-lg shadow-slate-900/10'
                    : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:shadow-sm'
                    }`}
                >
                  <div className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${active ? 'text-slate-300' : 'text-slate-400'}`}>
                    {mode.audience}
                  </div>
                  <div className="mt-2 flex items-center justify-between gap-3">
                    <div className="font-semibold">{mode.label}</div>
                    {active && <CheckCircle2 size={16} className="text-emerald-300" />}
                  </div>
                  <div className={`mt-2 text-sm leading-6 ${active ? 'text-slate-200' : 'text-slate-500'}`}>
                    {mode.description}
                  </div>
                </button>
              );
            })}
          </div>
        )}

        {/* Steps */}
        {step === 0 && (
          <ToolSelectionStep
            tools={availableTools}
            selectedTools={selectedTools}
            setSelectedTools={setSelectedTools}
            loading={toolsLoading}
            error={toolsError}
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
            benchmarkMode={benchmarkMode}
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
            benchmarkMode={benchmarkMode}
            selectedPreset={selectedPreset}
            onBack={() => setStep(1)}
            onComplete={(data) => {
              setResults({ ...data, benchmarkMode });
              if (data.history_summary) {
                setBenchmarkHistory(prev => [
                  data.history_summary,
                  ...prev.filter(run => run.job_id !== data.history_summary.job_id),
                ]);
              }
              goToStep(3, 2);
            }}
          />
        )}

        {step === 3 && results && (
          <ReportStep results={results} onRestart={restart} />
        )}
      </div>
    </DashboardLayout>
  );
}
