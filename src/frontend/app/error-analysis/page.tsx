// @ts-nocheck
'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { useAuth } from '@/components/AuthProvider';
import { useState, useEffect, useMemo } from 'react';
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
} from 'lucide-react';

/* ─── tiny helpers ─────────────────────────────────────────────────────── */
const pct = (n: number) => `${(n * 100).toFixed(1)}%`;

/* ─── types ────────────────────────────────────────────────────────────── */
interface ErrorCase {
  id: number;
  fileA: string;
  fileB: string;
  score: number;
  reason: string;
  explanation: string;
  codeSnippet: string;
  recommendation: string;
}

/* ─── sub-components ───────────────────────────────────────────────────── */

function MetricCard({
  label,
  value,
  sub,
  color,
  icon: Icon,
}: {
  label: string;
  value: string;
  sub: string;
  color: 'blue' | 'emerald' | 'amber' | 'violet';
  icon: React.ElementType;
}) {
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

/* Proper 2×2 confusion matrix */
function ConfusionMatrix({ tp, fp, fn, tn }: { tp: number; fp: number; fn: number; tn: number }) {
  const total = tp + fp + fn + tn;
  const cell = (
    value: number,
    label: string,
    sub: string,
    bg: string,
    text: string,
    border: string,
  ) => (
    <div className={`${bg} ${border} border rounded-xl p-5 flex flex-col gap-1`}>
      <span className={`text-3xl font-black ${text}`}>{value}</span>
      <span className={`text-sm font-semibold ${text}`}>{label}</span>
      <span className="text-xs text-slate-500">{sub}</span>
      <span className="text-xs text-slate-400 mt-1">{((value / total) * 100).toFixed(1)}% of total</span>
    </div>
  );

  return (
    <div className="space-y-3">
      {/* axis labels */}
      <div className="grid grid-cols-[auto_1fr_1fr] gap-3 items-center text-xs font-semibold text-slate-500 uppercase tracking-wider">
        <div />
        <div className="text-center">Predicted Plagiarism</div>
        <div className="text-center">Predicted Original</div>
      </div>

      <div className="grid grid-cols-[auto_1fr_1fr] gap-3 items-stretch">
        {/* row label */}
        <div className="flex flex-col justify-around text-xs font-semibold text-slate-500 uppercase tracking-wider text-right pr-2 gap-3">
          <div>Actual<br />Plagiarism</div>
          <div>Actual<br />Original</div>
        </div>

        {/* TP */}
        {cell(tp, 'True Positives', 'Correctly flagged plagiarism', 'bg-emerald-50', 'text-emerald-700', 'border-emerald-200')}
        {/* FN */}
        {cell(fn, 'False Negatives', 'Plagiarism that slipped through', 'bg-orange-50', 'text-orange-700', 'border-orange-200')}
        {/* FP */}
        {cell(fp, 'False Positives', 'Legitimate work incorrectly flagged', 'bg-rose-50', 'text-rose-700', 'border-rose-200')}
        {/* TN */}
        {cell(tn, 'True Negatives', 'Correctly cleared as original', 'bg-slate-50', 'text-slate-600', 'border-slate-200')}
      </div>
    </div>
  );
}

/* Expandable error case row */
function ErrorCaseRow({ item, prefix, isOpen, onToggle }: {
  item: ErrorCase;
  prefix: string;
  isOpen: boolean;
  onToggle: () => void;
}) {
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
          <span className="font-medium text-slate-900 truncate">
            {item.fileA}
          </span>
          <span className="text-slate-400 shrink-0">↔</span>
          <span className="font-medium text-slate-900 truncate">
            {item.fileB}
          </span>
        </div>
        <div className="flex items-center gap-3 shrink-0 ml-4">
          <span className={`text-xs font-semibold px-2.5 py-1 rounded-full border ${scoreColor}`}>
            {scorePct}% similarity
          </span>
          {isOpen
            ? <ChevronUp size={16} className="text-slate-400" />
            : <ChevronDown size={16} className="text-slate-400" />}
        </div>
      </button>

      {isOpen && (
        <div className="px-5 pb-5 border-t border-slate-100 space-y-4 pt-4">
          {/* reason badge */}
          <div className="inline-flex items-center gap-1.5 text-xs font-medium bg-slate-100 text-slate-700 rounded-full px-3 py-1">
            <AlertTriangle size={11} />
            {item.reason}
          </div>

          <p className="text-sm text-slate-600 leading-relaxed">{item.explanation}</p>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">Code Sample</p>
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

/* Engine bar chart — fixed: uses full container width for proper scaling */
function EngineBar({ engine, percent, color }: { engine: string; percent: number; color: string }) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-sm">
        <span className="text-slate-700 capitalize font-medium">{engine}</span>
        <span className="font-semibold text-slate-900 tabular-nums">{percent}%</span>
      </div>
      <div className="w-full bg-slate-100 rounded-full h-2.5">
        <div
          className={`${color} h-2.5 rounded-full transition-all duration-700`}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

/* Section header */
function SectionHeader({
  icon: Icon,
  iconClass,
  title,
  count,
  description,
}: {
  icon: React.ElementType;
  iconClass: string;
  title: string;
  count?: number;
  description: string;
}) {
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
function ErrorAnalysisPage() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [expandedErrors, setExpandedErrors] = useState<Set<string>>(new Set());

  const errorData = useMemo(() => ({
    summary: {
      totalPairs: 800,
      truePositives: 120,
      trueNegatives: 680,
      falsePositives: 12,
      falseNegatives: 45,
      precision: 0.91,
      recall: 0.73,
      f1: 0.81,
      accuracy: 0.94,
    },
    falsePositives: [
      {
        id: 1,
        fileA: 'student1.java',
        fileB: 'student2.java',
        score: 0.87,
        reason: 'Shared boilerplate code and common patterns',
        explanation:
          'Both submissions used identical Java class structure and import statements from the assignment template. The similarity score was inflated by these necessary code elements.',
        codeSnippet: `import java.util.Scanner;\npublic class Main {\n    public static void main(String[] args) {\n        Scanner sc = new Scanner(System.in);\n        // Assignment code here\n    }\n}`,
        recommendation: 'Implement boilerplate filtering or base code removal',
      },
      {
        id: 2,
        fileA: 'student3.java',
        fileB: 'student4.java',
        score: 0.82,
        reason: 'Algorithmic coincidence',
        explanation:
          'Both students independently implemented the same efficient sorting algorithm, leading to structural similarity despite no copying.',
        codeSnippet: `// Quick sort implementation\nprivate static void quickSort(int[] arr, int low, int high) {\n    if (low < high) {\n        int pi = partition(arr, low, high);\n        quickSort(arr, low, pi-1);\n        quickSort(arr, pi+1, high);\n    }\n}`,
        recommendation: 'Add algorithmic pattern recognition to distinguish legitimate solutions',
      },
    ] as ErrorCase[],
    falseNegatives: [
      {
        id: 1,
        fileA: 'student5.java',
        fileB: 'student6.java',
        score: 0.25,
        reason: 'Heavy variable renaming and restructuring',
        explanation:
          'Student copied code but systematically renamed all variables and reordered functions. Current engines missed the semantic similarity.',
        codeSnippet: `// Original: calculateSum\n// Copied: computeTotal\npublic int computeTotal(List<Integer> numbers) {\n    return numbers.stream().mapToInt(Integer::intValue).sum();\n}`,
        recommendation: 'Enhance semantic similarity detection and AST-based matching',
      },
      {
        id: 2,
        fileA: 'student7.java',
        fileB: 'student8.java',
        score: 0.18,
        reason: 'Commented out original code',
        explanation:
          'Student copied code but commented out sections and rewrote them differently. The plagiarism was obscured by the comments.',
        codeSnippet: `// Old implementation\n/*\npublic void processData(String input) {\n    // processing logic\n}\n*/\n// New implementation\npublic void handleInput(String data) {\n    // different logic\n}`,
        recommendation: 'Improve detection of commented code and partial copying patterns',
      },
    ] as ErrorCase[],
    engineContributions: {
      falsePositives: { token: 35, ast: 20, embedding: 25, winnowing: 15, execution: 5 },
      falseNegatives: { token: 10, ast: 40, embedding: 30, winnowing: 15, execution: 5 },
    },
  }), []);

  useEffect(() => {
    const t = setTimeout(() => setLoading(false), 800);
    return () => clearTimeout(t);
  }, []);

  const toggleError = (key: string) => {
    setExpandedErrors((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
          <div className="relative">
            <div className="h-12 w-12 rounded-full border-4 border-slate-100 border-t-violet-600 animate-spin" />
          </div>
          <p className="text-sm text-slate-500 font-medium">Loading error analysis…</p>
        </div>
      </DashboardLayout>
    );
  }

  const { summary, falsePositives, falseNegatives, engineContributions } = errorData;

  return (
    <DashboardLayout>
      <div className="max-w-7xl mx-auto space-y-8 pb-12">

        {/* ── Page Header ── */}
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2.5 mb-1">
              <ShieldAlert size={22} className="text-violet-600" />
              <h1 className="text-2xl font-black text-slate-900 tracking-tight">
                Error Analysis Report
              </h1>
            </div>
            <p className="text-sm text-slate-500 pl-8">
              Detection quality audit across {summary.totalPairs.toLocaleString()} submission pairs
            </p>
          </div>
          <div className="flex items-center gap-1.5 bg-slate-100 text-slate-600 text-xs font-semibold px-3 py-1.5 rounded-full">
            <GraduationCap size={13} />
            Professor View
          </div>
        </div>

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
            description="Cases where the system incorrectly flagged legitimate student work as plagiarism. These can damage student reputations and require urgent manual review."
          />
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
        </div>

        {/* ── Engine Contribution ── */}
        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
          <div className="flex items-center gap-2 mb-1">
            <Cpu size={18} className="text-slate-500" />
            <h2 className="text-base font-bold text-slate-900">Engine Contribution to Errors</h2>
          </div>
          <p className="text-sm text-slate-500 mb-6 pl-7">
            Which detection engines are responsible for each error type. Bars show percentage of errors attributable to each engine.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div>
              <p className="text-xs font-bold uppercase tracking-widest text-rose-500 mb-4">
                False Positive Drivers
              </p>
              <div className="space-y-4">
                {Object.entries(engineContributions.falsePositives).map(([engine, percent]) => (
                  <EngineBar key={engine} engine={engine} percent={percent} color="bg-rose-400" />
                ))}
              </div>
            </div>

            <div>
              <p className="text-xs font-bold uppercase tracking-widest text-orange-500 mb-4">
                False Negative Drivers
              </p>
              <div className="space-y-4">
                {Object.entries(engineContributions.falseNegatives).map(([engine, percent]) => (
                  <EngineBar key={engine} engine={engine} percent={percent} color="bg-orange-400" />
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* ── Recommendations ── */}
        <div className="bg-slate-900 text-white rounded-2xl p-6 shadow-sm">
          <div className="flex items-center gap-2 mb-6">
            <GraduationCap size={18} className="text-violet-400" />
            <h2 className="text-base font-bold">Recommendations for Professors</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[
              {
                title: 'System Improvements',
                color: 'border-rose-500',
                accent: 'text-rose-400',
                items: [
                  ['Enhance semantic detection', 'Current system misses heavily obfuscated plagiarism — prioritise AST and embedding analysis.'],
                  ['Implement boilerplate filtering', 'Many false positives stem from required assignment templates.'],
                  ['Add partial copying detection', 'System struggles with mixed original/copied segments.'],
                  ['Recalibrate thresholds', 'Current thresholds are too conservative, missing real cases.'],
                ],
              },
              {
                title: 'Manual Review Guidelines',
                color: 'border-amber-500',
                accent: 'text-amber-400',
                items: [
                  ['High-confidence flags', 'Investigate immediately — these are very likely real cases.'],
                  ['Medium-confidence flags', 'Review code structure and comments for plagiarism indicators.'],
                  ['Low-confidence flags', 'Check for shared assignment requirements before dismissing.'],
                  ['Missed cases', 'Look for patterns in undetected plagiarism to improve future detection.'],
                ],
              },
              {
                title: 'Preventive Measures',
                color: 'border-emerald-500',
                accent: 'text-emerald-400',
                items: [
                  ['Assignment design', 'Create unique problems that reduce template code sharing.'],
                  ['Code review process', 'Implement peer code reviews during development.'],
                  ['Integrity education', 'Teach students about plagiarism consequences proactively.'],
                  ['Staged submissions', 'Require intermediate submissions to track code evolution.'],
                ],
              },
            ].map((section) => (
              <div
                key={section.title}
                className={`bg-white/5 border-t-2 ${section.color} rounded-xl p-4 space-y-3`}
              >
                <h3 className={`text-sm font-bold ${section.accent}`}>{section.title}</h3>
                <ul className="space-y-3">
                  {section.items.map(([title, desc]) => (
                    <li key={title}>
                      <p className="text-xs font-semibold text-white">{title}</p>
                      <p className="text-xs text-slate-400 leading-relaxed">{desc}</p>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

export default ErrorAnalysisPage;