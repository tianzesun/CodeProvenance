'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { useAuth } from '@/components/AuthProvider';
import { useState, useCallback, useEffect, useMemo, useRef } from 'react';
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
  Layers3,
  Sparkles,
  ArrowRight,
  Zap,
  Shield,
} from 'lucide-react';

const API = '';
const UPLOAD_FORM_STORAGE_KEY = 'integritydesk-upload-form-v1';
const UPLOAD_ENGINE_OPTIONS = [
  { key: 'token', label: 'Token' },
  { key: 'ast', label: 'AST' },
  { key: 'winnowing', label: 'Winnowing' },
  { key: 'gst', label: 'GST' },
  { key: 'semantic', label: 'Semantic' },
];
const FALLBACK_TOOL_OPTIONS = [
  {
    id: 'integritydesk',
    name: 'IntegrityDesk',
    desc: 'Gold standard. Best for most programming assignments. Uses 5 different engines with ML fusion. Detects all modification types including variable renaming, reordering, and structural changes.',
    available: true,
    status: 'Built in',
    engines: ['Token', 'AST', 'Winnowing', 'GST', 'Semantic'],
  },
  {
    id: 'token_only',
    name: 'Token Matching',
    desc: 'Fast and precise. Best for detecting exact copies and minor modifications. Very low false positive rate. Good for introductory courses.',
    available: true,
    status: 'Built in',
    engines: ['Token'],
  },
  {
    id: 'structure_only',
    name: 'Structure Detection',
    desc: 'Ignores syntax changes. Best for detecting heavily obfuscated plagiarism. Finds copies where variable names, comments, and formatting have been completely rewritten.',
    available: true,
    status: 'Built in',
    engines: ['AST', 'GST'],
  },
  {
    id: 'semantic',
    name: 'Semantic Analysis',
    desc: 'Deep logic analysis. Best for advanced courses where algorithm reuse is the main concern. Finds submissions that implement identical logic with completely different code.',
    available: true,
    status: 'Built in',
    engines: ['Semantic'],
  },
  {
    id: 'jplag',
    name: 'JPlag',
    desc: 'Reference implementation. Classic algorithm used in universities for 20+ years. Good baseline for comparison.',
    available: true,
    status: 'Built in',
    engines: ['Winnowing'],
  },
  {
    id: 'moss',
    name: 'MOSS',
    desc: 'Stanford MOSS (Measure Of Software Similarity). Original command-line tool used by universities worldwide. Provides identical results to running moss.pl directly.',
    available: true,
    status: 'External Tool',
    engines: ['MOSS'],
  },
];

const EXT_COLORS: Record<string, { bg: string; text: string }> = {
  py: { bg: '#dbeafe', text: '#1d4ed8' },
  java: { bg: '#ffedd5', text: '#c2410c' },
  js: { bg: '#fef9c3', text: '#a16207' },
  ts: { bg: '#dbeafe', text: '#1e40af' },
  c: { bg: '#ede9fe', text: '#6d28d9' },
  cpp: { bg: '#ede9fe', text: '#6d28d9' },
  h: { bg: '#ede9fe', text: '#6d28d9' },
  go: { bg: '#cffafe', text: '#0e7490' },
  rs: { bg: '#fee2e2', text: '#b91c1c' },
  rb: { bg: '#fce7f3', text: '#be185d' },
  php: { bg: '#e0e7ff', text: '#4338ca' },
  cs: { bg: '#d1fae5', text: '#065f46' },
  kt: { bg: '#fce7f3', text: '#be185d' },
  swift: { bg: '#ffedd5', text: '#c2410c' },
};

type DetectionTool = {
  id: string; name: string; desc?: string;
  available?: boolean; runnable?: boolean; status?: string; engines?: string[];
};
type AssignmentMode = {
  id: string; name: string; category?: string; access?: string;
  context?: string; version?: string; overlay?: boolean; warnings?: string[]; pipelines?: string[];
};
type ModeSuggestion = {
  recommended_mode_id: string; recommended_mode_name: string;
  confidence?: number; reasons?: string[];
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

function getExtColor(filename: string) {
  const ext = filename.split('.').pop()?.toLowerCase() || '';
  return EXT_COLORS[ext] || { bg: '#f1f5f9', text: '#475569' };
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
const btnShadow = { boxShadow: '0 1px 2px rgba(37,99,235,0.2), 0 4px 14px rgba(37,99,235,0.28)' };
const dotGrid = { backgroundImage: 'radial-gradient(circle, #cbd5e1 1px, transparent 1px)', backgroundSize: '22px 22px' };
const blueBg = { background: 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)' };
const blueCardBg = { background: 'linear-gradient(135deg, #eff6ff 0%, #f0f9ff 100%)', border: '1px solid #bfdbfe' };

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
  const [assignmentModes, setAssignmentModes] = useState<AssignmentMode[]>([]);
  const [selectedAssignmentModeId, setSelectedAssignmentModeId] = useState('intro_programming');
  const [modeSuggestion, setModeSuggestion] = useState<ModeSuggestion | null>(null);
  const [modeSuggesting, setModeSuggesting] = useState(false);
  const [toolOptions, setToolOptions] = useState<DetectionTool[]>(FALLBACK_TOOL_OPTIONS);
  const [selectedToolIds, setSelectedToolIds] = useState<string[]>(['integritydesk']);
  const [thresholdLoading, setThresholdLoading] = useState(true);
  const [modesLoading, setModesLoading] = useState(true);
  const [toolsLoading, setToolsLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [isDragOver, setIsDragOver] = useState(false);
  const [progress, setProgress] = useState(0);
  const [scanIndex, setScanIndex] = useState(0);
  const [animateFiles, setAnimateFiles] = useState(false);
  const [dragCount, setDragCount] = useState(0);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [starterFile, setStarterFile] = useState<File | null>(null);
  const starterFileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  const startPolling = useCallback((jobId: string) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const s = await axios.get(`${API}/api/jobs/${jobId}`);
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
  const selectedAssignmentMode = useMemo(() => assignmentModes.find((m) => m.id === selectedAssignmentModeId), [assignmentModes, selectedAssignmentModeId]);
  const hasMixedZipSelection = useMemo(() => files.length > 1 && files.some((f) => f.name.toLowerCase().endsWith('.zip')), [files]);
  const canRunCheck = useMemo(() => {
    if (uploading || hasMixedZipSelection || selectedToolIds.length === 0) return false;
    if (selectedToolIds.includes('integritydesk') && activeEngines.length === 0) return false;
    return zipFile ? true : files.length >= 2;
  }, [activeEngines.length, files.length, hasMixedZipSelection, selectedToolIds, uploading, zipFile]);

  const uploadFormStorageKey = useMemo(
    () => `${UPLOAD_FORM_STORAGE_KEY}:${user?.tenant_id || 'no-tenant'}:${user?.id || 'guest'}`,
    [user?.id, user?.tenant_id],
  );

  useEffect(() => {
    let active = true;
    axios.get(`${API}/api/upload-settings`).then((res) => {
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

  useEffect(() => {
    let active = true;
    axios.get(`${API}/api/benchmark-tools`).then((res) => {
      if (!active) return;
      const t = Array.isArray(res.data?.tools) ? res.data.tools : [];
      const tools = t.length > 0 ? t : FALLBACK_TOOL_OPTIONS;
      setToolOptions(tools);
      if (!tools.some((x: DetectionTool) => x.id === 'integritydesk')) setSelectedToolIds(['integritydesk']);
    }).catch(() => { if (active) { setToolOptions(FALLBACK_TOOL_OPTIONS); setSelectedToolIds(['integritydesk']); } })
      .finally(() => { if (active) setToolsLoading(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (authLoading || typeof window === 'undefined') return;
    try {
      const raw = window.localStorage.getItem(uploadFormStorageKey);
      if (!raw) return;
      const p = JSON.parse(raw);
      if (typeof p.course_name === 'string') setCourseName(p.course_name);
      if (typeof p.assignment_name === 'string') setAssignmentName(p.assignment_name);
      if (typeof p.assignment_mode === 'string') setSelectedAssignmentModeId(p.assignment_mode);
    } catch { }
  }, [authLoading, uploadFormStorageKey]);

  useEffect(() => {
    if (authLoading || typeof window === 'undefined') return;
    window.localStorage.setItem(uploadFormStorageKey, JSON.stringify({
      course_name: courseName, assignment_name: assignmentName, assignment_mode: selectedAssignmentModeId,
    }));
  }, [assignmentName, authLoading, courseName, selectedAssignmentModeId, uploadFormStorageKey]);

  useEffect(() => {
    if (modesLoading || assignmentModes.length === 0) return;
    if (!courseName.trim() && !assignmentName.trim() && files.length === 0) { setModeSuggestion(null); return; }
    const timer = window.setTimeout(async () => {
      setModeSuggesting(true);
      try {
        const res = await axios.post(`${API}/api/assignment-modes/suggest`, {
          course_name: courseName, assignment_name: assignmentName, filenames: files.map((f) => f.name),
        });
        setModeSuggestion(res.data);
      } catch { setModeSuggestion(null); } finally { setModeSuggesting(false); }
    }, 450);
    return () => window.clearTimeout(timer);
  }, [assignmentModes.length, assignmentName, courseName, files, modesLoading]);

  const handleDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault(); setIsDragOver(false);
    const f = Array.from(e.dataTransfer.files);
    if (f.length) setFiles(f);
  }, []);

  const handleSubmit = async () => {
    setError('');
    if (hasMixedZipSelection) { setError('Upload either one ZIP archive or multiple files, not both.'); return; }
    if (selectedToolIds.length === 0) { setError('Select at least one tool.'); return; }
    if (selectedToolIds.includes('integritydesk') && activeEngines.length === 0) { setError('Select at least one engine.'); return; }
    if (!zipFile && files.length < 2) { setError('Select at least 2 submission files.'); return; }
    setUploading(true);
    const fd = new FormData();
    if (zipFile) fd.append('file', zipFile); else files.forEach((f) => fd.append('files', f));
    fd.append('course_name', courseName || assignmentName || 'Assignment Check');
    fd.append('assignment_name', assignmentName || courseName || 'Assignment Check');
    fd.append('assignment_mode', selectedAssignmentModeId);
    fd.append('threshold', String(threshold));
    fd.append('engine_keys', JSON.stringify(activeEngines));
    fd.append('tool_ids', JSON.stringify(selectedToolIds));
    try {
      const url = zipFile ? `${API}/api/upload-zip` : `${API}/api/upload`;
      const res = await axios.post(url, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      const jobId = res.data?.job_id;
      if (!jobId) { setUploading(false); setError('Upload completed but no job ID returned.'); return; }
      if (res.data?.status === 'completed') { router.push(`/results/${jobId}`); return; }
      startPolling(jobId);
    } catch (err) { setUploading(false); setError(getApiErrorMessage(err, 'Upload failed')); }
  };

  const toggleEngine = useCallback((k: string) =>
    setActiveEngines((c) => c.includes(k) ? c.filter((x) => x !== k) : [...c, k]), []);
  const toggleTool = useCallback((id: string) =>
    setSelectedToolIds((c) => c.includes(id) ? c.filter((x) => x !== id) : [...c, id]), []);

  return (
    <DashboardLayout>
      <div className="px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
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
                      New Assignment Check
                    </h1>
                  </div>
                  <p className="max-w-3xl text-sm leading-7 text-[var(--text-secondary)]">
                    Upload submission files, configure detection settings, and run a full similarity analysis.
                  </p>
                </div>
                <div className="flex flex-wrap gap-3">
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
                      : <><Zap size={16} />Run Check<ArrowRight size={15} className="opacity-70" /></>}
                  </button>
                </div>
              </div>
            </div>
          </section>

          {/* Context Fields */}
          <div className="grid gap-4 lg:grid-cols-2 mb-4">
            <div className="rounded-2xl bg-white p-5 overflow-hidden" style={cardShadow}>
              <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2 block">Course</label>
              <input
                type="text"
                placeholder="e.g. CS 101 - Introduction to Programming"
                value={courseName}
                onChange={(e) => setCourseName(e.target.value)}
                className="w-full h-11 px-4 rounded-xl border text-sm outline-none transition-all"
                style={{ borderColor: '#e2e8f0', background: '#f8fafc' }}
              />
            </div>
            <div className="rounded-2xl bg-white p-5 overflow-hidden" style={cardShadow}>
              <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2 block">Assignment</label>
              <input
                type="text"
                placeholder="e.g. Assignment 3 - Sorting Algorithms"
                value={assignmentName}
                onChange={(e) => setAssignmentName(e.target.value)}
                className="w-full h-11 px-4 rounded-xl border text-sm outline-none transition-all"
                style={{ borderColor: '#e2e8f0', background: '#f8fafc' }}
              />
            </div>
          </div>

          {/* Upload Card */}
          <div className="rounded-2xl bg-white mb-4 overflow-hidden relative transition-all duration-300" style={cardShadow}>
            <div
              onDrop={handleDrop}
              onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
              onDragLeave={() => setIsDragOver(false)}
              className="relative"
            >
              {/* Dot-grid bg — only visible in empty state */}
              {files.length === 0 && (
                <div className="absolute inset-0 pointer-events-none" style={{ ...dotGrid, opacity: 0.5 }} />
              )}

              {/* Drag ring */}
              {isDragOver && (
                <div className="absolute inset-0 z-10 pointer-events-none rounded-t-2xl"
                  style={{ boxShadow: 'inset 0 0 0 2px #3b82f6', background: 'rgba(239,246,255,0.5)' }} />
              )}

              {files.length === 0 ? (
                /* ── Empty drop zone ── */
                <div
                  className="relative flex flex-col items-center justify-center text-center px-8 py-20 cursor-pointer"
                  onClick={() => fileInputRef.current?.click()}
                >
                  <div
                    className="w-[72px] h-[72px] rounded-[20px] flex items-center justify-center mb-5 transition-all duration-300"
                    style={{
                      background: isDragOver ? '#dbeafe' : '#f8fafc',
                      boxShadow: isDragOver
                        ? '0 0 0 10px rgba(59,130,246,0.08), 0 1px 3px rgba(0,0,0,0.06)'
                        : '0 0 0 10px #f1f5f9, 0 1px 3px rgba(0,0,0,0.06)',
                      transform: isDragOver ? 'scale(1.08)' : 'scale(1)',
                    }}
                  >
                    <UploadIcon size={28} style={{ color: isDragOver ? '#3b82f6' : '#94a3b8', transition: 'color 0.2s' }} />
                  </div>
                  <h3 className="text-[15px] font-semibold text-slate-800 mb-1.5">
                    {isDragOver ? 'Release to upload' : 'Drop submission files here'}
                  </h3>
                  <p className="text-sm text-slate-400 mb-6 max-w-sm leading-relaxed">
                    Upload multiple code files for comparison, or a single ZIP archive containing all submissions
                  </p>
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click(); }}
                    className="inline-flex items-center gap-2 rounded-xl border px-4 py-2 text-sm font-medium transition-all duration-200 hover:bg-blue-50 hover:border-blue-300 hover:text-blue-600"
                    style={{ borderColor: '#e2e8f0', color: '#475569', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}
                  >
                    <FileUp size={13} />Browse files
                  </button>
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
                          <div className="w-5 h-5 rounded-md flex items-center justify-center" style={{ background: '#fef3c7' }}>
                            <FolderArchive size={11} style={{ color: '#d97706' }} />
                          </div>
                          <span className="text-sm font-semibold text-slate-700">ZIP Archive</span>
                        </>
                      ) : (
                        <>
                          <span className="inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold text-white" style={{ background: '#2563eb' }}>
                            {selectedFiles.length}
                          </span>
                          <span className="text-sm font-semibold text-slate-700">
                            {selectedFiles.length} {selectedFiles.length === 1 ? 'file' : 'files'} selected
                          </span>
                          {files.length < 2 && (
                            <span className="text-[11px] font-semibold rounded-full px-2 py-0.5" style={{ background: '#fef3c7', color: '#b45309' }}>
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
                      <div className="flex items-center gap-3 rounded-xl px-4 py-3.5"
                        style={{ background: '#fffbeb', border: '1px solid #fde68a' }}>
                        <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0" style={{ background: '#fef3c7' }}>
                          <FolderArchive size={15} style={{ color: '#d97706' }} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-slate-800 truncate">{zipFile.name}</p>
                          <p className="text-xs font-medium" style={{ color: '#b45309' }}>{formatSize(zipFile.size)}</p>
                        </div>
                      </div>
                    ) : (
                      selectedFiles.map((f, i) => {
                        const c = getExtColor(f.name);
                        return (
                          <div
                            key={i}
                            className="flex items-center gap-3 rounded-xl border px-3 py-2.5 group/row transition-all duration-150 hover:border-slate-200"
                            style={{ borderColor: '#f1f5f9', background: '#f8fafc' }}
                            onMouseEnter={(e) => { e.currentTarget.style.background = '#ffffff'; }}
                            onMouseLeave={(e) => { e.currentTarget.style.background = '#f8fafc'; }}
                          >
                            <div className="w-8 h-8 rounded-lg flex items-center justify-center text-[9px] font-bold shrink-0"
                              style={{ background: c.bg, color: c.text }}>
                              {getExt(f.name)}
                            </div>
                            <span className="flex-1 text-sm font-medium text-slate-700 truncate">{f.name}</span>
                            <span className="text-xs text-slate-400 shrink-0 mr-1">{formatSize(f.size)}</span>
                            <button
                              onClick={(e) => { e.stopPropagation(); setFiles(files.filter((_, j) => j !== i)); }}
                              className="opacity-0 group-hover/row:opacity-100 w-6 h-6 flex items-center justify-center rounded-lg transition-all shrink-0 hover:bg-red-50"
                              style={{ color: '#cbd5e1' }}
                              onMouseEnter={(e) => { e.currentTarget.style.color = '#f87171'; }}
                              onMouseLeave={(e) => { e.currentTarget.style.color = '#cbd5e1'; }}
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
                <button onClick={() => setError('')} className="text-red-300 hover:text-red-500 transition-colors shrink-0"><X size={13} /></button>
              </div>
            )}
            {hasMixedZipSelection && (
              <div className="border-t border-amber-100 bg-amber-50 px-5 py-3 flex items-center gap-2">
                <AlertCircle size={13} className="text-amber-500 shrink-0" />
                <p className="text-sm text-amber-700">Remove the ZIP or the other files — can't mix both.</p>
              </div>
            )}
          </div>

          {/* Config */}
          <div className="grid gap-4 lg:grid-cols-2">

            {/* Tools */}
            <div className="rounded-2xl bg-white overflow-hidden" style={cardShadow}>
              <div className="p-5">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2.5">
                    <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: '#f1f5f9' }}>
                      <Settings2 size={13} style={{ color: '#64748b' }} />
                    </div>
                    <span className="text-sm font-semibold text-slate-800">Detection Tools</span>
                  </div>
                  {!toolsLoading && toolOptions.length > 1 && (
                    <button
                      type="button"
                      onClick={() => setSelectedToolIds(
                        selectedToolIds.length === toolOptions.length ? [] : toolOptions.map((t) => t.id)
                      )}
                      className="text-xs font-medium text-slate-400 hover:text-blue-600 transition-colors"
                    >
                      {selectedToolIds.length === toolOptions.length ? 'Unselect all' : 'Select all'}
                    </button>
                  )}
                </div>

                {toolsLoading ? (
                  <div className="flex items-center gap-2 text-sm text-slate-400 py-3">
                    <Loader2 size={13} className="animate-spin" /> Loading tools…
                  </div>
                ) : (
                  <div className="space-y-1.5">
                    {toolOptions.map((tool) => {
                      const on = selectedToolIds.includes(tool.id);
                      return (
                        <button
                          key={tool.id}
                          type="button"
                          onClick={() => toggleTool(tool.id)}
                          className="w-full flex items-center gap-3 rounded-xl border px-3.5 py-3 text-left transition-all duration-200"
                          style={on
                            ? { borderColor: '#bfdbfe', background: '#eff6ff' }
                            : { borderColor: '#f1f5f9', background: '#f8fafc' }}
                        >
                          <div
                            className="w-4 h-4 rounded flex items-center justify-center border-2 transition-all duration-200 shrink-0"
                            style={on ? { borderColor: '#2563eb', background: '#2563eb' } : { borderColor: '#cbd5e1', background: 'white' }}
                          >
                            {on && <Check size={9} className="text-white" strokeWidth={3} />}
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-semibold" style={{ color: on ? '#1d4ed8' : '#374151' }}>{tool.name}</p>
                            {tool.desc && <p className="text-xs text-slate-400 truncate">{tool.desc}</p>}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
              {!toolsLoading && selectedToolIds.length === 0 && (
                <div className="border-t border-amber-100 bg-amber-50 px-5 py-3 flex items-center gap-2">
                  <AlertCircle size={12} className="text-amber-500" />
                  <p className="text-xs text-amber-700">Select at least one tool to proceed.</p>
                </div>
              )}
            </div>

            {/* Mode - Only show for IntegrityDesk (assignment modes are specific to IntegrityDesk fusion engine) */}
            {selectedToolIds.includes('integritydesk') && (
              <div className="rounded-2xl bg-white overflow-hidden" style={cardShadow}>
              <div className="p-5">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2.5">
                    <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: '#f1f5f9' }}>
                      <Layers3 size={13} style={{ color: '#64748b' }} />
                    </div>
                    <span className="text-sm font-semibold text-slate-800">Detection Mode</span>
                  </div>
                  {selectedAssignmentMode?.version && (
                    <span className="text-[10px] font-bold tracking-wider rounded-md px-2 py-0.5" style={{ background: '#f1f5f9', color: '#94a3b8' }}>
                      v{selectedAssignmentMode.version}
                    </span>
                  )}
                </div>

                {modesLoading ? (
                  <div className="flex items-center gap-2 text-sm text-slate-400 py-3">
                    <Loader2 size={13} className="animate-spin" /> Loading…
                  </div>
                ) : assignmentModes.length > 0 ? (
                  <select
                    value={selectedAssignmentModeId || ''}
                    onChange={(e) => setSelectedAssignmentModeId(e.target.value)}
                    className="w-full h-11 px-3.5 rounded-xl border text-sm font-medium text-slate-800 outline-none transition-all duration-200 focus:ring-2 focus:ring-blue-400/15"
                    style={{ borderColor: '#e2e8f0', background: '#f8fafc' }}
                  >
                    {assignmentModes.map((mode) => {
                      const adv = mode.access === 'advanced';
                      const label = mode.overlay ? 'Overlay' : adv ? 'Advanced' : mode.category || 'Mode';
                      return (
                        <option key={mode.id} value={mode.id}>
                          {mode.name} ({label}){mode.pipelines?.length ? ` · ${mode.pipelines.join(' + ')}` : ''}
                        </option>
                      );
                    })}
                  </select>
                ) : (
                  <div className="h-11 flex items-center px-3.5 rounded-xl border text-sm text-slate-400"
                    style={{ borderColor: '#e2e8f0', background: '#f8fafc' }}>
                    Mode catalog unavailable
                  </div>
                )}

                {selectedAssignmentMode?.context && (
                  <p className="mt-2.5 text-xs text-slate-500 leading-relaxed">{selectedAssignmentMode.context}</p>
                )}

                {selectedAssignmentMode?.warnings?.length ? (
                  <div className="mt-3 flex items-start gap-2 rounded-xl px-3.5 py-3"
                    style={{ background: '#fffbeb', border: '1px solid #fde68a' }}>
                    <AlertCircle size={13} style={{ color: '#f59e0b' }} className="mt-0.5 shrink-0" />
                    <p className="text-xs leading-relaxed" style={{ color: '#92400e' }}>{selectedAssignmentMode.warnings[0]}</p>
                  </div>
                ) : null}

                {/* AI Suggestion */}
                <div
                  className="mt-3 rounded-xl px-3.5 py-3.5 transition-all duration-300"
                  style={modeSuggestion
                    ? { background: 'linear-gradient(135deg, #eff6ff, #f0f9ff)', border: '1px solid #bfdbfe' }
                    : { background: '#f8fafc', border: '1px solid #f1f5f9' }}
                >
                  <div className="flex items-center gap-1.5 mb-2">
                    <Sparkles size={11} style={{ color: modeSuggestion ? '#60a5fa' : '#cbd5e1' }} />
                    <span className="text-[10px] font-bold uppercase tracking-[0.1em] text-slate-400">AI Suggestion</span>
                  </div>
                  {modeSuggesting ? (
                    <div className="flex items-center gap-2 text-xs text-slate-400">
                      <Loader2 size={11} className="animate-spin" /> Analyzing context…
                    </div>
                  ) : modeSuggestion ? (
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold leading-snug" style={{ color: '#1e3a5f' }}>
                          {modeSuggestion.recommended_mode_name}
                          {typeof modeSuggestion.confidence === 'number' && (
                            <span className="ml-1.5 text-[11px] font-normal" style={{ color: '#60a5fa' }}>
                              {Math.round(modeSuggestion.confidence * 100)}% match
                            </span>
                          )}
                        </p>
                        {modeSuggestion.reasons?.[0] && (
                          <p className="text-xs mt-0.5 leading-relaxed" style={{ color: '#3b82f6' }}>
                            {modeSuggestion.reasons[0]}
                          </p>
                        )}
                      </div>
                      <button
                        type="button"
                        onClick={() => setSelectedAssignmentModeId(modeSuggestion.recommended_mode_id)}
                        className="shrink-0 inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold text-white transition-all duration-200 hover:opacity-90"
                        style={{ ...blueBg, boxShadow: '0 1px 3px rgba(37,99,235,0.3)' }}
                      >
                        <Check size={10} strokeWidth={3} />Apply
                      </button>
                    </div>
                  ) : (
                    <p className="text-xs text-slate-400 leading-relaxed">
                      Add files or assignment details for a mode suggestion.
                    </p>
                  )}
                </div>
              </div>
            </div>
            )}
          </div>

          {/* Ready Banner */}
          {canRunCheck && (
            <div className="mt-4 rounded-2xl flex items-center justify-between px-5 py-4" style={blueCardBg}>
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-xl flex items-center justify-center" style={{ background: '#dbeafe' }}>
                  <Zap size={14} style={{ color: '#2563eb' }} />
                </div>
                <div>
                  <p className="text-sm font-semibold" style={{ color: '#1e3a5f' }}>
                    {zipFile ? '1 archive' : `${selectedFiles.length} files`} ready to analyze
                  </p>
                  <p className="text-xs" style={{ color: '#60a5fa' }}>
                    {selectedToolIds.length} tool{selectedToolIds.length !== 1 ? 's' : ''} · {activeEngines.length} engine{activeEngines.length !== 1 ? 's' : ''} active
                  </p>
                </div>
              </div>
              <button
                onClick={handleSubmit}
                disabled={uploading}
                className="inline-flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold text-white transition-all duration-200 disabled:opacity-60"
                style={{ ...blueBg, ...btnShadow }}
              >
                {uploading
                  ? <><Loader2 size={14} className="animate-spin" />Analyzing…</>
                  : <><Zap size={14} />Run Check<ArrowRight size={13} className="opacity-70" /></>}
              </button>
            </div>
          )}

        </div>
      </div>
    </DashboardLayout>
  );
}