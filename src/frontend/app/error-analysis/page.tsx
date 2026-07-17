// @ts-nocheck — TODO: add proper types (tracked in types/api.ts)
'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { useAuth } from '@/components/AuthProvider';
import { apiClient } from '@/lib/apiClient';
import { useState, useEffect } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  XCircle,
  TrendingUp,
  BarChart3,
  ChevronDown,
  ChevronUp,
  FileText,
  Lightbulb,
  Cpu,
  ShieldAlert,
  GraduationCap,
  Zap,
  RefreshCw,
  Database,
  Info,
} from 'lucide-react';

/* ─── helpers ──────────────────────────────────────────────────────────── */
const pct = (n: number) => `${(n * 100).toFixed(1)}%`;

/* ─── sub-components ───────────────────────────────────────────────────── */
function MetricCard({ label, value, sub, color, icon: Icon }) {
  const palette = {
    blue: { bg: 'bg-blue-50', border: 'border-blue-200', text: 'text-blue-700', icon: 'text-blue-500', sub: 'text-blue-500' },
    emerald: { bg: 'bg-emerald-50', border: 'border-emerald-200', text: 'text-emerald-700', icon: 'text-emerald-500', sub: 'text-emerald-500' },
    amber: { bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-700', icon: 'text-amber-500', sub: 'text-amber-500' },
    violet: { bg: 'bg-violet-50', border: 'border-violet-200', text: 'text-violet-700', icon: 'text-violet-500', sub: 'text-violet-500' },
  }[color];

  return (
    <div className={`${palette.bg} ${palette.border} border rounded-2xl p-5 flex flex-col gap-3`}>
      <div className="flex items-center justify-between">
        <span className={`text-xs font-semibold uppercase tracking-widest ${palette.sub}`}>{label}</span>
        <Icon size={16} className={palette.icon} />
      </div>
      <div className={`text-4xl font-black ${palette.text} leading-none`}>{value}</div>
      <div className={`text-xs ${palette.sub}`}>{sub}</div>
    </div>
  );
}

function ConfusionMatrix({ tp, fp, fn, tn }) {
  const total = tp + fp + fn + tn || 1;
  const cell = (value, label, sub, bg, text, border) => (
    <div className={`${bg} ${border} border rounded-xl p-5 flex flex-col gap-1`}>
      <span className={`text-3xl font-black ${text}`}>{value}</span>
      <span className={`text-sm font-semibold ${text}`}>{label}</span>
      <span className="text-xs text-slate-500">{sub}</span>
      <span className="text-xs text-slate-400 mt-1">{((value / total) * 100).toFixed(1)}% of total</span>
    </div>
  );
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-[auto_1fr_1fr] gap-3 items-center text-xs font-semibold text-slate-500 uppercase tracking-wider">
        <div />
        <div className="text-center">Predicted Plagiarism</div>
        <div className="text-center">Predicted Original</div>
      </div>
      <div className="grid grid-cols-[auto_1fr_1fr] gap-3 items-stretch">
        <div className="flex flex-col justify-around text-xs font-semibold text-slate-500 uppercase tracking-wider text-right pr-2 gap-3">
          <div>Actual<br />Plagiarism</div>
          <div>Actual<br />Original</div>
        </div>
        {cell(tp, 'True Positives', 'Correctly flagged plagiarism', 'bg-emerald-50', 'text-emerald-700', 'border-emerald-200')}
        {cell(fn, 'False Negatives', 'Plagiarism that slipped through', 'bg-orange-50', 'text-orange-700', 'border-orange-200')}
        {cell(fp, 'False Positives', 'Legitimate work incorrectly flagged', 'bg-rose-50', 'text-rose-700', 'border-rose-200')}
        {cell(tn, 'True Negatives', 'Correctly cleared as original', 'bg-slate-50', 'text-slate-600', 'border-slate-200')}
      </div>
    </div>
  );
}

function ErrorCaseRow({ item, prefix, isOpen, onToggle }) {
  const scorePct = (item.score * 100).toFixed(1);
  const scoreColor =
    item.score >= 0.7 ? 'text-rose-600 bg-rose-50 border-rose-200' :
      item.score >= 0.4 ? 'text-amber-600 bg-amber-50 border-amber-200' :
        'text-slate-600 bg-slate-50 border-slate-200';

  return (
    <div className="border border-slate-200 rounded-xl overflow-hidden transition-shadow hover:shadow-sm">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-slate-50/80 transition-colors text-left"
      >
        <div className="flex items-center gap-3 min-w-0">
          <FileText size={15} className="text-slate-400 shrink-0" />
          <span className="font-medium text-slate-900 truncate">{item.fileA}</span>
          <span className="text-slate-400 shrink-0">↔</span>
          <span className="font-medium text-slate-900 truncate">{item.fileB}</span>
        </div>
        <div className="flex items-center gap-3 shrink-0 ml-4">
          <span className={`text-xs font-semibold px-2.5 py-1 rounded-full border ${scoreColor}`}>
            {scorePct}% similarity
          </span>
          {isOpen ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
        </div>
      </button>

      {isOpen && (
        <div className="px-5 pb-5 border-t border-slate-100 space-y-4 pt-4">
          <div className="inline-flex items-center gap-1.5 text-xs font-medium bg-slate-100 text-slate-700 rounded-full px-3 py-1">
            <AlertTriangle size={11} />
            {item.reason}
          </div>
          <p className="text-sm text-slate-600 leading-relaxed">{item.explanation}</p>

          {/* Engine feature breakdown */}
          {item.features && Object.keys(item.features).length > 0 && (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">Engine Scores</p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {Object.entries(item.features)
                  .sort(([, a], [, b]) => Number(b) - Number(a))
                  .slice(0, 6)
                  .map(([engine, score]) => (
                    <div key={engine} className="bg-slate-50 rounded-lg px-3 py-2">
                      <div className="text-xs text-slate-500 capitalize">{engine.replace(/_/g, ' ')}</div>
                      <div className="text-sm font-bold text-slate-800">{(Number(score) * 100).toFixed(1)}%</div>
                      <div className="mt-1 h-1.5 bg-slate-200 rounded-full overflow-hidden">
                        <div className="h-full bg-violet-500 rounded-full" style={{ width: `${Number(score) * 100}%` }} />
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          )}

          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">Feature Summary</p>
            <pre className="bg-slate-950 text-slate-100 rounded-xl p-4 text-xs font-mono leading-relaxed overflow-x-auto">
              {item.codeSnippet}
            </pre>
          </div>

          <div className="flex items-start gap-2.5 bg-blue-50 border border-blue-100 rounded-xl p-4">
            <Lightbulb size={15} className="text-blue-500 mt-0.5 shrink-0" />
            <div>
              <p className="text-xs font-semibold text-blue-700 mb-0.5">Recommendation</p>
              <p className="text-sm text-blue-700">{item.recommendation}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function EngineBar({ engine, percent, color }) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-sm">
        <span className="text-slate-700 capitalize font-medium">{engine.replace(/_/g, ' ')}</span>
        <span className="font-semibold text-slate-900 tabular-nums">{percent}%</span>
      </div>
      <div className="w-full bg-slate-100 rounded-full h-2.5">
        <div className={`${color} h-2.5 rounded-full transition-all duration-700`} style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

function SectionHeader({ icon: Icon, iconClass, title, count, description }) {
  return (
    <div className="mb-5">
      <div className="flex items-center gap-2.5 mb-1">
        <div className={`p-1.5 rounded-lg ${iconClass} bg-opacity-15`}>
          <Icon size={18} className={iconClass} />
        </div>
        <h2 className="text-lg font-bold text-slate-900">
          {title}
          {count !== undefined && (
            <span className="ml-2 text-sm font-semibold text-slate-400">({count} cases)</span>
          )}
        </h2>
      </div>
      <p className="text-sm text-slate-500 leading-relaxed pl-9">{description}</p>
    </div>
  );
}

/* ─── main page ────────────────────────────────────────────────────────── */
export default function ErrorAnalysisPage() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [data, setData] = useState(null);
  const [expandedErrors, setExpandedErrors] = useState(new Set());

  const fetchData = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await apiClient.get('/api/error-analysis');
      setData(res.data);
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to load error analysis.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const toggleError = (key) => {
    setExpandedErrors((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  if (loading) {
    return (
      <DashboardLayout>
        <div className="p-4 flex flex-col items-center justify-center min-h-[60vh] gap-4">
          <div className="h-12 w-12 rounded-full border-4 border-slate-100 border-t-violet-600 animate-spin" />
          <p className="text-sm text-slate-500 font-medium">Loading error analysis…</p>
        </div>
      </DashboardLayout>
    );
  }

  if (error) {
    return (
      <DashboardLayout>
        <div className="p-4 flex flex-col items-center justify-center min-h-[60vh] gap-4">
          <AlertTriangle size={32} className="text-amber-500" />
          <p className="text-slate-700 font-medium">{error}</p>
          <button onClick={fetchData} className="flex items-center gap-2 px-4 py-2 bg-slate-900 text-white rounded-lg text-sm font-semibold hover:bg-slate-800">
            <RefreshCw size={14} /> Retry
          </button>
        </div>
      </DashboardLayout>
    );
  }

  if (!data) return null;

  const { summary, falsePositives, falseNegatives, engineContributions, recommendations, source, dataset, has_ground_truth } = data;

  const noData = summary.totalPairs === 0;

  return (
    <DashboardLayout>
      <div className="p-4">
        <div className="space-y-6">

          {/* ── Page Header ── */}
          <div className="flex items-start justify-between flex-wrap gap-3">
            <div>
              <div className="flex items-center gap-2.5 mb-1">
                <ShieldAlert size={22} className="text-violet-600" />
                <h1 className="text-2xl font-black text-slate-900 tracking-tight">Error Analysis Report</h1>
              </div>
              <p className="text-sm text-slate-500 pl-8">
                {noData
                  ? 'No plagiarism checks or benchmark runs found yet.'
                  : `Detection quality audit across ${summary.totalPairs.toLocaleString()} submission pairs`}
              </p>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              {/* Data source badge */}
              <div className={`flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-full ${has_ground_truth ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
                }`}>
                <Database size={12} />
                {has_ground_truth ? `Ground truth · ${dataset}` : `Heuristic · ${dataset}`}
              </div>
              <div className="flex items-center gap-1.5 bg-slate-100 text-slate-600 text-xs font-semibold px-3 py-1.5 rounded-full">
                <GraduationCap size={13} />
                {user?.role === 'admin' ? 'Admin View' : 'Professor View'}
              </div>
              <button onClick={fetchData} className="flex items-center gap-1.5 bg-slate-100 hover:bg-slate-200 text-slate-600 text-xs font-semibold px-3 py-1.5 rounded-full transition-colors">
                <RefreshCw size={12} /> Refresh
              </button>
            </div>
          </div>

          {/* ── No data state ── */}
          {noData && (
            <div className="bg-white border border-slate-200 rounded-2xl p-10 text-center shadow-sm">
              <Database size={40} className="text-slate-300 mx-auto mb-4" />
              <h2 className="text-lg font-bold text-slate-700 mb-2">No analysis data yet</h2>
              <p className="text-sm text-slate-500 max-w-md mx-auto mb-6">
                Run a plagiarism check on the <strong>Upload</strong> page, or run a benchmark with a labeled dataset to generate real error analysis data.
              </p>
              <div className="flex items-center justify-center gap-3">
                <a href="/upload" className="px-4 py-2 bg-slate-900 text-white rounded-lg text-sm font-semibold hover:bg-slate-800">
                  Run a Check
                </a>
                <a href="/benchmark" className="px-4 py-2 bg-violet-600 text-white rounded-lg text-sm font-semibold hover:bg-violet-700">
                  Run Benchmark
                </a>
              </div>
            </div>
          )}

          {!noData && (
            <>
              {/* ── Ground truth notice ── */}
              {!has_ground_truth && (
                <div className="flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-2xl px-5 py-4 text-sm text-amber-800">
                  <Info size={16} className="shrink-0 mt-0.5 text-amber-600" />
                  <div>
                    <span className="font-semibold">Heuristic analysis — no ground-truth labels available.</span>
                    {' '}Metrics are estimated from score distributions across your real job results.
                    Run a benchmark with a labeled dataset (e.g. a PAN or demo dataset) to get exact TP/FP/FN/TN counts.
                  </div>
                </div>
              )}

              {/* ── Metric Cards ── */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <MetricCard label="Accuracy" value={pct(summary.accuracy)} sub="Overall correctness" color="blue" icon={BarChart3} />
                <MetricCard label="Precision" value={pct(summary.precision)} sub="Flagged cases that are real" color="emerald" icon={CheckCircle2} />
                <MetricCard label="Recall" value={pct(summary.recall)} sub="Real cases detected" color="amber" icon={TrendingUp} />
                <MetricCard label="F1 Score" value={pct(summary.f1)} sub="Precision–recall balance" color="violet" icon={Zap} />
              </div>

              {/* ── Confusion Matrix ── */}
              <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
                <div className="flex items-center gap-2 mb-6">
                  <BarChart3 size={18} className="text-slate-500" />
                  <h2 className="text-base font-bold text-slate-900">Confusion Matrix</h2>
                  <span className="ml-auto text-xs text-slate-400 font-medium">
                    {summary.totalPairs.toLocaleString()} total pairs evaluated
                  </span>
                </div>
                <ConfusionMatrix
                  tp={summary.truePositives}
                  fp={summary.falsePositives}
                  fn={summary.falseNegatives}
                  tn={summary.trueNegatives}
                />
              </div>

              {/* ── False Positives ── */}
              <div className="bg-white border border-rose-100 rounded-2xl p-6 shadow-sm">
                <SectionHeader
                  icon={XCircle}
                  iconClass="text-rose-600"
                  title="False Positives"
                  count={falsePositives.length}
                  description="Cases where the system incorrectly flagged legitimate work as plagiarism. These can damage student reputations and require urgent manual review."
                />
                {falsePositives.length === 0 ? (
                  <div className="text-center py-8 text-slate-400 text-sm">
                    <CheckCircle2 size={28} className="mx-auto mb-2 text-emerald-400" />
                    No false positives detected in this dataset.
                  </div>
                ) : (
                  <div className="space-y-3">
                    {falsePositives.map((fp) => (
                      <ErrorCaseRow
                        key={fp.id}
                        item={fp}
                        prefix="fp"
                        isOpen={expandedErrors.has(`fp-${fp.id}`)}
                        onToggle={() => toggleError(`fp-${fp.id}`)}
                      />
                    ))}
                  </div>
                )}
              </div>

              {/* ── False Negatives ── */}
              <div className="bg-white border border-orange-100 rounded-2xl p-6 shadow-sm">
                <SectionHeader
                  icon={AlertTriangle}
                  iconClass="text-orange-600"
                  title="False Negatives"
                  count={falseNegatives.length}
                  description="Cases where actual plagiarism went undetected. These are the more serious failure mode — cheating that reaches your gradebook unchallenged."
                />
                {falseNegatives.length === 0 ? (
                  <div className="text-center py-8 text-slate-400 text-sm">
                    <CheckCircle2 size={28} className="mx-auto mb-2 text-emerald-400" />
                    No false negatives detected in this dataset.
                  </div>
                ) : (
                  <div className="space-y-3">
                    {falseNegatives.map((fn) => (
                      <ErrorCaseRow
                        key={fn.id}
                        item={fn}
                        prefix="fn"
                        isOpen={expandedErrors.has(`fn-${fn.id}`)}
                        onToggle={() => toggleError(`fn-${fn.id}`)}
                      />
                    ))}
                  </div>
                )}
              </div>

              {/* ── Engine Contribution ── */}
              {(Object.keys(engineContributions.falsePositives || {}).length > 0 ||
                Object.keys(engineContributions.falseNegatives || {}).length > 0) && (
                  <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
                    <div className="flex items-center gap-2 mb-1">
                      <Cpu size={18} className="text-slate-500" />
                      <h2 className="text-base font-bold text-slate-900">Engine Contribution to Errors</h2>
                    </div>
                    <p className="text-sm text-slate-500 mb-6 pl-7">
                      Which detection engines are responsible for each error type, computed from real feature scores.
                    </p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                      <div>
                        <p className="text-xs font-bold uppercase tracking-widest text-rose-500 mb-4">False Positive Drivers</p>
                        <div className="space-y-4">
                          {Object.entries(engineContributions.falsePositives || {}).map(([engine, percent]) => (
                            <EngineBar key={engine} engine={engine} percent={percent} color="bg-rose-400" />
                          ))}
                          {Object.keys(engineContributions.falsePositives || {}).length === 0 && (
                            <p className="text-sm text-slate-400">No false positive engine data available.</p>
                          )}
                        </div>
                      </div>
                      <div>
                        <p className="text-xs font-bold uppercase tracking-widest text-orange-500 mb-4">False Negative Drivers</p>
                        <div className="space-y-4">
                          {Object.entries(engineContributions.falseNegatives || {}).map(([engine, percent]) => (
                            <EngineBar key={engine} engine={engine} percent={percent} color="bg-orange-400" />
                          ))}
                          {Object.keys(engineContributions.falseNegatives || {}).length === 0 && (
                            <p className="text-sm text-slate-400">No false negative engine data available.</p>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                )}

              {/* ── Recommendations ── */}
              {recommendations && recommendations.length > 0 && (
                <div className="bg-slate-900 text-white rounded-2xl p-6 shadow-sm">
                  <div className="flex items-center gap-2 mb-6">
                    <GraduationCap size={18} className="text-violet-400" />
                    <h2 className="text-base font-bold">Actionable Recommendations</h2>
                    <span className="ml-auto text-xs text-slate-400">Based on your real data</span>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                    {recommendations.map((rec) => {
                      const priorityColor = rec.priority === 'high'
                        ? 'border-rose-500'
                        : rec.priority === 'medium'
                          ? 'border-amber-500'
                          : 'border-emerald-500';
                      const accentColor = rec.priority === 'high'
                        ? 'text-rose-400'
                        : rec.priority === 'medium'
                          ? 'text-amber-400'
                          : 'text-emerald-400';
                      return (
                        <div key={rec.category} className={`bg-white/5 border-t-2 ${priorityColor} rounded-xl p-4 space-y-3`}>
                          <div className="flex items-center justify-between gap-2">
                            <h3 className={`text-sm font-bold ${accentColor}`}>{rec.category}</h3>
                            <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${rec.priority === 'high' ? 'bg-rose-500/20 text-rose-400' :
                                rec.priority === 'medium' ? 'bg-amber-500/20 text-amber-400' :
                                  'bg-emerald-500/20 text-emerald-400'
                              }`}>{rec.priority}</span>
                          </div>
                          <ul className="space-y-3">
                            {rec.items.map((item) => (
                              <li key={item.title}>
                                <p className="text-xs font-semibold text-white">{item.title}</p>
                                <p className="text-xs text-slate-400 leading-relaxed">{item.detail}</p>
                              </li>
                            ))}
                          </ul>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
