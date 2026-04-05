'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { useState, useCallback } from 'react';
import axios from 'axios';
import {
  Upload as UploadIcon,
  BarChart3,
  Loader2,
  Trophy,
  FileUp,
  FolderArchive,
  X,
  AlertCircle,
  Zap,
  Target,
  Layers,
  TrendingUp,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Download,
  Code2,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8500';

const TOOLS = [
  { id: 'integritydesk', name: 'IntegrityDesk', desc: 'Multi-engine fusion', color: '#0066cc', gradient: 'from-blue-500 to-blue-600', bgLight: 'bg-blue-50', ring: 'ring-blue-500' },
  { id: 'moss', name: 'MOSS', desc: 'Token-based (Stanford)', color: '#7c3aed', gradient: 'from-violet-500 to-violet-600', bgLight: 'bg-violet-50', ring: 'ring-violet-500' },
  { id: 'jplag', name: 'JPlag', desc: 'AST structural (KIT)', color: '#059669', gradient: 'from-emerald-500 to-emerald-600', bgLight: 'bg-emerald-50', ring: 'ring-emerald-500' },
  { id: 'dolos', name: 'Dolos', desc: 'Winnowing fingerprints', color: '#d97706', gradient: 'from-amber-500 to-amber-600', bgLight: 'bg-amber-50', ring: 'ring-amber-500' },
  { id: 'codequiry', name: 'Codequiry', desc: 'Semantic embeddings', color: '#dc2626', gradient: 'from-red-500 to-red-600', bgLight: 'bg-red-50', ring: 'ring-red-500' },
];

export default function BenchmarkPage() {
  const [mode, setMode] = useState('individual');
  const [files, setFiles] = useState([]);
  const [zipFile, setZipFile] = useState(null);
  const [selectedTools, setSelectedTools] = useState(TOOLS.map(t => t.id));
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState('');
  const [results, setResults] = useState(null);
  const [error, setError] = useState('');
  const [expandedPairs, setExpandedPairs] = useState({});

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    if (mode === 'individual') {
      setFiles(Array.from(e.dataTransfer.files));
    } else {
      setZipFile(e.dataTransfer.files[0]);
    }
  }, [mode]);

  const toggleTool = (id) => {
    setSelectedTools((prev) =>
      prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id]
    );
  };

  const selectAll = () => setSelectedTools(TOOLS.map(t => t.id));
  const deselectAll = () => setSelectedTools([]);

  const runBenchmark = async () => {
    if (selectedTools.length === 0) {
      setError('Select at least one tool');
      return;
    }
    if (mode === 'individual' && files.length < 2) {
      setError('Upload at least 2 files');
      return;
    }
    if (mode === 'zip' && !zipFile) {
      setError('Select a ZIP file');
      return;
    }

    setError('');
    setRunning(true);
    setResults(null);
    setProgress('Uploading files...');

    const formData = new FormData();
    if (mode === 'individual') {
      files.forEach((f) => formData.append('files', f));
    } else {
      formData.append('file', zipFile);
    }
    selectedTools.forEach((t) => formData.append('tools', t));

    try {
      setProgress('Running analysis across all tools...');
      const res = await axios.post(`${API}/api/benchmark`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setProgress('Compiling results...');
      setResults(res.data);
    } catch (err) {
      setError(err.response?.data?.error || 'Benchmark failed');
    }
    setRunning(false);
    setProgress('');
  };

  return (
    <DashboardLayout>
      <div className="p-6 lg:p-8">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-violet-600 flex items-center justify-center shadow-lg shadow-violet-500/25">
              <Layers size={20} className="text-white" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Multi-Tool Comparison</h1>
              <p className="text-slate-500 mt-0.5">
                Run all detection tools on the same files and compare results side by side.
              </p>
            </div>
          </div>
        </div>

        {/* Tool Selection */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden mb-6">
          <div className="px-6 py-5 border-b border-slate-100 flex items-center justify-between">
            <div>
              <h2 className="font-semibold text-slate-900">Detection Tools</h2>
              <p className="text-sm text-slate-500 mt-0.5">
                {selectedTools.length} of {TOOLS.length} tools selected
              </p>
            </div>
            <div className="flex gap-2">
              <button onClick={selectAll} className="text-xs font-medium text-brand-600 hover:text-brand-700 px-3 py-1.5 rounded-lg hover:bg-brand-50 transition-colors">
                Select All
              </button>
              <button onClick={deselectAll} className="text-xs font-medium text-slate-500 hover:text-slate-700 px-3 py-1.5 rounded-lg hover:bg-slate-50 transition-colors">
                Clear
              </button>
            </div>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              {TOOLS.map((tool) => {
                const isSelected = selectedTools.includes(tool.id);
                return (
                  <button
                    key={tool.id}
                    onClick={() => toggleTool(tool.id)}
                    className={`relative p-4 rounded-xl border-2 text-left transition-all duration-200 ${
                      isSelected
                        ? `border-transparent ring-2 ${tool.ring} ring-offset-2`
                        : 'border-slate-200 hover:border-slate-300'
                    }`}
                  >
                    {isSelected && (
                      <div className="absolute top-2 right-2">
                        <CheckCircle2 size={16} className={tool.color.replace('500', '600')} />
                      </div>
                    )}
                    <div className={`w-9 h-9 rounded-lg bg-gradient-to-br ${tool.gradient} flex items-center justify-center mb-3 shadow-sm`}>
                      <Zap size={16} className="text-white" />
                    </div>
                    <div className="font-semibold text-sm text-slate-900">{tool.name}</div>
                    <div className="text-xs text-slate-400 mt-0.5">{tool.desc}</div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Upload Section */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden mb-6">
          <div className="px-6 py-5 border-b border-slate-100">
            <h2 className="font-semibold text-slate-900">Upload Assignments</h2>
            <p className="text-sm text-slate-500 mt-0.5">
              Upload student submissions to compare across all selected tools.
            </p>
          </div>
          <div className="p-6">
            {/* Mode Toggle */}
            <div className="flex gap-2 mb-5">
              <button
                onClick={() => setMode('individual')}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all ${
                  mode === 'individual'
                    ? 'bg-brand-600 text-white shadow-lg shadow-brand-500/25'
                    : 'bg-white border border-slate-200 text-slate-600 hover:border-slate-300'
                }`}
              >
                <FileUp size={15} />
                Individual Files
              </button>
              <button
                onClick={() => setMode('zip')}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all ${
                  mode === 'zip'
                    ? 'bg-brand-600 text-white shadow-lg shadow-brand-500/25'
                    : 'bg-white border border-slate-200 text-slate-600 hover:border-slate-300'
                }`}
              >
                <FolderArchive size={15} />
                ZIP Archive
              </button>
            </div>

            {/* Drop Zone */}
            <div
              onDrop={handleDrop}
              onDragOver={(e) => e.preventDefault()}
              className="border-2 border-dashed border-slate-200 rounded-xl p-10 text-center hover:border-brand-400 hover:bg-brand-50/30 transition-all duration-200 cursor-pointer group"
              onClick={() => {
                if (mode === 'individual') document.getElementById('benchFileInput').click();
                else document.getElementById('benchZipInput').click();
              }}
            >
              <div className="w-14 h-14 rounded-2xl bg-slate-50 flex items-center justify-center mx-auto mb-4 group-hover:bg-brand-50 transition-colors">
                <UploadIcon size={24} className="text-slate-400 group-hover:text-brand-500 transition-colors" />
              </div>
              <p className="text-sm font-semibold text-slate-700 mb-1">
                {mode === 'individual' ? 'Drop files here or click to browse' : 'Drop ZIP file here or click to browse'}
              </p>
              <p className="text-xs text-slate-400">
                {mode === 'individual' ? 'Python, Java, C/C++, JavaScript, Rust, Go, and 20+ languages' : 'All code files within the archive will be analyzed'}
              </p>
              <input id="benchFileInput" type="file" multiple accept=".py,.java,.c,.cpp,.h,.js,.ts,.go,.rs,.rb,.php,.cs,.kt,.swift" className="hidden" onChange={(e) => setFiles(Array.from(e.target.files))} />
              <input id="benchZipInput" type="file" accept=".zip" className="hidden" onChange={(e) => setZipFile(e.target.files[0])} />
            </div>

            {/* File List */}
            {(files.length > 0 || zipFile) && (
              <div className="mt-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    {mode === 'individual' ? `${files.length} files` : 'Archive'}
                  </span>
                  {mode === 'individual' && files.length > 0 && (
                    <button onClick={() => setFiles([])} className="text-xs text-slate-400 hover:text-red-500 transition-colors">Clear all</button>
                  )}
                </div>
                <div className="space-y-1.5 max-h-36 overflow-y-auto scrollbar-thin pr-1">
                  {mode === 'individual'
                    ? files.map((f, i) => (
                        <div key={i} className="flex items-center justify-between px-3 py-2.5 bg-slate-50 rounded-lg text-sm group/file">
                          <div className="flex items-center gap-2 min-w-0 flex-1">
                            <div className="w-7 h-7 rounded-md bg-emerald-50 flex items-center justify-center shrink-0">
                              <FileUp size={12} className="text-emerald-600" />
                            </div>
                            <span className="font-medium text-slate-700 truncate">{f.name}</span>
                          </div>
                          <span className="text-xs text-slate-400 ml-2">{(f.size / 1024).toFixed(1)} KB</span>
                        </div>
                      ))
                    : zipFile && (
                        <div className="flex items-center justify-between px-3 py-2.5 bg-slate-50 rounded-lg text-sm">
                          <div className="flex items-center gap-2 min-w-0 flex-1">
                            <div className="w-7 h-7 rounded-md bg-amber-50 flex items-center justify-center shrink-0">
                              <FolderArchive size={12} className="text-amber-600" />
                            </div>
                            <span className="font-medium text-slate-700 truncate">{zipFile.name}</span>
                          </div>
                          <span className="text-xs text-slate-400 ml-2">{(zipFile.size / 1024).toFixed(1)} KB</span>
                        </div>
                      )}
                </div>
              </div>
            )}

            {/* Error */}
            {error && (
              <div className="mt-4 flex items-start gap-3 p-4 bg-red-50 border border-red-100 rounded-xl">
                <AlertCircle size={18} className="text-red-500 mt-0.5 shrink-0" />
                <p className="text-sm text-red-700">{error}</p>
              </div>
            )}

            {/* Progress */}
            {running && (
              <div className="mt-4 flex items-center gap-3 p-4 bg-brand-50 border border-brand-100 rounded-xl">
                <Loader2 size={18} className="text-brand-600 animate-spin shrink-0" />
                <p className="text-sm text-brand-700 font-medium">{progress}</p>
              </div>
            )}

            {/* Submit */}
            <button
              onClick={runBenchmark}
              disabled={running || selectedTools.length === 0}
              className="w-full mt-5 py-3.5 bg-gradient-to-r from-violet-600 to-brand-600 hover:from-violet-700 hover:to-brand-700 disabled:from-slate-300 disabled:to-slate-200 text-white font-semibold rounded-xl transition-all flex items-center justify-center gap-2 shadow-lg shadow-violet-500/25 hover:shadow-xl hover:shadow-violet-500/30 disabled:shadow-none"
            >
              {running ? (
                <>
                  <Loader2 size={18} className="animate-spin" />
                  Running All Tools...
                </>
              ) : (
                <>
                  <BarChart3 size={18} />
                  Run {selectedTools.length} Tool{selectedTools.length !== 1 ? 's' : ''} on {mode === 'individual' ? files.length : zipFile ? 'archive' : 0} File{mode === 'individual' && files.length !== 1 ? 's' : ''}
                </>
              )}
            </button>
          </div>
        </div>

        {/* Results */}
        {results && <BenchmarkResults results={results} expandedPairs={expandedPairs} setExpandedPairs={setExpandedPairs} />}
      </div>
    </DashboardLayout>
  );
}

function BenchmarkResults({ results, expandedPairs, setExpandedPairs }) {
  const { tool_scores, pair_results, summary } = results;
  const activeTools = Object.keys(tool_scores);

  const chartData = pair_results.map((pair) => {
    const d = { pair: pair.label };
    activeTools.forEach((t) => {
      const tr = pair.tool_results?.find((r) => r.tool === t);
      d[t] = tr ? Math.round(tr.score * 1000) / 10 : 0;
    });
    return d;
  });

  const TOOL_COLORS = {
    integritydesk: '#0066cc',
    moss: '#7c3aed',
    jplag: '#059669',
    dolos: '#d97706',
    codequiry: '#dc2626',
  };

  const togglePair = (idx) => {
    setExpandedPairs((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-xl bg-blue-50 flex items-center justify-center">
              <Layers size={18} className="text-blue-600" />
            </div>
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Tools Run</span>
          </div>
          <div className="text-2xl font-bold text-slate-900">{summary?.tools_compared || 0}</div>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-xl bg-emerald-50 flex items-center justify-center">
              <Target size={18} className="text-emerald-600" />
            </div>
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Pairs Tested</span>
          </div>
          <div className="text-2xl font-bold text-slate-900">{summary?.pairs_tested || 0}</div>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-xl bg-brand-50 flex items-center justify-center">
              <TrendingUp size={18} className="text-brand-600" />
            </div>
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">IntegrityDesk Avg</span>
          </div>
          <div className="text-2xl font-bold text-brand-600">{summary?.accuracy ? (summary.accuracy.integritydesk * 100).toFixed(1) : 0}%</div>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-xl bg-slate-50 flex items-center justify-center">
              <Trophy size={18} className="text-slate-600" />
            </div>
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Best Competitor</span>
          </div>
          <div className="text-2xl font-bold text-slate-700">{summary?.accuracy ? (summary.accuracy.best_competitor * 100).toFixed(1) : 0}%</div>
        </div>
      </div>

      {/* Chart */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-5 border-b border-slate-100">
          <h2 className="font-semibold text-slate-900">Score Comparison Chart</h2>
          <p className="text-sm text-slate-500 mt-0.5">Similarity scores from each tool for every file pair</p>
        </div>
        <div className="p-6">
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="pair" tick={{ fontSize: 11, fill: '#64748b' }} />
                <YAxis tick={{ fontSize: 11, fill: '#64748b' }} domain={[0, 100]} label={{ value: 'Similarity %', angle: -90, position: 'insideLeft', fontSize: 11, fill: '#94a3b8' }} />
                <Tooltip formatter={(value) => `${value.toFixed(1)}%`} contentStyle={{ borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }} />
                <Legend wrapperStyle={{ fontSize: '12px' }} />
                {activeTools.map((tool) => (
                  <Bar key={tool} dataKey={tool} fill={TOOL_COLORS[tool] || '#94a3b8'} radius={[4, 4, 0, 0]} name={TOOLS.find(t => t.id === tool)?.name || tool} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Detailed Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-5 border-b border-slate-100">
          <h2 className="font-semibold text-slate-900">Detailed Pair Results</h2>
          <p className="text-sm text-slate-500 mt-0.5">Click any pair to see individual tool scores and code comparison</p>
        </div>

        {/* Table Header */}
        <div className="hidden lg:grid grid-cols-12 gap-4 px-6 py-3 bg-slate-50/80 text-[11px] uppercase tracking-wider text-slate-400 font-semibold">
          <div className="col-span-3">File Pair</div>
          {activeTools.map((tool) => (
            <div key={tool} className="col-span-2 text-center flex items-center justify-center gap-1.5">
              <div className="w-2 h-2 rounded-full" style={{ backgroundColor: TOOL_COLORS[tool] }} />
              {TOOLS.find(t => t.id === tool)?.name || tool}
            </div>
          ))}
          <div className="col-span-1 text-center">Max</div>
          <div className="col-span-1 text-center">Min</div>
          <div className="col-span-1 text-center">Spread</div>
        </div>

        {/* Rows */}
        <div className="divide-y divide-slate-50">
          {pair_results.map((pair, idx) => {
            const scores = activeTools.map((t) => {
              const tr = pair.tool_results?.find((r) => r.tool === t);
              return tr ? tr.score : null;
            });
            const validScores = scores.filter((s) => s !== null);
            const maxScore = validScores.length ? Math.max(...validScores) : 0;
            const minScore = validScores.length ? Math.min(...validScores) : 0;
            const spread = maxScore - minScore;
            const isExpanded = expandedPairs[idx];

            return (
              <div key={idx}>
                <button
                  onClick={() => togglePair(idx)}
                  className="w-full lg:grid lg:grid-cols-12 lg:gap-4 px-6 py-4 hover:bg-slate-50/50 transition-colors text-left flex flex-col lg:flex-row lg:items-center"
                >
                  <div className="col-span-3 flex items-center gap-3 mb-2 lg:mb-0">
                    <div className={`w-2 h-8 rounded-full ${maxScore >= 0.9 ? 'bg-red-500' : maxScore >= 0.75 ? 'bg-amber-500' : maxScore >= 0.5 ? 'bg-yellow-500' : 'bg-emerald-500'}`} />
                    <div>
                      <div className="text-sm font-semibold text-slate-900">{pair.label}</div>
                      <div className="text-xs text-slate-400">{pair.file_a} vs {pair.file_b}</div>
                    </div>
                    {isExpanded ? <ChevronUp size={14} className="text-slate-400 ml-auto lg:ml-0" /> : <ChevronDown size={14} className="text-slate-400 ml-auto lg:ml-0" />}
                  </div>
                  {activeTools.map((tool, ti) => {
                    const score = scores[ti];
                    const toolInfo = TOOLS.find(t => t.id === tool);
                    return (
                      <div key={tool} className="col-span-2 text-center py-1 lg:py-0">
                        {score !== null ? (
                          <div>
                            <span className={`inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-bold ${tool === 'integritydesk' ? 'bg-blue-50 text-blue-700' : 'bg-slate-50 text-slate-600'}`}>
                              {(score * 100).toFixed(1)}%
                            </span>
                          </div>
                        ) : (
                          <span className="text-xs text-slate-300">N/A</span>
                        )}
                      </div>
                    );
                  })}
                  <div className="hidden lg:flex col-span-1 items-center justify-center">
                    <span className="text-xs font-bold text-red-600">{(maxScore * 100).toFixed(0)}%</span>
                  </div>
                  <div className="hidden lg:flex col-span-1 items-center justify-center">
                    <span className="text-xs font-bold text-emerald-600">{(minScore * 100).toFixed(0)}%</span>
                  </div>
                  <div className="hidden lg:flex col-span-1 items-center justify-center">
                    <span className={`text-xs font-bold ${spread >= 0.3 ? 'text-red-600' : 'text-emerald-600'}`}>
                      {(spread * 100).toFixed(0)}%
                    </span>
                  </div>
                </button>

                {/* Expanded Detail */}
                {isExpanded && (
                  <div className="px-6 pb-5 bg-slate-50/50">
                    <div className="grid md:grid-cols-2 gap-4 mt-3">
                      {pair.tool_results?.map((tr) => {
                        const toolInfo = TOOLS.find(t => t.id === tr.tool);
                        if (!toolInfo) return null;
                        const scorePct = (tr.score * 100).toFixed(1);
                        return (
                          <div key={tr.tool} className="bg-white rounded-xl border border-slate-200 p-4">
                            <div className="flex items-center justify-between mb-3">
                              <div className="flex items-center gap-2">
                                <div className={`w-7 h-7 rounded-lg bg-gradient-to-br ${toolInfo.gradient} flex items-center justify-center`}>
                                  <Zap size={13} className="text-white" />
                                </div>
                                <span className="text-sm font-semibold text-slate-900">{toolInfo.name}</span>
                              </div>
                              <span className={`text-lg font-bold ${tr.tool === 'integritydesk' ? 'text-brand-600' : 'text-slate-700'}`}>
                                {scorePct}%
                              </span>
                            </div>
                            <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                              <div
                                className="h-full rounded-full transition-all duration-500"
                                style={{
                                  width: `${tr.score * 100}%`,
                                  background: `linear-gradient(90deg, ${toolInfo.color}, ${toolInfo.color}dd)`,
                                }}
                              />
                            </div>
                            <div className="flex items-center justify-between mt-2">
                              <span className="text-xs text-slate-400">
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
    </div>
  );
}
