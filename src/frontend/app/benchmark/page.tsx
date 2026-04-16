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
  ChevronRight, UploadCloud, Database, Settings2, ClipboardList,
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from 'recharts';

const API = process.env.NEXT_PUBLIC_API_URL || '';

let TOOLS = [];

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
  return `${languageLabel} • ${sizeLabel}`;
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

  return items.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
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

function DatasetCard({ dataset, isActive, onSelect }) {
  const categoryMeta = getDatasetCategoryMeta(dataset);

  return (
    <button
      onClick={() => onSelect(dataset.id)}
      className={`relative rounded-2xl border-2 p-4 text-left transition-all duration-200 ${isActive
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
          {categoryMeta?.label}
        </span>
      </div>
      <div className={`mt-4 text-[11px] font-semibold uppercase tracking-[0.18em] ${isActive ? 'text-slate-300' : 'text-slate-400'
        }`}>
        {categoryMeta?.eyebrow}
      </div>
      <div className={`mt-2 text-base font-semibold ${isActive ? 'text-white' : 'text-slate-900'}`}>
        {dataset.name}
      </div>
      <div className={`mt-2 text-sm leading-6 ${isActive ? 'text-slate-200' : 'text-slate-500'}`}>
        {dataset.desc}
      </div>
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
      </div>
    </button>
  );
}

function formatChartPercent(value) {
  return `${Number(value || 0).toFixed(1)}%`;
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

// ── Step 1: Tool Selection ──────────────────────────────────────────────────
function ToolSelectionStep({ tools, selectedTools, setSelectedTools, onNext, loading, error }) {
  const [activeEngines, setActiveEngines] = useState([]);
  const engineFilters = Array.from(new Set(tools.flatMap((tool) => tool.engines ?? []))).sort();

  const visibleTools = activeEngines.length
    ? tools.filter((tool) => activeEngines.some((engine) => tool.engines.includes(engine)))
    : tools;

  const toggleTool = (id) => setSelectedTools(prev =>
    prev.includes(id) ? prev.filter(t => t !== id) : [...prev, id]
  );

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
            }`}>{selectedTools.length} / {tools.length} selected</span>
           <div className="flex gap-1">
             <button onClick={() => setSelectedTools(tools.map(t => t.id))} className="text-xs font-medium text-slate-500 hover:text-slate-700 px-3 py-1.5 rounded-lg hover:bg-slate-50 transition-colors">Select All</button>
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
              return (
                <button key={tool.id} onClick={() => toggleTool(tool.id)}
                  className={`relative p-4 rounded-xl border-2 text-left transition-all duration-200 group ${isSelected
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
function DatasetStep({ selectedDataset, setSelectedDataset, uploadMode, setUploadMode, files, setFiles, benchmarkDatasets, canManageDemoDatasets, onBack, onNext }) {
  const [libraryFilter, setLibraryFilter] = useState('all');

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setFiles(Array.from(e.dataTransfer.files));
  }, [setFiles]);

  const handleDragOver = (e) => e.preventDefault();

  const { presetDatasets, demoDatasets, allDatasets } = useMemo(
    () => buildDatasetLibrary(benchmarkDatasets),
    [benchmarkDatasets]
  );
  const visibleLibraryDatasets = allDatasets.filter((dataset) => {
    if (libraryFilter === 'preset') {
      return dataset.datasetType === 'preset';
    }
    if (libraryFilter === 'demo') {
      return dataset.datasetType === 'demo';
    }
    return true;
  });
  const activeDataset = allDatasets.find((dataset) => dataset.id === selectedDataset);
  const activeDatasetMeta = getDatasetCategoryMeta(activeDataset);
  const hasZipUpload = files.some((file) => file.name?.toLowerCase().endsWith('.zip'));
  const canProceed = uploadMode === 'builtin'
    ? !!selectedDataset
    : hasZipUpload || files.length >= 2;

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
            Choose a reusable benchmark dataset from the library, or upload your own files.
          </p>
        </div>
        <div className="flex border-b border-slate-100">
          {[
            { id: 'builtin', label: 'Dataset Library', icon: FlaskConical },
            { id: 'upload', label: 'Upload Files or ZIP', icon: FileUp },
          ].map(({ id, label, icon: Icon }) => (
            <button key={id} onClick={() => { setUploadMode(id); setFiles([]); if (id !== 'builtin') setSelectedDataset(null); }}
              className={`flex items-center gap-2 px-5 py-3.5 text-sm font-medium border-b-2 transition-colors ${uploadMode === id ? 'border-violet-500 text-violet-700 bg-violet-50/50' : 'border-transparent text-slate-500 hover:text-slate-700'
                }`}>
              <Icon size={15} />
              {label}
            </button>
          ))}
        </div>

        <div className="p-6">
          {uploadMode === 'builtin' && (
            <div className="space-y-6">
              <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-slate-50/80 dark:bg-slate-800/80 p-5">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between mb-4">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Dataset Library</p>
                    <p className="mt-1 text-sm text-slate-500">
                      Choose any reusable benchmark dataset here. Preset datasets and demo datasets all live in one library so you can filter them without switching sections.
                    </p>
                  </div>
                  {canManageDemoDatasets ? (
                    <Link
                      href="/admin"
                      className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800"
                    >
                      Create Demo Dataset
                      <ArrowRight size={15} />
                    </Link>
                  ) : null}
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  {[
                    { id: 'all', label: 'All', count: allDatasets.length },
                    { id: 'preset', label: 'Preset', count: presetDatasets.length },
                    { id: 'demo', label: 'Demo', count: demoDatasets.length },
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
                  {!canManageDemoDatasets && (
                    <div className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-500">
                      Need another demo? Ask an administrator to create one.
                    </div>
                  )}
                </div>

                {visibleLibraryDatasets.length > 0 ? (
                  <div className="mt-5 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                    {visibleLibraryDatasets.map((dataset) => {
                      const isActive = selectedDataset === dataset.id;
                      return <DatasetCard key={dataset.id} dataset={dataset} isActive={isActive} onSelect={setSelectedDataset} />;
                    })}
                  </div>
                ) : (
                  <div className="mt-5 rounded-2xl border border-dashed border-slate-300 bg-white px-5 py-6">
                    <div className="text-sm font-semibold text-slate-900">
                      {libraryFilter === 'demo' ? 'No demo datasets yet' : 'No datasets match this filter'}
                    </div>
                    <div className="mt-2 text-sm leading-6 text-slate-500">
                      {libraryFilter === 'demo'
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
                          <div className="text-sm text-slate-600">{activeDatasetMeta.label}</div>
                        </div>
                      </div>
                    </div>
                    <span className={`rounded-full px-3 py-1 text-xs font-semibold ${activeDatasetMeta.badgeClass}`}>
                      {activeDatasetMeta.summaryLabel}
                    </span>
                  </div>

                  <div className="mt-4 text-sm leading-6 text-slate-600">{activeDataset.desc}</div>

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
                              : (activeDataset.similarity_type || 'Standard')}
                          </div>
                          <div className="text-xs text-slate-500">{activeDataset.is_demo ? 'Created' : 'Benchmark Type'}</div>
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
    </div>
  );
}

// ── Step 3: Run ─────────────────────────────────────────────────────────────
function RunStep({ selectedTools, selectedDataset, uploadMode, files, benchmarkDatasets, onBack, onComplete }) {
  const { token } = useAuth();
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState('');
  const [progressPct, setProgressPct] = useState(0);
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

          try {
            setProgress('Running benchmark analysis...');
            setProgressPct(50);

            const res = await axios.post(`${API}/api/benchmark`, formData, createRequestOptions());

            setProgressPct(100);
            setProgress('Complete!');
            setTimeout(() => onComplete({ ...res.data, datasetName: activeDataset.name, runAt: new Date().toISOString() }), 400);
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
            <div className="h-2.5 bg-slate-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-violet-500 to-blue-500 rounded-full transition-all duration-500"
                style={{ width: `${progressPct}%` }}
              />
            </div>
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
  const [pdfDownloading, setPdfDownloading] = useState(false);
  const [pdfError, setPdfError] = useState('');
  const { tool_scores, pair_results, summary } = results;
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
              Generated {results.runAt ? new Date(results.runAt).toLocaleString() : 'just now'}
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

      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { icon: Layers, bg: 'bg-blue-50', color: 'text-blue-600', label: 'Tools Run', value: summary?.tools_compared || activeTools.length },
          { icon: Target, bg: 'bg-emerald-50', color: 'text-emerald-600', label: 'Pairs Tested', value: summary?.pairs_tested || (pair_results?.length || 0) },
          { icon: TrendingUp, bg: 'bg-violet-50', color: 'text-violet-600', label: 'IntegrityDesk Avg', value: summary?.accuracy?.integritydesk ? `${(summary.accuracy.integritydesk * 100).toFixed(1)}%` : '—' },
          { icon: Trophy, bg: 'bg-amber-50', color: 'text-amber-600', label: 'Best Competitor', value: summary?.accuracy?.best_competitor ? `${(summary.accuracy.best_competitor * 100).toFixed(1)}%` : '—' },
        ].map(({ icon: Icon, bg, color, label, value }) => (
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

      {/* Charts */}
      {chartData.length > 0 && (
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
      {(pair_results?.length || 0) > 0 && (
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
            {(pair_results || []).slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage).map((pair, idx) => {
              const scores = activeTools.map(t => {
                const tr = pair.tool_results?.find(r => r.tool === t);
                return tr ? tr.score : null;
              });
              const valid = scores.filter(s => s !== null);
              const maxScore = valid.length ? Math.max(...valid) : 0;
              const minScore = valid.length ? Math.min(...valid) : 0;
              const spread = maxScore - minScore;
              const isExpanded = expandedPairs[idx];
              const pairKey = `${pair.file_a || 'unknown-a'}::${pair.file_b || 'unknown-b'}::${pair.label || idx}`;

              return (
                <div key={pairKey}>
                  <button onClick={() => togglePair(idx)}
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
                  <button onClick={() => togglePair(idx)} className="lg:hidden w-full px-4 py-3 hover:bg-slate-50/50 text-left flex items-center gap-3">
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
  const [selectedTools, setSelectedTools] = useState([]);
  const [selectedDataset, setSelectedDataset] = useState(null);
  const [uploadMode, setUploadMode] = useState('builtin');
  const [files, setFiles] = useState([]);
  const [benchmarkDatasets, setBenchmarkDatasets] = useState([]);
  const [availableTools, setAvailableTools] = useState([]);
  const [toolsLoading, setToolsLoading] = useState(true);
  const [toolsError, setToolsError] = useState('');
  const [results, setResults] = useState(null);

  // Pagination for detailed results table
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(50);

  useEffect(() => {
    if (authLoading || !user) {
      return;
    }
    setToolsLoading(true);
    axios.get(`${API}/api/benchmark-tools`).then(res => {
      if (res.data?.tools) {
        setAvailableTools(res.data.tools);
      }
    }).catch(() => {
      setToolsError('Unable to confirm the installed benchmark tools. Showing the last known real-tool set.');
      setAvailableTools(TOOLS.filter((tool) => ['integritydesk', 'moss', 'jplag', 'dolos', 'nicad', 'ac', 'pmd'].includes(tool.id)));
    }).finally(() => {
      setToolsLoading(false);
    });
    axios.get(`${API}/api/benchmark-datasets`).then(res => {
      if (res.data?.datasets) setBenchmarkDatasets(res.data.datasets);
    }).catch(() => { });
  }, [authLoading, user]);

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
            onBack={() => setStep(1)}
            onComplete={(data) => {
              setResults(data);
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
