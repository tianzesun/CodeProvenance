// @ts-nocheck — TODO: add proper types (tracked in types/api.ts)
'use client';
import DashboardLayout from '@/components/DashboardLayout';
import { useAuth } from '@/components/AuthProvider';
import { ErrorState, PageHeader } from '@/components/saas/SaaSPrimitives';
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
  Info,
  Loader2,
  Search,
  Upload,
  X,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

// ── Helpers ────────────────────────────────────────────────────────────────

const REFERENCE_HEADERS = ['x-correlation-id', 'x-request-id'];

/** Generic, status-keyed text; the server's own wording is not shown. A correlation id is appended when sent. */
function describeError(error, fallback) {
  const status = typeof error?.response?.status === 'number' ? error.response.status : undefined;
  const headers = error?.response?.headers || {};
  const reference = REFERENCE_HEADERS.map((name) => headers[name]).find((v) => typeof v === 'string' && v);

  let message = fallback;
  if (status === 401) message = 'Your session has expired. Please sign in again.';
  else if (status === 403) message = 'You don’t have permission to do that.';
  else if (status === 413) message = 'The upload is too large. Remove some files or upload a smaller archive.';
  else if (status === 400 || status === 415 || status === 422) message = 'The files couldn’t be analysed. Check that they are readable source files and try again.';
  else if (status === 429) message = 'Too many requests. Please wait a moment and try again.';
  else if (status !== undefined && status >= 500) message = 'Something went wrong on our side. Please try again.';

  return reference ? `${message} (Reference: ${reference})` : message;
}

function isCanceled(err) {
  return err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED';
}

function formatSize(bytes) {
  return bytes < 1024 * 1024
    ? `${(bytes / 1024).toFixed(1)} KB`
    : `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function getTone(score) {
  if (score >= 0.7) return 'border-red-200 bg-red-50 text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300';
  if (score >= 0.45) return 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-300';
  return 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-300';
}

function formatDate(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat('en-US', { dateStyle: 'medium', timeStyle: 'short' }).format(date);
}

const PAGE_SIZES = [5, 10, 25];

// The file picker only hints at these types; dragged-in files bypass `accept`, so they are checked here.
const ALLOWED_EXTENSIONS = ['zip', 'py', 'java', 'c', 'cpp', 'h', 'js', 'ts', 'go', 'rs', 'rb', 'php', 'cs', 'kt', 'swift'];
const ACCEPT = ALLOWED_EXTENSIONS.map((ext) => `.${ext}`).join(',');
const MAX_FILE_BYTES = 5 * 1024 * 1024;

function fileExtension(name) {
  const dot = String(name || '').lastIndexOf('.');
  return dot === -1 ? '' : name.slice(dot + 1).toLowerCase();
}

function fileKey(file) {
  return `${file.name}:${file.size}:${file.lastModified}`;
}

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

// ── Page ───────────────────────────────────────────────────────────────────

export default function AIDetectorPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  // A guest demo session can run assessments but owns no workspace: no
  // courses to file one under, and no history to list (the workspace
  // listing endpoint denies guests by design).
  const isGuest = user?.role === 'guest';
  const fileInputRef = useRef(null);
  const uploadAbortRef = useRef(null);
  const dragDepth = useRef(0);
  const historyRequestRef = useRef(0);

  const [files, setFiles] = useState([]);
  const [fileNotice, setFileNotice] = useState('');
  const [isDragging, setIsDragging] = useState(false);
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
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState('');
  const [historyExpanded, setHistoryExpanded] = useState(false);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyPageSize, setHistoryPageSize] = useState(5);
  const [historyCourseId, setHistoryCourseId] = useState('');
  const [historyAssignmentId, setHistoryAssignmentId] = useState('');
  const [historyAssignments, setHistoryAssignments] = useState([]);

  const loadHistory = useCallback(async (signal) => {
    const requestId = ++historyRequestRef.current;
    setHistoryLoading(true);
    try {
      const res = await apiClient.get('/api/jobs', { signal });
      if (requestId !== historyRequestRef.current) return;
      const jobs = (Array.isArray(res.data?.jobs) ? res.data.jobs : []).filter((job) => job.job_type === 'ai_detector');
      // Newest first. The list came back in whatever order the API used, and carried no date.
      jobs.sort((a, b) => (new Date(b.created_at || 0).getTime() || 0) - (new Date(a.created_at || 0).getTime() || 0));
      setHistory(jobs);
      setHistoryError('');
    } catch (err) {
      if (signal?.aborted || requestId !== historyRequestRef.current) return;
      // A failed load used to set an empty list, which read as "No prior assessments recorded".
      setHistoryError(describeError(err, 'Couldn’t load your previous assessments.'));
    } finally {
      if (requestId === historyRequestRef.current) setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    // Wait for the session to resolve, then skip the workspace listing for
    // guests — /api/jobs answers 403 for them, so the call is pure noise.
    if (authLoading) return undefined;
    if (isGuest) {
      setHistoryLoading(false);
      return undefined;
    }
    const controller = new AbortController();
    loadHistory(controller.signal);
    return () => controller.abort();
  }, [authLoading, isGuest, loadHistory]);

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

  // Leaving the page cancels an upload that is still being sent.
  useEffect(() => () => uploadAbortRef.current?.abort(), []);

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

  // ── Files ──────────────────────────────────────────────────────────────────

  // Adds to the list. "Add more" used to replace it (`setFiles(next)`), so the earlier files were thrown away.
  // Duplicates are skipped, and unsupported or oversized files are dropped with a note.
  const addFiles = (incoming) => {
    const list = Array.from(incoming || []);
    if (list.length === 0) return;

    const seen = new Set(files.map(fileKey));
    const accepted = [];
    const skipped = [];
    for (const file of list) {
      if (!ALLOWED_EXTENSIONS.includes(fileExtension(file.name)) || file.size > MAX_FILE_BYTES) {
        skipped.push(file.name);
      } else if (!seen.has(fileKey(file))) {
        seen.add(fileKey(file));
        accepted.push(file);
      }
    }

    setFiles([...files, ...accepted]);
    setFileNotice(skipped.length
      ? `Skipped ${skipped.length} unsupported or oversized file${skipped.length === 1 ? '' : 's'} (${skipped.slice(0, 3).join(', ')}${skipped.length > 3 ? '…' : ''}). Files must be source code or a ZIP under ${Math.round(MAX_FILE_BYTES / 1024 / 1024)} MB.`
      : '');
    setError('');
  };

  const canRun = files.length > 0 && !uploading;

  const runDetection = async () => {
    if (!canRun) return;
    const controller = new AbortController();
    uploadAbortRef.current = controller;
    setUploading(true);
    setError('');

    const fd = new FormData();
    files.forEach((file) => fd.append('files', file));

    // Only add course/assignment if both are selected
    if (selectedCourseId && selectedAssignmentId) {
      const selectedCourse = courses.find((course) => course.id === selectedCourseId);
      const selectedAssignment = assignments.find((assignment) => assignment.id === selectedAssignmentId);

      if (selectedCourse && selectedAssignment) {
        fd.append('course_name', selectedCourse.name);
        fd.append('assignment_name', selectedAssignment.name);
        fd.append('assignment_id', selectedAssignment.id);
      }
    }

    try {
      // No manual Content-Type: the browser has to add the multipart boundary itself.
      const res = await apiClient.post('/api/ai-detect', fd, { signal: controller.signal });
      const jobId = res.data?.job_id;
      if (jobId) {
        router.push(`/ai-detector/results/${encodeURIComponent(jobId)}`);
        return;
      }
      // Success without a job id used to refresh the history and show nothing at all.
      setError('The analysis finished but returned no result to open. Check your assessment history, or try again.');
      await loadHistory();
    } catch (err) {
      if (isCanceled(err)) {
        setError('Upload cancelled.');
      } else {
        setError(describeError(err, 'The analysis failed. Please try again.'));
      }
    } finally {
      if (uploadAbortRef.current === controller) uploadAbortRef.current = null;
      setUploading(false);
    }
  };

  return (
    <DashboardLayout>
      <div className="theme-page-container space-y-6">
        <PageHeader
          eyebrow="AI Detector"
          eyebrowStyle="badge"
          title="AI-Generated Code Review"
          description="Upload student submissions for automated assistance analysis. Scores are review indicators, not proof."
          action={
            <div className="flex flex-wrap items-center gap-2">
              {uploading && (
                <button
                  type="button"
                  onClick={() => uploadAbortRef.current?.abort()}
                  className="inline-flex h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
                >
                  Cancel
                </button>
              )}
              <button
                type="button"
                onClick={runDetection}
                disabled={!canRun}
                className="inline-flex h-10 items-center gap-2 rounded-xl bg-blue-600 px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {uploading ? (
                  <>
                    <Loader2 size={16} className="animate-spin" aria-hidden="true" />
                    Analyzing...
                  </>
                ) : (
                  <>
                    <Bot size={16} aria-hidden="true" />
                    Run Assessment
                    <ArrowRight size={15} aria-hidden="true" />
                  </>
                )}
              </button>
            </div>
          }
        />

        <p
          role="note"
          className="flex items-start gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400"
        >
          <Info size={16} className="mt-0.5 shrink-0 text-slate-400 dark:text-slate-500" aria-hidden="true" />
          <span>
            AI-detection scores can be wrong in both directions, and they are least reliable for short submissions, simple
            exercises and writers who are still learning. Treat a high score as a reason to talk to the student, never as
            a finding on its own.
          </span>
        </p>

        {/* Course & Assignment — hidden for the guest demo: it owns no
            workspace, so there is nothing to associate an assessment with. */}
        {!isGuest && (
          <section className="rounded-[28px] border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
            <div className="border-b border-slate-200 px-5 py-4 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Course &amp; Assignment</h2>
                <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-100 px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
                  Optional
                </span>
              </div>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                Associate this assessment with a course and assignment for better organization (optional)
              </p>
            </div>
            <div className="p-5">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="ai-course" className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">Course</label>
                  <select
                    id="ai-course"
                    value={selectedCourseId}
                    onChange={(event) => { setSelectedCourseId(event.target.value); setSelectedAssignmentId(''); }}
                    disabled={coursesLoading}
                    className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-400 dark:border-slate-700 dark:bg-slate-950 dark:text-white dark:disabled:bg-slate-900 dark:disabled:text-slate-500"
                  >
                    <option value="">{coursesLoading ? 'Loading courses…' : coursesError ? 'Courses unavailable' : courses.length ? 'None (standalone assessment)' : 'No courses yet'}</option>
                    {courses.map((course) => <option key={course.id} value={course.id}>{course.code ? `${course.code} – ` : ''}{course.name}</option>)}
                  </select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="ai-assignment" className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">Assignment</label>
                  <select
                    id="ai-assignment"
                    value={selectedAssignmentId}
                    onChange={(event) => setSelectedAssignmentId(event.target.value)}
                    disabled={!selectedCourseId || assignmentsLoading}
                    className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-400 dark:border-slate-700 dark:bg-slate-950 dark:text-white dark:disabled:bg-slate-900 dark:disabled:text-slate-500"
                  >
                    <option value="">{!selectedCourseId ? 'None (choose course first if needed)' : assignmentsLoading ? 'Loading assignments…' : assignments.length ? 'None (unassociated)' : 'No assignments yet'}</option>
                    {assignments.map((assignment) => <option key={assignment.id} value={assignment.id}>{assignment.name}</option>)}
                  </select>
                </div>
              </div>
              {/* A course without an assignment was silently ignored; now it says so. */}
              {selectedCourseId && !selectedAssignmentId && !assignmentsLoading && (
                <p role="status" className="mt-3 flex items-start gap-2 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-300">
                  Choose an assignment as well to file this assessment under the course. With only a course selected it is saved as a standalone assessment.
                </p>
              )}
            </div>
          </section>
        )}

        <section
          onDragEnter={() => { dragDepth.current += 1; setIsDragging(true); }}
          onDragOver={(event) => event.preventDefault()}
          onDragLeave={() => {
            // dragleave also fires when crossing a child element, which made the highlight flicker.
            dragDepth.current = Math.max(0, dragDepth.current - 1);
            if (dragDepth.current === 0) setIsDragging(false);
          }}
          onDrop={(event) => {
            event.preventDefault();
            dragDepth.current = 0;
            setIsDragging(false);
            addFiles(event.dataTransfer.files);
          }}
          className={`rounded-[28px] border bg-white shadow-sm transition dark:bg-slate-950 ${isDragging ? 'border-blue-500 ring-2 ring-blue-500/40' : 'border-slate-200 dark:border-slate-800'}`}
        >
          {files.length === 0 ? (
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="flex w-full flex-col items-center justify-center px-8 py-20 text-center"
            >
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400">
                <Upload size={22} aria-hidden="true" />
              </div>
              <h3 className="mt-4 text-base font-semibold text-slate-900 dark:text-white">
                {isDragging ? 'Release to add files' : 'Upload student code submissions'}
              </h3>
              <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500 dark:text-slate-400">
                Accept source files (.py, .java, .cpp, etc.) or compressed archives for batch analysis. Drag files here or select them.
              </p>
              <span className="mt-5 inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200">
                <FileUp size={14} aria-hidden="true" />
                Select files
              </span>
            </button>
          ) : (
            <div className="p-5">
              <div className="flex items-center justify-between gap-4">
                <div className="text-sm font-semibold text-slate-900 dark:text-white">{files.length} submission{files.length === 1 ? '' : 's'} ready for review</div>
                <div className="flex items-center gap-3">
                  <button type="button" onClick={() => fileInputRef.current?.click()} className="text-sm font-semibold text-blue-600 hover:underline dark:text-blue-400">Add more</button>
                  <button type="button" onClick={() => { setFiles([]); setFileNotice(''); }} className="text-sm font-semibold text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200">Clear</button>
                </div>
              </div>
              <div className="mt-4 grid gap-2">
                {files.map((file, index) => (
                  <div key={`${fileKey(file)}-${index}`} className="flex items-center gap-3 rounded-xl border border-slate-100 bg-slate-50 px-4 py-3 dark:border-slate-800 dark:bg-slate-900">
                    <FileUp size={15} className="text-slate-400 dark:text-slate-500" aria-hidden="true" />
                    <div className="min-w-0 flex-1 truncate text-sm font-medium text-slate-700 dark:text-slate-300" title={file.name}>{file.name}</div>
                    <div className="text-xs text-slate-500 dark:text-slate-400">{formatSize(file.size)}</div>
                    <button type="button" onClick={() => setFiles(files.filter((_, i) => i !== index))} aria-label={`Remove ${file.name}`} className="text-slate-400 hover:text-red-500 dark:text-slate-500 dark:hover:text-red-400">
                      <X size={14} aria-hidden="true" />
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
            accept={ACCEPT}
            className="hidden"
            onChange={(event) => {
              addFiles(event.target.files);
              // Lets the same file be chosen again after it has been removed.
              event.target.value = '';
            }}
          />
        </section>
        {fileNotice && (
          <p role="status" className="flex items-start gap-2 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-300">
            <AlertCircle size={15} className="mt-0.5 shrink-0" aria-hidden="true" />
            {fileNotice}
          </p>
        )}
        {error && <ErrorState message={error} onRetry={() => runDetection()} />}

        {/* Assessment History — hidden for guests: the workspace listing
            they would read is denied to them, so it is always empty. */}
        {!isGuest && (
          <section className="overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
              <button
                type="button"
                onClick={() => setHistoryExpanded((expanded) => !expanded)}
                aria-expanded={historyExpanded}
                className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left transition hover:bg-slate-50 dark:hover:bg-slate-900"
              >
                <span className="min-w-0">
                  <span className="block">Assessment History</span>
                  <span className="mt-1 block text-xs font-normal text-slate-500 dark:text-slate-400">
                    {historyExpanded
                      ? 'Previous analyses retained for institutional review.'
                      : historyLoading
                        ? 'Loading previous assessments…'
                        : historyError
                          ? 'Previous assessments couldn’t be loaded — click to retry'
                          : `${history.length} previous assessment${history.length === 1 ? '' : 's'} — click to view`}
                  </span>
                </span>
                <span className="flex items-center gap-2 text-slate-400 dark:text-slate-500">
                  <CalendarClock size={18} aria-hidden="true" />
                  <ChevronDown size={16} aria-hidden="true" className={`transition-transform ${historyExpanded ? 'rotate-180' : ''}`} />
                </span>
              </button>
            </h2>
            {historyExpanded && (
              <div className="border-t border-slate-100 dark:border-slate-800">
                {historyError ? (
                  <div role="alert" className="mx-4 my-4 flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300">
                    <AlertCircle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
                    <span className="flex-1">{historyError}</span>
                    <button type="button" onClick={() => loadHistory()} className="font-semibold underline underline-offset-2">Retry</button>
                  </div>
                ) : historyLoading ? (
                  <div role="status" aria-label="Loading previous assessments" className="px-5 py-6">
                    <div className="space-y-3" aria-hidden="true">
                      <div className="h-4 w-44 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
                      <div className="h-3 w-64 max-w-full animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
                      <div className="h-4 w-36 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
                      <div className="h-3 w-52 max-w-full animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
                    </div>
                  </div>
                ) : history.length === 0 ? (
                  <div className="px-5 py-16 text-center">
                    <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-slate-100 text-slate-500 dark:bg-slate-900 dark:text-slate-400">
                      <CalendarClock size={22} aria-hidden="true" />
                    </div>
                    <h3 className="mt-4 text-base font-semibold text-slate-900 dark:text-white">No prior assessments recorded</h3>
                    <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500 dark:text-slate-400">
                      Assessments you run appear here with their highest AI score and a link to the full report.
                    </p>
                  </div>
                ) : (
                  <>
                    <div className="grid gap-3 border-b border-slate-100 bg-slate-50/70 p-4 sm:grid-cols-2 dark:border-slate-800 dark:bg-slate-900/60">
                      <label className="flex flex-col gap-1.5 text-xs font-medium text-slate-500 dark:text-slate-400">
                        Filter by course
                        <select
                          value={historyCourseId}
                          onChange={(event) => {
                            setHistoryCourseId(event.target.value);
                            setHistoryAssignmentId('');
                            setHistoryPage(1);
                          }}
                          className="h-9 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white"
                        >
                          <option value="">All courses</option>
                          {courses.map((course) => (
                            <option key={course.id} value={course.id}>
                              {course.code ? `${course.code} – ` : ''}{course.name}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="flex flex-col gap-1.5 text-xs font-medium text-slate-500 dark:text-slate-400">
                        Filter by assignment
                        <select
                          value={historyAssignmentId}
                          onChange={(event) => {
                            setHistoryAssignmentId(event.target.value);
                            setHistoryPage(1);
                          }}
                          disabled={!historyCourseId}
                          className="h-9 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 disabled:cursor-not-allowed disabled:text-slate-400 dark:border-slate-800 dark:bg-slate-900 dark:text-white dark:disabled:text-slate-500"
                        >
                          <option value="">{historyCourseId ? 'All assignments' : 'Choose a course first…'}</option>
                          {historyAssignments.map((assignment) => (
                            <option key={assignment.id} value={assignment.id}>{assignment.name}</option>
                          ))}
                        </select>
                      </label>
                    </div>
                    {filteredHistory.length === 0 ? (
                      <div className="px-5 py-16 text-center">
                        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-slate-100 text-slate-500 dark:bg-slate-900 dark:text-slate-400">
                          <Search size={22} aria-hidden="true" />
                        </div>
                        <h3 className="mt-4 text-base font-semibold text-slate-900 dark:text-white">No assessments match these filters</h3>
                        <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500 dark:text-slate-400">
                          Try a different course or assignment filter to widen the results.
                        </p>
                      </div>
                    ) : (
                      <>
                        <ul className="divide-y divide-slate-100 dark:divide-slate-800">
                          {paginatedHistory.map((job) => {
                            const score = Number(job.summary?.highest_ai_probability) || 0;
                            const when = formatDate(job.created_at);
                            return (
                              <li key={job.id}>
                                <Link
                                  href={`/ai-detector/results/${encodeURIComponent(job.id)}`}
                                  className="grid gap-3 px-5 py-4 transition hover:bg-slate-50 dark:hover:bg-slate-900 md:grid-cols-[1fr_auto] md:items-center"
                                >
                                  <div>
                                    <div className="font-medium text-slate-900 dark:text-white">{job.assignment_name || 'AI-Generated Code Analysis Report'}</div>
                                    {/* "Course" was shown for a standalone assessment, which read like a course name. */}
                                    <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                                      {job.course_name || 'Standalone assessment'}
                                      {when ? ` · ${when}` : ''}
                                    </div>
                                  </div>
                                  <div className="flex items-center gap-3">
                                    {/* A detection score isn't a misconduct risk, so the chip no longer says "risk". */}
                                    <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${getTone(score)}`}>
                                      {Math.round(score * 100)}% highest AI score
                                    </span>
                                    <ArrowRight size={16} className="text-slate-400 dark:text-slate-500" aria-hidden="true" />
                                  </div>
                                </Link>
                              </li>
                            );
                          })}
                        </ul>
                        {totalHistoryPages > 1 && (
                          <div className="flex flex-col gap-3 border-t border-slate-100 px-5 py-3 sm:flex-row sm:items-center sm:justify-between dark:border-slate-800">
                            <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                              <label htmlFor="ai-history-page-size">Rows per page</label>
                              <select
                                id="ai-history-page-size"
                                value={historyPageSize}
                                onChange={(event) => {
                                  setHistoryPageSize(Number(event.target.value));
                                  setHistoryPage(1);
                                }}
                                className="h-8 w-auto rounded-xl border border-slate-200 bg-white px-2.5 text-xs text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white"
                              >
                                {PAGE_SIZES.map((size) => <option key={size} value={size}>{size}</option>)}
                              </select>
                              <span className="ml-2 text-xs text-slate-500 dark:text-slate-400">Page {safeHistoryPage} of {totalHistoryPages}</span>
                            </div>
                            <nav aria-label="Pagination" className="flex items-center gap-1">
                              <button
                                type="button"
                                disabled={safeHistoryPage <= 1}
                                // Based on the visible page: after the list shrank, the stored page could exceed it
                                // and "Previous" appeared to do nothing.
                                onClick={() => setHistoryPage(Math.max(1, safeHistoryPage - 1))}
                                aria-label="Previous page"
                                className="theme-icon-button"
                              >
                                <ChevronLeft size={15} aria-hidden="true" />
                              </button>
                              {historyPageNumbers.map((num, i) => num === '…' ? (
                                <span key={`gap-${i}`} className="px-1 text-xs text-slate-400 dark:text-slate-500" aria-hidden="true">…</span>
                              ) : (
                                <button
                                  key={num}
                                  type="button"
                                  onClick={() => setHistoryPage(Number(num))}
                                  aria-label={`Page ${num}`}
                                  aria-current={safeHistoryPage === num ? 'page' : undefined}
                                  className={`inline-flex h-8 w-8 items-center justify-center rounded-lg text-xs font-semibold transition ${safeHistoryPage === num ? 'bg-blue-600 text-white shadow-sm shadow-blue-500/25' : 'border border-slate-200 text-slate-600 hover:bg-slate-50 dark:border-slate-800 dark:text-slate-300 dark:hover:bg-slate-900'}`}
                                >
                                  {num}
                                </button>
                              ))}
                              <button
                                type="button"
                                disabled={safeHistoryPage >= totalHistoryPages}
                                onClick={() => setHistoryPage(Math.min(totalHistoryPages, safeHistoryPage + 1))}
                                aria-label="Next page"
                                className="theme-icon-button"
                              >
                                <ChevronRight size={15} aria-hidden="true" />
                              </button>
                            </nav>
                          </div>
                        )}
                      </>
                    )}
                  </>
                )}
              </div>
            )}
          </section>
        )}
      </div>
    </DashboardLayout>
  );
}
