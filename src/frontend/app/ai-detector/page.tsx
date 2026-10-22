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
  FileArchive,
  FileCode,
  Info,
  Loader2,
  Plus,
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
  else if (status === 400 || status === 415 || status === 422) message = 'The files couldn’t be analyzed. Check that they are readable source files and try again.';
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

// Same thresholds as getTone, so the little meter and the chip always agree.
function getBarColor(score) {
  if (score >= 0.7) return 'bg-red-500';
  if (score >= 0.45) return 'bg-amber-500';
  return 'bg-emerald-500';
}

function formatDate(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat('en-CA', { dateStyle: 'medium', timeStyle: 'short' }).format(date);
}

const PAGE_SIZES = [5, 10, 25];

// The file picker only hints at these types; dragged-in files bypass `accept`, so they are checked here.
const ALLOWED_EXTENSIONS = ['zip', 'py', 'java', 'c', 'cpp', 'h', 'js', 'ts', 'go', 'rs', 'rb', 'php', 'cs', 'kt', 'swift'];
const ACCEPT = ALLOWED_EXTENSIONS.map((ext) => `.${ext}`).join(',');
const MAX_FILE_BYTES = 5 * 1024 * 1024;

const FILE_TYPE_LABELS = {
  zip: 'ZIP archive',
  py: 'Python',
  java: 'Java',
  c: 'C',
  cpp: 'C++',
  h: 'C/C++ header',
  js: 'JavaScript',
  ts: 'TypeScript',
  go: 'Go',
  rs: 'Rust',
  rb: 'Ruby',
  php: 'PHP',
  cs: 'C#',
  kt: 'Kotlin',
  swift: 'Swift',
};

function fileExtension(name) {
  const dot = String(name || '').lastIndexOf('.');
  return dot === -1 ? '' : name.slice(dot + 1).toLowerCase();
}

function fileKey(file) {
  return `${file.name}:${file.size}:${file.lastModified}`;
}

// Only react to drags that carry files. Dragging selected text over the page used to light up the dropzone.
function hasFiles(event) {
  return Array.from(event.dataTransfer?.types || []).includes('Files');
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

const CARD = 'rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950';
const FOCUS = 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40';
const SELECT_CLASS = 'h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-400 dark:border-slate-700 dark:bg-slate-950 dark:text-white dark:disabled:bg-slate-900 dark:disabled:text-slate-500';
const FILTER_SELECT_CLASS = SELECT_CLASS.replace('h-10', 'h-9');
const SECONDARY_BUTTON = `inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800 ${FOCUS}`;

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
  // The list is locked while an upload is being sent, so what was sent is what is on screen.
  const addFiles = (incoming) => {
    if (uploading) return;
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
  const totalBytes = files.reduce((sum, file) => sum + file.size, 0);
  const pickFiles = () => fileInputRef.current?.click();

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
        />

        {/* Files on the left, the action on the right: the Run button used to sit in the page header,
            far from the files it acts on. On narrow screens the card simply follows the files. */}
        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_21rem]">
          <div className="min-w-0 space-y-4">
            <section
              onDragEnter={(event) => {
                if (uploading || !hasFiles(event)) return;
                dragDepth.current += 1;
                setIsDragging(true);
              }}
              onDragOver={(event) => {
                // Always stop the browser from opening a dropped file in this tab: that would lose the upload.
                if (hasFiles(event)) event.preventDefault();
              }}
              onDragLeave={(event) => {
                if (uploading || !hasFiles(event)) return;
                // dragleave also fires when crossing a child element, which made the highlight flicker.
                dragDepth.current = Math.max(0, dragDepth.current - 1);
                if (dragDepth.current === 0) setIsDragging(false);
              }}
              onDrop={(event) => {
                if (!hasFiles(event)) return;
                event.preventDefault();
                dragDepth.current = 0;
                setIsDragging(false);
                addFiles(event.dataTransfer.files);
              }}
              className={`relative transition ${CARD} ${isDragging ? '!border-blue-500 ring-2 ring-blue-500/30' : ''}`}
            >
              {files.length === 0 ? (
                <div className="p-3">
                  <button
                    type="button"
                    onClick={pickFiles}
                    className={`flex w-full flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-24 text-center transition hover:border-blue-400 hover:bg-blue-50/50 dark:hover:border-blue-500/60 dark:hover:bg-blue-500/5 ${FOCUS} ${isDragging ? 'border-blue-500 bg-blue-50/60 dark:bg-blue-500/10' : 'border-slate-300 dark:border-slate-700'}`}
                  >
                    <span className="flex h-12 w-12 items-center justify-center rounded-full bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400">
                      <Upload size={22} aria-hidden="true" />
                    </span>
                    <span className="mt-4 text-base font-semibold text-slate-900 dark:text-white">
                      {isDragging ? 'Release to add files' : 'Drop student submissions here'}
                    </span>
                    <span className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                      or <span className="font-semibold text-blue-600 dark:text-blue-400">choose files</span> from your computer
                    </span>
                    <span className="mx-auto mt-5 max-w-md text-xs leading-5 text-slate-500 dark:text-slate-400">
                      Python, Java, C and C++, JavaScript, TypeScript, Go, Rust, Ruby, PHP, C#, Kotlin, Swift, or a ZIP archive for batch analysis.
                      Up to {Math.round(MAX_FILE_BYTES / 1024 / 1024)} MB per file.
                    </span>
                  </button>
                </div>
              ) : (
                <div>
                  <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-4 dark:border-slate-800">
                    <div>
                      <h2 className="text-base font-semibold text-slate-900 dark:text-white">
                        {files.length} submission{files.length === 1 ? '' : 's'} ready for review
                      </h2>
                      <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{formatSize(totalBytes)} in total</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <button type="button" onClick={pickFiles} disabled={uploading} className={SECONDARY_BUTTON}>
                        <Plus size={14} aria-hidden="true" />
                        Add more
                      </button>
                      <button
                        type="button"
                        onClick={() => { setFiles([]); setFileNotice(''); }}
                        disabled={uploading}
                        className={`rounded-xl px-3 py-2 text-sm font-semibold text-slate-500 transition hover:bg-slate-100 hover:text-slate-700 disabled:cursor-not-allowed disabled:opacity-50 dark:text-slate-400 dark:hover:bg-slate-900 dark:hover:text-slate-200 ${FOCUS}`}
                      >
                        Clear all
                      </button>
                    </div>
                  </div>
                  <ul aria-label="Selected files" className="max-h-[22rem] divide-y divide-slate-100 overflow-y-auto dark:divide-slate-800">
                    {files.map((file, index) => {
                      const ext = fileExtension(file.name);
                      return (
                        <li key={`${fileKey(file)}-${index}`} className="flex items-center gap-3 px-5 py-2.5">
                          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-500 dark:bg-slate-900 dark:text-slate-400">
                            {ext === 'zip' ? <FileArchive size={16} aria-hidden="true" /> : <FileCode size={16} aria-hidden="true" />}
                          </span>
                          <div className="min-w-0 flex-1">
                            <div className="truncate text-sm font-medium text-slate-800 dark:text-slate-200" title={file.name}>{file.name}</div>
                            <div className="text-xs text-slate-500 dark:text-slate-400">{FILE_TYPE_LABELS[ext] || 'Source file'}</div>
                          </div>
                          <div className="shrink-0 text-xs tabular-nums text-slate-500 dark:text-slate-400">{formatSize(file.size)}</div>
                          <button
                            type="button"
                            onClick={() => setFiles(files.filter((_, i) => i !== index))}
                            disabled={uploading}
                            aria-label={`Remove ${file.name}`}
                            className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-slate-400 transition hover:bg-red-50 hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-40 dark:text-slate-500 dark:hover:bg-red-500/10 dark:hover:text-red-400 ${FOCUS}`}
                          >
                            <X size={15} aria-hidden="true" />
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                  {isDragging && (
                    <div aria-hidden="true" className="pointer-events-none absolute inset-0 flex items-center justify-center rounded-2xl bg-blue-50/90 text-sm font-semibold text-blue-700 dark:bg-blue-950/80 dark:text-blue-200">
                      Release to add files
                    </div>
                  )}
                </div>
              )}
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept={ACCEPT}
                disabled={uploading}
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
          </div>

          <aside className="space-y-4 lg:sticky lg:top-6">
            <section aria-busy={uploading} className={`p-5 ${CARD}`}>
              <h2 className="text-base font-semibold text-slate-900 dark:text-white">Run assessment</h2>
              {/* The file list already shows the count and total size, so only the empty state needs a line here. */}
              {files.length === 0 && (
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Add at least one submission to begin.</p>
              )}

              {/* Hidden for the guest demo: it owns no workspace, so there is nothing to associate an assessment with. */}
              {!isGuest && (
                <fieldset disabled={uploading} className="mt-5 space-y-4 border-t border-slate-100 pt-5 dark:border-slate-800">
                  <legend className="sr-only">Course and assignment</legend>
                  <p className="text-sm font-semibold text-slate-900 dark:text-white">
                    File under a course <span className="font-normal text-slate-500 dark:text-slate-400">(optional)</span>
                  </p>
                  <div className="flex flex-col gap-1.5">
                    <label htmlFor="ai-course" className="text-sm font-medium text-slate-700 dark:text-slate-200">Course</label>
                    <select
                      id="ai-course"
                      value={selectedCourseId}
                      onChange={(event) => { setSelectedCourseId(event.target.value); setSelectedAssignmentId(''); }}
                      disabled={coursesLoading}
                      className={SELECT_CLASS}
                    >
                      <option value="">{coursesLoading ? 'Loading courses…' : coursesError ? 'Courses unavailable' : courses.length ? 'None (standalone assessment)' : 'No courses yet'}</option>
                      {courses.map((course) => <option key={course.id} value={course.id}>{course.code ? `${course.code} – ` : ''}{course.name}</option>)}
                    </select>
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label htmlFor="ai-assignment" className="text-sm font-medium text-slate-700 dark:text-slate-200">Assignment</label>
                    <select
                      id="ai-assignment"
                      value={selectedAssignmentId}
                      onChange={(event) => setSelectedAssignmentId(event.target.value)}
                      disabled={!selectedCourseId || assignmentsLoading}
                      className={SELECT_CLASS}
                    >
                      <option value="">{!selectedCourseId ? 'Choose a course first' : assignmentsLoading ? 'Loading assignments…' : assignments.length ? 'None (unassociated)' : 'No assignments yet'}</option>
                      {assignments.map((assignment) => <option key={assignment.id} value={assignment.id}>{assignment.name}</option>)}
                    </select>
                  </div>
                  {/* A course without an assignment was silently ignored; now it says so. */}
                  {selectedCourseId && !selectedAssignmentId && !assignmentsLoading && (
                    <p role="status" className="text-xs leading-5 text-amber-700 dark:text-amber-300">
                      Choose an assignment as well to file this assessment under the course. With only a course selected it is saved as a standalone assessment.
                    </p>
                  )}
                </fieldset>
              )}

              <button
                type="button"
                onClick={runDetection}
                disabled={!canRun}
                className={`mt-5 inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50 ${FOCUS}`}
              >
                {uploading ? (
                  <>
                    <Loader2 size={16} className="animate-spin" aria-hidden="true" />
                    Analyzing…
                  </>
                ) : (
                  <>
                    <Bot size={16} aria-hidden="true" />
                    Run assessment
                  </>
                )}
              </button>
              {uploading && (
                <>
                  <button type="button" onClick={() => uploadAbortRef.current?.abort()} className={`mt-2 w-full ${SECONDARY_BUTTON}`}>
                    Cancel upload
                  </button>
                  <p role="status" className="mt-3 text-xs leading-5 text-slate-500 dark:text-slate-400">
                    Uploading and analyzing. Keep this page open: leaving it cancels the upload.
                  </p>
                </>
              )}
            </section>

            {error && <ErrorState message={error} onRetry={() => runDetection()} />}

            <p
              role="note"
              className="flex items-start gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs leading-5 text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400"
            >
              <Info size={15} className="mt-0.5 shrink-0 text-slate-400 dark:text-slate-500" aria-hidden="true" />
              <span>
                AI-detection scores can be wrong in both directions, and they are least reliable for short submissions, simple
                exercises and writers who are still learning. Treat a high score as a reason to talk to the student, never as
                a finding on its own.
              </span>
            </p>
          </aside>
        </div>

        {/* Assessment History — hidden for guests: the workspace listing
            they would read is denied to them, so it is always empty. */}
        {!isGuest && (
          <section className={`overflow-hidden ${CARD}`}>
            <h2 className="text-base font-semibold text-slate-900 dark:text-white">
              <button
                type="button"
                onClick={() => setHistoryExpanded((expanded) => !expanded)}
                aria-expanded={historyExpanded}
                className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-500/40 dark:hover:bg-slate-900"
              >
                <span className="flex min-w-0 items-center gap-3">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-500 dark:bg-slate-900 dark:text-slate-400">
                    <CalendarClock size={18} aria-hidden="true" />
                  </span>
                  <span className="min-w-0">
                    <span className="block">Assessment history</span>
                    <span className="mt-0.5 block text-xs font-normal text-slate-500 dark:text-slate-400">
                      {historyExpanded
                        ? 'Previous analyses retained for institutional review.'
                        : historyLoading
                          ? 'Loading previous assessments…'
                          : historyError
                            ? 'Previous assessments couldn’t be loaded. Open to retry.'
                            : `${history.length} previous assessment${history.length === 1 ? '' : 's'}. Open to view.`}
                    </span>
                  </span>
                </span>
                <ChevronDown size={18} aria-hidden="true" className={`shrink-0 text-slate-400 transition-transform motion-reduce:transition-none dark:text-slate-500 ${historyExpanded ? 'rotate-180' : ''}`} />
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
                  <div role="status" aria-label="Loading previous assessments" className="divide-y divide-slate-100 dark:divide-slate-800">
                    {[0, 1, 2].map((row) => (
                      <div key={row} aria-hidden="true" className="flex items-center justify-between gap-4 px-5 py-4">
                        <div className="space-y-2">
                          <div className="h-4 w-44 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
                          <div className="h-3 w-28 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
                        </div>
                        <div className="h-6 w-36 animate-pulse rounded-full bg-slate-200 dark:bg-slate-800" />
                      </div>
                    ))}
                  </div>
                ) : history.length === 0 ? (
                  <div className="px-5 py-14 text-center">
                    <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-500 dark:bg-slate-900 dark:text-slate-400">
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
                      <label className="flex flex-col gap-1.5 text-xs font-medium text-slate-600 dark:text-slate-300">
                        Filter by course
                        <select
                          value={historyCourseId}
                          onChange={(event) => {
                            setHistoryCourseId(event.target.value);
                            setHistoryAssignmentId('');
                            setHistoryPage(1);
                          }}
                          className={FILTER_SELECT_CLASS}
                        >
                          <option value="">All courses</option>
                          {courses.map((course) => (
                            <option key={course.id} value={course.id}>
                              {course.code ? `${course.code} – ` : ''}{course.name}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="flex flex-col gap-1.5 text-xs font-medium text-slate-600 dark:text-slate-300">
                        Filter by assignment
                        <select
                          value={historyAssignmentId}
                          onChange={(event) => {
                            setHistoryAssignmentId(event.target.value);
                            setHistoryPage(1);
                          }}
                          disabled={!historyCourseId}
                          className={FILTER_SELECT_CLASS}
                        >
                          <option value="">{historyCourseId ? 'All assignments' : 'Choose a course first…'}</option>
                          {historyAssignments.map((assignment) => (
                            <option key={assignment.id} value={assignment.id}>{assignment.name}</option>
                          ))}
                        </select>
                      </label>
                    </div>
                    {filteredHistory.length === 0 ? (
                      <div className="px-5 py-14 text-center">
                        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-500 dark:bg-slate-900 dark:text-slate-400">
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
                            const percent = Math.round(score * 100);
                            const when = formatDate(job.created_at);
                            return (
                              <li key={job.id}>
                                <Link
                                  href={`/ai-detector/results/${encodeURIComponent(job.id)}`}
                                  className="group flex flex-col gap-3 px-5 py-4 transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-500/40 sm:flex-row sm:items-center sm:justify-between dark:hover:bg-slate-900"
                                >
                                  <div className="min-w-0">
                                    <div className="truncate font-medium text-slate-900 dark:text-white">{job.assignment_name || 'AI-Generated Code Analysis Report'}</div>
                                    {/* "Course" was shown for a standalone assessment, which read like a course name. */}
                                    <div className="mt-0.5 truncate text-xs text-slate-500 dark:text-slate-400">{job.course_name || 'Standalone assessment'}</div>
                                  </div>
                                  <div className="flex shrink-0 items-center gap-4">
                                    {/* The meter repeats the chip visually so a long list can be scanned at a glance. */}
                                    <span aria-hidden="true" className="hidden h-1.5 w-20 overflow-hidden rounded-full bg-slate-100 sm:block dark:bg-slate-800">
                                      <span className={`block h-full rounded-full ${getBarColor(score)}`} style={{ width: `${Math.min(100, percent)}%` }} />
                                    </span>
                                    <div className="sm:text-right">
                                      {/* A detection score isn't a misconduct risk, so the chip doesn't say "risk". */}
                                      <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${getTone(score)}`}>
                                        {percent}% highest AI score
                                      </span>
                                      {when && <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">{when}</div>}
                                    </div>
                                    <ArrowRight size={16} className="hidden text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-slate-500 motion-reduce:transition-none sm:block dark:text-slate-600 dark:group-hover:text-slate-400" aria-hidden="true" />
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
