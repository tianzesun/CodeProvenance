// @ts-nocheck — TODO: add proper types (tracked in types/api.ts)
'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { apiClient } from '@/lib/apiClient';
import {
  AlertTriangle,
  BarChart3,
  Bot,
  CheckCircle2,
  FlaskConical,
  Info,
  Shield,
  Sigma,
} from 'lucide-react';
import { useEffect, useState } from 'react';

function fmt(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return 'n/a';
  return `${(value * 100).toFixed(1)}%`;
}

function auc(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return 'n/a';
  return value.toFixed(3);
}

function tone(value, higherIsBetter = true) {
  if (value === null || value === undefined || Number.isNaN(value)) return 'bg-slate-100 text-slate-500';
  if (higherIsBetter) {
    if (value >= 0.8) return 'bg-emerald-50 text-emerald-700';
    if (value >= 0.6) return 'bg-blue-50 text-blue-700';
    if (value >= 0.4) return 'bg-amber-50 text-amber-700';
    return 'bg-red-50 text-red-700';
  }
  if (value <= 0.2) return 'bg-emerald-50 text-emerald-700';
  if (value <= 0.5) return 'bg-blue-50 text-blue-700';
  return 'bg-red-50 text-red-700';
}

function MetricCell({ value, higherIsBetter = true, soc }) {
  return (
    <td>
      <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${tone(value, higherIsBetter)}`}>
        {soc === 'auc' ? auc(value) : fmt(value)}
      </span>
    </td>
  );
}

function renderMetrics(metrics, soc = 'none') {
  if (!metrics) return null;
  const socKey = soc === 'auc' ? 'auc' : null;
  return (
    <>
      <MetricCell value={metrics.accuracy} soc={socKey} />
      <MetricCell value={metrics.precision} soc={socKey} />
      <MetricCell value={metrics.recall} soc={socKey} />
      <MetricCell value={metrics.f1} soc={socKey} />
    </>
  );
}

function ThresholdTable({ report, soc }) {
  const gh = report?.grouped_holdout;
  if (!gh) return null;
  const rows = [
    { label: '0.50 (default decision)', metrics: gh.metrics },
    { label: '0.40 (medium-risk)', metrics: gh.metrics_at_040 },
    { label: '0.70 (high-risk)', metrics: gh.metrics_at_070 },
  ];
  return (
    <div className="overflow-x-auto rounded-xl ring-1 ring-slate-200">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wider text-slate-500">
            <th className="px-4 py-3 font-semibold">Threshold</th>
            <th className="px-4 py-3 font-semibold">Accuracy</th>
            <th className="px-4 py-3 font-semibold">Precision</th>
            <th className="px-4 py-3 font-semibold">Recall</th>
            <th className="px-4 py-3 font-semibold">F1</th>
            {soc === 'auc' && <th className="px-4 py-3 font-semibold">AUC</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label} className="border-b border-slate-100 last:border-0">
              <td className="px-4 py-3 font-medium text-slate-700">{row.label}</td>
              {renderMetrics(row.metrics, soc)}
              {soc === 'auc' && (
                <td>
                  <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600">
                    {auc(row.metrics.auc)}
                  </span>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ComparisonTable({ report }) {
  const cmp = report?.heuristic_comparison;
  if (!cmp || (!cmp.heuristic_only && !cmp.ml_classifier)) return null;
  const rows = [
    { label: 'Heuristic-only (current default)', metrics: cmp.heuristic_only },
    { label: 'Trained ML classifier', metrics: cmp.ml_classifier },
  ];
  return (
    <div className="overflow-x-auto rounded-xl ring-1 ring-slate-200">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wider text-slate-500">
            <th className="px-4 py-3 font-semibold">Method</th>
            <th className="px-4 py-3 font-semibold">Accuracy</th>
            <th className="px-4 py-3 font-semibold">Precision</th>
            <th className="px-4 py-3 font-semibold">Recall</th>
            <th className="px-4 py-3 font-semibold">F1</th>
            <th className="px-4 py-3 font-semibold">AUC</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label} className="border-b border-slate-100 last:border-0">
              <td className="px-4 py-3 font-medium text-slate-700">{row.label}</td>
              {renderMetrics(row.metrics, 'auc')}
              <td>
                <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600">
                  {auc(row.metrics.auc)}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function GeneratorTable({ report }) {
  const cross = report?.cross_llm;
  if (!cross) return null;
  const gens = Object.entries(cross);
  if (!gens.length) return null;
  return (
    <div className="overflow-x-auto rounded-xl ring-1 ring-slate-200">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wider text-slate-500">
            <th className="px-4 py-3 font-semibold">Generator</th>
            <th className="px-4 py-3 font-semibold">AI samples</th>
            <th className="px-4 py-3 font-semibold">Precision</th>
            <th className="px-4 py-3 font-semibold">Recall</th>
            <th className="px-4 py-3 font-semibold">AUC</th>
          </tr>
        </thead>
        <tbody>
          {gens.map(([name, g]) => (
            <tr key={name} className="border-b border-slate-100 last:border-0">
              <td className="px-4 py-3 font-medium text-slate-700">{name}</td>
              <td className="px-4 py-3 text-slate-600">{g.ai_samples}</td>
              <td>
                <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${tone(g.metrics?.precision)}`}>
                  {fmt(g.metrics?.precision)}
                </span>
              </td>
              <td>
                <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${tone(g.metrics?.recall)}`}>
                  {fmt(g.metrics?.recall)}
                </span>
              </td>
              <td>
                <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600">
                  {auc(g.metrics?.auc)}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PerplexityCompare({ statistical, codelm }) {
  if (!statistical && !codelm) return null;
  const srcs = [
    {
      label: 'Statistical bigram (current default)',
      report: statistical,
      model: 'statistical bigram',
    },
    {
      label: 'Causal code-LM (CodeGPT-small-py)',
      report: codelm,
      model: 'causal code-LM',
    },
  ];
  return (
    <div className="overflow-x-auto rounded-xl ring-1 ring-slate-200">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wider text-slate-500">
            <th className="px-4 py-3 font-semibold">Perplexity source</th>
            <th className="px-4 py-3 font-semibold">F1</th>
            <th className="px-4 py-3 font-semibold">AUC</th>
          </tr>
        </thead>
        <tbody>
          {srcs.map((src) => {
            const m = src.report?.grouped_holdout?.metrics;
            if (!m) return null;
            return (
              <tr key={src.label} className="border-b border-slate-100 last:border-0">
                <td className="px-4 py-3 font-medium text-slate-700">{src.label}</td>
                <td>
                  <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${tone(m.f1)}`}>
                    {fmt(m.f1)}
                  </span>
                </td>
                <td>
                  <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600">
                    {auc(m.auc)}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function StatBadge({ label, value, on }) {
  return (
    <div className={`flex items-center gap-2 rounded-xl px-4 py-3 text-sm ${on ? 'bg-slate-100' : 'bg-slate-50 text-slate-500'}`}>
      {on ? <CheckCircle2 size={16} className="text-emerald-600" /> : <AlertTriangle size={16} className="text-amber-500" />}
      <span className="font-medium text-slate-700">{label}</span>
      <span className="ml-auto font-semibold text-slate-900">{value}</span>
    </div>
  );
}

export default function AIDetectionAccuracyPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    apiClient
      .get('/api/ai-detect/accuracy')
      .then((res) => {
        if (active) setData(res.data);
      })
      .catch(() => {
        if (active) setError('Failed to load accuracy benchmark data.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const reports = data?.reports || {};
  const main = reports.main;
  const runtime = data?.runtime || {};

  if (loading) {
    return (
      <DashboardLayout requiredRole="admin">
        <div className="flex items-center justify-center py-32 text-sm text-slate-400">Loading benchmark…</div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout requiredRole="admin">
      <div className="px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <div className="space-y-8">
          <section className="theme-card-strong rounded-[30px] overflow-hidden">
            <div className="theme-section-line px-6 py-5 lg:px-7">
              <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
                <div className="space-y-4">
                  <div className="inline-flex items-center gap-2 rounded-full border border-blue-600/10 bg-blue-600/[0.06] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--accent-blue)]">
                    <FlaskConical size={13} />
                    AI Detector Accuracy Benchmark
                  </div>
                  <div>
                    <h1 className="font-display text-3xl font-semibold tracking-tight text-[var(--text-primary)] sm:text-4xl">
                      Measured accuracy, not marketing
                    </h1>
                    <p className="mt-3 max-w-3xl text-sm leading-7 text-[var(--text-secondary)]">
                      The real, reproducible numbers the AI detector achieves on unseen problems
                      (AIGCodeSet, grouped holdout by problem_id). These are the same figures a
                      Turnitin-style vendor would publish — so reviewers can judge the engine on
                      data, not UI polish.
                    </p>
                  </div>
                </div>
                <BarChart3 size={28} className="text-slate-300" />
              </div>
            </div>
          </section>

          {error && (
            <section className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
              <AlertTriangle size={16} className="mt-0.5 shrink-0" />
              <span>{error}</span>
            </section>
          )}

          {!data?.available && !error && (
            <section className="rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm text-amber-800">
              <div className="flex items-start gap-3">
                <Info size={16} className="mt-0.5 shrink-0" />
                <div>
                  No benchmark report found. Build and run the AIGCodeSet benchmark to populate
                  this page:
                  <pre className="mt-3 rounded-lg bg-white/60 p-3 text-xs leading-6">
                    {'bash data/datasets/aigcodeset/download.sh\npython -m src.backend.engines.ai.build_aigcodeset\npython -m src.backend.engines.ai.benchmark_classifier'}
                  </pre>
                </div>
              </div>
            </section>
          )}

          <section className="rounded-2xl bg-white shadow-sm ring-1 ring-slate-200">
            <div className="border-b border-slate-100 px-5 py-4">
              <div className="text-sm font-semibold text-slate-900">Current runtime configuration</div>
              <div className="mt-1 text-xs text-slate-500">What the detector actually uses in production right now.</div>
            </div>
            <div className="grid gap-3 p-5 md:grid-cols-3">
              <StatBadge label="ML classifier" value={runtime.ml_classifier_enabled ? 'Enabled' : 'Disabled'} on={runtime.ml_classifier_enabled} />
              <StatBadge label="Perplexity source" value={runtime.perplexity_model || 'statistical-bigram'} on={!String(runtime.perplexity_model || '').startsWith('statistical')} />
              <StatBadge label="Default engine" value={runtime.default_engine || 'heuristic'} on={false} />
            </div>
          </section>

          <section className="rounded-2xl bg-white shadow-sm ring-1 ring-slate-200">
            <div className="flex items-center justify-between gap-4 border-b border-slate-100 px-5 py-4">
              <div>
                <div className="text-sm font-semibold text-slate-900">Grouped holdout (no leakage)</div>
                <div className="mt-1 text-xs text-slate-500">
                  {main?.n_samples ?? '—'} samples ({main?.n_ai ?? '—'} AI). 20% of problems held out; the same problem never spans train and test.
                </div>
              </div>
              <Sigma size={18} className="text-slate-400" />
            </div>
            <div className="space-y-4 p-5">
              <ThresholdTable report={main} soc="auc" />
            </div>
          </section>

          <section className="rounded-2xl bg-white shadow-sm ring-1 ring-slate-200">
            <div className="border-b border-slate-100 px-5 py-4">
              <div className="text-sm font-semibold text-slate-900">Heuristic vs ML classifier</div>
              <div className="mt-1 text-xs text-slate-500">Same unseen test fold, two scoring methods. ML is disabled by default for false-positive safety.</div>
            </div>
            <div className="space-y-4 p-5">
              <ComparisonTable report={main} />
            </div>
          </section>

          <section className="rounded-2xl bg-white shadow-sm ring-1 ring-slate-200">
            <div className="border-b border-slate-100 px-5 py-4">
              <div className="text-sm font-semibold text-slate-900">Per-generator sensitivity</div>
              <div className="mt-1 text-xs text-slate-500">Recall against each generator on problems the model never trained on.</div>
            </div>
            <div className="space-y-4 p-5">
              <GeneratorTable report={main} />
            </div>
          </section>

          <section className="rounded-2xl bg-white shadow-sm ring-1 ring-slate-200">
            <div className="border-b border-slate-100 px-5 py-4">
              <div className="text-sm font-semibold text-slate-900">Perplexity signal comparison</div>
              <div className="mt-1 text-xs text-slate-500">The causal code-LM improves AUC over the statistical bigram — but is not enabled by default.</div>
            </div>
            <div className="space-y-4 p-5">
              <PerplexityCompare statistical={reports.statistical} codelm={reports.codelm} />
            </div>
          </section>

          <section className="rounded-2xl border border-slate-200 bg-slate-50 px-5 py-4 text-sm text-slate-600">
            <div className="flex items-start gap-3">
              <Shield size={16} className="mt-0.5 shrink-0 text-slate-400" />
              <div className="leading-7">
                <div className="mb-2 font-semibold text-slate-700">Honest reading</div>
                <p>
                  The heuristic path (the live default) reaches AUC ~0.52–0.55 — modest. The trained
                  ML classifier (0.66) and causal code-LM (0.63) are measured improvements but remain
                  <span className="font-semibold text-slate-700"> disabled by default</span> because on short,
                  terse student code they raise false positives. This is deliberately honest: we show real
                  numbers, treat scores as indicators (not proof), and flag that AIGCodeSet alone cannot
                  validate the product&apos;s real input distribution. See
                  <span className="font-mono text-xs text-slate-500"> docs/AI_DETECTOR_VS_TURNITIN.md</span> for the full gap analysis.
                </p>
              </div>
            </div>
          </section>
        </div>
      </div>
    </DashboardLayout>
  );
}