// @ts-nocheck — TODO: add proper types (tracked in types/api.ts)
'use client';
import DashboardLayout from '@/components/DashboardLayout';
import { ErrorState } from '@/components/saas/SaaSPrimitives';
import { apiClient } from '@/lib/apiClient';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  AlertCircle,
  ArrowRight,
  Bot,
  CalendarClock,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  FileUp,
  Loader2,
  Shield,
  Upload,
  X,
} from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
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
const PAGE_SIZES = [5, 10, 25];
function buildPageNumbers(current, total) {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }
  const pages = [1];
  const start = Math.max(2, current - 1);
  const end = Math.min(total - 1, current + 1);
  if (start > 2) pages.push('…');
  for (let i = start; i <= end; i += 1) pages.push(i);
  if (end < total - 1) pages.push('…');
  pages.push(total);
  return pages;
}
export default function AIDetectorPage() {
  const router = useRouter();
  const fileInputRef = useRef(null);
  const [files, setFiles] = useState([]);
  const [courses, setCourses] = useState([]);
  const [coursesLoading, setCoursesLoading] = useState(true);
  const [coursesError, setCoursesError] = useState(false);
  const [selectedCourseId, setSelectedCourseId] = useState('');
  const [assignments, setAssignments] = useState([]);
  const [assignmentsLoading, setAssignmentsLoading] = useState(false);
  const [selectedAssignmentId, setSelectedAssignmentId] = useState('');
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [history, setHistory] = useState([]);
  const [historyExpanded, setHistoryExpanded] = useState(false);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyPageSize, setHistoryPageSize] = useState(5);
  const [historyCourseId, setHistoryCourseId] = useState('');
  const [historyAssignmentId, setHistoryAssignmentId] = useState('');
  const [historyAssignments, setHistoryAssignments] = useState([]);
  const loadHistory = async () => {
    try {
      const res = await apiClient.get('/api/jobs');
      setHistory((res.data?.jobs || []).filter((job) => job.job_type === 'ai_detector'));
    } catch {
      setHistory([]);
    }
  };
  useEffect(() => {
    loadHistory();
  }, []);
  useEffect(() => {
    let active = true;
    apiClient.get('/api/courses')
      .then((res) => {
        if (active) setCourses(Array.isArray(res.data?.courses) ? res.data.courses : []);
      })
      .catch(() => {
        if (active) { setCourses([]); setCoursesError(true); }
      })
      .finally(() => {
        if (active) setCoursesLoading(false);
      });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    if (!selectedCourseId) {
      setAssignments([]);
      setSelectedAssignmentId('');
      return undefined;
    }
    let active = true;
    setAssignmentsLoading(true);
    apiClient.get('/api/assignments', { params: { course_id: selectedCourseId } })
      .then((res) => {
        if (active) setAssignments(Array.isArray(res.data?.assignments) ? res.data.assignments : []);
      })
      .catch(() => {
        if (active) setAssignments([]);
      })
      .finally(() => {
        if (active) setAssignmentsLoading(false);
      });
    return () => { active = false; };
  }, [selectedCourseId]);
  useEffect(() => {
    if (!historyCourseId) {
      setHistoryAssignments([]);
      setHistoryAssignmentId('');
      return undefined;
    }
    let active = true;
    apiClient.get('/api/assignments', { params: { course_id: historyCourseId } })
      .then((res) => {
        if (active) setHistoryAssignments(Array.isArray(res.data?.assignments) ? res.data.assignments : []);
      })
      .catch(() => {
        if (active) setHistoryAssignments([]);
      });
    return () => { active = false; };
  }, [historyCourseId]);
  const filteredHistory = useMemo(() => history.filter((job) => {
    if (historyCourseId && job.course_id !== historyCourseId) return false;
    if (historyAssignmentId && job.assignment_id !== historyAssignmentId) return false;
    return true;
  }), [history, historyCourseId, historyAssignmentId]);
  const totalHistoryPages = Math.max(1, Math.ceil(filteredHistory.length / historyPageSize));
  const safeHistoryPage = Math.min(historyPage, totalHistoryPages);
  const paginatedHistory = useMemo(() => {
    const start = (safeHistoryPage - 1) * historyPageSize;
    return filteredHistory.slice(start, start + historyPageSize);
  }, [filteredHistory, safeHistoryPage, historyPageSize]);
  const historyPageNumbers = useMemo(
    () => buildPageNumbers(safeHistoryPage, totalHistoryPages),
    [safeHistoryPage, totalHistoryPages]
  );
  const canRun = files.length > 0 && Boolean(selectedCourseId && selectedAssignmentId) && !uploading;
  const runDetection = async () => {
    if (!canRun) return;
    setUploading(true);
    setError('');
    const selectedCourse = courses.find((course) => course.id === selectedCourseId);
    const selectedAssignment = assignments.find((assignment) => assignment.id === selectedAssignmentId);
    if (!selectedCourse || !selectedAssignment) {
      setError('Select a course and assignment before running the assessment.');
      setUploading(false);
      return;
    }
    const fd = new FormData();
    files.forEach((file) => fd.append('files', file));
    fd.append('course_name', selectedCourse.name);
    fd.append('assignment_name', selectedAssignment.name);
    fd.append('assignment_id', selectedAssignment.id);
    try {
      const res = await apiClient.post('/api/ai-detect', fd, {
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
    <DashboardLayout>
      <div className="theme-page-container">
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
                      Upload student submissions for automated assistance analysis. Scores are review indicators, not proof.
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
          <section className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
            <div className="mb-4 text-sm font-semibold text-slate-800">Course &amp; Assignment</div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-1">
                <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Course</label>
                <select value={selectedCourseId} onChange={(event) => { setSelectedCourseId(event.target.value); setSelectedAssignmentId(''); }} disabled={coursesLoading} className="theme-field">
                  <option value="">{coursesLoading ? 'Loading courses…' : coursesError ? 'Courses unavailable' : courses.length ? 'Select course…' : 'No courses yet'}</option>
                  {courses.map((course) => <option key={course.id} value={course.id}>{course.code ? `${course.code} – ` : ''}{course.name}</option>)}
                </select>
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">Assignment</label>
                <select value={selectedAssignmentId} onChange={(event) => setSelectedAssignmentId(event.target.value)} disabled={!selectedCourseId || assignmentsLoading} className="theme-field disabled:text-slate-400">
                  <option value="">{!selectedCourseId ? 'Choose a course first…' : assignmentsLoading ? 'Loading assignments…' : assignments.length ? 'Select assignment…' : 'No assignments yet'}</option>
                  {assignments.map((assignment) => <option key={assignment.id} value={assignment.id}>{assignment.name}</option>)}
                </select>
              </div>
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
          {error && <ErrorState message={error} />}
          <section className="rounded-2xl bg-white shadow-sm ring-1 ring-slate-200">
            <button
              type="button"
              onClick={() => setHistoryExpanded((expanded) => !expanded)}
              aria-expanded={historyExpanded}
              className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left transition hover:bg-slate-50"
            >
              <div>
                <div className="text-sm font-semibold text-slate-900">Assessment History</div>
                <div className="mt-1 text-xs text-slate-500">
                  {historyExpanded
                    ? 'Previous analyses retained for institutional review.'
                    : `${history.length} previous assessment${history.length === 1 ? '' : 's'} — click to view`}
                </div>
              </div>
              <div className="flex items-center gap-2 text-slate-400">
                <CalendarClock size={18} />
                <ChevronDown size={16} className={`transition-transform ${historyExpanded ? 'rotate-180' : ''}`} />
              </div>
            </button>
            {historyExpanded && (
              <div className="border-t border-slate-100">
                {history.length === 0 ? (
                  <div className="px-5 py-8 text-sm text-slate-500">No prior assessments recorded.</div>
                ) : (
                  <>
                    <div className="grid gap-3 border-b border-slate-100 bg-slate-50/70 p-4 sm:grid-cols-2">
                      <label className="flex flex-col gap-1 text-xs font-medium text-slate-500">
                        Filter by course
                        <select
                          value={historyCourseId}
                          onChange={(event) => {
                            setHistoryCourseId(event.target.value);
                            setHistoryAssignmentId('');
                            setHistoryPage(1);
                          }}
                          className="theme-compact-field"
                        >
                          <option value="">All courses</option>
                          {courses.map((course) => (
                            <option key={course.id} value={course.id}>
                              {course.code ? `${course.code} – ` : ''}{course.name}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="flex flex-col gap-1 text-xs font-medium text-slate-500">
                        Filter by assignment
                        <select
                          value={historyAssignmentId}
                          onChange={(event) => {
                            setHistoryAssignmentId(event.target.value);
                            setHistoryPage(1);
                          }}
                          disabled={!historyCourseId}
                          className="theme-compact-field"
                        >
                          <option value="">{historyCourseId ? 'All assignments' : 'Choose a course first…'}</option>
                          {historyAssignments.map((assignment) => (
                            <option key={assignment.id} value={assignment.id}>{assignment.name}</option>
                          ))}
                        </select>
                      </label>
                    </div>
                    {filteredHistory.length === 0 ? (
                      <div className="px-5 py-8 text-sm text-slate-500">No assessments match these filters.</div>
                    ) : (
                      <>
                        <div className="divide-y divide-slate-100">
                          {paginatedHistory.map((job) => (
                            <Link
                              key={job.id}
                              href={`/ai-detector/results/${job.id}`}
                              className="grid gap-3 px-5 py-4 transition hover:bg-slate-50 md:grid-cols-[1fr_auto] md:items-center"
                            >
                              <div>
                                <div className="font-medium text-slate-900">{job.assignment_name || 'AI-Generated Code Analysis Report'}</div>
                                <div className="mt-1 text-xs text-slate-500">{job.course_name || 'Course'}</div>
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
                        {totalHistoryPages > 1 && (
                          <div className="flex flex-col gap-3 border-t border-slate-100 px-5 py-3 sm:flex-row sm:items-center sm:justify-between">
                            <div className="flex items-center gap-2 text-xs text-slate-500">
                              <span>Rows per page</span>
                              <select
                                value={historyPageSize}
                                onChange={(event) => {
                                  setHistoryPageSize(Number(event.target.value));
                                  setHistoryPage(1);
                                }}
                                className="theme-compact-field h-8 w-auto"
                              >
                                {PAGE_SIZES.map((size) => <option key={size} value={size}>{size}</option>)}
                              </select>
                              <span className="ml-2 text-xs text-slate-500">Page {safeHistoryPage} of {totalHistoryPages}</span>
                            </div>
                            <div className="flex items-center gap-1">
                              <button
                                type="button"
                                disabled={safeHistoryPage <= 1}
                                onClick={() => setHistoryPage((p) => Math.max(1, p - 1))}
                                aria-label="Previous page"
                                className="theme-icon-button"
                              >
                                <ChevronLeft size={15} />
                              </button>
                              {historyPageNumbers.map((num, i) => num === '…' ? (
                                <span key={`gap-${i}`} className="px-1 text-xs text-slate-400">…</span>
                              ) : (
                                <button
                                  key={num}
                                  type="button"
                                  onClick={() => setHistoryPage(Number(num))}
                                  className={`inline-flex h-8 w-8 items-center justify-center rounded-md text-xs font-semibold transition ${safeHistoryPage === num ? 'bg-slate-900 text-white' : 'border border-slate-200 text-slate-600 hover:bg-slate-50'}`}
                                >
                                  {num}
                                </button>
                              ))}
                              <button
                                type="button"
                                disabled={safeHistoryPage >= totalHistoryPages}
                                onClick={() => setHistoryPage((p) => Math.min(totalHistoryPages, p + 1))}
                                aria-label="Next page"
                                className="theme-icon-button"
                              >
                                <ChevronRight size={15} />
                              </button>
                            </div>
                          </div>
                        )}
                      </>
                    )}
                  </>
                )}
              </div>
            )}
          </section>

         </div>
       </div>
    </DashboardLayout>
  );
}
