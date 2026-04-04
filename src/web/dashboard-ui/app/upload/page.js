'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import axios from 'axios';
import {
  Upload as UploadIcon,
  FileUp,
  FolderArchive,
  Loader2,
  Check,
  X,
  AlertCircle,
  Settings2,
} from 'lucide-react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8500';

export default function UploadPage() {
  const router = useRouter();
  const [mode, setMode] = useState('individual');
  const [files, setFiles] = useState([]);
  const [zipFile, setZipFile] = useState(null);
  const [courseName, setCourseName] = useState('');
  const [assignmentName, setAssignmentName] = useState('');
  const [threshold, setThreshold] = useState(0.5);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    if (mode === 'individual') {
      setFiles(Array.from(e.dataTransfer.files));
    } else {
      setZipFile(e.dataTransfer.files[0]);
    }
  }, [mode]);

  const handleSubmit = async () => {
    setError('');
    if (mode === 'individual' && files.length < 2) {
      setError('Select at least 2 files');
      return;
    }
    if (mode === 'zip' && !zipFile) {
      setError('Select a ZIP file');
      return;
    }

    setUploading(true);
    const formData = new FormData();

    if (mode === 'individual') {
      files.forEach((f) => formData.append('files', f));
    } else {
      formData.append('file', zipFile);
    }
    formData.append('course_name', courseName);
    formData.append('assignment_name', assignmentName);
    formData.append('threshold', threshold);

    try {
      const url = mode === 'individual'
        ? `${API}/api/upload`
        : `${API}/api/upload-zip`;
      const res = await axios.post(url, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const jobId = res.data.job_id;

      const poll = setInterval(async () => {
        const status = await axios.get(`${API}/api/job/${jobId}`);
        if (status.data.status === 'completed') {
          clearInterval(poll);
          router.push(`/results/${jobId}`);
        } else if (status.data.status === 'failed') {
          clearInterval(poll);
          setUploading(false);
          setError(status.data.error || 'Analysis failed');
        }
      }, 1000);
    } catch (err) {
      setUploading(false);
      setError(err.response?.data?.error || 'Upload failed');
    }
  };

  return (
    <DashboardLayout>
      <div className="p-6 lg:p-8">
        <div className="max-w-3xl mx-auto">
          {/* Header */}
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-slate-900 tracking-tight">New Analysis</h1>
            <p className="text-slate-500 mt-1.5">
              Upload student submissions to detect code similarity and potential academic integrity issues.
            </p>
          </div>

          {/* Mode Toggle */}
          <div className="flex gap-2 mb-6">
            <button
              onClick={() => setMode('individual')}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all ${
                mode === 'individual'
                  ? 'bg-brand-600 text-white shadow-lg shadow-brand-500/25'
                  : 'bg-white border border-slate-200 text-slate-600 hover:border-slate-300'
              }`}
            >
              <FileUp size={16} />
              Individual Files
            </button>
            <button
              onClick={() => setMode('zip')}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all ${
                mode === 'zip'
                  ? 'bg-brand-600 text-white shadow-lg shadow-brand-500/25'
                  : 'bg-white border border-slate-200 text-slate-600 hover:border-slate-300'
              }`}
            >
              <FolderArchive size={16} />
              ZIP Archive
            </button>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="p-6">
              {/* Drop Zone */}
              <div
                onDrop={handleDrop}
                onDragOver={(e) => e.preventDefault()}
                className="border-2 border-dashed border-slate-200 rounded-xl p-12 text-center hover:border-brand-400 hover:bg-brand-50/30 transition-all duration-200 cursor-pointer group"
                onClick={() => {
                  if (mode === 'individual') {
                    document.getElementById('fileInput').click();
                  } else {
                    document.getElementById('zipInput').click();
                  }
                }}
              >
                <div className="w-14 h-14 rounded-2xl bg-slate-50 flex items-center justify-center mx-auto mb-4 group-hover:bg-brand-50 transition-colors">
                  <UploadIcon size={24} className="text-slate-400 group-hover:text-brand-500 transition-colors" />
                </div>
                <p className="text-sm font-semibold text-slate-700 mb-1">
                  {mode === 'individual'
                    ? 'Drop files here or click to browse'
                    : 'Drop ZIP file here or click to browse'}
                </p>
                <p className="text-xs text-slate-400">
                  {mode === 'individual'
                    ? 'Python, Java, C/C++, JavaScript, Rust, Go, and 20+ languages'
                    : 'All code files within the archive will be extracted and analyzed'}
                </p>
                <input
                  id="fileInput"
                  type="file"
                  multiple
                  accept=".py,.java,.c,.cpp,.h,.js,.ts,.go,.rs,.rb,.php,.cs,.kt,.swift"
                  className="hidden"
                  onChange={(e) => setFiles(Array.from(e.target.files))}
                />
                <input
                  id="zipInput"
                  type="file"
                  accept=".zip"
                  className="hidden"
                  onChange={(e) => setZipFile(e.target.files[0])}
                />
              </div>

              {/* File List */}
              {(files.length > 0 || zipFile) && (
                <div className="mt-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                      {mode === 'individual' ? `${files.length} files selected` : 'Archive selected'}
                    </span>
                    {mode === 'individual' && files.length > 0 && (
                      <button
                        onClick={() => setFiles([])}
                        className="text-xs text-slate-400 hover:text-red-500 transition-colors"
                      >
                        Clear all
                      </button>
                    )}
                  </div>
                  <div className="space-y-1.5 max-h-40 overflow-y-auto scrollbar-thin pr-1">
                    {mode === 'individual'
                      ? files.map((f, i) => (
                          <div
                            key={i}
                            className="flex items-center justify-between px-3 py-2.5 bg-slate-50 rounded-lg text-sm group/file"
                          >
                            <div className="flex items-center gap-2 min-w-0 flex-1">
                              <div className="w-7 h-7 rounded-md bg-emerald-50 flex items-center justify-center shrink-0">
                                <FileUp size={12} className="text-emerald-600" />
                              </div>
                              <span className="font-medium text-slate-700 truncate">{f.name}</span>
                            </div>
                            <div className="flex items-center gap-2 shrink-0 ml-2">
                              <span className="text-xs text-slate-400">{(f.size / 1024).toFixed(1)} KB</span>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setFiles(files.filter((_, j) => j !== i));
                                }}
                                className="opacity-0 group-hover/file:opacity-100 text-slate-300 hover:text-red-500 transition-all"
                              >
                                <X size={14} />
                              </button>
                            </div>
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
            </div>

            {/* Settings Footer */}
            <div className="border-t border-slate-100 bg-slate-50/50 p-6">
              <div className="flex items-center gap-2 mb-4">
                <Settings2 size={16} className="text-slate-400" />
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Analysis Settings</span>
              </div>

              <div className="grid md:grid-cols-2 gap-4 mb-5">
                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                    Course
                  </label>
                  <input
                    type="text"
                    value={courseName}
                    onChange={(e) => setCourseName(e.target.value)}
                    placeholder="e.g., CS101 - Intro to Programming"
                    className="w-full px-3.5 py-2.5 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 bg-white transition-all"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                    Assignment
                  </label>
                  <input
                    type="text"
                    value={assignmentName}
                    onChange={(e) => setAssignmentName(e.target.value)}
                    placeholder="e.g., Assignment 3 - Sorting"
                    className="w-full px-3.5 py-2.5 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 bg-white transition-all"
                  />
                </div>
              </div>

              <div className="mb-6">
                <div className="flex items-center justify-between mb-2">
                  <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    Similarity Threshold
                  </label>
                  <span className="text-sm font-bold text-brand-600 bg-brand-50 px-2.5 py-0.5 rounded-lg">
                    {(threshold * 100).toFixed(0)}%
                  </span>
                </div>
                <input
                  type="range"
                  min="0.1"
                  max="0.9"
                  step="0.05"
                  value={threshold}
                  onChange={(e) => setThreshold(parseFloat(e.target.value))}
                  className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-brand-600"
                />
                <div className="flex justify-between text-xs text-slate-400 mt-1.5">
                  <span>Strict (10%)</span>
                  <span>Moderate (50%)</span>
                  <span>Lenient (90%)</span>
                </div>
              </div>

              <button
                onClick={handleSubmit}
                disabled={uploading}
                className="w-full py-3.5 bg-gradient-to-r from-brand-600 to-brand-500 hover:from-brand-700 hover:to-brand-600 disabled:from-brand-300 disabled:to-brand-200 text-white font-semibold rounded-xl transition-all flex items-center justify-center gap-2 shadow-lg shadow-brand-500/25 hover:shadow-xl hover:shadow-brand-500/30 disabled:shadow-none"
              >
                {uploading ? (
                  <>
                    <Loader2 size={18} className="animate-spin" />
                    Analyzing submissions...
                  </>
                ) : (
                  <>
                    <Check size={18} />
                    Run Similarity Analysis
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
