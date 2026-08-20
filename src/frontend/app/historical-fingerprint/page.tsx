'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { useAuth } from '@/components/AuthProvider';
import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '@/lib/apiClient';
import {
  TrendingUp, ShieldCheck, AlertCircle,
  ChevronLeft, RefreshCw, Download,
  LineChart, Activity, Clock,
} from 'lucide-react';

interface StyleChange {
  submission_id: string;
  assignment_id: string;
  change_type: string;
  magnitude: number;
  confidence: number;
  explanation: string;
}

interface StyleTrend {
  submission_id: string;
  assignment_id: string;
  style_vector: number[];
}

export default function HistoricalFingerprintPage() {
  const { user } = useAuth();
  const [trends, setTrends] = useState<Record<string, StyleTrend[]>>({});
  const [alerts, setAlerts] = useState<StyleChange[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const loadHistoricalData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await apiClient.get('/api/historical-fingerprint/alerts');
      setAlerts(response.data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to load data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadHistoricalData();
  }, []);

  const getRiskColor = (level: string) => {
    switch (level) {
      case 'critical': return 'text-red-600 bg-red-100';
      case 'high': return 'text-orange-600 bg-orange-100';
      case 'medium': return 'text-amber-600 bg-amber-100';
      default: return 'text-emerald-600 bg-emerald-100';
    }
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
            Back to Dashboard
          </button>
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-slate-900">Historical Fingerprint</h1>
              <p className="text-slate-500 mt-1">Detect sudden style changes that may indicate AI or external code</p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={loadHistoricalData}
                disabled={loading}
                className="flex items-center gap-2 px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-800 disabled:opacity-50"
              >
                {loading ? <RefreshCw size={16} className="animate-spin" /> : <RefreshCw size={16} />}
                Refresh
              </button>
              <button className="flex items-center gap-2 px-4 py-2 border border-slate-200 text-slate-700 rounded-lg hover:bg-slate-50">
                <Download size={16} />
                Export
              </button>
            </div>
          </div>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <div className="text-2xl font-bold text-slate-900">{alerts.length}</div>
            <div className="text-sm text-slate-500">Style Changes Detected</div>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <div className="text-2xl font-bold text-slate-900">
              {alerts.filter(a => a.confidence > 0.7).length}
            </div>
            <div className="text-sm text-slate-500">High Confidence Alerts</div>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <div className="text-2xl font-bold text-slate-900">
              {alerts.filter(a => a.change_type === 'composite').length}
            </div>
            <div className="text-sm text-slate-500">Composite Changes</div>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <div className="text-2xl font-bold text-slate-900">
              {alerts.length > 0 ? (alerts.reduce((s, a) => s + a.magnitude, 0) / alerts.length * 100).toFixed(0) : 0}%
            </div>
            <div className="text-sm text-slate-500">Avg Change Magnitude</div>
          </div>
        </div>

        {error && (
          <div className="mb-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 flex items-center gap-2">
            <AlertCircle size={16} />
            {error}
          </div>
        )}

        {/* Alerts List */}
        <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-200 bg-slate-50 flex items-center gap-2">
            <TrendingUp size={16} className="text-slate-500" />
            <span className="font-medium text-slate-700">Style Change Alerts</span>
          </div>

          {loading ? (
            <div className="p-8 text-center">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-slate-900"></div>
              <p className="mt-2 text-slate-500">Analyzing style trends...</p>
            </div>
          ) : alerts.length === 0 ? (
            <div className="p-8 text-center">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-slate-100 mb-4">
                <ShieldCheck size={24} className="text-slate-400" />
              </div>
              <h3 className="text-lg font-medium text-slate-800 mb-2">No Style Changes Detected</h3>
              <p className="text-slate-500">
                Students' coding styles appear consistent across submissions.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {alerts.map((alert, i) => (
                <div key={i} className="p-4 hover:bg-slate-50">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <span className="font-medium text-slate-900">
                          {alert.assignment_id || 'Assignment'}
                        </span>
                        <span className={`text-xs font-semibold px-2 py-1 rounded ${getRiskColor('medium')}`}>
                          {alert.change_type}
                        </span>
                      </div>
                      <div className="text-sm text-slate-600 mb-2">{alert.explanation}</div>
                      <div className="flex items-center gap-4 text-xs text-slate-400">
                        <span>Magnitude: {(alert.magnitude * 100).toFixed(1)}%</span>
                        <span>Confidence: {(alert.confidence * 100).toFixed(0)}%</span>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-lg font-bold text-slate-900">
                        {(alert.magnitude * 100).toFixed(0)}%
                      </div>
                      <div className="text-xs text-slate-400">Change</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Style Timeline (Conceptual) */}
        <div className="mt-6 bg-white rounded-2xl border border-slate-200 p-4">
          <div className="flex items-center gap-2 mb-4">
            <Activity size={16} className="text-slate-500" />
            <h3 className="font-medium text-slate-700">Style Consistency Overview</h3>
          </div>
          <div className="h-40 flex items-center justify-center text-slate-500">
            <div className="text-center">
              <LineChart size={32} className="mx-auto mb-2 text-slate-300" />
              <p>Style timeline visualization would appear here</p>
              <p className="text-xs mt-1">Connect historical fingerprint data to render</p>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}