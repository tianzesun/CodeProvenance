'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { useAuth } from '@/components/AuthProvider';
import Link from 'next/link';
import { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { useRouter } from 'next/navigation';
import axios, { AxiosError } from 'axios';
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

const API = '';
const UPLOAD_FORM_STORAGE_KEY = 'integritydesk-upload-form-v1';
const UPLOAD_ENGINE_OPTIONS = [
  { key: 'token', label: 'Token' },
  { key: 'ast', label: 'AST' },
  { key: 'winnowing', label: 'Winnowing' },
  { key: 'gst', label: 'GST' },
  { key: 'semantic', label: 'Semantic' },
  { key: 'web', label: 'Web' },
  { key: 'ai_detection', label: 'AI Detection' },
  { key: 'execution_cfg', label: 'Execution/CFG' },
];

function getApiErrorMessage(error: unknown, fallback = 'Request failed') {
  if (axios.isAxiosError(error)) {
    return (
      (error.response?.data as { detail?: string; error?: string } | undefined)?.detail ||
      (error.response?.data as { detail?: string; error?: string } | undefined)?.error ||
      error.message ||
      fallback
    );
  }
  return fallback;
}

export default function UploadPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [courseName, setCourseName] = useState('');
  const [assignmentName, setAssignmentName] = useState('');
  const [threshold, setThreshold] = useState(0.5);
  const [activeEngines, setActiveEngines] = useState<string[]>([]);
  const [thresholdLoading, setThresholdLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
      }
    };
  }, []);

  // Start job polling with proper cleanup
  const startPolling = useCallback((jobId: string) => {
    if (pollRef.current) clearInterval(pollRef.current);

    pollRef.current = setInterval(async () => {
      try {
        const jobStatus = await axios.get(`${API}/api/job/${jobId}`);
        if (jobStatus.data.status === 'completed') {
          if (pollRef.current) clearInterval(pollRef.current);
          router.push(`/results/${jobId}`);
        } else if (jobStatus.data.status === 'failed') {
          if (pollRef.current) clearInterval(pollRef.current);
          setUploading(false);
          setError(jobStatus.data.error || 'Analysis failed');
        }
      } catch (error) {
        if (pollRef.current) clearInterval(pollRef.current);
        setUploading(false);
        setError(getApiErrorMessage(error, 'Could not load analysis status.'));
      }
    }, 1000);
  }, [router]);

  const zipFile = useMemo(() => {
    if (files.length !== 1) {
      return null;
    }
    const [file] = files;
    return file.name.toLowerCase().endsWith('.zip') ? file : null;
  }, [files]);

  const selectedFiles = useMemo(() => (zipFile ? [] : files), [files, zipFile]);

  const hasMixedZipSelection = useMemo(
    () => files.length > 1 && files.some((file) => file.name.toLowerCase().endsWith('.zip')),
    [files],
  );

  const canRunCheck = useMemo(() => {
    if (uploading || hasMixedZipSelection) {
      return false;
    }
    if (activeEngines.length === 0) {
      return false;
    }
    if (zipFile) {
      return true;
    }
    return files.length >= 2;
  }, [activeEngines.length, files.length, hasMixedZipSelection, uploading, zipFile]);

  const uploadFormStorageKey = useMemo(
    () => `${UPLOAD_FORM_STORAGE_KEY}:${user?.tenant_id || 'no-tenant'}:${user?.id || 'guest'}`,
    [user?.id, user?.tenant_id],
  );

  useEffect(() => {
    let active = true;

    axios
      .get(`${API}/api/upload-settings`)
      .then((res) => {
        if (!active) {
          return;
        }
        const nextThreshold = Number(res.data?.default_threshold);
        setThreshold(Number.isFinite(nextThreshold) ? nextThreshold : 0.5);
        const nextEngineKeys = Array.isArray(res.data?.active_engine_keys)
          ? res.data.active_engine_keys
          : UPLOAD_ENGINE_OPTIONS.map((engine) => engine.key);
        setActiveEngines(nextEngineKeys);
      })
      .catch(() => {
        if (active) {
          setThreshold(0.5);
          setActiveEngines(UPLOAD_ENGINE_OPTIONS.map((engine) => engine.key));
        }
      })
      .finally(() => {
        if (active) {
          setThresholdLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (authLoading || typeof window === 'undefined') {
      return;
    }

    try {
      const raw = window.localStorage.getItem(uploadFormStorageKey);
      if (!raw) {
        return;
      }
      const parsed = JSON.parse(raw);
      if (typeof parsed.course_name === 'string') {
        setCourseName(parsed.course_name);
      }
      if (typeof parsed.assignment_name === 'string') {
        setAssignmentName(parsed.assignment_name);
      }
    } catch {
      // Ignore malformed saved form data.
    }
  }, [authLoading, uploadFormStorageKey]);

  useEffect(() => {
    if (authLoading || typeof window === 'undefined') {
      return;
    }

    window.localStorage.setItem(
      uploadFormStorageKey,
      JSON.stringify({
        course_name: courseName,
        assignment_name: assignmentName,
      }),
    );
  }, [assignmentName, authLoading, courseName, uploadFormStorageKey]);

  const handleDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const droppedFiles = Array.from(e.dataTransfer.files);
    if (!droppedFiles.length) {
      return;
    }
    setFiles(droppedFiles);
  }, []);

  const handleSubmit = async () => {
    setError('');
    if (hasMixedZipSelection) {
      setError('Upload either one ZIP archive or multiple submission files, not both together.');
      return;
    }
    if (activeEngines.length === 0) {
      setError('Select at least one engine for this assignment check.');
      return;
    }
    if (!zipFile && files.length < 2) {
      setError('Select at least 2 submissions');
      return;
    }

    setUploading(true);
    const formData = new FormData();

    if (zipFile) {
      formData.append('file', zipFile);
    } else {
      files.forEach((f) => formData.append('files', f));
    }
    formData.append('course_name', courseName || assignmentName || 'Assignment Check');
    formData.append('assignment_name', assignmentName || courseName || 'Assignment Check');
    formData.append('threshold', String(threshold));
    formData.append('engine_keys', JSON.stringify(activeEngines));

    try {
      const url = zipFile ? `${API}/api/upload-zip` : `${API}/api/upload`;
      const res = await axios.post(url, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const jobId = res.data?.job_id;
      const status = res.data?.status;

      if (!jobId) {
        setUploading(false);
        setError('Upload completed, but no job ID was returned.');
        return;
      }

      // The current backend completes analysis before responding, so we can
      // navigate straight to the results page without a follow-up poll.
      if (status === 'completed') {
        router.push(`/results/${jobId}`);
        return;
      }

      startPolling(jobId);
    } catch (err) {
      setUploading(false);
      setError(getApiErrorMessage(err, 'Upload failed'));
    }
  };

  const toggleEngine = useCallback((engineKey: string) => {
    setActiveEngines((current) =>
      current.includes(engineKey)
        ? current.filter((key) => key !== engineKey)
        : [...current, engineKey],
    );
  }, []);

  return (
    <DashboardLayout>
      <div className="p-4 lg:p-6">
        <div className="">
          {/* Header */}
          <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Check Assignment</h1>
              <p className="mt-1.5 text-slate-500">
                Upload the submissions for one assignment, run the similarity check, and open the result when it is ready.
              </p>
            </div>
            <button
              onClick={handleSubmit}
              disabled={!canRunCheck}
              className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white transition-all hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400"
            >
              {uploading ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  Running...
                </>
              ) : (
                <>
                  <Check size={16} />
                  Run Check
                </>
              )}
            </button>
          </div>

          <div className="theme-card rounded-2xl overflow-hidden">
            <div className="p-6">
              <div className="grid gap-4 lg:grid-cols-2 lg:items-stretch">
                {/* Drop Zone */}
                <div
                  onDrop={handleDrop}
                  onDragOver={(e) => e.preventDefault()}
                  className="border-2 border-dashed border-slate-200 rounded-xl p-12 text-center hover:border-blue-400 hover:bg-blue-50/30 transition-all duration-200 cursor-pointer group min-h-[260px] h-full flex flex-col items-center justify-center"
                  onClick={() => {
                    fileInputRef.current?.click();
                  }}
                >
                  <div className="w-14 h-14 rounded-2xl bg-slate-50 flex items-center justify-center mx-auto mb-4 group-hover:bg-blue-50 transition-colors">
                    <UploadIcon size={24} className="text-slate-400 group-hover:text-blue-500 transition-colors" />
                  </div>
                  <p className="text-sm font-semibold text-slate-700 mb-1">
                    Drop submission files or one ZIP archive here
                  </p>
                  <p className="text-xs text-slate-400">
                    Upload multiple code files, or one ZIP archive containing the submissions
                  </p>
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    accept=".zip,.py,.java,.c,.cpp,.h,.js,.ts,.go,.rs,.rb,.php,.cs,.kt,.swift"
                    className="hidden"
                    onChange={(e) => setFiles(Array.from(e.target.files || []))}
                  />
                </div>

                {/* File List */}
                <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-4 min-h-[260px] h-full flex flex-col">
                  <div className="mb-3 flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                      {files.length > 0
                        ? zipFile
                          ? 'Archive selected'
                          : `${selectedFiles.length} files selected`
                        : 'No files selected'}
                    </span>
                    {files.length > 0 ? (
                      <button
                        onClick={() => setFiles([])}
                        className="text-xs text-slate-400 hover:text-red-500 transition-colors"
                      >
                        Clear all
                      </button>
                    ) : null}
                  </div>

                  {files.length > 0 ? (
                    <div className="space-y-1.5 max-h-56 overflow-y-auto scrollbar-thin pr-1">
                      {zipFile ? (
                        <div className="flex items-center justify-between px-3 py-2.5 bg-slate-50 rounded-lg text-sm">
                          <div className="flex items-center gap-2 min-w-0 flex-1">
                            <div className="w-7 h-7 rounded-md bg-amber-50 flex items-center justify-center shrink-0">
                              <FolderArchive size={12} className="text-amber-600" />
                            </div>
                            <span className="font-medium text-slate-700 truncate">{zipFile.name}</span>
                          </div>
                          <span className="text-xs text-slate-400 ml-2">{(zipFile.size / 1024).toFixed(1)} KB</span>
                        </div>
                      ) : (
                        selectedFiles.map((f, i) => (
                          <div
                            key={i}
                            className="flex items-center justify-between px-3 py-2.5 bg-white rounded-lg text-sm group/file"
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
                      )}
                    </div>
                  ) : (
                    <div className="flex flex-1 flex-col items-center justify-center rounded-lg border border-dashed border-slate-200 bg-white text-center">
                      <div className="mb-2 rounded-full bg-slate-100 p-3 text-slate-400">
                        <FileUp size={18} />
                      </div>
                      <p className="text-sm font-medium text-slate-600">Selected files will appear here</p>
                      <p className="mt-1 text-xs text-slate-400">Choose multiple files or one ZIP archive to begin</p>
                    </div>
                  )}
                </div>
              </div>

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

              <div className="grid md:grid-cols-2 gap-4 mb-5">
                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                    Reference Label
                  </label>
                  <input
                    type="text"
                    value={courseName}
                    onChange={(e) => setCourseName(e.target.value)}
                    placeholder="Optional, e.g. Section A or Spring 2026"
                    className="w-full px-3.5 py-2.5 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 bg-white transition-all"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                    Assignment Name
                  </label>
                  <input
                    type="text"
                    value={assignmentName}
                    onChange={(e) => setAssignmentName(e.target.value)}
                    placeholder="e.g., Assignment 3 - Sorting"
                    className="w-full px-3.5 py-2.5 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 bg-white transition-all"
                  />
                </div>
              </div>

              <div className="mb-6 grid gap-4 lg:grid-cols-2">
                <div className="rounded-xl border border-slate-200 bg-white px-4 py-3">
                  <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Current Similarity Threshold
                  </div>
                  <span className="mt-2 inline-flex shrink-0 rounded-lg bg-blue-50 px-2.5 py-1 text-sm font-bold text-blue-600">
                    {thresholdLoading ? '...' : `${(threshold * 100).toFixed(0)}%`}
                  </span>
                  <div className="mt-2 text-sm text-slate-600">
                    {thresholdLoading
                      ? 'Loading current threshold...'
                      : 'This score decides when a result is flagged for review after the engines finish scoring it.'}
                  </div>
                </div>

                <div className="rounded-xl border border-slate-200 bg-white px-4 py-3">
                  <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Engines for This Check
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {thresholdLoading ? (
                      <span className="rounded-lg bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-400">
                        Loading...
                      </span>
                    ) : (
                      UPLOAD_ENGINE_OPTIONS.map((engine) => {
                        const active = activeEngines.includes(engine.key);
                        return (
                          <button
                            key={engine.key}
                            type="button"
                            onClick={() => toggleEngine(engine.key)}
                            className={`rounded-lg border px-2.5 py-1 text-xs font-medium transition ${active
                              ? 'border-blue-200 bg-blue-50 text-blue-700'
                              : 'border-slate-200 bg-slate-50 text-slate-500 hover:border-slate-300'
                              }`}
                          >
                            {engine.label}
                          </button>
                        );
                      })
                    )}
                  </div>
                  <div className="mt-2 text-sm text-slate-600">
                    {thresholdLoading
                      ? 'Loading current engines...'
                      : activeEngines.length > 0
                        ? 'Choose which engines should run for this assignment check.'
                        : 'Select at least one engine for this assignment check.'}
                  </div>
                </div>
                <p className="mt-3 text-xs text-slate-500">
                  Update these values from the{' '}
                  <Link href="/settings" className="font-semibold text-blue-600 hover:text-blue-700">
                    Settings page
                  </Link>
                  .
                </p>
              </div>

            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
