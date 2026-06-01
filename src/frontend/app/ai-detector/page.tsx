// @ts-nocheck
'use client';

import DashboardLayout from '@/components/DashboardLayout';
import axios from 'axios';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  AlertCircle,
  ArrowRight,
  Bot,
  CalendarClock,
  FileUp,
  Loader2,
  Shield,
  Upload,
  X,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

const API = '';

function formatSize(bytes) {
  return bytes < 1024 * 1024
    ? `${(bytes / 1024).toFixed(1)} KB`
    : `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function getTone(score) {
  if (score >= 0.7) return 'border-red-200 bg-red-50 text-red-700';
  if (score >= 0.45) return 'border-amber-200 bg-amber-50 text-amber-700';
  return 'border-emerald-200 bg-emerald-50 text-emerald-700';
}

function getApiErrorMessage(error) {
  return error?.response?.data?.error || error?.response?.data?.detail || error?.message || 'Analysis failed';
}

export default function AIDetectorPage() {
  const router = useRouter();
  const fileInputRef = useRef(null);
  const [files, setFiles] = useState([]);
  const [courseName, setCourseName] = useState('');
  const [assignmentName, setAssignmentName] = useState('');
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [history, setHistory] = useState([]);

  const loadHistory = async () => {
    try {
      const res = await axios.get(`${API}/api/jobs`);
      setHistory((res.data?.jobs || []).filter((job) => job.job_type === 'ai_detector').slice(0, 6));
    } catch {
      setHistory([]);
    }
  };

  useEffect(() => {
    loadHistory();
  }, []);

  const canRun = files.length > 0 && !uploading;

  const runDetection = async () => {
    if (!canRun) return;
    setUploading(true);
    setError('');
    const fd = new FormData();
    files.forEach((file) => fd.append('files', file));
    fd.append('course_name', courseName || 'Academic Integrity Review');
    fd.append('assignment_name', assignmentName || 'Code Similarity Assessment');

    try {
      const res = await axios.post(`${API}/api/ai-detect`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const jobId = res.data?.job_id;
      if (jobId) {
        router.push(`/ai-detector/results/${jobId}`);
        return;
      }
      await loadHistory();
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setUploading(false);
    }
  };

  return (
    <DashboardLayout requireAuth={false}>
      <div className="px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <div className="space-y-8">
          <section className="theme-card-strong rounded-[30px] overflow-hidden">
            <div className="theme-section-line px-6 py-5 lg:px-7">
              <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
                <div className="space-y-4">
                  <div className="inline-flex items-center gap-2 rounded-full border border-blue-600/10 bg-blue-600/[0.06] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--accent-blue)]">
                    <Shield size={13} />
                    Academic Integrity Assessment
                  </div>
                  <div>
                    <h1 className="font-display text-3xl font-semibold tracking-tight text-[var(--text-primary)] sm:text-4xl">
                      AI-Generated Code Review
                    </h1>
                    <p className="mt-3 max-w-3xl text-sm leading-7 text-[var(--text-secondary)]">
                      Upload student submissions for automated similarity and assistance analysis. 
                      Results include explainable signals: token entropy, code burstiness, stylometry, reasoning consistency, 
                      source verification, and structural patterns. Use scores as review indicators - not definitive proof.
                    </p>
                  </div>
                </div>
                <button
                  onClick={runDetection}
                  disabled={!canRun}
                  className="theme-button-primary inline-flex items-center gap-2 rounded-2xl px-6 py-4 text-base font-semibold transition hover:scale-105 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:scale-100"
                >
                  {uploading ? <><Loader2 size={16} className="animate-spin" />Analyzing...</> : <><Bot size={16} />Run Assessment<ArrowRight size={15} /></>}
                </button>
              </div>
            </div>
          </section>

          <section className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
              <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Course Identifier</label>
              <input
                value={courseName}
                onChange={(event) => setCourseName(event.target.value)}
                placeholder="e.g. CS 101 - Introduction to Programming"
                className="mt-2 h-11 w-full rounded-xl border border-slate-200 bg-slate-50 px-4 text-sm outline-none focus:border-blue-300 focus:ring-4 focus:ring-blue-50"
              />
            </div>
            <div className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
              <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Assignment Title</label>
              <input
                value={assignmentName}
                onChange={(event) => setAssignmentName(event.target.value)}
                placeholder="e.g. Programming Assignment 3"
                className="mt-2 h-11 w-full rounded-xl border border-slate-200 bg-slate-50 px-4 text-sm outline-none focus:border-blue-300 focus:ring-4 focus:ring-blue-50"
              />
            </div>
          </section>

          <section className="rounded-2xl bg-white shadow-sm ring-1 ring-slate-200">
            {files.length === 0 ? (
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="flex w-full flex-col items-center justify-center px-8 py-20 text-center"
              >
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-50 text-blue-600">
                  <Upload size={26} />
                </div>
                <div className="mt-5 text-base font-semibold text-slate-900">Upload student code submissions</div>
                <div className="mt-2 max-w-md text-sm leading-6 text-slate-500">
                  Accept source files (.py, .java, .cpp, etc.) or compressed archives for batch analysis.
                </div>
                <span className="mt-5 inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700">
                  <FileUp size={14} />
                  Select files
                </span>
              </button>
            ) : (
              <div className="p-5">
                <div className="flex items-center justify-between gap-4">
                  <div className="text-sm font-semibold text-slate-900">{files.length} submission{files.length === 1 ? '' : 's'} ready for review</div>
                  <div className="flex items-center gap-3">
                    <button type="button" onClick={() => fileInputRef.current?.click()} className="text-sm font-semibold text-blue-600">Add more</button>
                    <button type="button" onClick={() => setFiles([])} className="text-sm font-semibold text-slate-400">Clear</button>
                  </div>
                </div>
                <div className="mt-4 grid gap-2">
                  {files.map((file, index) => (
                    <div key={`${file.name}-${index}`} className="flex items-center gap-3 rounded-xl border border-slate-100 bg-slate-50 px-4 py-3">
                      <FileUp size={15} className="text-slate-400" />
                      <div className="min-w-0 flex-1 truncate text-sm font-medium text-slate-700">{file.name}</div>
                      <div className="text-xs text-slate-400">{formatSize(file.size)}</div>
                      <button type="button" onClick={() => setFiles(files.filter((_, i) => i !== index))} className="text-slate-300 hover:text-red-500">
                        <X size={14} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".zip,.py,.java,.c,.cpp,.h,.js,.ts,.go,.rs,.rb,.php,.cs,.kt,.swift"
              className="hidden"
              onChange={(event) => {
                const next = Array.from(event.target.files || []);
                if (next.length) setFiles(next);
              }}
            />
          </section>

          {error && (
            <section className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
              <AlertCircle size={16} className="mt-0.5 shrink-0" />
              <span>{error}</span>
            </section>
          )}

          <section className="rounded-2xl border border-slate-200 bg-slate-50 px-5 py-4 text-sm text-slate-600">
            <div className="font-semibold text-slate-700 mb-2">About AI Detection Signals</div>
<p className="leading-relaxed">
              The assessment analyzes multiple signals: token entropy, code burstiness, style profile, 
              reasoning consistency, source verification, and structural patterns. 
              Scores above 70% indicate elevated likelihood of assistance and warrant review, 
              but do not constitute proof of academic misconduct.
            </p>
          </section>

          <section className="rounded-2xl bg-white shadow-sm ring-1 ring-slate-200">
            <div className="flex items-center justify-between gap-4 border-b border-slate-100 px-5 py-4">
              <div>
                <div className="text-sm font-semibold text-slate-900">Assessment History</div>
                <div className="mt-1 text-xs text-slate-500">Previous analyses are retained for institutional review.</div>
              </div>
              <CalendarClock size={18} className="text-slate-400" />
            </div>
            {history.length === 0 ? (
              <div className="px-5 py-8 text-sm text-slate-500">No prior assessments recorded.</div>
            ) : (
              <div className="divide-y divide-slate-100">
                {history.map((job) => (
                  <Link
                    key={job.id}
                    href={`/ai-detector/results/${job.id}`}
                    className="grid gap-3 px-5 py-4 transition hover:bg-slate-50 md:grid-cols-[1fr_auto] md:items-center"
                  >
                    <div>
                      <div className="font-medium text-slate-900">{job.assignment_name || 'Code Similarity Assessment'}</div>
                      <div className="mt-1 text-xs text-slate-500">{job.course_name || 'Course'} · {job.file_count || 0} submission{job.file_count === 1 ? '' : 's'}</div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${getTone(job.summary?.highest_ai_probability || 0)}`}>
                        {Math.round((job.summary?.highest_ai_probability || 0) * 100)}% highest risk
                      </span>
                      <ArrowRight size={16} className="text-slate-400" />
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </section>
        </div>
      </div>
    </DashboardLayout>
  );
}
