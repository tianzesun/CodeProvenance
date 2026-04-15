'use client';

import { useState, useEffect } from 'react';
import DashboardLayout from '@/components/DashboardLayout';
import { useAuth } from '@/components/AuthProvider';
import { Database, Plus, FileText, Trash2, Edit, ExternalLink, Loader2 } from 'lucide-react';
import axios from 'axios';

const API = process.env.NEXT_PUBLIC_API_URL || '';

interface Dataset {
  id: string;
  name: string;
  desc: string;
  language: string;
  size: string;
  is_demo: boolean;
  created_at: string;
  created_by: string;
  case_count?: number;
}

interface Tool {
  id: string;
  name: string;
  desc: string;
  runnable: boolean;
  installed: boolean;
  status: string;
  engines: string[];
}

export default function DatasetsPage() {
  const { user } = useAuth();
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [tools, setTools] = useState<Tool[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const [datasetsRes, toolsRes] = await Promise.all([
          axios.get(`${API}/api/benchmark-datasets`, { withCredentials: true }),
          axios.get(`${API}/api/benchmark-tools`, { withCredentials: true })
        ]);
        setDatasets(datasetsRes.data.datasets);
        setTools(toolsRes.data.tools);
      } catch (err) {
        setError('Failed to load datasets and tools');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [user]);

  return (
    <DashboardLayout>
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-3">
                <Database size={24} className="text-blue-600" />
                Dataset Manager
              </h1>
              <p className="mt-2 text-slate-600">
                Manage benchmark and demonstration datasets for testing detection engines
              </p>
            </div>
            <button className="inline-flex items-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-xl transition shadow-md">
              <Plus size={16} />
              Create New Dataset
            </button>
          </div>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl text-red-700">
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 size={32} className="animate-spin text-blue-600" />
            <span className="ml-3 text-slate-600">Loading datasets...</span>
          </div>
        ) : datasets.length === 0 ? (
          <div className="text-center py-20 bg-slate-50 rounded-2xl border border-dashed border-slate-200">
            <Database size={48} className="mx-auto text-slate-400 mb-4" />
            <h3 className="font-semibold text-slate-700">No datasets found</h3>
            <p className="text-slate-500 mt-2">Create your first dataset or import one from the benchmark library</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {datasets.map((dataset) => (
              <div key={dataset.id} className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm hover:shadow-md transition">
                <div className="flex items-start justify-between mb-4">
                  <div className="w-10 h-10 rounded-xl bg-blue-100 flex items-center justify-center">
                    <Database size={18} className="text-blue-600" />
                  </div>
                  <div className="flex items-center gap-1">
                    <button className="p-2 hover:bg-slate-100 rounded-lg transition text-slate-500 hover:text-slate-700">
                      <Edit size={14} />
                    </button>
                    <button className="p-2 hover:bg-slate-100 rounded-lg transition text-slate-500 hover:text-red-600">
                      <Trash2 size={14} />
                    </button>
                    <button className="p-2 hover:bg-slate-100 rounded-lg transition text-slate-500 hover:text-blue-600">
                      <ExternalLink size={14} />
                    </button>
                  </div>
                </div>

                <h3 className="font-semibold text-slate-900">{dataset.name}</h3>
                <p className="text-sm text-slate-500 mt-1 line-clamp-2">{dataset.desc}</p>

                <div className="mt-4 flex flex-wrap gap-2">
                  <span className="px-2 py-1 bg-slate-100 text-slate-600 text-xs rounded-lg font-medium">
                    {dataset.language?.toUpperCase() || 'Mixed'}
                  </span>
                  <span className="px-2 py-1 bg-slate-100 text-slate-600 text-xs rounded-lg font-medium">
                    {dataset.size}
                  </span>
                  {dataset.is_demo && (
                    <span className="px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded-lg font-medium">
                      Demo
                    </span>
                  )}
                </div>

                <div className="mt-4 pt-4 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
                  <span>Created by {dataset.created_by || 'System'}</span>
                  <span>{new Date(dataset.created_at).toLocaleDateString()}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
