'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/apiClient';
import { AxiosError } from 'axios';
import {
  AlertCircle,
  ClipboardList,
  FileText,
  Loader2,
  Play,
  RefreshCw,
  ShieldCheck,
  UploadCloud,
  X,
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceArea,
} from 'recharts';

interface RecommendationItem {
  threshold: number;
  fpr: number;
  type: string;
  title: string;
  advice: string;
}

interface FprResult {
  num_submissions: number;
  num_pairs: number;
  mean_score: number;
  max_score: number;
  fpr_table: Array<{
    threshold: number;
    fpr: number;
    fpr_percent: number;
    label: string;
    flagged_pairs: number;
  }>;
  score_histogram: Array<{ bin: string; count: number }>;
  recommendation: string;                    // legacy
  recommendations?: RecommendationItem[];
  overall_assessment?: string;
  suggested_actions?: string[];
}

interface FprRunSummary {
  id: string;
  name: string;
  created_at: string;
  num_submissions: number | null;
  num_pairs: number | null;
  recommended_threshold: number | null;
  fpr_at_recommended_threshold: number | null;
  is_certified: boolean;
  status: string;
}

interface FprRunDetail {
  id: string;
  name: string;
  created_at: string;
  notes: string | null;
  is_certified: boolean;
  certified_at: string | null;
  result: FprResult;
}

function generateFprReportHtml(result: FprResult): string {
  const dateStr = new Date().toLocaleString();

  // Build FPR table rows
  const fprRows = result.fpr_table
    .map(
      (row) => `
        <tr>
          <td style="padding: 8px; border: 1px solid #ddd;">${(row.threshold * 100).toFixed(0)}%</td>
          <td style="padding: 8px; border: 1px solid #ddd; font-weight: 600;">${row.fpr_percent.toFixed(2)}%</td>
          <td style="padding: 8px; border: 1px solid #ddd;">${row.flagged_pairs} / ${result.num_pairs}</td>
          <td style="padding: 8px; border: 1px solid #ddd;">${row.label}</td>
        </tr>
      `
    )
    .join('');

  // Build recommendations
  let recHtml = '';
  if (result.recommendations && result.recommendations.length > 0) {
    recHtml = result.recommendations
      .map(
        (rec) => `
          <div style="margin-bottom: 12px; padding: 12px; border: 1px solid #ddd; border-radius: 6px;">
            <strong>${rec.title}</strong> — ${rec.threshold * 100}% threshold (FPR: ${rec.fpr.toFixed(1)}%)<br>
            <span style="color: #444;">${rec.advice}</span>
          </div>
        `
      )
      .join('');
  } else {
    recHtml = `<p>${result.recommendation}</p>`;
  }

  // Build suggested actions
  const actionsHtml =
    result.suggested_actions && result.suggested_actions.length > 0
      ? `<ul style="margin: 8px 0 0 20px;">${result.suggested_actions.map((a) => `<li>${a}</li>`).join('')}</ul>`
      : '';

  // Histogram text
  const histText = result.score_histogram
    ? result.score_histogram.map((h) => `${h.bin}: ${h.count}`).join(' | ')
    : 'N/A';

  return `
    <html>
      <head>
        <title>Real FPR Validation Report - ${dateStr}</title>
        <style>
          body { font-family: system-ui, -apple-system, sans-serif; padding: 40px; line-height: 1.5; color: #222; }
          h1 { color: #065f46; margin-bottom: 4px; }
          h2 { color: #065f46; border-bottom: 2px solid #d1fae5; padding-bottom: 4px; margin-top: 28px; }
          table { border-collapse: collapse; width: 100%; margin: 12px 0; }
          th, td { padding: 8px 12px; border: 1px solid #ddd; text-align: left; }
          th { background: #d1fae5; }
          .section { margin-bottom: 24px; }
          .footer { font-size: 11px; color: #666; margin-top: 40px; border-top: 1px solid #eee; padding-top: 12px; }
        </style>
      </head>
      <body>
        <h1>Real FPR Validation Report</h1>
        <p><strong>Generated:</strong> ${dateStr}</p>

        <div class="section">
          <h2>Summary</h2>
          <ul>
            <li><strong>Submissions analyzed:</strong> ${result.num_submissions}</li>
            <li><strong>Pairs analyzed:</strong> ${result.num_pairs}</li>
            <li><strong>Mean similarity on clean data:</strong> ${(result.mean_score * 100).toFixed(1)}%</li>
            <li><strong>Maximum similarity on clean data:</strong> ${(result.max_score * 100).toFixed(1)}%</li>
          </ul>
        </div>

        <div class="section">
          <h2>False Positive Rate by Threshold</h2>
          <table>
            <thead>
              <tr>
                <th>Threshold</th>
                <th>FPR</th>
                <th>Flagged Pairs</th>
                <th>Assessment</th>
              </tr>
            </thead>
            <tbody>
              ${fprRows}
            </tbody>
          </table>
        </div>

        <div class="section">
          <h2>Recommendations</h2>
          ${recHtml}
        </div>

        ${result.overall_assessment ? `
          <div class="section">
            <h2>Corpus Assessment</h2>
            <p>${result.overall_assessment}</p>
          </div>
        ` : ''}

        ${result.suggested_actions && result.suggested_actions.length > 0 ? `
          <div class="section">
            <h2>Suggested Actions</h2>
            ${actionsHtml}
          </div>
        ` : ''}

        <div class="section">
          <h2>Similarity Score Distribution (Histogram)</h2>
          <p style="font-family: monospace; font-size: 13px; background: #f8fafc; padding: 12px; border-radius: 6px;">
            ${histText}
          </p>
          <p style="font-size: 12px; color: #666;">Higher counts in lower bins (e.g. 0.0-0.1) indicate healthier clean data with fewer near-misses.</p>
        </div>

        <div class="footer">
          Generated by IntegrityDesk Real FPR Validation Tool<br>
          This report reflects the false positive behavior of the system on the specific clean corpus you provided.
        </div>
      </body>
    </html>
  `;
}

export default function FprValidationPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<FprResult | null>(null);
  const [error, setError] = useState('');
  const [isDragging, setIsDragging] = useState(false);

  // === Persistence (database-backed) ===
  const [savedRuns, setSavedRuns] = useState<FprRunSummary[]>([]);

  const loadFprHistory = async () => {
    try {
      const res = await apiClient.get('/api/fpr-validation-runs');
      setSavedRuns(res.data?.runs || []);
    } catch (err) {
      console.error('Failed to load FPR history', err);
    }
  };

  // Load history on mount
  useEffect(() => {
    loadFprHistory();
  }, []);

  const saveCurrentRun = async () => {
    if (!result) return;

    const name = prompt('Name for this FPR validation run:', `FPR Run - ${new Date().toLocaleDateString()}`);
    if (!name) return;

    try {
      await apiClient.post('/api/fpr-validation-runs', {
        name,
        result,
        notes: '', // can be extended later
      });
      alert('Run saved successfully.');
      await loadFprHistory(); // refresh list
    } catch (err: any) {
      console.error(err);
      alert('Failed to save run: ' + (err?.response?.data?.detail || err.message));
    }
  };

  const loadSavedRun = async (runSummary: FprRunSummary) => {
    try {
      const res = await apiClient.get(`/api/fpr-validation-runs/${runSummary.id}`);
      setResult(res.data.result);
      setFiles([]);
      setError('');
    } catch (err: any) {
      alert('Failed to load run: ' + (err?.response?.data?.detail || err.message));
    }
  };

  const deleteSavedRun = async (id: string) => {
    if (!confirm('Delete this saved FPR validation run?')) return;

    try {
      await apiClient.delete(`/api/fpr-validation-runs/${id}`);
      await loadFprHistory();
    } catch (err: any) {
      alert('Failed to delete run: ' + (err?.response?.data?.detail || err.message));
    }
  };

  // Default to focusing on the fine-tuning zone (0.65–0.78)
  const [fprView, setFprView] = useState<'all' | 'fine-tuning'>('fine-tuning');

  const handleFiles = (selected: FileList | null) => {
    if (!selected) return;
    setFiles(Array.from(selected));
    setResult(null);
    setError('');
  };

  const runAnalysis = async () => {
    if (files.length < 2) {
      setError('Please select at least 2 clean submissions.');
      return;
    }

    setLoading(true);
    setError('');
    setResult(null);

    const form = new FormData();
    files.forEach(f => form.append('files', f));

    try {
      const res = await apiClient.post('/api/benchmark/real-fpr', form);
      setResult(res.data);
    } catch (err: unknown) {
      const axiosError = err as AxiosError<{ detail?: string }>;
      const detail = axiosError.response?.data?.detail || axiosError.message || 'Unknown error';
      setError(`Failed to compute FPR: ${detail}`);
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setFiles([]);
    setResult(null);
    setError('');
  };

  const chartData = result?.fpr_table.map(row => ({
    threshold: row.threshold,
    fpr: row.fpr * 100,
  })) || [];

  return (
    <DashboardLayout requiredRole="admin">
      <div className="px-6 py-8">
        <div className="flex items-center gap-3 mb-6">
          <ShieldCheck className="text-emerald-600" size={28} />
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Real FPR Validation</h1>
            <p className="text-slate-600">Measure actual false positive risk on your own clean student data</p>
          </div>
        </div>

        <div className="bg-white rounded-2xl border border-emerald-200 p-6 shadow-sm">
          <div className="mb-4">
            <p className="text-sm text-emerald-700">
              Upload known-clean submissions (no plagiarism) to see the real-world false positive rate
              your students would experience at different similarity thresholds.
            </p>
          </div>

          {/* Drag & Drop + File List */}
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setIsDragging(false);
              handleFiles(e.dataTransfer.files);
            }}
            className={`border-2 border-dashed rounded-2xl p-8 text-center mb-4 transition-all ${
              isDragging
                ? 'border-emerald-500 bg-emerald-50'
                : 'border-emerald-300 bg-white hover:border-emerald-400'
            }`}
          >
            <input
              type="file"
              multiple
              onChange={(e) => handleFiles(e.target.files)}
              className="hidden"
              id="fpr-files"
            />
            <label htmlFor="fpr-files" className="cursor-pointer block">
              <div className="flex flex-col items-center justify-center">
                <UploadCloud size={32} className="text-emerald-600 mb-3" />
                <div className="font-medium text-emerald-800">
                  Drop clean submissions here
                </div>
                <div className="text-sm text-emerald-600 mt-1">
                  or <span className="underline">click to browse</span>
                </div>
                <p className="text-xs text-emerald-500 mt-3 max-w-[260px]">
                  Recommended: 40+ real student submissions from past semesters with no plagiarism
                </p>
              </div>
            </label>
          </div>

          {/* Selected Files List */}
          {files.length > 0 && (
            <div className="mb-6">
              <div className="flex items-center justify-between mb-2 px-1">
                <div className="text-sm font-medium text-emerald-700">
                  Selected files ({files.length})
                </div>
                <button
                  onClick={reset}
                  className="text-xs text-emerald-600 hover:text-emerald-800"
                >
                  Clear all
                </button>
              </div>

              <div className="max-h-48 overflow-auto border border-emerald-200 rounded-xl bg-white divide-y">
                {files.map((file, index) => (
                  <div
                    key={index}
                    className="flex items-center justify-between px-4 py-2.5 text-sm hover:bg-emerald-50/50"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-8 h-8 rounded-lg bg-emerald-100 flex items-center justify-center flex-shrink-0">
                        <FileText size={16} className="text-emerald-600" />
                      </div>
                      <div className="min-w-0">
                        <div className="truncate font-medium text-emerald-900">{file.name}</div>
                        <div className="text-xs text-emerald-600">
                          {(file.size / 1024).toFixed(1)} KB
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={() => {
                        const newFiles = files.filter((_, i) => i !== index);
                        setFiles(newFiles);
                        if (newFiles.length === 0) {
                          setResult(null);
                        }
                      }}
                      className="ml-2 p-1 text-emerald-400 hover:text-red-500 hover:bg-red-50 rounded-full"
                      aria-label="Remove file"
                    >
                      <X size={16} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="flex gap-3">
            <button
              onClick={runAnalysis}
              disabled={loading || files.length < 2}
              className="flex items-center gap-2 px-6 py-3 bg-emerald-600 text-white rounded-xl font-semibold disabled:opacity-50 hover:bg-emerald-700"
            >
              {loading ? <Loader2 className="animate-spin" size={18} /> : <Play size={18} />}
              Run Real FPR Analysis
            </button>

            <button
              onClick={reset}
              className="flex items-center gap-2 px-5 py-3 border border-slate-300 rounded-xl hover:bg-slate-50"
            >
              <RefreshCw size={16} /> Reset
            </button>

            {result && (
              <button
                onClick={saveCurrentRun}
                className="flex items-center gap-2 px-5 py-3 border border-emerald-300 bg-emerald-50 text-emerald-700 rounded-xl hover:bg-emerald-100 font-medium"
              >
                Save this run
              </button>
            )}

            {result && (
              <button
                onClick={() => {
                  const printWindow = window.open('', '_blank');
                  if (printWindow) {
                    printWindow.document.write(generateFprReportHtml(result));
                    printWindow.document.close();
                    printWindow.print();
                  }
                }}
                className="flex items-center gap-2 px-5 py-3 bg-emerald-700 text-white rounded-xl hover:bg-emerald-800"
              >
                Download PDF Report
              </button>
            )}
          </div>

          {error && (
            <div className="mt-4 flex items-center gap-2 text-red-600 text-sm">
              <AlertCircle size={16} /> {error}
            </div>
          )}
        </div>

        {/* Saved Runs History */}
        {savedRuns.length > 0 && (
          <div className="mt-8">
            <div className="font-semibold text-emerald-800 mb-3 flex items-center gap-2">
              <ClipboardList size={18} /> Previous FPR Validations
            </div>
            <div className="space-y-2">
              {savedRuns.map((run) => (
                <div
                  key={run.id}
                  className="flex items-center justify-between bg-white border border-emerald-200 rounded-xl px-4 py-3 hover:bg-emerald-50/50"
                >
                  <div>
                    <div className="font-medium text-emerald-900">{run.name}</div>
                    <div className="text-xs text-emerald-600">
                      {new Date(run.created_at).toLocaleString()} • {run.num_submissions} submissions • {run.num_pairs} pairs
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => loadSavedRun(run)}
                      className="px-3 py-1.5 text-sm bg-emerald-600 text-white rounded-lg hover:bg-emerald-700"
                    >
                      Load
                    </button>
                    <button
                      onClick={() => deleteSavedRun(run.id)}
                      className="px-3 py-1.5 text-sm border border-red-200 text-red-600 rounded-lg hover:bg-red-50"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {result && (
          <div className="mt-8 space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { label: 'Submissions', value: result.num_submissions },
                { label: 'Pairs Analyzed', value: result.num_pairs },
                { label: 'Mean Similarity', value: `${(result.mean_score * 100).toFixed(1)}%` },
                { label: 'Max Similarity', value: `${(result.max_score * 100).toFixed(1)}%` },
              ].map((stat, i) => (
                <div key={i} className="bg-white border border-emerald-200 rounded-2xl p-5">
                  <div className="text-xs text-emerald-600 font-medium uppercase tracking-wide">{stat.label}</div>
                  <div className="text-3xl font-bold text-emerald-900 mt-2">{stat.value}</div>
                </div>
              ))}
            </div>

            {/* FPR Curve */}
            <div className="bg-white border border-emerald-200 rounded-2xl p-6">
              <div className="font-semibold mb-4">False Positive Rate Curve</div>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="threshold" tickFormatter={v => `${v * 100}%`} />
                    <YAxis tickFormatter={v => `${v}%`} />
                    <Tooltip />

                    {/* Highlight the dense fine-tuning zone (0.65 – 0.78) */}
                    <ReferenceArea 
                      x1={0.65} 
                      x2={0.78} 
                      fill="#10b981" 
                      fillOpacity={0.08} 
                      stroke="#10b981" 
                      strokeOpacity={0.3}
                    />

                    <Line type="monotone" dataKey="fpr" stroke="#10b981" strokeWidth={3} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Detailed Table with Fine-tuning Zone Focus (default) */}
            <div className="bg-white border border-emerald-200 rounded-2xl overflow-hidden">
              <div className="px-6 py-4 border-b flex items-center justify-between">
                <div className="font-semibold text-emerald-800">
                  False Positive Rate at Different Thresholds
                </div>

                {/* View toggle - defaults to Fine-tuning Zone */}
                <div className="flex rounded-lg border border-emerald-200 bg-emerald-50 p-0.5 text-sm">
                  <button
                    onClick={() => setFprView('fine-tuning')}
                    className={`px-3 py-1 rounded-md transition ${fprView === 'fine-tuning' ? 'bg-white shadow text-emerald-700 font-medium' : 'text-emerald-600 hover:bg-emerald-100'}`}
                  >
                    Fine-tuning Zone (0.65–0.78)
                  </button>
                  <button
                    onClick={() => setFprView('all')}
                    className={`px-3 py-1 rounded-md transition ${fprView === 'all' ? 'bg-white shadow text-emerald-700 font-medium' : 'text-emerald-600 hover:bg-emerald-100'}`}
                  >
                    All Thresholds
                  </button>
                </div>
              </div>

              {(() => {
                const denseRows = result.fpr_table.filter(
                  (r) => r.threshold >= 0.65 && r.threshold <= 0.78
                );
                let tableRows = fprView === 'fine-tuning' ? denseRows : result.fpr_table;

                // In fine-tuning zone view (default): 
                // - Sort by FPR ascending so the best option appears first
                // - Identify the best row for prominent "Recommended" highlighting
                let bestInZoneRow = null;
                if (fprView === 'fine-tuning') {
                  tableRows = [...tableRows].sort((a, b) => a.fpr - b.fpr);
                  if (tableRows.length > 0) {
                    bestInZoneRow = tableRows[0]; // After sorting by FPR, first row is the best
                  }
                }

                return (
                  <>
                    <table className="w-full text-sm">
                      <thead className="bg-emerald-50 text-emerald-700">
                        <tr>
                          <th className="text-left px-6 py-3">Threshold</th>
                          <th className="text-left px-6 py-3">FPR</th>
                          <th className="text-left px-6 py-3">Flagged Pairs</th>
                          <th className="text-left px-6 py-3">Assessment</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {tableRows.map((row, index) => {
                          const isDenseZone = row.threshold >= 0.65 && row.threshold <= 0.78;
                          const isBestInZone = fprView === 'fine-tuning' && bestInZoneRow && row.threshold === bestInZoneRow.threshold;

                          return (
                            <tr 
                              key={index} 
                              className={`hover:bg-emerald-50/50 ${isDenseZone ? 'bg-emerald-50/70' : ''} ${isBestInZone ? 'ring-1 ring-emerald-400' : ''}`}
                            >
                              <td className="px-6 py-3 font-mono">
                                {(row.threshold * 100).toFixed(0)}%
                                {isDenseZone && (
                                  <span className="ml-2 px-1.5 py-0.5 text-[10px] font-medium bg-emerald-200 text-emerald-700 rounded">
                                    Fine-tuning zone
                                  </span>
                                )}
                                {isBestInZone && (
                                  <span className="ml-2 px-2 py-0.5 text-[10px] font-bold bg-emerald-600 text-white rounded">
                                    Recommended
                                  </span>
                                )}
                              </td>
                              <td className="px-6 py-3 font-semibold">{row.fpr_percent.toFixed(2)}%</td>
                              <td className="px-6 py-3 text-slate-600">{row.flagged_pairs} / {result.num_pairs}</td>
                              <td className="px-6 py-3">
                                <span className={`inline-block px-3 py-1 rounded-full text-xs font-medium ${
                                  row.fpr <= 0.02 ? 'bg-emerald-100 text-emerald-700' :
                                  row.fpr <= 0.04 ? 'bg-emerald-50 text-emerald-600' :
                                  row.fpr <= 0.07 ? 'bg-amber-100 text-amber-700' :
                                  'bg-red-100 text-red-700'
                                }`}>
                                  {row.label}
                                </span>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>

                    {fprView === 'fine-tuning' && (
                      <div className="px-6 py-2 text-xs text-emerald-600 border-t bg-emerald-50">
                        Focused on the fine-tuning zone (0.65–0.78). 
                        Sorted by lowest FPR first — the top row is automatically marked <strong>“Recommended”</strong>. 
                        Switch to "All Thresholds" for the complete view.
                      </div>
                    )}
                  </>
                );
              })()}
            </div>

            {/* Sophisticated Recommendations */}
            <div className="bg-white border border-emerald-200 rounded-2xl p-6">
              <div className="font-semibold text-emerald-800 mb-4 text-lg">Recommended Thresholds</div>

              {result.recommendations && result.recommendations.length > 0 ? (
                <div className="space-y-4">
                  {result.recommendations.map((rec: RecommendationItem, idx: number) => (
                    <div key={idx} className={`p-4 rounded-xl border ${
                      rec.type === 'balanced' ? 'border-emerald-300 bg-emerald-50' : 
                      rec.type === 'very_safe' ? 'border-blue-300 bg-blue-50' : 
                      'border-amber-300 bg-amber-50'
                    }`}>
                      <div className="flex items-center justify-between">
                        <div>
                          <span className="font-semibold text-lg">{rec.title}</span>
                          <span className="ml-3 text-sm font-mono bg-white px-2 py-0.5 rounded border">
                            {rec.threshold * 100}% threshold
                          </span>
                        </div>
                        <div className="text-right">
                          <div className="text-sm text-slate-600">FPR on your data</div>
                          <div className="text-xl font-bold text-emerald-700">{rec.fpr.toFixed(1)}%</div>
                        </div>
                      </div>
                      <p className="mt-2 text-sm text-slate-700">{rec.advice}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-emerald-700">{result.recommendation}</p>
              )}

              {/* Overall Assessment */}
              {result.overall_assessment && (
                <div className="mt-5 pt-5 border-t">
                  <div className="font-medium text-emerald-800 mb-1">Corpus Assessment</div>
                  <p className="text-sm text-emerald-700">{result.overall_assessment}</p>
                </div>
              )}

              {/* Actionable Suggestions */}
              {result.suggested_actions && result.suggested_actions.length > 0 && (
                <div className="mt-5 pt-5 border-t">
                  <div className="font-medium text-emerald-800 mb-2">Suggested Actions</div>
                  <ul className="list-disc list-inside text-sm text-emerald-700 space-y-1">
                    {result.suggested_actions.map((action: string, i: number) => (
                      <li key={i}>{action}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
