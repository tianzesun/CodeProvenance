'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { Modal, PageHeader } from '@/components/saas/SaaSPrimitives';
import { useAuth } from '@/components/AuthProvider';
import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '@/lib/apiClient';
import {
  Network, Users, ShieldCheck, Download,
  RefreshCw, AlertCircle, CheckCircle2,
  ChevronLeft, MoreVertical, Eye,
} from 'lucide-react';

interface Cluster {
  cluster_id: number;
  members: string[];
  center: string;
  avg_similarity: number;
  max_similarity: number;
  suspicious_pairs: number;
  evidence_strength: string;
  size: number;
}

export default function ClusterDetectionPage() {
  const { user } = useAuth();
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selectedCluster, setSelectedCluster] = useState<Cluster | null>(null);

  const loadClusters = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await apiClient.get('/api/cluster-detection/clusters');
      setClusters(response.data);
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { detail?: string; message?: string } } };
      setError(axiosError?.response?.data?.detail || axiosError?.response?.data?.message || (err as Error)?.message || 'Failed to load clusters');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadClusters();
  }, []);

  const getStrengthColor = (strength: string) => {
    switch (strength) {
      case 'strong': return 'text-red-600 bg-red-100';
      case 'moderate': return 'text-amber-600 bg-amber-100';
      case 'weak': return 'text-emerald-600 bg-emerald-100';
      default: return 'text-slate-600 bg-slate-100';
    }
  };

  return (
    <DashboardLayout>
      <div className="theme-page-container">
        {/* Header */}
        <div className="mb-4">
          <button
            onClick={() => window.history.back()}
            className="theme-link mb-4 flex items-center gap-2 text-sm font-semibold"
          >
            <ChevronLeft size={16} />
            Back to Dashboard
          </button>
        </div>
        <PageHeader
          eyebrow="Engine & R&D"
          eyebrowStyle="badge"
          title="Cluster Detection"
          description="Identify cheating groups through similarity network analysis"
          action={
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={loadClusters}
                disabled={loading}
                className="theme-button-primary inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition disabled:opacity-50"
              >
                {loading ? <RefreshCw size={16} className="animate-spin" /> : <RefreshCw size={16} />}
                Refresh
              </button>
              <button
                type="button"
                className="theme-button-secondary inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition"
              >
                <Download size={16} />
                Export
              </button>
            </div>
          }
        />

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <div className="text-2xl font-bold text-slate-900">{clusters.length}</div>
            <div className="text-sm text-slate-500">Clusters Found</div>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <div className="text-2xl font-bold text-slate-900">
              {clusters.reduce((sum, c) => sum + c.size, 0)}
            </div>
            <div className="text-sm text-slate-500">Students Involved</div>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <div className="text-2xl font-bold text-slate-900">
              {clusters.reduce((sum, c) => sum + c.suspicious_pairs, 0)}
            </div>
            <div className="text-sm text-slate-500">Suspicious Pairs</div>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <div className="text-2xl font-bold text-slate-900">
              {clusters.length > 0 ? (clusters.reduce((sum, c) => sum + c.avg_similarity, 0) / clusters.length * 100).toFixed(0) : 0}%
            </div>
            <div className="text-sm text-slate-500">Avg Similarity</div>
          </div>
        </div>

        {error && (
          <div className="mb-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 flex items-center gap-2">
            <AlertCircle size={16} />
            {error}
          </div>
        )}

        {/* Clusters Table */}
        <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-200 bg-slate-50 flex items-center gap-2">
            <Network size={16} className="text-slate-500" />
            <span className="font-medium text-slate-700">Detected Cheating Groups</span>
          </div>

          {loading ? (
            <div className="p-8 text-center">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-slate-900"></div>
              <p className="mt-2 text-slate-500">Analyzing similarity graph...</p>
            </div>
          ) : clusters.length === 0 ? (
            <div className="p-8 text-center">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-slate-100 mb-4">
                <ShieldCheck size={24} className="text-slate-400" />
              </div>
              <h3 className="text-lg font-medium text-slate-800 mb-2">No Cheating Groups Detected</h3>
              <p className="text-slate-500">
                Run analysis on more submissions to detect coordinated plagiarism.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {clusters.map((cluster) => (
                <div key={cluster.cluster_id} className="p-4 hover:bg-slate-50 cursor-pointer" onClick={() => setSelectedCluster(cluster)}>
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <span className="font-medium text-slate-900">
                          Group #{cluster.cluster_id + 1} • {cluster.size} students
                        </span>
                        <span className={`text-xs font-semibold px-2 py-1 rounded ${getStrengthColor(cluster.evidence_strength)}`}>
                          {cluster.evidence_strength}
                        </span>
                      </div>
                      <div className="flex items-center gap-4 text-sm text-slate-500">
                        <span>Avg Similarity: {(cluster.avg_similarity * 100).toFixed(1)}%</span>
                        <span>Suspicious Pairs: {cluster.suspicious_pairs}</span>
                      </div>
                      <div className="mt-2 flex items-center gap-1 text-xs text-slate-400">
                        {cluster.members.slice(0, 5).map((m, i) => (
                          <span key={i} className="bg-slate-100 px-2 py-1 rounded">
                            {m.split('/').pop()}
                          </span>
                        ))}
                        {cluster.members.length > 5 && (
                          <span>+{cluster.members.length - 5} more</span>
                        )}
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedCluster(cluster);
                      }}
                      className="p-2 hover:bg-slate-100 rounded-lg"
                    >
                      <Eye size={16} className="text-slate-500" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Detail Panel */}
        <Modal
          open={Boolean(selectedCluster)}
          title={selectedCluster ? `Cluster #${selectedCluster.cluster_id + 1} details` : 'Cluster details'}
          onClose={() => setSelectedCluster(null)}
        >
          {selectedCluster && (
            <div className="space-y-4">
              <div>
                <div className="theme-muted-text mb-1 text-sm">Members ({selectedCluster.size})</div>
                <div className="scrollbar-thin max-h-48 space-y-1 overflow-y-auto">
                  {selectedCluster.members.map((m, i) => (
                    <div key={i} className="text-sm font-mono text-[var(--text-secondary)]">
                      {m}
                    </div>
                  ))}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <div className="theme-muted-text">Avg Similarity</div>
                  <div className="theme-section-title">{(selectedCluster.avg_similarity * 100).toFixed(1)}%</div>
                </div>
                <div>
                  <div className="theme-muted-text">Max Similarity</div>
                  <div className="theme-section-title">{(selectedCluster.max_similarity * 100).toFixed(1)}%</div>
                </div>
                <div>
                  <div className="theme-muted-text">Suspicious Pairs</div>
                  <div className="theme-section-title">{selectedCluster.suspicious_pairs}</div>
                </div>
                <div>
                  <div className="theme-muted-text">Evidence Strength</div>
                  <div className="theme-section-title">{selectedCluster.evidence_strength}</div>
                </div>
              </div>
            </div>
          )}
        </Modal>
      </div>
    </DashboardLayout>
  );
}