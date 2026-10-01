'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { useAuth } from '@/components/AuthProvider';
import { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { apiClient } from '@/lib/apiClient';
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
  Layers3,
  ArrowRight,
  Zap,
  Shield,
  Clock3,
  FileCode,
  SearchCheck,
  BookOpen,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

const API = '';
const UPLOAD_FORM_STORAGE_KEY = 'integritydesk-upload-form-v1';
/** Course/assignment labels a guest demo run files itself under. */
const GUEST_COURSE_LABEL = 'Guest demo';
const GUEST_ASSIGNMENT_LABEL = 'Guest demo check';
const UPLOAD_ENGINE_OPTIONS = [
  { key: 'token', label: 'Token' },
  { key: 'ast', label: 'AST' },
  { key: 'winnowing', label: 'Winnowing' },
  { key: 'gst', label: 'GST' },
  { key: 'semantic', label: 'Semantic' },
  { key: 'embedding', label: 'Embedding' },
  { key: 'cfg', label: 'Control Flow' },
  { key: 'tree_kernel', label: 'Tree Kernel' },
  { key: 'web', label: 'Web Matching' },
  { key: 'ai_detection', label: 'AI Detection' },
];

/**
 * Engine key -> human label, for rendering server-side recommendations.
 * Covers every key an assignment-mode weight dict can use, which is a superset
 * of the upload toggles (e.g. execution_cfg and fingerprint are weight-only
 * signals that have no toggle).
 */
const ENGINE_LABELS: Record<string, string> = {
  ...Object.fromEntries(UPLOAD_ENGINE_OPTIONS.map((o) => [o.key, o.label])),
  ast: 'AST',
  cfg: 'Control Flow',
  execution_cfg: 'Execution Flow',
  fingerprint: 'Fingerprint',
  graph: 'Code Graph',
  ngram: 'N-gram',
  static_rules: 'Static Rules',
  web: 'Web Matching',
  ai_detection: 'AI Detection',
  semantic: 'Semantic',
  embedding: 'Embedding',
  token: 'Token',
  winnowing: 'Winnowing',
  gst: 'GST',
  tree_kernel: 'Tree Kernel',
};

const ASSIGNMENT_TYPE_OPTIONS = [
  {
    id: 'auto_detect',
    label: 'Auto Detect',
    eyebrow: 'Recommended',
    description: 'AI automatically chooses the best detection strategy based on your files',
  },
  {
    id: 'foundations_code',
    label: 'Foundations Code (Intro CS)',
    eyebrow: 'CSCA08, CSCA48',
    description: 'CS1/CS2 with high template overlap. Strong rename/copy detection, class baseline calibration.',
  },
  {
    id: 'algorithmic_code',
    label: 'Algorithmic Code (Data Structures/Algo)',
    eyebrow: 'CSCB63, CSCC73',
    description: 'Logic similarity hidden behind different implementations. Deep semantic + execution analysis.',
  },
  {
    id: 'systems_projects',
    label: 'Systems & Projects',
    eyebrow: 'CSCB09, CSCD01, CSCD58',
    description: 'Systems programming & large projects. Architecture-level similarity with CFG/execution focus.',
  },
  {
    id: 'sql_data_logic',
    label: 'SQL & Data Logic',
    eyebrow: 'CSCC43, CSCD43',
    description: 'Database/SQL assignments. Semantic equivalence over syntax. Query logic + embedding focus.',
  },
  {
    id: 'notebook_ai',
    label: 'Notebook & Applied AI',
    eyebrow: 'CSCC11, CSCD84',
    description: 'Jupyter notebooks with code + narrative + AI risk. Separate code/markdown analysis.',
  },
  {
    id: 'reports_proofs',
    label: 'Reports & Proofs',
    eyebrow: 'CSCA67, CSCC63',
    description: 'Text-based assignments. Source attribution, paraphrase detection, AI authorship analysis.',
  },
];

/** File-extension chips: light tint by default, tinted dark surface in dark mode. */
const EXT_COLORS: Record<string, string> = {
  py: 'bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-300',
  java: 'bg-orange-100 text-orange-700 dark:bg-orange-500/20 dark:text-orange-300',
  js: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-500/20 dark:text-yellow-300',
  ts: 'bg-blue-100 text-blue-800 dark:bg-blue-500/20 dark:text-blue-300',
  c: 'bg-violet-100 text-violet-700 dark:bg-violet-500/20 dark:text-violet-300',
  cpp: 'bg-violet-100 text-violet-700 dark:bg-violet-500/20 dark:text-violet-300',
  h: 'bg-violet-100 text-violet-700 dark:bg-violet-500/20 dark:text-violet-300',
  go: 'bg-cyan-100 text-cyan-700 dark:bg-cyan-500/20 dark:text-cyan-300',
  rs: 'bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-300',
  rb: 'bg-pink-100 text-pink-700 dark:bg-pink-500/20 dark:text-pink-300',
  php: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-500/20 dark:text-indigo-300',
  cs: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-300',
  kt: 'bg-pink-100 text-pink-700 dark:bg-pink-500/20 dark:text-pink-300',
  swift: 'bg-orange-100 text-orange-700 dark:bg-orange-500/20 dark:text-orange-300',
};

type AssignmentMode = {
  id: string; name: string; category?: string; access?: string;
  context?: string; version?: string; overlay?: boolean; warnings?: string[]; pipelines?: string[];
  weights?: Record<string, number>;
};

function getApiErrorMessage(error: unknown, fallback = 'Request failed') {
  if (axios.isAxiosError(error)) {
    return (
      (error.response?.data as { detail?: string; error?: string } | undefined)?.detail ||
      (error.response?.data as { detail?: string; error?: string } | undefined)?.error ||
      error.message || fallback
    );
  }
  return fallback;
}

/** Tailwind classes for the extension chip shown beside each selected file. */
function getExtColor(filename: string) {
  const ext = filename.split('.').pop()?.toLowerCase() || '';
  return EXT_COLORS[ext] || 'bg-slate-100 text-slate-600 dark:bg-slate-700/60 dark:text-slate-300';
}
function getExt(filename: string) {
  return (filename.split('.').pop() || 'FILE').toUpperCase();
}
function formatSize(bytes: number) {
  return bytes < 1024 * 1024
    ? `${(bytes / 1024).toFixed(1)} KB`
    : `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

const cardShadow = { boxShadow: '0 1px 2px rgba(0,0,0,0.04), 0 4px 16px rgba(0,0,0,0.06), 0 0 0 1px rgba(0,0,0,0.04)' };
const dotGrid = { backgroundImage: 'radial-gradient(circle, #cbd5e1 1px, transparent 1px)', backgroundSize: '22px 22px' };
type UploadProgressStage = { stage: string; label: string };

type UploadJobProgress = {
  stage: string;
  label: string;
  detail: string;
  percent: number;
  completed_units: number | null;
  total_units: number | null;
  unit: string;
  current_pair: { file_a: string; file_b: string } | null;
  plan: UploadProgressStage[];
  updated_at: string;
};

// Mirrors the backend stage plan. Only used until the first server progress
// payload arrives, since the upload request itself has no server-side progress.
const FALLBACK_PROGRESS_STAGES: UploadProgressStage[] = [
  { stage: 'queued', label: 'Queued for analysis' },
  { stage: 'reading_submissions', label: 'Reading submissions' },
  { stage: 'building_pairs', label: 'Building comparison plan' },
  { stage: 'comparing_submissions', label: 'Comparing submissions' },
  { stage: 'ai_detection', label: 'Detecting AI-generated code' },
  { stage: 'generating_reports', label: 'Generating reports' },
];

function describeProgress(progress: UploadJobProgress) {
  const pair = progress.current_pair;
  if (progress.stage === 'comparing_submissions' && pair) {
    const counter = progress.total_units
      ? `${progress.completed_units ?? 0}/${progress.total_units} · `
      : '';
    return `${counter}${pair.file_a} ↔ ${pair.file_b}`;
  }
  return progress.detail ? `${progress.label} — ${progress.detail}` : progress.label;
}

export default function UploadPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  // A guest demo session owns no workspace: its run is not filed under a
  // course, so the picker stays hidden and the review starts without one.
  const isGuest = user?.role === 'guest';

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const starterFileInputRef = useRef<HTMLInputElement | null>(null);

  const [files, setFiles] = useState<File[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const [starterFiles, setStarterFiles] = useState<File[]>([]);
  const [isStarterDragOver, setIsStarterDragOver] = useState(false);
  const [activeEngines, setActiveEngines] = useState<string[]>(
    UPLOAD_ENGINE_OPTIONS.map((e) => e.key)
  );
  const [engineWeights, setEngineWeights] = useState<Record<string, number>>({});
  const [threshold, setThreshold] = useState(0.5);
  const [assignmentModes, setAssignmentModes] = useState<AssignmentMode[]>([]);
  const [selectedAssignmentModeId, setSelectedAssignmentModeId] = useState('auto_detect');
  const [thresholdLoading, setThresholdLoading] = useState(true);
  const [modesLoading, setModesLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [progress, setProgress] = useState(0);
  const [jobProgress, setJobProgress] = useState<UploadJobProgress | null>(null);
  const [activity, setActivity] = useState<string[]>([]);
  const [scanIndex, setScanIndex] = useState(0);
  const [animateFiles, setAnimateFiles] = useState(false);
  const [dragCount, setDragCount] = useState(0);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [sourceScanEnabled, setSourceScanEnabled] = useState(true);
  const [tenantExternalScanEnabled, setTenantExternalScanEnabled] = useState<boolean | null>(null);

  // Course / assignment picker (options are read from the database)
  type Course = { id: string; name: string; code?: string; assignment_count?: number };
  type RecommendedMode = {
    matched: boolean;
    mode_id: string | null;
    mode_name: string | null;
    engine_weights: Record<string, number>;
    top_engines: { key: string; weight: number }[];
    reason: string;
  };
  type Assignment = {
    id: string;
    name: string;
    assignment_type?: string;
    recommended_mode?: RecommendedMode | null;
  };
  const [courses, setCourses] = useState<Course[]>([]);
  const [coursesLoading, setCoursesLoading] = useState(true);
  const [coursesError, setCoursesError] = useState(false);
  const [selectedCourseId, setSelectedCourseId] = useState('');
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [assignmentsLoading, setAssignmentsLoading] = useState(false);
  const [selectedAssignmentId, setSelectedAssignmentId] = useState('');

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  // Fallback crawl for the window between "Analyze" and the first server-side
  // progress payload: real stage/percent values take over as soon as the job
  // status poll reports them.
  useEffect(() => {
    if (!uploading) {
      setProgress(0);
      return;
    }
    setProgress(0.03);
    const timer = window.setInterval(() => {
      setProgress((current) => Math.min(0.1, current + 0.015));
    }, 400);
    return () => window.clearInterval(timer);
  }, [uploading]);

  // Fetch tenant-level external source scan setting + source count for visibility
  const [configuredSourceCount, setConfiguredSourceCount] = useState(0);

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const res = await apiClient.get('/api/settings');
        const enabled = Boolean(res.data?.source_scan_enabled);
        const sites = res.data?.source_scan_sites || [];
        setTenantExternalScanEnabled(enabled);
        setConfiguredSourceCount(Array.isArray(sites) ? sites.length : 0);
      } catch (e) {
        setTenantExternalScanEnabled(false);
        setConfiguredSourceCount(0);
      }
    };
    if (user) {
      fetchSettings();
    }
  }, [user]);

  const startPolling = useCallback((jobId: string) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const s = await apiClient.get(`/api/jobs/${jobId}`);
        const reported = s.data?.progress as UploadJobProgress | undefined;
        if (reported) {
          setJobProgress(reported);
          const entry = describeProgress(reported);
          setActivity((previous) =>
            previous[0] === entry ? previous : [entry, ...previous].slice(0, 6),
          );
        }
        if (s.data.status === 'completed') { clearInterval(pollRef.current!); router.push(`/results/${jobId}`); }
        else if (s.data.status === 'failed') { clearInterval(pollRef.current!); setUploading(false); setError(s.data.error || 'Analysis failed'); }
      } catch (e) { clearInterval(pollRef.current!); setUploading(false); setError(getApiErrorMessage(e, 'Could not load status.')); }
    }, 1000);
  }, [router]);

  const zipFile = useMemo(() => {
    if (files.length !== 1) return null;
    return files[0].name.toLowerCase().endsWith('.zip') ? files[0] : null;
  }, [files]);

  const selectedFiles = useMemo(() => (zipFile ? [] : files), [files, zipFile]);
  const inferredComparisonScope = useMemo(() => {
    if (zipFile || files.length > 2) {
      return {
        label: 'Class-wide comparison',
        detail: 'IntegrityDesk will rank suspicious pairs across the uploaded submissions.',
      };
    }
    if (files.length === 2) {
      return {
        label: 'Pairwise comparison',
        detail: 'IntegrityDesk will compare the two selected submissions directly.',
      };
    }
    return {
      label: 'Awaiting submissions',
      detail: 'Upload two files, multiple files, or one ZIP to start plagiarism review.',
    };
  }, [files.length, zipFile]);
  const selectedAssignmentMode = useMemo(() => assignmentModes.find((m) => m.id === selectedAssignmentModeId), [assignmentModes, selectedAssignmentModeId]);
  const hasMixedZipSelection = useMemo(() => files.length > 1 && files.some((f) => f.name.toLowerCase().endsWith('.zip')), [files]);
  const submissionScope = zipFile ? '1 archive' : `${files.length} submissions`;
  // Live progress reported by the backend while the job runs; `progress` is the
  // local fallback animation used before the first poll response.
  const displayProgress = jobProgress ? jobProgress.percent : progress;
  const progressPlan = jobProgress?.plan?.length ? jobProgress.plan : FALLBACK_PROGRESS_STAGES;
  const reportedStageIndex = jobProgress
    ? progressPlan.findIndex((stage) => stage.stage === jobProgress.stage)
    : -1;
  // `completed`/`failed` are not part of the plan: treat them as "every
  // reported stage finished" so the checklist never flips back to all-pending.
  // Before the first poll response, `queued` is the stage in flight.
  const activeStageIndex = jobProgress
    ? (reportedStageIndex === -1 ? progressPlan.length : reportedStageIndex)
    : 0;
  const currentWork = jobProgress
    ? (jobProgress.current_pair
      ? `${jobProgress.current_pair.file_a} ↔ ${jobProgress.current_pair.file_b}`
      : jobProgress.detail)
    : 'Uploading files to the analysis queue…';
  const progressFooter = jobProgress?.total_units
    ? `${submissionScope} · ${jobProgress.completed_units ?? 0} of ${jobProgress.total_units} ${jobProgress.unit || 'units'} complete`
    : submissionScope;
  const canRunCheck = useMemo(() => {
    if (uploading || hasMixedZipSelection) return false;
    // IntegrityDesk is always used, so we just need files
    return zipFile ? true : files.length >= 2;
  }, [files.length, hasMixedZipSelection, uploading, zipFile]);

  const uploadFormStorageKey = useMemo(
    () => `${UPLOAD_FORM_STORAGE_KEY}:${user?.tenant_id || 'no-tenant'}:${user?.id || 'guest'}`,
    [user?.id, user?.tenant_id],
  );

  // Normalize weights to sum to 1.0
  const normalizeWeights = useCallback((weights: Record<string, number>) => {
    const total = Object.values(weights).reduce((sum, v) => sum + v, 0);
    if (total === 0) return weights;
    const normalized: Record<string, number> = {};
    for (const [k, v] of Object.entries(weights)) {
      normalized[k] = Math.round((v / total) * 10000) / 10000;
    }
    return normalized;
  }, []);

  useEffect(() => {
    let active = true;
    apiClient.get('/api/upload-settings').then((res) => {
      if (!active) return;
      const t = Number(res.data?.default_threshold);
      setThreshold(Number.isFinite(t) ? t : 0.5);
      const keys = Array.isArray(res.data?.active_engine_keys) ? res.data.active_engine_keys : [];
      const mp = res.data?.assignment_modes;
      setActiveEngines(keys.length > 0 ? keys : UPLOAD_ENGINE_OPTIONS.map((e) => e.key));
      setAssignmentModes(Array.isArray(mp?.modes) ? mp.modes : []);
      if (typeof mp?.default_mode_id === 'string') setSelectedAssignmentModeId((c) => c || mp.default_mode_id);
    }).catch(() => {
      if (active) { setThreshold(0.5); setActiveEngines(UPLOAD_ENGINE_OPTIONS.map((e) => e.key)); setAssignmentModes([]); }
    }).finally(() => { if (active) { setThresholdLoading(false); setModesLoading(false); } });
    return () => { active = false; };
  }, []);

  // Initialize engine weights from selected assignment mode
  useEffect(() => {
    const mode = assignmentModes.find((m) => m.id === selectedAssignmentModeId);
    if (mode?.weights && Object.keys(mode.weights).length > 0) {
      setEngineWeights(normalizeWeights(mode.weights));
    } else if (selectedAssignmentModeId !== 'auto_detect') {
      // Default: equal weights for active engines
      const defaultWeights: Record<string, number> = {};
      activeEngines.forEach((k) => { defaultWeights[k] = 1 / activeEngines.length; });
      setEngineWeights(defaultWeights);
    }
  }, [selectedAssignmentModeId, assignmentModes, activeEngines, normalizeWeights]);

  useEffect(() => {
    if (authLoading || typeof window === 'undefined') return;
    try {
      const raw = window.localStorage.getItem(uploadFormStorageKey);
      if (!raw) return;
      const p = JSON.parse(raw);
      if (typeof p.assignment_mode === 'string') setSelectedAssignmentModeId(p.assignment_mode);
    } catch { }
  }, [authLoading, uploadFormStorageKey]);

  useEffect(() => {
    if (authLoading || typeof window === 'undefined') return;
    window.localStorage.setItem(uploadFormStorageKey, JSON.stringify({
      assignment_mode: selectedAssignmentModeId,
    }));
  }, [authLoading, selectedAssignmentModeId, uploadFormStorageKey]);

  // Fetch courses from the database once the session is known
  const fetchCourses = useCallback(async () => {
    setCoursesLoading(true);
    setCoursesError(false);
    try {
      const res = await apiClient.get('/api/courses');
      const list = Array.isArray(res.data?.courses) ? res.data.courses : (Array.isArray(res.data) ? res.data : []);
      setCourses(list);
    } catch {
      setCourses([]);
      setCoursesError(true);
    } finally {
      setCoursesLoading(false);
    }
  }, []);

  useEffect(() => {
    // Wait for the session check so we never flash an empty list at sign-in.
    if (authLoading) return;
    if (!user) { setCourses([]); setCoursesLoading(false); return; }
    fetchCourses();
  }, [authLoading, user, fetchCourses]);

  // Fetch the selected course's assignments from the database
  useEffect(() => {
    if (!selectedCourseId) { setAssignments([]); setSelectedAssignmentId(''); return; }
    setAssignmentsLoading(true);
    setSelectedAssignmentId('');
    apiClient.get('/api/assignments', { params: { course_id: selectedCourseId } })
      .then((res) => {
        const list = Array.isArray(res.data?.assignments) ? res.data.assignments : (Array.isArray(res.data) ? res.data : []);
        setAssignments(list);
      })
      .catch(() => { setAssignments([]); })
      .finally(() => { setAssignmentsLoading(false); });
  }, [selectedCourseId]);

  // Recommendation for the chosen assignment, derived server-side from its
  // stored assignment_type. Null until a course + assignment are picked, and
  // also null when the stored type has no engine-weight-backed mode.
  const selectedAssignment = useMemo(
    () => assignments.find((a) => a.id === selectedAssignmentId) ?? null,
    [assignments, selectedAssignmentId],
  );
  const recommendedMode = selectedAssignment?.recommended_mode ?? null;

  // Apply the recommendation so the scan actually uses it rather than merely
  // displaying it. Guarded per-assignment so re-renders do not fight the
  // professor's own choice made afterwards in Advanced detection settings.
  const appliedRecommendationRef = useRef<string | null>(null);
  useEffect(() => {
    if (!recommendedMode?.matched || !recommendedMode.mode_id) return;
    if (appliedRecommendationRef.current === selectedAssignmentId) return;
    setSelectedAssignmentModeId(recommendedMode.mode_id);
    appliedRecommendationRef.current = selectedAssignmentId;
  }, [recommendedMode, selectedAssignmentId]);

  const handleDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault(); setIsDragOver(false);
    const f = Array.from(e.dataTransfer.files);
    if (f.length) setFiles(f);
  }, []);

  const handleStarterDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault(); setIsStarterDragOver(false);
    const f = Array.from(e.dataTransfer.files);
    if (f.length) setStarterFiles(f);
  }, []);

  const handleSubmit = async () => {
    setError('');
    if (!isGuest && (!selectedCourseId || !selectedAssignmentId)) {
      setError('Select a course and assignment before starting the review.');
      return;
    }
    if (hasMixedZipSelection) { setError('Upload either one ZIP archive or multiple files, not both.'); return; }
    if (!zipFile && files.length < 2) { setError('Select at least 2 submission files.'); return; }
    setUploading(true);
    setProgress(0.03);
    setJobProgress(null);
    setActivity([]);
    const fd = new FormData();
    if (zipFile) fd.append('file', zipFile); else files.forEach((f) => fd.append('files', f));
    starterFiles.forEach((f) => fd.append('starter_files', f));
    const chosenCourse = courses.find((c) => c.id === selectedCourseId);
    const chosenAssignment = assignments.find((a) => a.id === selectedAssignmentId);
    if (!isGuest && (!chosenCourse || !chosenAssignment)) {
      setError('Select a course and assignment before starting the review.');
      setUploading(false);
      return;
    }
    // A guest run files itself under a demo label instead of a course it has
    // no access to; signed-in reviews keep their real course and assignment.
    fd.append('course_name', chosenCourse?.name ?? GUEST_COURSE_LABEL);
    fd.append('assignment_name', chosenAssignment?.name ?? GUEST_ASSIGNMENT_LABEL);
    if (chosenAssignment) fd.append('assignment_id', chosenAssignment.id);
    fd.append('assignment_mode', selectedAssignmentModeId);
    fd.append('threshold', String(threshold));
    fd.append('engine_weights', JSON.stringify(engineWeights));
    fd.append('source_scan_enabled', String(sourceScanEnabled));
    try {
      const url = zipFile ? `${API}/api/upload-zip` : `${API}/api/upload`;
      const res = await apiClient.post(url, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      const jobId = res.data?.job_id;
      if (!jobId) { setUploading(false); setError('Upload completed but no job ID returned.'); return; }
      if (res.data?.status === 'completed') { router.push(`/results/${jobId}`); return; }
      startPolling(jobId);
    } catch (err) { setUploading(false); setError(getApiErrorMessage(err, 'Upload failed')); }
  };

  const toggleEngine = useCallback((k: string) =>
    setActiveEngines((c) => c.includes(k) ? c.filter((x) => x !== k) : [...c, k]), []);
  const updateEngineWeight = useCallback((engineKey: string, value: number) => {
    setEngineWeights((prev) => {
      const next = { ...prev, [engineKey]: Math.max(0, value) };
      return normalizeWeights(next);
    });
  }, [normalizeWeights]);

  return (
    <DashboardLayout>
      <div className="theme-page-container">
        <div className="space-y-8 lg:space-y-10">

          {/* Header */}
          <section className="theme-card-strong rounded-[30px] overflow-hidden mb-8">
            <div className="theme-section-line px-6 py-5 lg:px-7">
              <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
                <div className="space-y-4">
                  <div className="inline-flex items-center gap-2 rounded-full border border-blue-600/10 bg-blue-600/[0.06] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--accent-blue)]">
                    <Shield size={13} />
                    Plagiarism Detection
                  </div>
                  <div>
                    <h1 className="font-display text-3xl font-semibold tracking-tight text-[var(--text-primary)] sm:text-4xl">
                      Plagiarism Checker
                    </h1>
                  </div>
                  <p className="max-w-3xl text-sm leading-7 text-[var(--text-secondary)]">
                    Upload files and IntegrityDesk compares them using similarity engines + AI detection.
                    When enabled in Settings, it also scans admin-configured GitHub repos and public websites for copied code.
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  {/* Small external scan status pill next to Analyze button */}
                  {tenantExternalScanEnabled !== null && (
                    <div className={`hidden md:flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium border ${tenantExternalScanEnabled
                      ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                      : 'border-amber-200 bg-amber-50 text-amber-700'
                      }`}>
                      <div className={`w-1.5 h-1.5 rounded-full ${tenantExternalScanEnabled ? 'bg-emerald-500' : 'bg-amber-500'}`} />
                      External: {tenantExternalScanEnabled ? 'On' : 'Off'}
                    </div>
                  )}

                  <button
                    onClick={handleSubmit}
                    disabled={!canRunCheck}
                    className="theme-button-primary inline-flex items-center gap-2 rounded-2xl px-6 py-4 text-base font-semibold transition hover:scale-105 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:scale-100"
                  >
                    {uploading
                      ? <>
                        <svg width="18" height="18" viewBox="0 0 20 20">
                          <circle cx="10" cy="10" r="8" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="2" />
                          <circle cx="10" cy="10" r="8" fill="none" stroke="white" strokeWidth="2" strokeDasharray="50" strokeDashoffset={50 - (progress * 50)} strokeLinecap="round" className="transition-all duration-150" style={{ transformOrigin: '50% 50%', transform: 'rotate(-90deg)' }} />
                        </svg>
                        Analyzing…
                      </>
                      : <><Zap size={16} />Analyze<ArrowRight size={15} className="opacity-70" /></>}
                  </button>
                </div>
              </div>
            </div>
          </section>

          {uploading && (
            <section className="rounded-2xl border border-blue-200 bg-blue-50 p-5">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2 text-sm font-semibold text-blue-950">
                    <Loader2 size={16} className="animate-spin shrink-0" />
                    <span className="truncate">
                      {jobProgress?.label ?? `Analyzing ${zipFile ? 'submissions from archive' : `${files.length} submissions`}...`}
                    </span>
                    {jobProgress?.stage === 'comparing_submissions' && jobProgress.total_units ? (
                      <span className="rounded-full bg-blue-600/10 px-2 py-0.5 text-[11px] font-semibold text-blue-700">
                        pair {jobProgress.completed_units ?? 0} of {jobProgress.total_units}
                      </span>
                    ) : null}
                  </div>
                  <div className="mt-1.5 flex items-center gap-2 text-xs text-blue-800">
                    <FileCode size={12} className="shrink-0 text-blue-500" />
                    <span className="truncate">{currentWork}</span>
                  </div>
                  <div className="mt-3 h-3 overflow-hidden rounded-full bg-white shadow-inner">
                    <div className="h-full rounded-full bg-blue-600 shadow-sm transition-all duration-500" style={{ width: `${Math.round(displayProgress * 100)}%` }} />
                  </div>
                  <div className="mt-2 flex items-center justify-between gap-3">
                    <span className="truncate text-[11px] text-blue-700/80">{progressFooter}</span>
                    <span className="text-xs font-medium text-blue-700">{Math.round(displayProgress * 100)}%</span>
                  </div>
                </div>
                <div className="grid gap-2 text-sm text-blue-800 sm:grid-cols-2">
                  {progressPlan.map((task, index) => (
                    <div key={task.stage} className="flex items-center gap-2">
                      <span className="flex h-4 w-4 shrink-0 items-center justify-center">
                        {index < activeStageIndex ? (
                          <Check size={14} className="text-blue-700" />
                        ) : index === activeStageIndex ? (
                          <Loader2 size={13} className="animate-spin text-blue-700" />
                        ) : (
                          <span className="h-2 w-2 rounded-full bg-blue-300" />
                        )}
                      </span>
                      <span className={index === activeStageIndex ? 'font-semibold text-blue-950' : index < activeStageIndex ? 'text-blue-700' : 'text-blue-500/70'}>
                        {task.label}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {activity.length > 0 && (
                <div className="mt-4 rounded-xl border border-blue-100 bg-white/70 px-3 py-2.5">
                  <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-blue-700">
                    <Clock3 size={12} /> Live activity
                  </div>
                  <ul className="mt-2 space-y-1">
                    {activity.map((line, index) => (
                      <li key={`${index}-${line}`} className="truncate font-mono text-[11px] text-blue-900/80">
                        {line}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </section>
          )}

          {inferredComparisonScope && (
            <section className="rounded-2xl border border-blue-200 bg-blue-50 px-5 py-4">
              <div className="flex items-start gap-3">
                <SearchCheck size={16} className="mt-0.5 shrink-0 text-blue-600" />
                <div>
                  <div className="text-sm font-semibold text-blue-950">{inferredComparisonScope.label}</div>
                  <p className="mt-1 text-sm leading-6 text-blue-800">{inferredComparisonScope.detail}</p>
                </div>
              </div>
            </section>
          )}

          {/* Only show this when tenant-level is disabled AND user hasn't overridden for this submission */}
          {tenantExternalScanEnabled === false && !sourceScanEnabled && (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 px-5 py-3.5">
              <div className="flex items-center gap-3 text-sm">
                <AlertCircle size={16} className="shrink-0 text-amber-600" />
                <div className="flex-1 text-amber-900">
                  External source scanning (GitHub + web) is disabled at the tenant level.
                  <a href="/settings" className="ml-1.5 underline hover:text-amber-800">Enable it in Settings</a>
                </div>
              </div>
            </div>
          )}

          {/* Course & Assignment Picker — omitted for the guest demo, which
              has no workspace to file a run under (and no Courses page to
              create one on). */}
          {!isGuest && (
            <div className="rounded-2xl bg-white p-5" style={cardShadow}>
              <div className="flex items-center gap-2 mb-4">
                <BookOpen size={15} className="text-slate-500" />
                <span className="text-sm font-semibold text-slate-800">Course & Assignment</span>

              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                {/* Course select — options are read from the database */}
                <div className="flex flex-col gap-1">
                  <label className="text-xs font-medium text-slate-500">Course</label>
                  <select
                    value={selectedCourseId}
                    onChange={(e) => { setSelectedCourseId(e.target.value); setSelectedAssignmentId(''); }}
                    disabled={coursesLoading}
                    className="theme-field"
                  >
                    <option value="">
                      {coursesLoading
                        ? 'Loading courses…'
                        : coursesError
                          ? 'Courses unavailable'
                          : courses.length > 0
                            ? 'Select course…'
                            : user ? 'No courses yet' : 'Sign in to see courses'}
                    </option>
                    {courses.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.code ? `${c.code} – ` : ''}{c.name}
                        {typeof c.assignment_count === 'number' ? ` (${c.assignment_count} assignment${c.assignment_count === 1 ? '' : 's'})` : ''}
                      </option>
                    ))}
                  </select>
                  {coursesError && (
                    <button type="button" onClick={() => { fetchCourses(); }} className="text-left text-xs text-blue-600 hover:underline">
                      Couldn&apos;t load courses — retry
                    </button>
                  )}
                  {!coursesLoading && !coursesError && courses.length === 0 && (
                    <span className="text-xs text-slate-400">
                      {user ? 'Create a course on the Courses page first.' : 'Sign in to load your courses.'}
                    </span>
                  )}
                </div>

                {/* Assignment select — filled from the selected course */}
                <div className="flex flex-col gap-1">
                  <label className="text-xs font-medium text-slate-500">Assignment</label>
                  <select
                    value={selectedAssignmentId}
                    onChange={(e) => setSelectedAssignmentId(e.target.value)}
                    disabled={!selectedCourseId || assignmentsLoading}
                    className="theme-field"
                  >
                    <option value="">
                      {!selectedCourseId
                        ? 'Choose a course first…'
                        : assignmentsLoading
                          ? 'Loading assignments…'
                          : assignments.length > 0
                            ? 'Select assignment…'
                            : 'No assignments yet'}
                    </option>
                    {assignments.map((a) => (
                      <option key={a.id} value={a.id}>{a.name}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Recommended scan engine — appears once a course and assignment are
                  chosen, so the professor can confirm the detection strategy
                  before uploading rather than after. */}
              {recommendedMode?.matched && recommendedMode.mode_id && (
                <div className="mt-4 rounded-xl border border-blue-200 bg-blue-50/70 px-4 py-3.5">
                  <div className="flex flex-wrap items-start gap-3">
                    <SearchCheck size={15} className="mt-0.5 shrink-0 text-blue-600" />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                        <span className="text-sm font-semibold text-slate-900">
                          Recommended scan engine
                        </span>
                        <span className="rounded-md bg-blue-600 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white">
                          {recommendedMode.mode_name}
                        </span>
                      </div>
                      <p className="mt-1 text-xs leading-5 text-slate-600">
                        {selectedAssignment?.name} is stored as{' '}
                        <span className="font-medium">
                          {selectedAssignment?.assignment_type?.replace(/_/g, ' ') ?? 'programming'}
                        </span>
                        , so this detection strategy and its engine weighting were selected
                        automatically.
                      </p>
                      {recommendedMode.top_engines.length > 0 && (
                        <div className="mt-2 flex flex-wrap items-center gap-1.5">
                          <span className="text-[11px] font-medium uppercase tracking-wide text-slate-500">
                            Key engines
                          </span>
                          {recommendedMode.top_engines.map((engine) => (
                            <span
                              key={engine.key}
                              className="rounded-md bg-white px-1.5 py-0.5 text-[11px] font-medium text-slate-700 ring-1 ring-blue-200"
                            >
                              {ENGINE_LABELS[engine.key] ?? engine.key}
                              <span className="ml-1 text-slate-400">
                                {Math.round(engine.weight * 100)}%
                              </span>
                            </span>
                          ))}
                        </div>
                      )}
                      <button
                        type="button"
                        onClick={() => {
                          const details = document.getElementById('advanced-detection');
                          if (details instanceof HTMLDetailsElement) details.open = true;
                        }}
                        className="mt-2 text-xs font-medium text-blue-700 hover:underline"
                      >
                        Change engine weights →
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Upload Cards */}
          <div className="grid gap-4 lg:grid-cols-2">
            {/* Upload Card */}
            <div className="rounded-2xl bg-white overflow-hidden relative transition-all duration-300" style={cardShadow}>
              <div
                onDrop={handleDrop}
                onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
                onDragLeave={() => setIsDragOver(false)}
                className="relative"
              >
                {/* Dot-grid bg — only visible in empty state */}
                {files.length === 0 && (
                  <div className="absolute inset-0 pointer-events-none dark:invisible" style={{ ...dotGrid, opacity: 0.5 }} />
                )}

                {/* Drag ring */}
                {isDragOver && (
                  <div className="absolute inset-0 z-10 pointer-events-none rounded-t-2xl bg-blue-50/60 ring-2 ring-inset ring-blue-500 dark:bg-blue-500/10" />
                )}

                {files.length === 0 ? (
                  /* ── Empty drop zone ── */
                  <div
                    className="relative flex flex-col items-center justify-center text-center px-8 py-20 cursor-pointer"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <div
                      className={`w-[72px] h-[72px] rounded-[20px] flex items-center justify-center mb-5 transition-all duration-300 shadow-sm ring-[10px] ${isDragOver
                          ? 'scale-[1.08] bg-blue-100 ring-blue-500/10 dark:bg-blue-500/20 dark:ring-blue-500/25'
                          : 'bg-slate-50 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700/80'
                        }`}
                    >
                      <UploadIcon
                        size={28}
                        className={`transition-colors ${isDragOver ? 'text-blue-600' : 'text-slate-400'}`}
                      />
                    </div>
                    <h3 className="text-[15px] font-semibold text-slate-800 mb-1.5">
                      {isDragOver ? 'Release to upload' : 'Drag files here'}
                    </h3>
                    <p className="text-sm text-slate-400 mb-6 max-w-sm leading-relaxed">
                      Upload a ZIP archive, LMS export, repository bundle, or source files for this review.
                    </p>
                    <div className="flex flex-wrap justify-center gap-3">
                      <button
                        type="button"
                        onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click(); }}
                        className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 shadow-sm transition-all duration-200 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-600"
                      >
                        <FileUp size={13} />Browse files
                      </button>
                    </div>
                    <p className="mt-5 text-xs text-slate-300 font-medium">
                      .py · .java · .c · .cpp · .js · .ts · .go · .rs · .rb · .php · .cs · .kt · .swift · .zip
                    </p>
                  </div>
                ) : (
                  /* ── File list ── */
                  <div className="px-5 pt-5 pb-4">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2.5">
                        {zipFile ? (
                          <>
                            <div className="w-5 h-5 rounded-md flex items-center justify-center bg-amber-100">
                              <FolderArchive size={11} className="text-amber-600" />
                            </div>
                            <span className="text-sm font-semibold text-slate-700">ZIP Archive</span>
                          </>
                        ) : (
                          <>
                            <span className="inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold text-white bg-blue-600">
                              {selectedFiles.length}
                            </span>
                            <span className="text-sm font-semibold text-slate-700">
                              {selectedFiles.length} {selectedFiles.length === 1 ? 'file' : 'files'} selected
                            </span>
                            {files.length < 2 && (
                              <span className="text-[11px] font-semibold rounded-full px-2 py-0.5 bg-amber-100 text-amber-700">
                                Need 2+
                              </span>
                            )}
                          </>
                        )}
                      </div>
                      <div className="flex items-center gap-3">
                        <button type="button" onClick={() => fileInputRef.current?.click()} className="text-xs font-medium text-blue-600 hover:text-blue-700 transition-colors">
                          Add more
                        </button>
                        <button onClick={() => setFiles([])} className="text-xs text-slate-400 hover:text-red-500 transition-colors">
                          Clear all
                        </button>
                      </div>
                    </div>

                    <div className="grid gap-1.5 max-h-56 overflow-y-auto" style={{ scrollbarWidth: 'thin' }}>
                      {zipFile ? (
                        <div className="flex items-center gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3.5">
                          <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 bg-amber-100">
                            <FolderArchive size={15} className="text-amber-600" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-slate-800 truncate">{zipFile.name}</p>
                            <p className="text-xs font-medium text-amber-700">{formatSize(zipFile.size)}</p>
                          </div>
                        </div>
                      ) : (
                        selectedFiles.map((f, i) => {
                          const c = getExtColor(f.name);
                          return (
                            <div
                              key={i}
                              className="flex items-center gap-3 rounded-xl border border-slate-100 bg-slate-50 px-3 py-2.5 group/row transition-all duration-150 hover:border-slate-200 hover:bg-white"
                            >
                              <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-[9px] font-bold shrink-0 ${c}`}>
                                {getExt(f.name)}
                              </div>
                              <span className="flex-1 text-sm font-medium text-slate-700 truncate">{f.name}</span>
                              <span className="text-xs text-slate-400 shrink-0 mr-1">{formatSize(f.size)}</span>
                              <button
                                onClick={(e) => { e.stopPropagation(); setFiles(files.filter((_, j) => j !== i)); }}
                                aria-label={`Remove ${f.name}`}
                                className="w-6 h-6 flex items-center justify-center rounded-lg transition-all shrink-0 hover:bg-red-50 text-slate-300 hover:text-red-500"
                              >
                                <X size={12} />
                              </button>
                            </div>
                          );
                        })
                      )}
                    </div>
                  </div>
                )}
              </div>

              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".zip,.py,.java,.c,.cpp,.h,.js,.ts,.go,.rs,.rb,.php,.cs,.kt,.swift"
                className="hidden"
                onChange={(e) => { const f = Array.from(e.target.files || []); if (f.length) setFiles(f); }}
              />

              {error && (
                <div className="border-t border-red-100 bg-red-50 px-5 py-3.5 flex items-start gap-2.5">
                  <AlertCircle size={14} className="text-red-400 mt-0.5 shrink-0" />
                  <p className="text-sm text-red-700 flex-1">{error}</p>
                  <button onClick={() => setError('')} aria-label="Dismiss error" className="text-red-300 hover:text-red-500 transition-colors shrink-0"><X size={13} /></button>
                </div>
              )}
              {hasMixedZipSelection && (
                <div className="border-t border-amber-100 bg-amber-50 px-5 py-3 flex items-center gap-2">
                  <AlertCircle size={13} className="text-amber-500 shrink-0" />
                  <p className="text-sm text-amber-700">Remove the ZIP or the other files. Do not mix both.</p>
                </div>
              )}
            </div>

            {/* Starter Code Upload */}
            <div className="rounded-2xl bg-white overflow-hidden relative transition-all duration-300" style={cardShadow}>
              <div
                onDrop={handleStarterDrop}
                onDragOver={(e) => { e.preventDefault(); setIsStarterDragOver(true); }}
                onDragLeave={() => setIsStarterDragOver(false)}
                className="relative"
              >
                {/* Dot-grid bg */}
                {starterFiles.length === 0 && (
                  <div className="absolute inset-0 pointer-events-none dark:invisible" style={{ ...dotGrid, opacity: 0.5 }} />
                )}

                {/* Drag ring */}
                {isStarterDragOver && (
                  <div className="absolute inset-0 z-10 pointer-events-none rounded-t-2xl bg-emerald-50/60 ring-2 ring-inset ring-emerald-500 dark:bg-emerald-500/10" />
                )}

                {starterFiles.length === 0 ? (
                  /* Empty drop zone */
                  <div
                    className="relative flex flex-col items-center justify-center text-center px-8 py-16 cursor-pointer"
                    onClick={() => starterFileInputRef.current?.click()}
                  >
                    <div
                      className={`w-[60px] h-[60px] rounded-[16px] flex items-center justify-center mb-4 transition-all duration-300 shadow-sm ring-[8px] ${isStarterDragOver
                          ? 'scale-[1.05] bg-emerald-100 ring-emerald-500/10 dark:bg-emerald-500/20 dark:ring-emerald-500/25'
                          : 'bg-slate-50 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700/80'
                        }`}
                    >
                      <Layers3
                        size={24}
                        className={`transition-colors ${isStarterDragOver ? 'text-emerald-600' : 'text-slate-400'}`}
                      />
                    </div>
                    <h3 className="text-sm font-semibold text-slate-800 mb-1">
                      {isStarterDragOver ? 'Release to upload starter code' : 'Starter Code (Optional)'}
                    </h3>
                    <p className="text-xs text-slate-400 mb-4 max-w-xs leading-relaxed">
                      Upload template files, boilerplate code, or reference implementations that should be ignored during comparison.
                    </p>
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); starterFileInputRef.current?.click(); }}
                      className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-xs font-medium text-slate-600 transition-all duration-200 hover:border-emerald-300 hover:bg-emerald-50 hover:text-emerald-600"
                    >
                      <FileUp size={11} />Browse files
                    </button>
                    <p className="mt-3 text-[10px] text-slate-300 font-medium">
                      .py · .java · .c · .cpp · .js · .ts · .go · .rs · .rb · .php · .cs · .kt · .swift
                    </p>
                  </div>
                ) : (
                  /* File list */
                  <div className="px-5 pt-5 pb-4">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2.5">
                        <span className="inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold text-white bg-emerald-500">
                          {starterFiles.length}
                        </span>
                        <span className="text-sm font-semibold text-slate-700">
                          Starter file{starterFiles.length === 1 ? '' : 's'} uploaded
                        </span>
                      </div>
                      <div className="flex items-center gap-3">
                        <button type="button" onClick={() => starterFileInputRef.current?.click()} className="text-xs font-medium text-emerald-600 hover:text-emerald-700 transition-colors">
                          Add more
                        </button>
                        <button onClick={() => setStarterFiles([])} className="text-xs text-slate-400 hover:text-red-500 transition-colors">
                          Clear all
                        </button>
                      </div>
                    </div>

                    <div className="grid gap-1.5 max-h-48 overflow-y-auto" style={{ scrollbarWidth: 'thin' }}>
                      {starterFiles.map((f, i) => {
                        const c = getExtColor(f.name);
                        return (
                          <div
                            key={i}
                            className="flex items-center gap-3 rounded-xl border border-slate-100 bg-slate-50 px-3 py-2.5 group/row transition-all duration-150 hover:border-slate-200 hover:bg-white"
                          >
                            <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-[9px] font-bold shrink-0 ${c}`}>
                              {getExt(f.name)}
                            </div>
                            <span className="flex-1 text-sm font-medium text-slate-700 truncate">{f.name}</span>
                            <span className="text-xs text-slate-400 shrink-0 mr-1">{formatSize(f.size)}</span>
                            <button
                              onClick={(e) => { e.stopPropagation(); setStarterFiles(starterFiles.filter((_, j) => j !== i)); }}
                              aria-label={`Remove ${f.name}`}
                              className="w-6 h-6 flex items-center justify-center rounded-lg transition-all shrink-0 hover:bg-red-50 text-slate-300 hover:text-red-500"
                            >
                              <X size={12} />
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>

              <input
                ref={starterFileInputRef}
                type="file"
                multiple
                accept=".zip,.py,.java,.c,.cpp,.h,.js,.ts,.go,.rs,.rb,.php,.cs,.kt,.swift"
                className="hidden"
                onChange={(e) => { const f = Array.from(e.target.files || []); if (f.length) setStarterFiles(f); }}
              />

              {error && starterFiles.length > 0 && (
                <div className="border-t border-red-100 bg-red-50 px-5 py-3.5 flex items-start gap-2.5">
                  <AlertCircle size={14} className="text-red-400 mt-0.5 shrink-0" />
                  <p className="text-sm text-red-700 flex-1">{error}</p>
                  <button onClick={() => setError('')} aria-label="Dismiss error" className="text-red-300 hover:text-red-500 transition-colors shrink-0"><X size={13} /></button>
                </div>
              )}
            </div>
          </div>

          {/* Config */}
          <details id="advanced-detection" className="rounded-2xl bg-white p-5" style={cardShadow}>
            <summary className="cursor-pointer text-sm font-semibold text-slate-800">
              Advanced detection settings
            </summary>
            <p className="mt-2 text-sm text-slate-500">
              Defaults are recommended for professors. Adjust engine weights for your specific assignment type.
            </p>

            {/* External Source Scan moved out of the main flow into advanced
                settings: it is a per-submission opt-in that most professors
                never change, so it should not compete with the primary
                upload/analysis controls. */}
            <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50/60 px-4 py-3.5">
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={sourceScanEnabled}
                  onChange={(e) => setSourceScanEnabled(e.target.checked)}
                  disabled={tenantExternalScanEnabled === false}
                  className="mt-0.5 h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
                />
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-semibold text-slate-800">
                    External Source Scan
                  </span>
                  <span className="mt-0.5 block text-xs leading-5 text-slate-500">
                    {tenantExternalScanEnabled === false
                      ? 'Disabled for this workspace. A tenant administrator can enable it in Settings → External Sources.'
                      : tenantExternalScanEnabled === true
                        ? `Check public sources for this submission (${configuredSourceCount} source${configuredSourceCount === 1 ? '' : 's'} configured).`
                        : 'Checking public sources for this submission.'}
                  </span>
                </span>
              </label>
            </div>

            <div className="mt-5 grid gap-4 lg:grid-cols-2">

              {/* Assignment Type - Left side */}
              <div className="rounded-2xl bg-white overflow-hidden" style={cardShadow}>
                <div className="p-5">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2.5">
                      <div className="w-7 h-7 rounded-lg flex items-center justify-center bg-slate-100">
                        <Layers3 size={13} className="text-slate-500" />
                      </div>
                      <span className="text-sm font-semibold text-slate-800">Assignment Type</span>
                    </div>
                    {selectedAssignmentMode?.version && (
                      <span className="text-[10px] font-bold tracking-wider rounded-md px-2 py-0.5 bg-slate-100 text-slate-400">
                        v{selectedAssignmentMode.version}
                      </span>
                    )}
                  </div>

                  <div className="grid gap-3">
                    {ASSIGNMENT_TYPE_OPTIONS.map((option) => (
                      <button
                        key={option.id}
                        type="button"
                        onClick={() => setSelectedAssignmentModeId(option.id)}
                        className={`rounded-xl border p-4 text-left transition ${selectedAssignmentModeId === option.id ? 'border-blue-300 bg-blue-50 ring-2 ring-blue-100' : 'border-slate-200 hover:bg-slate-50'
                          }`}
                      >
                        <div className="text-sm font-semibold text-slate-950">{option.label}</div>
                        <div className={`text-[11px] font-semibold uppercase tracking-[0.18em] mb-1 ${selectedAssignmentModeId === option.id ? 'text-blue-600' : 'text-slate-400'}`}>{option.eyebrow}</div>
                        <div className="text-sm leading-6 text-slate-500">{option.description}</div>
                      </button>
                    ))}
                  </div>

                  {selectedAssignmentMode?.context && (
                    <p className="mt-2.5 text-xs text-slate-500 leading-relaxed">{selectedAssignmentMode.context}</p>
                  )}

                  {selectedAssignmentMode?.warnings?.length ? (
                    <div className="mt-3 flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3.5 py-3">
                      <AlertCircle size={13} className="mt-0.5 shrink-0 text-amber-500" />
                      <p className="text-xs leading-relaxed text-amber-800">{selectedAssignmentMode.warnings[0]}</p>
                    </div>
                  ) : null}

                </div>
              </div>

              {/* Similarity Engine Weights - Right side */}
              <div className="rounded-2xl bg-white overflow-hidden" style={cardShadow}>
                <div className="p-5">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2.5">
                      <div className="w-7 h-7 rounded-lg flex items-center justify-center bg-slate-100">
                        <SearchCheck size={13} className="text-slate-500" />
                      </div>
                      <span className="text-sm font-semibold text-slate-800">Similarity Engine Weights</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        const mode = assignmentModes.find((m) => m.id === selectedAssignmentModeId);
                        if (mode?.weights) {
                          setEngineWeights(normalizeWeights(mode.weights));
                        }
                      }}
                      className="text-xs font-medium text-slate-400 hover:text-blue-600 transition-colors"
                    >
                      Reset to preset
                    </button>
                  </div>

                  <div className="space-y-1.5">
                    {UPLOAD_ENGINE_OPTIONS.map((engine) => {
                      const weight = engineWeights[engine.key] ?? 0;
                      const percentage = Math.round(weight * 100);
                      return (
                        <div
                          key={engine.key}
                          className={`w-full flex items-center gap-3 rounded-xl border px-3.5 py-3 text-left transition-all duration-200 ${weight > 0
                              ? 'border-blue-200 bg-blue-50'
                              : 'border-slate-100 bg-slate-50'
                            }`}
                        >
                          <div className={`w-4 h-4 rounded flex items-center justify-center border-2 shrink-0 ${weight > 0
                              ? 'border-blue-600 bg-blue-600'
                              : 'border-slate-300 bg-white'
                            }`}
                          >
                          </div>
                          <p className={`text-sm font-semibold flex-1 ${weight > 0 ? 'text-blue-700' : 'text-slate-700'}`}>{engine.label}</p>
                          <div className="flex items-center gap-2 w-48">
                            <input
                              type="range"
                              min="0"
                              max="100"
                              step="1"
                              value={percentage}
                              onChange={(e) => updateEngineWeight(engine.key, Number(e.target.value) / 100)}
                              className="flex-1 h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                            />
                            <span className="text-xs font-mono text-slate-600 w-10 text-right">{percentage}%</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {Object.values(engineWeights).every((v) => v === 0) && (
                    <div className="mt-3 border-t border-amber-100 bg-amber-50 px-3.5 py-3 flex items-center gap-2 rounded-xl">
                      <AlertCircle size={12} className="text-amber-500" />
                      <p className="text-xs text-amber-700">All weights are zero. At least one engine must have weight &#62; 0.</p>
                    </div>
                  )}

                  <div className="mt-2 text-xs text-slate-500">
                    Weights are normalized to sum to 100%. Sliders adjust proportionally.
                  </div>
                </div>
              </div>
            </div>
          </details>

          {/* Ready Banner: status only — the header holds the single Analyze CTA */}
          {canRunCheck && (
            <div className="mt-4 flex items-center gap-3 rounded-2xl border border-blue-200 bg-blue-50 px-5 py-4">
              <div className="w-8 h-8 rounded-xl flex items-center justify-center bg-blue-100">
                <Zap size={14} className="text-blue-600" />
              </div>
              <div>
                <p className="text-sm font-semibold text-blue-900">
                  {zipFile ? '1 archive' : `${selectedFiles.length} files`} ready to analyze
                </p>
                <p className="text-xs text-blue-600">
                  Auto profile · starter code removal · previous-term matching when available
                </p>
              </div>
            </div>
          )}

        </div>
      </div>
    </DashboardLayout>
  );
}

function AutoStep({ icon: Icon, title, detail }: { icon: LucideIcon; title: string; detail: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4" style={cardShadow}>
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-600">
          <Icon size={16} />
        </div>
        <div>
          <div className="text-sm font-semibold text-slate-900">{title}</div>
          <div className="mt-1 text-sm leading-5 text-slate-500">{detail}</div>
        </div>
      </div>
    </div>
  );
}
