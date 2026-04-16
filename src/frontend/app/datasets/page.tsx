'use client';

import { useState, useEffect, useCallback, useRef, useMemo, FormEvent } from 'react';
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
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [creatingDataset, setCreatingDataset] = useState(false);

  // Dataset creation state - same implementation as admin page
  const datasetFormRef = useRef({
    name: '',
    description: '',
    language: 'python',
    numFiles: 10,
    similarityType: 'type1_exact',
  });

  const [datasetForm, setDatasetForm] = useState(datasetFormRef.current);

  // Optimized form change handlers to prevent unnecessary re-renders
  const handleDatasetFormChange = useCallback((field: string, value: string | number) => {
    setDatasetForm(prev => ({ ...prev, [field]: value }));
  }, []);

  // Update ref when form changes
  useEffect(() => {
    datasetFormRef.current = datasetForm;
  }, [datasetForm]);

  const similarityHelpText = useMemo(() => {
    const helpTexts: Record<string, string> = {
      type1_exact: 'Creates identical code segments for testing exact copy detection.',
      type2_renamed: 'Generates code with renamed variables and functions.',
      type3_modified: 'Produces code with added comments, reordered statements, or modified structure.',
      type4_semantic: 'Creates functionally equivalent code with different algorithms or syntax.',
      token_similarity: 'Focuses on programming-language token patterns and usage.',
      structural_similarity: 'Emphasizes code organization and structural similarities.',
      semantic_similarity: 'Generates conceptually similar solutions using different approaches.',
    };
    return helpTexts[datasetForm.similarityType] || '';
  }, [datasetForm.similarityType]);

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

  const createDemoDataset = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setCreatingDataset(true);

    try {
      const result = await axios.post(`${API}/api/admin/create-demo-dataset`, datasetForm, { withCredentials: true });

      if (result.data && result.data.files_created) {
        // Refresh datasets list after creation
        const datasetsRes = await axios.get(`${API}/api/benchmark-datasets`, { withCredentials: true });
        setDatasets(datasetsRes.data.datasets);
      }

      // Reset form
      setDatasetForm({
        name: '',
        description: '',
        language: 'python',
        numFiles: 10,
        similarityType: 'type1_exact',
      });
      
      setShowCreateModal(false);
    } catch (error: unknown) {
      console.error('Demo dataset creation error:', error);
      let errorMessage = 'Failed to create demo dataset.';
      
      if (axios.isAxiosError(error)) {
        errorMessage = error.response?.data?.detail || error.response?.data?.message || error.message || errorMessage;
      }
      
      setError(errorMessage);
    } finally {
      setCreatingDataset(false);
    }
  };

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
            <button 
              onClick={() => setShowCreateModal(true)}
              className="inline-flex items-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-xl transition shadow-md"
            >
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

        {/* Create Dataset Modal */}
        {showCreateModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-[30px] shadow-2xl max-w-3xl w-full p-8">
              <div className="flex items-start justify-between mb-6">
                <div>
                  <div className="inline-flex items-center gap-2 rounded-full border border-emerald-600/10 bg-emerald-600/[0.06] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-emerald-600 mb-3">
                    <Database size={14} />
                    Dataset Tools
                  </div>
                  <h3 className="text-2xl font-semibold text-slate-900">Demo dataset creation</h3>
                  <p className="mt-2 text-sm text-slate-600 max-w-xl">
                    Generate synthetic datasets for testing plagiarism detection algorithms. Create custom datasets with controlled similarity patterns.
                  </p>
                </div>
                <button 
                  onClick={() => {
                    setShowCreateModal(false);
                    setError('');
                    setDatasetForm({
                      name: '',
                      description: '',
                      language: 'python',
                      numFiles: 10,
                      similarityType: 'type1_exact',
                    });
                  }}
                  className="p-2 hover:bg-slate-100 rounded-xl transition text-slate-500"
                >
                  ✕
                </button>
              </div>
              
              <form className="space-y-6 mt-6" onSubmit={createDemoDataset}>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Dataset Name</label>
                    <input
                      type="text"
                      value={datasetForm.name}
                      onChange={(event) => handleDatasetFormChange('name', event.target.value)}
                      className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                      placeholder="my_test_dataset"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Programming Language</label>
                    <select
                      value={datasetForm.language}
                      onChange={(event) => handleDatasetFormChange('language', event.target.value)}
                      className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                    >
                      <option value="python">Python</option>
                      <option value="java">Java</option>
                      <option value="javascript">JavaScript</option>
                      <option value="cpp">C++</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Description</label>
                  <input
                    type="text"
                    value={datasetForm.description}
                    onChange={(event) => handleDatasetFormChange('description', event.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                    placeholder="Dataset for testing plagiarism detection"
                  />
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Number of Files</label>
                    <input
                      type="number"
                      min="5"
                      max="100"
                      value={datasetForm.numFiles}
                      onChange={(event) => handleDatasetFormChange('numFiles', parseInt(event.target.value) || 10)}
                      className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Similarity Type</label>
                    <select
                      value={datasetForm.similarityType}
                      onChange={(event) => handleDatasetFormChange('similarityType', event.target.value)}
                      className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                    >
                      <option value="type1_exact">Type 1 - Exact Copy (Direct copy-paste)</option>
                      <option value="type2_renamed">Type 2 - Renamed Identifiers (Variable renaming)</option>
                      <option value="type3_modified">Type 3 - Modified Structure (Added/removed code)</option>
                      <option value="type4_semantic">Type 4 - Semantic Equivalence (Different syntax, same behavior)</option>
                      <option value="token_similarity">Token-Level Similarity (Programming style patterns)</option>
                      <option value="structural_similarity">Structural Similarity (Code organization)</option>
                      <option value="semantic_similarity">Semantic Similarity (Conceptual equivalence)</option>
                    </select>
                    <p className="mt-1 text-xs text-slate-500">
                      {similarityHelpText}
                    </p>
                  </div>
                </div>
              
                <div className="mt-8 flex justify-end gap-3">
                  <button
                    type="button"
                    onClick={() => {
                      setShowCreateModal(false);
                      setError('');
                      setDatasetForm({
                        name: '',
                        description: '',
                        language: 'python',
                        numFiles: 10,
                        similarityType: 'type1_exact',
                      });
                    }}
                    className="px-5 py-3 text-slate-700 hover:bg-slate-100 rounded-xl transition font-medium"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={creatingDataset || !datasetForm.name.trim()}
                    className="px-8 py-3 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 text-white rounded-xl transition flex items-center gap-3 font-semibold min-w-[200px] justify-center"
                  >
                    {creatingDataset ? (
                      <>
                        <Loader2 size={18} className="animate-spin" />
                        Generating code samples...
                      </>
                    ) : (
                      'Create Demo Dataset'
                    )}
                  </button>
                </div>
              </form>
            </div>
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
