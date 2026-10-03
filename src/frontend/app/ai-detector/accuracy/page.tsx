// @ts-nocheck — TODO: add proper types (tracked in types/api.ts)

'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { apiClient } from '@/lib/apiClient';
import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  FlaskConical,
  Info,
  Layers,
  Shield,
  Sigma,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

// ── Number helpers ─────────────────────────────────────────────────────────

// Anything that isn't a finite number is "unknown". Values used to be formatted directly, so a string crashed
// `.toFixed`, and a missing false-positive rate was shown as 0%.
function num(value) {
  if (value === null || value === undefined || value === '') return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function fmt(value) {
  const n = num(value);
  return n === null ? 'n/a' : `${(n * 100).toFixed(1)}%`;
}

function auc(value) {
  const n = num(value);
  return n === null ? 'n/a' : n.toFixed(3);
}

/** Whole percent, but one decimal below 10% so a 0.4% rate doesn't read as "0%". */
function pctSmart(value) {
  const n = num(value);
  if (n === null) return 'n/a';
  const p = n * 100;
  // Compare the rounded value, so 9.99% shows as "10%" rather than "10.0%".
  return p > 0 && Number(p.toFixed(1)) < 10 ? `${p.toFixed(1)}%` : `${Math.round(p)}%`;
}

const GREEN = 'bg-emerald-50 text-emerald-700';
const BLUE = 'bg-blue-50 text-blue-700';
const AMBER = 'bg-amber-50 text-amber-700';
const RED = 'bg-red-50 text-red-700';
const GREY = 'bg-slate-100 text-slate-500';

function higherTone(value) {
  const n = num(value);
  if (n === null) return GREY;
  if (n >= 0.8) return GREEN;
  if (n >= 0.6) return BLUE;
  if (n >= 0.4) return AMBER;
  return RED;
}

// A false-positive rate of 20% used to be green: one in five innocent submissions flagged. These cut-offs
// match the ones on the Real-World FPR page (2% / 4-5% / 7-10%).
function fprTone(value) {
  const n = num(value);
  if (n === null) return GREY;
  if (n <= 0.02) return GREEN;
  if (n <= 0.05) return BLUE;
  if (n <= 0.1) return AMBER;
  return RED;
}

// AUC of 0.5 is a coin flip. The pills were all neutral grey, so a near-chance 0.52 looked the same as 0.95.
function aucTone(value) {
  const n = num(value);
  if (n === null) return GREY;
  if (n >= 0.9) return GREEN;
  if (n >= 0.8) return BLUE;
  if (n >= 0.7) return AMBER;
  return RED;
}

const TONES = { higher: higherTone, fpr: fprTone, auc: aucTone };

// ── Table pieces ───────────────────────────────────────────────────────────

function Th({ children }) {
  return (
    <th scope="col" className="px-4 py-3 font-semibold">
      {children}
    </th>
  );
}

function Cell({ value, kind = 'higher', format = 'pct' }) {
  const text = format === 'auc' ? auc(value) : fmt(value);
  return (
    <td className="px-4 py-3">
      <span
        className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${TONES[kind](value)}`}
        title={kind === 'auc' ? '0.5 is chance; 1.0 is perfect' : undefined}
      >
        {text}
      </span>
    </td>
  );
}

function TableShell({ caption, children }) {
  return (
    <div className="overflow-x-auto rounded-xl ring-1 ring-slate-200">
      <table className="w-full border-collapse text-sm">
        <caption className="sr-only">{caption}</caption>
        {children}
      </table>
    </div>
  );
}

const HEAD_ROW = 'border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wider text-slate-500';

// A row without metrics used to render no metric cells at all, shifting the columns; and the AUC cells read
// `row.metrics.auc` without a guard, which crashed the page when a threshold's metrics were missing.
function MetricsRow({ label, metrics, withAuc }) {
  return (
    <tr className="border-b border-slate-100 last:border-0">
      <td className="px-4 py-3 font-medium text-slate-700">{label}</td>
      <Cell value={metrics?.accuracy} />
      <Cell value={metrics?.precision} />
      <Cell value={metrics?.recall} />
      <Cell value={metrics?.f1} />
      <Cell value={metrics?.fpr} kind="fpr" />
      {withAuc && <Cell value={metrics?.auc} kind="auc" format="auc" />}
      {withAuc && <Cell value={metrics?.pr_auc} kind="auc" format="auc" />}
    </tr>
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
  const withAuc = soc === 'auc';
  return (
    <TableShell caption="Detection performance at three decision thresholds">
      <thead>
        <tr className={HEAD_ROW}>
          <Th>Threshold</Th>
          <Th>Accuracy</Th>
          <Th>Precision</Th>
          <Th>Recall</Th>
          <Th>F1</Th>
          <Th>FPR</Th>
          {withAuc && <Th>ROC-AUC</Th>}
          {withAuc && <Th>PR-AUC</Th>}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <MetricsRow key={row.label} label={row.label} metrics={row.metrics} withAuc={withAuc} />
        ))}
      </tbody>
    </TableShell>
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
    <TableShell caption="Heuristic scoring compared with the trained ML classifier">
      <thead>
        <tr className={HEAD_ROW}>
          <Th>Method</Th>
          <Th>Accuracy</Th>
          <Th>Precision</Th>
          <Th>Recall</Th>
          <Th>F1</Th>
          <Th>FPR</Th>
          <Th>ROC-AUC</Th>
          <Th>PR-AUC</Th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <MetricsRow key={row.label} label={row.label} metrics={row.metrics} withAuc />
        ))}
      </tbody>
    </TableShell>
  );
}

function GeneratorTable({ report }) {
  const gens = Object.entries(report?.cross_llm || {});
  if (!gens.length) return null;
  return (
    <TableShell caption="Detection performance by AI code generator">
      <thead>
        <tr className={HEAD_ROW}>
          <Th>Generator</Th>
          <Th>AI samples</Th>
          <Th>Precision</Th>
          <Th>Recall</Th>
          <Th>FPR</Th>
          <Th>ROC-AUC</Th>
        </tr>
      </thead>
      <tbody>
        {gens.map(([name, g]) => (
          <tr key={name} className="border-b border-slate-100 last:border-0">
            <td className="px-4 py-3 font-medium text-slate-700">{name}</td>
            <td className="px-4 py-3 text-slate-600">{num(g?.ai_samples) ?? 'n/a'}</td>
            <Cell value={g?.metrics?.precision} />
            <Cell value={g?.metrics?.recall} />
            <Cell value={g?.metrics?.fpr} kind="fpr" />
            <Cell value={g?.metrics?.auc} kind="auc" format="auc" />
          </tr>
        ))}
      </tbody>
    </TableShell>
  );
}

function PerplexityCompare({ statistical, codelm }) {
  if (!statistical && !codelm) return null;
  const srcs = [
    { label: 'Statistical bigram (current default)', report: statistical },
    { label: 'Causal code-LM (CodeGPT-small-py)', report: codelm },
  ].filter((src) => src.report?.grouped_holdout?.metrics);
  if (!srcs.length) return null;
  return (
    <TableShell caption="Perplexity signal sources compared">
      <thead>
        <tr className={HEAD_ROW}>
          <Th>Perplexity source</Th>
          <Th>F1</Th>
          <Th>FPR</Th>
          <Th>ROC-AUC</Th>
          <Th>PR-AUC</Th>
        </tr>
      </thead>
      <tbody>
        {srcs.map((src) => {
          const m = src.report.grouped_holdout.metrics;
          return (
            <tr key={src.label} className="border-b border-slate-100 last:border-0">
              <td className="px-4 py-3 font-medium text-slate-700">{src.label}</td>
              <Cell value={m.f1} />
              <Cell value={m.fpr} kind="fpr" />
              <Cell value={m.auc} kind="auc" format="auc" />
              <Cell value={m.pr_auc} kind="auc" format="auc" />
            </tr>
          );
        })}
      </tbody>
    </TableShell>
  );
}

// `state`: 'on' (enabled / the stronger option), 'off' (something expected is missing), 'neutral' (just a setting).
// Every badge used to show an amber warning triangle when "off", including settings that are off on purpose,
// and "Default engine" always showed one because it was hard-coded to off.
function StatBadge({ label, value, state = 'neutral' }) {
  return (
    <div className={`flex items-center gap-2 rounded-xl px-4 py-3 text-sm ${state === 'on' ? 'bg-slate-100' : 'bg-slate-50 text-slate-500'}`}>
      {state === 'on' ? (
        <CheckCircle2 size={16} className="text-emerald-600" aria-hidden="true" />
      ) : state === 'off' ? (
        <AlertTriangle size={16} className="text-amber-500" aria-hidden="true" />
      ) : (
        <Info size={16} className="text-slate-400" aria-hidden="true" />
      )}
      <span className="font-medium text-slate-700">{label}</span>
      <span className="ml-auto font-semibold text-slate-900">{value}</span>
    </div>
  );
}

function HumanFpBaseline({ baseline }) {
  const rows = Object.entries(baseline?.corpora || {});
  if (!rows.length) return null;
  const student = baseline?.corpora?.kaggle_student_code;
  // The text used to say "while experienced/community human code scores 0%" whatever the table held.
  const others = rows.filter(([name]) => name !== 'kaggle_student_code').map(([, c]) => num(c?.['fp_at_0.70'])).filter((v) => v !== null);
  const worstOther = others.length ? Math.max(...others) : null;
  return (
    <section className="theme-card-strong rounded-[30px] overflow-hidden">
      <div className="theme-section-line px-6 py-5 lg:px-7">
        <div className="inline-flex items-center gap-2 rounded-full border border-amber-600/10 bg-amber-500/[0.08] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-amber-700">
          <AlertTriangle size={13} aria-hidden="true" />
          §2 False positive validation
        </div>
        <h2 className="mt-3 font-display text-2xl font-semibold tracking-tight text-[var(--text-primary)]">
          Real-World FPR Validation
        </h2>
        <p className="mt-3 max-w-3xl text-sm leading-7 text-[var(--text-secondary)]">
          {student ? (
            <>
              The production detector was run over known-human code. On {student.count}{' '}
              real novice student Python submissions,{' '}
              <strong className="text-amber-700">
                {pctSmart(student['fp_at_0.70'])} score in the high band (≥ 0.70)
              </strong>{' '}
              and{' '}
              <strong className="text-amber-700">
                {pctSmart(student['fp_at_0.40'])} in the medium band (≥ 0.40)
              </strong>
              {worstOther !== null && (
                <> — compared with at most {pctSmart(worstOther)} in the high band for the other human corpora</>
              )}
              . Treat every AI score as a screening signal for a human conversation, never as a verdict.
            </>
          ) : (
            <>
              The production detector was run over {rows.length} held-out corpora of known-human
              code. These are flag rates at the screening (0.40), default (0.50) and high-confidence
              (0.70) thresholds. Treat every AI score as a screening signal for a human
              conversation, never as a verdict.
            </>
          )}
        </p>
        <div className="mt-5 overflow-x-auto">
          <table className="w-full min-w-[560px] text-left text-sm">
            <caption className="sr-only">Share of known-human code flagged at each threshold, by corpus</caption>
            <thead className="text-xs uppercase tracking-wide text-[var(--text-secondary)]">
              <tr>
                <th scope="col" className="pb-2 pr-4 font-medium">Corpus (all human)</th>
                <th scope="col" className="pb-2 pr-4 font-medium">n</th>
                <th scope="col" className="pb-2 pr-4 font-medium">FP ≥ 0.40</th>
                <th scope="col" className="pb-2 pr-4 font-medium">FP ≥ 0.50</th>
                <th scope="col" className="pb-2 font-medium">FP ≥ 0.70</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {rows.map(([name, c]) => (
                <tr key={name}>
                  <td className="py-2 pr-4 text-[var(--text-primary)]">
                    {c?.description || name}
                  </td>
                  {/* A missing rate was shown as 0%, which reads as "no false positives". */}
                  <td className="py-2 pr-4 text-[var(--text-secondary)]">{num(c?.count) ?? 'n/a'}</td>
                  <td className="py-2 pr-4 text-[var(--text-secondary)]">{pctSmart(c?.['fp_at_0.40'])}</td>
                  <td className="py-2 pr-4 text-[var(--text-secondary)]">{pctSmart(c?.['fp_at_0.50'])}</td>
                  <td className="py-2 font-medium text-amber-700">{pctSmart(c?.['fp_at_0.70'])}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <ul className="mt-4 list-disc space-y-1 pl-5 text-xs text-[var(--text-secondary)]">
          {(baseline.caveats || []).map((c, i) => (
            <li key={`${i}-${c}`}>{c}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}

const TAXONOMY_PILL_TONES = {
  live: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  partial: 'bg-amber-50 text-amber-700 ring-amber-600/20',
  gap: 'bg-orange-50 text-orange-700 ring-orange-600/20',
  missing: 'bg-slate-100 text-slate-500 ring-slate-300/60',
};

function TaxonomyStatusPill({ status, label }) {
  const cls = TAXONOMY_PILL_TONES[status] || TAXONOMY_PILL_TONES.missing;
  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${cls}`}>
      {label || status}
    </span>
  );
}

function TaxonomyCoverage({ taxonomy }) {
  const components = taxonomy?.components || [];
  if (!components.length) return null;
  const summary = taxonomy?.summary || {};
  const order = ['live', 'partial', 'gap', 'missing'];
  return (
    <section className="theme-card-strong rounded-[30px] overflow-hidden">
      <div className="theme-section-line px-6 py-5 lg:px-7">
        <div className="inline-flex items-center gap-2 rounded-full border border-blue-600/10 bg-blue-600/[0.06] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--accent-blue)]">
          <Layers size={13} aria-hidden="true" />
          Benchmark coverage map
        </div>
        <h2 className="mt-3 font-display text-2xl font-semibold tracking-tight text-[var(--text-primary)]">
          What is measured — and what is still missing
        </h2>
        <p className="mt-3 max-w-3xl text-sm leading-7 text-[var(--text-secondary)]">
          Every figure on this page belongs to the four-part structure a review panel asks about:
          detection performance, false-positive validation, robustness and generalization (see{' '}
          <span className="font-mono text-xs">docs/CODEPROVENANCE_BENCHMARK.md</span>). The table
          below states the status we can defend today, derived only from artifacts that exist in
          this repository — measured items are reproducible, the gaps are named rather than hidden.
        </p>
        <div className="mt-4 flex flex-wrap gap-4 text-xs text-[var(--text-secondary)]">
          {order.map((key) => (
            <span key={key} className="inline-flex items-center gap-2">
              <TaxonomyStatusPill status={key} label={key} />
              {summary[key] ?? 0} item{summary[key] === 1 ? '' : 's'}
            </span>
          ))}
        </div>
      </div>
      <div className="space-y-6 px-6 py-6 lg:px-7">
        {components.map((component, index) => (
          <div key={component.key ?? index} className="overflow-x-auto">
            <div className="mb-2 flex flex-wrap items-baseline gap-2">
              <span className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--accent-blue)]">
                §{component.number}
              </span>
              <h3 className="font-display text-lg font-semibold tracking-tight text-[var(--text-primary)]">
                {component.title}
              </h3>
              <span className="text-xs text-[var(--text-secondary)]">{component.summary}</span>
            </div>
            <table className="w-full min-w-[640px] text-left text-sm">
              <caption className="sr-only">{component.title}</caption>
              <thead className="text-xs uppercase tracking-wide text-[var(--text-secondary)]">
                <tr>
                  <th scope="col" className="pb-2 pr-4 font-medium">Item</th>
                  <th scope="col" className="pb-2 pr-4 font-medium">Status</th>
                  <th scope="col" className="pb-2 font-medium">Evidence</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {(component.items || []).map((item, itemIndex) => (
                  <tr key={item.key ?? itemIndex}>
                    <td className="py-2 pr-4 text-[var(--text-primary)]">{item.label}</td>
                    <td className="py-2 pr-4">
                      <TaxonomyStatusPill status={item.status} label={item.status_label} />
                    </td>
                    <td className="py-2 text-xs text-[var(--text-secondary)]">{item.evidence}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>
    </section>
  );
}

function SectionCard({ title, description, icon: Icon, children }) {
  return (
    <section className="rounded-2xl bg-white shadow-sm ring-1 ring-slate-200">
      <div className="flex items-center justify-between gap-4 border-b border-slate-100 px-5 py-4">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
          <div className="mt-1 text-xs text-slate-500">{description}</div>
        </div>
        {Icon && <Icon size={18} className="shrink-0 text-slate-400" aria-hidden="true" />}
      </div>
      <div className="space-y-4 p-5">{children}</div>
    </section>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────

const REFERENCE_HEADERS = ['x-correlation-id', 'x-request-id'];

function describeLoadError(err) {
  const status = typeof err?.response?.status === 'number' ? err.response.status : undefined;
  const headers = err?.response?.headers || {};
  const reference = REFERENCE_HEADERS.map((name) => headers[name]).find((v) => typeof v === 'string' && v);

  let message = 'Failed to load accuracy benchmark data.';
  if (status === 401) message = 'Your session has expired. Please sign in again.';
  else if (status === 403) message = 'You don’t have permission to view the accuracy benchmark.';

  return reference ? `${message} (Reference: ${reference})` : message;
}

export default function AIDetectionAccuracyPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  const load = useCallback((signal) => {
    setLoading(true);
    setError('');
    apiClient
      .get('/api/ai-detect/accuracy', { signal })
      .then((res) => setData(res.data))
      .catch((err) => {
        if (!signal.aborted) setError(describeLoadError(err));
      })
      .finally(() => {
        if (!signal.aborted) setLoading(false);
      });
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load, reloadKey]);

  const reports = data?.reports || {};
  const main = reports.main;
  const runtime = data?.runtime || null;
  const hasRuntime = Boolean(runtime);

  // The explanatory text below used to hard-code figures ("AUC ~0.52–0.55", "ML classifier (0.66)",
  // "code-LM (0.63)") and claims ("the causal code-LM improves ROC-AUC"). It went stale whenever the benchmark
  // was re-run, and was shown even if the data said something different. It is now built from the loaded data.
  const heuristicAuc = num(main?.heuristic_comparison?.heuristic_only?.auc);
  const mlAuc = num(main?.heuristic_comparison?.ml_classifier?.auc);
  const statAuc = num(reports.statistical?.grouped_holdout?.metrics?.auc);
  const lmAuc = num(reports.codelm?.grouped_holdout?.metrics?.auc);

  const heuristicVerdict =
    heuristicAuc === null ? null
      : heuristicAuc < 0.6 ? 'close to chance (0.5)'
        : heuristicAuc < 0.7 ? 'modest'
          : heuristicAuc < 0.8 ? 'fair'
            : 'strong';

  const perplexityNote =
    statAuc !== null && lmAuc !== null
      ? lmAuc > statAuc
        ? `On this holdout the causal code-LM scores a higher ROC-AUC than the statistical bigram (${auc(lmAuc)} vs ${auc(statAuc)}).`
        : `On this holdout the causal code-LM does not improve ROC-AUC over the statistical bigram (${auc(lmAuc)} vs ${auc(statAuc)}).`
      : 'Both perplexity sources are scored on the same held-out problems.';

  return (
    <DashboardLayout requiredRole="admin">
      <div className="theme-page-container">
        <div className="space-y-8">
          <section className="theme-card-strong rounded-[30px] overflow-hidden">
            <div className="theme-section-line px-6 py-5 lg:px-7">
              <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
                <div className="space-y-4">
                  <div className="inline-flex items-center gap-2 rounded-full border border-blue-600/10 bg-blue-600/[0.06] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--accent-blue)]">
                    <FlaskConical size={13} aria-hidden="true" />
                    AI Detector Accuracy Benchmark
                  </div>
                  <div>
                    <h1 className="font-display text-3xl font-semibold tracking-tight text-[var(--text-primary)] sm:text-4xl">
                      Measured accuracy, not marketing
                    </h1>
                    <p className="mt-3 max-w-3xl text-sm leading-7 text-[var(--text-secondary)]">
                      The reproducible numbers the AI detector achieves on unseen problems
                      (AIGCodeSet, grouped holdout by problem_id), so reviewers can judge the engine
                      on data rather than on the interface.
                    </p>
                  </div>
                </div>
                <BarChart3 size={28} className="text-slate-300" aria-hidden="true" />
              </div>
            </div>
          </section>

          {loading && (
            <div role="status" className="flex items-center justify-center py-24 text-sm text-slate-500">Loading benchmark…</div>
          )}

          {error && (
            <section role="alert" className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
              <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
              <span className="flex-1">{error}</span>
              <button
                type="button"
                onClick={() => setReloadKey((key) => key + 1)}
                className="shrink-0 font-semibold underline underline-offset-2"
              >
                Try again
              </button>
            </section>
          )}

          {!loading && data && (
            <>
              <TaxonomyCoverage taxonomy={data?.taxonomy} />

              {data?.human_fp_baseline && <HumanFpBaseline baseline={data.human_fp_baseline} />}

              {!data?.available && !main && (
                <section className="rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm text-amber-800">
                  <div className="flex items-start gap-3">
                    <Info size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
                    <div>
                      No benchmark report found. Build and run the AIGCodeSet benchmark to populate
                      this page:
                      <pre className="mt-3 overflow-x-auto rounded-lg bg-white/60 p-3 text-xs leading-6">
                        {'bash data/datasets/aigcodeset/download.sh\npython -m src.backend.engines.ai.build_aigcodeset\npython -m src.backend.engines.ai.benchmark_classifier'}
                      </pre>
                    </div>
                  </div>
                </section>
              )}

              <section className="rounded-2xl bg-white shadow-sm ring-1 ring-slate-200">
                <div className="border-b border-slate-100 px-5 py-4">
                  <h2 className="text-sm font-semibold text-slate-900">Current runtime configuration</h2>
                  <div className="mt-1 text-xs text-slate-500">What the detector actually uses in production right now.</div>
                </div>
                {hasRuntime ? (
                  <div className="grid gap-3 p-5 md:grid-cols-3">
                    <StatBadge label="ML classifier" value={runtime.ml_classifier_enabled ? 'Enabled' : 'Disabled'} state={runtime.ml_classifier_enabled ? 'on' : 'neutral'} />
                    <StatBadge
                      label="Perplexity source"
                      value={runtime.perplexity_model || 'statistical-bigram'}
                      state={String(runtime.perplexity_model || 'statistical').startsWith('statistical') ? 'neutral' : 'on'}
                    />
                    <StatBadge label="Default engine" value={runtime.default_engine || 'heuristic'} state="neutral" />
                  </div>
                ) : (
                  // The badges used to fall back to "Disabled" / "heuristic" when the runtime block was missing,
                  // presenting guesses as the live configuration.
                  <p className="p-5 text-sm text-slate-500">The runtime configuration wasn’t reported, so it can’t be shown.</p>
                )}
              </section>

              <SectionCard
                title="§1 Detection performance — grouped holdout (no leakage)"
                description={`${num(main?.n_samples)?.toLocaleString('en-US') ?? '—'} samples (${num(main?.n_ai)?.toLocaleString('en-US') ?? '—'} AI). 20% of problems held out; the same problem never spans train and test.`}
                icon={Sigma}
              >
                <ThresholdTable report={main} soc="auc" />
              </SectionCard>

              <SectionCard
                title="§1 Detection performance — heuristic vs ML classifier"
                description={`Same unseen test fold, two scoring methods.${hasRuntime ? (runtime.ml_classifier_enabled ? ' The ML classifier is currently enabled in production.' : ' The ML classifier is currently disabled in production.') : ''}`}
              >
                <ComparisonTable report={main} />
              </SectionCard>

              <SectionCard
                title="§1 Detection performance — per-generator sensitivity"
                description="Recall (and FPR on the shared human pool) against each generator on problems the model never trained on."
              >
                <GeneratorTable report={main} />
              </SectionCard>

              <SectionCard
                title="§1 Detection performance — perplexity signal comparison"
                description={perplexityNote}
              >
                <PerplexityCompare statistical={reports.statistical} codelm={reports.codelm} />
              </SectionCard>

              <section className="rounded-2xl border border-slate-200 bg-slate-50 px-5 py-4 text-sm text-slate-600">
                <div className="flex items-start gap-3">
                  <Shield size={16} className="mt-0.5 shrink-0 text-slate-400" aria-hidden="true" />
                  <div className="leading-7">
                    <h2 className="mb-2 font-semibold text-slate-700">Honest reading</h2>
                    <p>
                      {heuristicAuc !== null && (
                        <>
                          On this holdout the heuristic path reaches ROC-AUC {auc(heuristicAuc)}
                          {heuristicVerdict ? `, which is ${heuristicVerdict}` : ''}.{' '}
                        </>
                      )}
                      {mlAuc !== null && <>The trained ML classifier reaches {auc(mlAuc)}{lmAuc !== null ? ', ' : '. '}</>}
                      {lmAuc !== null && <>and the causal code-LM {auc(lmAuc)}. </>}
                      {hasRuntime && !runtime.ml_classifier_enabled && (
                        <>
                          The ML classifier is <span className="font-semibold text-slate-700">disabled in production</span>:
                          check its FPR above, especially on short, terse student code, before enabling it.{' '}
                        </>
                      )}
                      Every table reports FPR next to recall, and PR-AUC alongside ROC-AUC, so the cost of a
                      wrongly flagged human is never hidden behind a single headline number. Scores are indicators,
                      not proof, and AIGCodeSet alone cannot validate the product&apos;s real input distribution.
                      These are point estimates from a single holdout split and are shown without confidence
                      intervals, so small differences between methods may not be meaningful. See
                      <span className="font-mono text-xs text-slate-500"> docs/AI_DETECTOR_VS_TURNITIN.md</span> for the full gap analysis.
                    </p>
                  </div>
                </div>
              </section>
            </>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
