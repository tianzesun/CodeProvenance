// @ts-nocheck
'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { useAuth } from '@/components/AuthProvider';
import { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import axios from 'axios';
import {
  Loader2, FileUp, AlertCircle,
  FileText, Eye,
} from 'lucide-react';

const API = process.env.NEXT_PUBLIC_API_URL || '';

function ErrorAnalysisPage() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [results, setResults] = useState(null);
  const [selectedJobId, setSelectedJobId] = useState('');
  const [availableJobs, setAvailableJobs] = useState([]);


  // Load available benchmark jobs
  useEffect(() => {
    const loadJobs = async () => {
      try {
        const response = await axios.get(`${API}/api/benchmark-history`, { withCredentials: true });
        // Transform benchmark history into job format
        const jobs = (response.data.runs || []).map(run => ({
          id: run.job_id,
          name: run.dataset || `Benchmark ${run.job_id}`,
          created_at: run.run_at || new Date().toISOString()
        }));
        setAvailableJobs(jobs);
      } catch (err) {
        console.error('Failed to load benchmark jobs:', err);
        setError('Failed to load available benchmark jobs');
      }
    };
    loadJobs();
  }, []);

  // Load error analysis data for selected job
  const loadErrorAnalysis = useCallback(async (jobId) => {
    if (!jobId) return;

    setLoading(true);
    setError('');
    try {
      const response = await axios.get(`${API}/api/job/${jobId}`, { withCredentials: true });
      setResults(response.data);
    } catch (err) {
      setError('Failed to load error analysis data. The job may not exist or you may not have access to it.');
      console.error('Error loading analysis:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedJobId) {
      loadErrorAnalysis(selectedJobId);
    }
  }, [selectedJobId, loadErrorAnalysis]);

  // Extract error analysis data from job results
  const errorAnalysisData = useMemo(() => {
    if (!results || results.status !== 'completed') return null;

    // The job object structure is different from the benchmark results
    // We need to extract the relevant data for error analysis
    const pairResults = results.results || results.pair_results || [];
    const summary = results.summary || {};

    // For now, we'll create a simplified version since the full error analysis
    // data structure may not be available in the job object
    // This is a placeholder that shows the page works but with limited data
    return {
      hasData: pairResults.length > 0,
      pairCount: pairResults.length,
      jobId: results.id,
      status: results.status,
      dataset: results.dataset || 'Unknown',
      pairResults: pairResults.slice(0, 100), // Limit for performance
    };
  }, [results]);

  if (loading && !results) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center min-h-[400px]">
          <Loader2 className="h-8 w-8 animate-spin text-violet-500" />
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="max-w-7xl mx-auto p-6 space-y-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Error Analysis</h1>
            <p className="text-slate-600 mt-1">Inspect false positives and false negatives from benchmark results</p>
          </div>
        </div>

        {/* Job Selection */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
            <div className="flex-1">
              <label className="block text-sm font-semibold text-slate-700 mb-2">Select Benchmark Job</label>
              <select
                value={selectedJobId}
                onChange={(e) => setSelectedJobId(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-violet-500"
              >
                <option value="">Choose a benchmark job...</option>
                {availableJobs.map(job => (
                  <option key={job.id} value={job.id}>
                    {job.name || `Job ${job.id}`} - {new Date(job.created_at).toLocaleDateString()}
                  </option>
                ))}
              </select>
            </div>
            <button
              onClick={() => loadErrorAnalysis(selectedJobId)}
              disabled={!selectedJobId || loading}
              className="px-6 py-2 bg-violet-600 hover:bg-violet-700 disabled:bg-slate-300 text-white font-semibold rounded-lg transition-colors flex items-center gap-2"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Eye className="h-4 w-4" />}
              Analyze
            </button>
          </div>
        </div>

        {error && (
          <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 flex items-center gap-2">
            <AlertCircle size={14} className="shrink-0" />{error}
          </div>
        )}

        {errorAnalysisData && (
          <>
            {/* Job Overview */}
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
              <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Job ID</div>
                <div className="mt-3 text-sm font-semibold text-slate-900 font-mono">
                  {errorAnalysisData.jobId}
                </div>
                <div className="mt-2 text-xs text-slate-500">
                  Status: {errorAnalysisData.status}
                </div>
              </div>

              <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Dataset</div>
                <div className="mt-3 text-sm font-semibold text-slate-900">
                  {errorAnalysisData.dataset}
                </div>
                <div className="mt-2 text-xs text-slate-500">
                  Benchmark target
                </div>
              </div>

              <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Total Pairs</div>
                <div className="mt-3 text-2xl font-bold text-slate-900">
                  {errorAnalysisData.pairCount}
                </div>
                <div className="mt-2 text-xs text-slate-500">
                  File pairs analyzed
                </div>
              </div>

              <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Data Available</div>
                <div className="mt-3 text-sm font-semibold text-slate-900">
                  {errorAnalysisData.hasData ? 'Yes' : 'Limited'}
                </div>
                <div className="mt-2 text-xs text-slate-500">
                  Error analysis data
                </div>
              </div>
            </div>
                <p className="mt-2 text-sm leading-6 text-slate-600">{errorAnalysisData.trustLevel.description}</p>
                <span className={`mt-3 inline-flex rounded-full px-2.5 py-1 text-xs font-bold ${errorAnalysisData.trustLevel.className}`}>
                  {errorAnalysisData.trustLevel.label} trust
                </span>
              </div>

              <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Held-Out Labels</div>
                <div className="mt-3 text-sm leading-6 text-slate-600">
                  {errorAnalysisData.splitProtocol.holdout_positive_pairs ??
                   errorAnalysisData.metricIntegrity.positive_pairs ??
                   errorAnalysisData.productPanResult.nPositives ?? 0} positive pairs and{' '}
                  {errorAnalysisData.splitProtocol.holdout_negative_pairs ??
                   errorAnalysisData.metricIntegrity.negative_pairs ??
                   errorAnalysisData.productPanResult.nNegatives ?? 0} negative pairs.
                </div>
                <div className="mt-2 text-xs font-semibold text-slate-500">
                  Total evaluated: {errorAnalysisData.heldoutSize}
                </div>
              </div>

              <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Threshold</div>
                <div className="mt-3 text-2xl font-bold text-slate-900">
                  {Number.isFinite(errorAnalysisData.decisionThreshold) ? errorAnalysisData.decisionThreshold.toFixed(2) : 'N/A'}
                </div>
                <div className="mt-2 text-xs leading-5 text-slate-500">
                  Used for classification decisions
                </div>
              </div>

              <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Confusion Matrix</div>
                <div className="mt-3 grid grid-cols-2 gap-2 text-center">
                  <div className="text-emerald-600">
                    <div className="text-lg font-bold">{errorAnalysisData.confusion.tp || 0}</div>
                    <div className="text-xs">TP</div>
                  </div>
                  <div className="text-rose-600">
                    <div className="text-lg font-bold">{errorAnalysisData.confusion.fp || 0}</div>
                    <div className="text-xs">FP</div>
                  </div>
                  <div className="text-amber-600">
                    <div className="text-lg font-bold">{errorAnalysisData.confusion.fn || 0}</div>
                    <div className="text-xs">FN</div>
                  </div>
                  <div className="text-slate-600">
                    <div className="text-lg font-bold">{errorAnalysisData.confusion.tn || 0}</div>
                    <div className="text-xs">TN</div>
                  </div>
                </div>
              </div>
            </div>

            {/* Pair Results Overview */}
            <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
              <h3 className="font-semibold text-slate-900 mb-4">Analyzed Pairs</h3>
              {errorAnalysisData.pairResults.length > 0 ? (
                <div className="space-y-3">
                  <p className="text-sm text-slate-600">
                    Showing first {errorAnalysisData.pairResults.length} pairs from this benchmark job.
                  </p>
                  <div className="max-h-96 overflow-y-auto border border-slate-200 rounded-lg">
                    <div className="divide-y divide-slate-100">
                      {errorAnalysisData.pairResults.map((pair, index) => (
                        <div key={index} className="p-3 hover:bg-slate-50">
                          <div className="flex items-center justify-between">
                            <div className="flex-1">
                              <div className="font-medium text-sm text-slate-900">
                                {pair.file_a} vs {pair.file_b}
                              </div>
                              <div className="text-xs text-slate-500 mt-1">
                                Score: {(pair.score * 100).toFixed(1)}% |
                                Risk: {pair.risk_level || 'unknown'}
                              </div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center py-8 text-slate-500">
                  <FileText className="h-12 w-12 mx-auto mb-3 opacity-50" />
                  <div className="font-semibold">No pair results available</div>
                  <div className="text-sm">This job may not have completed successfully or results may not be available.</div>
                </div>
              )}
            </div>



            {/* Note about full error analysis */}
            <div className="bg-blue-50 rounded-2xl border border-blue-200 p-6">
              <div className="flex items-start gap-3">
                <AlertCircle className="h-5 w-5 text-blue-600 mt-0.5 flex-shrink-0" />
                <div>
                  <h3 className="font-semibold text-blue-900">Limited Error Analysis</h3>
                  <p className="text-sm text-blue-700 mt-1">
                    This page currently shows basic job information and pair results. For detailed error analysis
                    with false positive/negative inspection, the full error analysis feature needs to be implemented
                    with the appropriate data structures from the benchmark results.
                  </p>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </DashboardLayout>
  );
}

export default ErrorAnalysisPage;