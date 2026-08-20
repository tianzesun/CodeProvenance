'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { useAuth } from '@/components/AuthProvider';
import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '@/lib/apiClient';
import {
  Code, GitCompare, SplitSquareVertical,
  FileText, Share2, Download, RefreshCw,
  AlertCircle, CheckCircle2, ExternalLink,
  ChevronLeft, ChevronRight, ZoomIn, ZoomOut,
} from 'lucide-react';

interface EvidenceViewProps {
  fileA: string;
  fileB: string;
  score: number;
  verdict: string;
  onBack?: () => void;
}

export default function EvidenceViewerPage() {
  const { user } = useAuth();
  const [fileA, setFileA] = useState('');
  const [fileB, setFileB] = useState('');
  const [score, setScore] = useState(0.5);
  const [verdict, setVerdict] = useState('REVIEW');
  const [loading, setLoading] = useState(false);
  const [evidenceData, setEvidenceData] = useState<any>(null);
  const [error, setError] = useState('');

  const loadEvidenceView = useCallback(async (submissionA: string, submissionB: string) => {
    setLoading(true);
    setError('');
    try {
      const response = await apiClient.post('/api/evidence-view/generate', {
        code_a: submissionA,
        code_b: submissionB,
        verdict,
        confidence: score,
        explanation: `Similarity score: ${(score * 100).toFixed(1)}%`,
      });
      setEvidenceData(response.data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to load evidence view');
    } finally {
      setLoading(false);
    }
  }, [score, verdict]);

  // Mock data for demonstration
  const mockCodeA = `def find_max(numbers):
    """Find the maximum value in a list."""
    if not numbers:
        return None
    max_val = numbers[0]
    for num in numbers:
        if num > max_val:
            max_val = num
    return max_val`;

  const mockCodeB = `def find_maximum(values):
    """Find the maximum value in a list."""
    if not values:
        return None
    max_val = values[0]
    for val in values:
        if val > max_val:
            max_val = val
    return max_val`;

  useEffect(() => {
    // Load with mock data for demo
    setFileA(mockCodeA);
    setFileB(mockCodeB);
    setScore(0.87);
    setVerdict('PROBABLE');
    loadEvidenceView(mockCodeA, mockCodeB);
  }, []);

  const VerdictBadge = ({ v }: { v: string }) => {
    const styles = {
      TRUE: 'bg-red-100 text-red-700 border-red-200',
      PROBABLE: 'bg-amber-100 text-amber-700 border-amber-200',
      REVIEW: 'bg-blue-100 text-blue-700 border-blue-200',
      FLAG: 'bg-yellow-100 text-yellow-700 border-yellow-200',
      CLEAN: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    };
    return (
      <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm font-semibold ${styles[v as keyof typeof styles] || styles.REVIEW}`}>
        <CheckCircle2 size={14} />
        {v}
      </span>
    );
  };

  return (
    <DashboardLayout>
      <div className="max-w-7xl mx-auto p-6">
        {/* Header */}
        <div className="mb-6">
          <button 
            onClick={() => window.history.back()}
            className="flex items-center gap-2 text-slate-600 hover:text-slate-900 mb-4"
          >
            <ChevronLeft size={16} />
            Back to Results
          </button>
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-slate-900">Evidence Viewer</h1>
              <p className="text-slate-500 mt-1">Side-by-side comparison with matched elements highlighted</p>
            </div>
            <div className="flex items-center gap-3">
              <VerdictBadge v={verdict} />
              <span className="text-sm font-medium text-slate-600">
                Score: {(score * 100).toFixed(1)}%
              </span>
            </div>
          </div>
        </div>

        {/* Controls */}
        <div className="mb-4 flex items-center gap-3">
          <button
            onClick={() => loadEvidenceView(fileA, fileB)}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-800 disabled:opacity-50"
          >
            {loading ? <RefreshCw size={16} className="animate-spin" /> : <RefreshCw size={16} />}
            Refresh
          </button>
          <button className="flex items-center gap-2 px-4 py-2 border border-slate-200 text-slate-700 rounded-lg hover:bg-slate-50">
            <Download size={16} />
            Export PDF
          </button>
        </div>

        {error && (
          <div className="mb-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 flex items-center gap-2">
            <AlertCircle size={16} />
            {error}
          </div>
        )}

        {/* Main Comparison View */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Submission A */}
          <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-200 bg-slate-50 flex items-center gap-2">
              <FileText size={16} className="text-slate-500" />
              <span className="font-medium text-slate-700">Submission A</span>
              <span className="text-xs text-slate-400 ml-auto">Python</span>
            </div>
            <div className="max-h-96 overflow-y-auto p-4 font-mono text-sm">
              <pre className="text-slate-800 whitespace-pre-wrap">{fileA || 'No code provided'}</pre>
            </div>
          </div>

          {/* Submission B */}
          <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-200 bg-slate-50 flex items-center gap-2">
              <FileText size={16} className="text-slate-500" />
              <span className="font-medium text-slate-700">Submission B</span>
              <span className="text-xs text-slate-400 ml-auto">Python</span>
            </div>
            <div className="max-h-96 overflow-y-auto p-4 font-mono text-sm">
              <pre className="text-slate-800 whitespace-pre-wrap">{fileB || 'No code provided'}</pre>
            </div>
          </div>
        </div>

        {/* Matched Elements Summary */}
        {evidenceData && (
          <div className="mt-6 space-y-4">
            <h2 className="text-lg font-semibold text-slate-900">Matched Elements</h2>
            
            {/* Functions */}
            <div className="bg-white rounded-2xl border border-slate-200 p-4">
              <div className="flex items-center gap-2 mb-3">
                <Code size={16} className="text-slate-600" />
                <h3 className="font-medium text-slate-800">Matched Functions</h3>
              </div>
              <div className="space-y-2">
                <div className="p-3 bg-slate-50 rounded-lg">
                  <div className="flex items-center justify-between">
                    <span className="font-medium">find_max vs find_maximum</span>
                    <span className="text-xs font-semibold text-emerald-700 bg-emerald-100 px-2 py-1 rounded">92%</span>
                  </div>
                  <div className="mt-2 text-sm text-slate-600">
                    Both functions iterate through a list to find the maximum value.
                    Parameter names differ (numbers vs values).
                  </div>
                </div>
              </div>
            </div>

            {/* AST Regions */}
            <div className="bg-white rounded-2xl border border-slate-200 p-4">
              <div className="flex items-center gap-2 mb-3">
                <Share2 size={16} className="text-slate-600" />
                <h3 className="font-medium text-slate-800">AST Structure Match</h3>
              </div>
              <div className="p-3 bg-slate-50 rounded-lg">
                <div className="flex items-center justify-between">
                  <span className="font-medium">Function definition structure</span>
                  <span className="text-xs font-semibold text-emerald-700 bg-emerald-100 px-2 py-1 rounded">87%</span>
                </div>
                <div className="mt-2 text-xs text-slate-500">
                  Both use the same control flow pattern: if-check-for-return
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Empty State */}
        {!evidenceData && !loading && (
          <div className="mt-6 text-center py-12">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-slate-100 mb-4">
              <AlertCircle size={24} className="text-slate-400" />
            </div>
            <h3 className="text-lg font-medium text-slate-800 mb-2">No Evidence Data Available</h3>
            <p className="text-slate-500 mb-4">
              Run a comparison to see matched functions, blocks, and AST regions.
            </p>
            <button
              onClick={() => loadEvidenceView(fileA, fileB)}
              className="px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-800"
            >
              Generate Evidence View
            </button>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}