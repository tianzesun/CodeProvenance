'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import axios from 'axios';
import {
  Upload as UploadIcon,
  BarChart3,
  Loader2,
  Check,
  Trophy,
  ArrowRight,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8500';

const TOOLS = [
  { id: 'integritydesk', name: 'IntegrityDesk (Ours)', color: '#0066cc' },
  { id: 'moss', name: 'MOSS', color: '#64748b' },
  { id: 'jplag', name: 'JPlag', color: '#64748b' },
  { id: 'dolos', name: 'Dolos', color: '#64748b' },
  { id: 'codequiry', name: 'Codequiry', color: '#64748b' },
];

const KNOWN_PAIRS = [
  { a: 'identical_a.py', b: 'identical_b.py', expected: 0.95, label: 'Identical Files' },
  { a: 'renamed_a.py', b: 'renamed_b.py', expected: 0.80, label: 'Renamed Variables' },
  { a: 'reordered_a.py', b: 'reordered_b.py', expected: 0.70, label: 'Reordered Functions' },
  { a: 'similar_a.py', b: 'similar_b.py', expected: 0.50, label: 'Similar Logic' },
  { a: 'unrelated_a.py', b: 'unrelated_b.py', expected: 0.10, label: 'Unrelated Files' },
];

export default function BenchmarkPage() {
  const router = useRouter();
  const [files, setFiles] = useState([]);
  const [selectedTools, setSelectedTools] = useState(['integritydesk', 'moss', 'jplag', 'dolos']);
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState('');

  const toggleTool = (id) => {
    setSelectedTools((prev) =>
      prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id]
    );
  };

  const runBenchmark = async () => {
    if (files.length < 2) {
      setError('Upload at least 2 files to benchmark');
      return;
    }
    setError('');
    setRunning(true);
    setResults(null);

    const formData = new FormData();
    files.forEach((f) => formData.append('files', f));
    selectedTools.forEach((t) => formData.append('tools', t));

    try {
      const res = await axios.post(`${API}/api/benchmark`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setResults(res.data);
    } catch (err) {
      setError(err.response?.data?.error || 'Benchmark failed');
    }
    setRunning(false);
  };

  return (
    <DashboardLayout>
      <div className="p-6 lg:p-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-slate-900">Benchmark</h1>
          <p className="text-slate-500 mt-1">
            Compare IntegrityDesk against other plagiarism detection tools on the same files.
          </p>
        </div>

        {/* Tool Selection */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <h2 className="text-sm font-semibold text-slate-900 uppercase tracking-wider mb-4">
            Select Tools
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {TOOLS.map((tool) => (
              <button
                key={tool.id}
                onClick={() => toggleTool(tool.id)}
                className={`p-3 rounded-lg border-2 text-sm font-medium transition-all ${
                  selectedTools.includes(tool.id)
                    ? 'border-brand-500 bg-brand-50 text-brand-700'
                    : 'border-slate-200 text-slate-500 hover:border-slate-300'
                }`}
              >
                {tool.name}
              </button>
            ))}
          </div>
        </div>

        {/* File Upload */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <h2 className="text-sm font-semibold text-slate-900 uppercase tracking-wider mb-4">
            Upload Test Files
          </h2>
          <div
            onDrop={(e) => {
              e.preventDefault();
              setFiles(Array.from(e.dataTransfer.files));
            }}
            onDragOver={(e) => e.preventDefault()}
            className="border-2 border-dashed border-slate-200 rounded-xl p-8 text-center hover:border-brand-300 hover:bg-brand-50/30 transition-colors cursor-pointer"
            onClick={() => document.getElementById('benchFileInput').click()}
          >
            <UploadIcon size={28} className="mx-auto text-slate-300 mb-2" />
            <p className="text-sm font-medium text-slate-700">Drop files here or click to browse</p>
            <p className="text-xs text-slate-400 mt-1">Upload pairs of files to compare across tools</p>
            <input
              id="benchFileInput"
              type="file"
              multiple
              accept=".py,.java,.c,.cpp,.h,.js,.ts,.go,.rs,.rb,.php,.cs,.kt,.swift"
              className="hidden"
              onChange={(e) => setFiles(Array.from(e.target.files))}
            />
          </div>

          {files.length > 0 && (
            <div className="mt-4 space-y-1.5">
              {files.map((f, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between px-3 py-2 bg-slate-50 rounded-lg text-sm"
                >
                  <span className="font-medium text-slate-700 truncate flex-1">{f.name}</span>
                  <span className="text-slate-400 ml-3 text-xs">{(f.size / 1024).toFixed(1)} KB</span>
                </div>
              ))}
            </div>
          )}

          {error && (
            <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {error}
            </div>
          )}

          <button
            onClick={runBenchmark}
            disabled={running || files.length < 2}
            className="w-full mt-6 py-3 bg-brand-600 hover:bg-brand-700 disabled:bg-brand-300 text-white font-semibold rounded-lg transition-colors flex items-center justify-center gap-2"
          >
            {running ? (
              <>
                <Loader2 size={18} className="animate-spin" />
                Running Benchmark...
              </>
            ) : (
              <>
                <BarChart3 size={18} />
                Run Benchmark
              </>
            )}
          </button>
        </div>

        {/* Results */}
        {results && <BenchmarkResults results={results} />}
      </div>
    </DashboardLayout>
  );
}

function BenchmarkResults({ results }) {
  const { tool_scores, pair_results, summary } = results;

  const chartData = (pairResults) => {
    const tools = Object.keys(tool_scores);
    return pairResults.map((pair) => {
      const d = { pair: pair.label };
      tools.forEach((t) => {
        const toolResult = pair.tool_results?.find((tr) => tr.tool === t);
        d[t] = toolResult ? toolResult.score * 100 : 0;
      });
      return d;
    });
  };

  const COLORS = {
    integritydesk: '#0066cc',
    moss: '#64748b',
    jplag: '#94a3b8',
    dolos: '#cbd5e1',
    codequiry: '#e2e8f0',
  };

  return (
    <div className="space-y-6">
      {/* Summary */}
      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-green-50 flex items-center justify-center">
            <Trophy size={20} className="text-green-600" />
          </div>
          <div>
            <h2 className="font-semibold text-slate-900">Benchmark Complete</h2>
            <p className="text-sm text-slate-500">
              {summary?.pairs_tested} pairs tested across {summary?.tools_compared} tools
            </p>
          </div>
        </div>

        {summary?.accuracy && (
          <div className="grid grid-cols-3 gap-4 mt-4">
            <div className="text-center p-4 bg-brand-50 rounded-lg">
              <div className="text-2xl font-bold text-brand-700">
                {(summary.accuracy.integritydesk * 100).toFixed(0)}%
              </div>
              <div className="text-xs text-brand-600 font-medium mt-1">IntegrityDesk Accuracy</div>
            </div>
            <div className="text-center p-4 bg-slate-50 rounded-lg">
              <div className="text-2xl font-bold text-slate-700">
                {(summary.accuracy.best_competitor * 100).toFixed(0)}%
              </div>
              <div className="text-xs text-slate-500 font-medium mt-1">Best Competitor</div>
            </div>
            <div className="text-center p-4 bg-green-50 rounded-lg">
              <div className="text-2xl font-bold text-green-700">
                +{((summary.accuracy.integritydesk - summary.accuracy.best_competitor) * 100).toFixed(0)}%
              </div>
              <div className="text-xs text-green-600 font-medium mt-1">Improvement</div>
            </div>
          </div>
        )}
      </div>

      {/* Chart */}
      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <h2 className="font-semibold text-slate-900 mb-4">Scores by Pair</h2>
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData(pair_results || [])}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="pair" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} domain={[0, 100]} />
              <Tooltip formatter={(value) => `${value.toFixed(1)}%`} />
              {Object.keys(tool_scores).map((tool) => (
                <Bar key={tool} dataKey={tool} fill={COLORS[tool] || '#94a3b8'} radius={[4, 4, 0, 0]} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Detailed Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100">
          <h2 className="font-semibold text-slate-900">Detailed Results</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-xs uppercase tracking-wider text-slate-500 bg-slate-50/50">
                <th className="text-left px-5 py-3 font-medium">Pair</th>
                {Object.keys(tool_scores).map((tool) => (
                  <th key={tool} className="text-center px-5 py-3 font-medium">
                    {TOOLS.find((t) => t.id === tool)?.name || tool}
                  </th>
                ))}
                <th className="text-center px-5 py-3 font-medium">Expected</th>
              </tr>
            </thead>
            <tbody>
              {(pair_results || []).map((pair, i) => (
                <tr key={i} className="border-t border-slate-100">
                  <td className="px-5 py-3 text-sm font-medium text-slate-900">
                    {pair.label}
                  </td>
                  {Object.keys(tool_scores).map((tool) => {
                    const tr = pair.tool_results?.find((r) => r.tool === tool);
                    const score = tr ? tr.score * 100 : null;
                    return (
                      <td key={tool} className="px-5 py-3 text-center">
                        {score !== null ? (
                          <span
                            className={`inline-flex px-2 py-0.5 rounded text-xs font-bold ${
                              tool === 'integritydesk'
                                ? 'bg-brand-100 text-brand-700'
                                : 'bg-slate-100 text-slate-600'
                            }`}
                          >
                            {score.toFixed(1)}%
                          </span>
                        ) : (
                          <span className="text-slate-300 text-xs">N/A</span>
                        )}
                      </td>
                    );
                  })}
                  <td className="px-5 py-3 text-center text-sm text-slate-500">
                    {pair.expected != null ? `${(pair.expected * 100).toFixed(0)}%` : '--'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
