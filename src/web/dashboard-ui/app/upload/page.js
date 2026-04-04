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
      <div className="p-6 lg:p-8 max-w-4xl">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-slate-900">New Analysis</h1>
          <p className="text-slate-500 mt-1">
            Upload student submissions to detect code similarity.
          </p>
        </div>

        {/* Mode toggle */}
        <div className="flex gap-2 mb-6">
          <button
            onClick={() => setMode('individual')}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
              mode === 'individual'
                ? 'bg-brand-600 text-white'
                : 'bg-white border border-slate-200 text-slate-600 hover:border-brand-300'
            }`}
          >
            <FileUp size={16} />
            Individual Files
          </button>
          <button
            onClick={() => setMode('zip')}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
              mode === 'zip'
                ? 'bg-brand-600 text-white'
                : 'bg-white border border-slate-200 text-slate-600 hover:border-brand-300'
            }`}
          >
            <FolderArchive size={16} />
            ZIP Archive
          </button>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-6">
          {/* Drop zone */}
          <div
            onDrop={handleDrop}
            onDragOver={(e) => e.preventDefault()}
            className="border-2 border-dashed border-slate-200 rounded-xl p-10 text-center hover:border-brand-300 hover:bg-brand-50/30 transition-colors cursor-pointer"
            onClick={() => {
              if (mode === 'individual') {
                document.getElementById('fileInput').click();
              } else {
                document.getElementById('zipInput').click();
              }
            }}
          >
            <UploadIcon size={32} className="mx-auto text-slate-300 mb-3" />
            <p className="text-sm font-medium text-slate-700">
              {mode === 'individual'
                ? 'Drop files here or click to browse'
                : 'Drop ZIP file here or click to browse'}
            </p>
            <p className="text-xs text-slate-400 mt-1">
              {mode === 'individual'
                ? 'Python, Java, C/C++, JavaScript, Rust, Go, and 20+ languages'
                : 'All code files within the archive will be analyzed'}
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

          {/* File list */}
          {(files.length > 0 || zipFile) && (
            <div className="mt-4 space-y-2 max-h-40 overflow-y-auto scrollbar-thin">
              {mode === 'individual'
                ? files.map((f, i) => (
                    <div
                      key={i}
                      className="flex items-center justify-between px-3 py-2 bg-slate-50 rounded-lg text-sm"
                    >
                      <span className="font-medium text-slate-700 truncate flex-1">
                        {f.name}
                      </span>
                      <span className="text-slate-400 ml-3 text-xs">
                        {(f.size / 1024).toFixed(1)} KB
                      </span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setFiles(files.filter((_, j) => j !== i));
                        }}
                        className="ml-2 text-slate-400 hover:text-red-500"
                      >
                        <X size={14} />
                      </button>
                    </div>
                  ))
                : zipFile && (
                    <div className="flex items-center justify-between px-3 py-2 bg-slate-50 rounded-lg text-sm">
                      <span className="font-medium text-slate-700 truncate flex-1">
                        {zipFile.name}
                      </span>
                      <span className="text-slate-400 ml-3 text-xs">
                        {(zipFile.size / 1024).toFixed(1)} KB
                      </span>
                    </div>
                  )}
            </div>
          )}

          {/* Form fields */}
          <div className="grid md:grid-cols-2 gap-4 mt-6">
            <div>
              <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wider mb-1.5">
                Course
              </label>
              <input
                type="text"
                value={courseName}
                onChange={(e) => setCourseName(e.target.value)}
                placeholder="e.g., CS101"
                className="w-full px-3 py-2.5 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wider mb-1.5">
                Assignment
              </label>
              <input
                type="text"
                value={assignmentName}
                onChange={(e) => setAssignmentName(e.target.value)}
                placeholder="e.g., Assignment 3"
                className="w-full px-3 py-2.5 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
              />
            </div>
          </div>

          {/* Threshold */}
          <div className="mt-5">
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-semibold text-slate-600 uppercase tracking-wider">
                Similarity Threshold
              </label>
              <span className="text-sm font-bold text-brand-600">
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
            <div className="flex justify-between text-xs text-slate-400 mt-1">
              <span>10%</span>
              <span>50%</span>
              <span>90%</span>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Submit */}
          <button
            onClick={handleSubmit}
            disabled={uploading}
            className="w-full mt-6 py-3 bg-brand-600 hover:bg-brand-700 disabled:bg-brand-300 text-white font-semibold rounded-lg transition-colors flex items-center justify-center gap-2"
          >
            {uploading ? (
              <>
                <Loader2 size={18} className="animate-spin" />
                Analyzing...
              </>
            ) : (
              <>
                <Check size={18} />
                Run Analysis
              </>
            )}
          </button>
        </div>
      </div>
    </DashboardLayout>
  );
}
