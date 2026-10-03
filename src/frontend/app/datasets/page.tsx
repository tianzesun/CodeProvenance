'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { useAuth } from '@/components/AuthProvider';
import { Modal, PageHeader } from '@/components/saas/SaaSPrimitives';
import { useState, useEffect, useCallback, useMemo, useRef, FormEvent, ReactNode } from 'react';
import { apiClient } from '@/lib/apiClient';
import { Database, Plus, Loader2, Grid, List, Search, CheckCircle2, AlertCircle } from 'lucide-react';

// ─── Types ─────────────────────────────────────────────────────────────────────

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

type DatasetForm = {
  name: string;
  description: string;
  language: string;
  /** Kept as text while typing; validated on submit. (A number state snapped an emptied box back to 10.) */
  numFiles: string;
  similarityType: string;
};

// ─── Constants ─────────────────────────────────────────────────────────────────

const INITIAL_FORM: DatasetForm = {
  name: '',
  description: '',
  language: 'python',
  numFiles: '10',
  similarityType: 'type1_exact',
};

const SIMILARITY_HELP: Record<string, string> = {
  type1_exact: 'Creates identical code segments for testing exact copy detection.',
  type2_renamed: 'Generates code with renamed variables and functions.',
  type3_modified: 'Produces code with added comments, reordered statements, or modified structure.',
  type4_semantic: 'Creates functionally equivalent code with different algorithms or syntax.',
  token_similarity: 'Focuses on programming-language token patterns and usage.',
  structural_similarity: 'Emphasizes code organization and structural similarities.',
  semantic_similarity: 'Generates conceptually similar solutions using different approaches.',
};

const NAME_PATTERN = /^[A-Za-z0-9][A-Za-z0-9 _.-]{1,63}$/;
const MIN_FILES = 5;
const MAX_FILES = 100;
const VIEW_STORAGE_KEY = 'integritydesk-datasets-view-v1';

const FIELD_CLASS =
  'w-full px-3 py-2 border border-slate-200 rounded-xl bg-white text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 dark:border-slate-800 dark:bg-slate-900 dark:text-white dark:placeholder:text-slate-500';

// ─── Helpers ───────────────────────────────────────────────────────────────────

const REFERENCE_HEADERS = ['x-correlation-id', 'x-request-id'];

/**
 * Generic, status-keyed text; the server's own wording is not shown. A correlation id is appended
 * when the backend sends one.
 */
function describeError(error: unknown, fallback: string): string {
  const response = (error as { response?: { status?: unknown; headers?: unknown } } | null)?.response;
  const status = typeof response?.status === 'number' ? response.status : undefined;
  const headers = (response?.headers ?? {}) as Record<string, unknown>;
  const reference = REFERENCE_HEADERS.map((name) => headers[name]).find(
    (value): value is string => typeof value === 'string' && value.length > 0
  );

  let message = fallback;
  if (status === 401) message = 'Your session has expired. Please sign in again.';
  else if (status === 403) message = 'You don’t have permission to do that. Administrator access is required.';
  else if (status === 409) message = 'A dataset with that name already exists. Choose a different name.';
  else if (status === 400 || status === 422) message = 'The server rejected those values. Check the name and file count and try again.';
  else if (status === 429) message = 'Too many requests. Please wait a moment and try again.';

  return reference ? `${message} (Reference: ${reference})` : message;
}

function normalizeDatasets(data: unknown): Dataset[] {
  const list = (data as { datasets?: unknown } | null)?.datasets;
  return Array.isArray(list) ? (list.filter((d) => d && typeof d === 'object' && (d as Dataset).id) as Dataset[]) : [];
}

function formatDate(value?: string): string {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat('en-US', { dateStyle: 'medium' }).format(date);
}

const safeStorage = {
  get(key: string): string | null {
    if (typeof window === 'undefined') return null;
    try {
      return window.localStorage.getItem(key);
    } catch {
      return null;
    }
  },
  set(key: string, value: string): void {
    if (typeof window === 'undefined') return;
    try {
      window.localStorage.setItem(key, value);
    } catch {
      // Storage unavailable; the preference simply won't persist.
    }
  },
};

/** The server still has to enforce all of this; these checks just save a round trip. */
function validateForm(form: DatasetForm, existing: Dataset[]): string | null {
  const name = form.name.trim();
  if (!NAME_PATTERN.test(name)) {
    return 'Use 2–64 characters: letters, numbers, spaces, dots, dashes and underscores, starting with a letter or number.';
  }
  if (existing.some((d) => d.name.trim().toLowerCase() === name.toLowerCase())) {
    return 'A dataset with that name already exists. Choose a different name.';
  }
  const files = Number(form.numFiles);
  if (!Number.isInteger(files) || files < MIN_FILES || files > MAX_FILES) {
    return `Number of files must be a whole number from ${MIN_FILES} to ${MAX_FILES}.`;
  }
  return null;
}

/** The control sits inside the <label>, so the two are associated for screen readers. */
function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <div>
      <label className="block">
        <span className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">{label}</span>
        {children}
      </label>
      {hint && <p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400">{hint}</p>}
    </div>
  );
}

function DatasetBadges({ dataset }: { dataset: Dataset }) {
  const pill = 'inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold';
  return (
    <>
      <span className={`${pill} bg-slate-100 text-slate-700 dark:bg-slate-500/15 dark:text-slate-300`}>
        {dataset.language?.toUpperCase() || 'Mixed'}
      </span>
      {dataset.size && (
        <span className={`${pill} bg-slate-100 text-slate-700 dark:bg-slate-500/15 dark:text-slate-300`}>
          {dataset.size}
        </span>
      )}
      {typeof dataset.case_count === 'number' && (
        <span className={`${pill} bg-slate-100 text-slate-700 dark:bg-slate-500/15 dark:text-slate-300`}>
          {dataset.case_count.toLocaleString('en-US')} case{dataset.case_count === 1 ? '' : 's'}
        </span>
      )}
      {/* Non-demo datasets used to carry no badge, so the two kinds were only distinguishable by a missing label. */}
      <span
        className={`${pill} ${
          dataset.is_demo
            ? 'bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300'
            : 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300'
        }`}
      >
        {dataset.is_demo ? 'Demo' : 'Preset'}
      </span>
    </>
  );
}

// ─── Page ──────────────────────────────────────────────────────────────────────

export default function DatasetsPage() {
  const { user, loading: authLoading } = useAuth();
  const userId = user?.id;
  // Creating datasets calls an admin-only endpoint; the button was shown to everyone, so a professor
  // could fill in the form and only then be refused. (The server must enforce this regardless.)
  const isAdmin = user?.role === 'admin';

  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [notice, setNotice] = useState<{ tone: 'success' | 'warning'; text: string } | null>(null);
  const [query, setQuery] = useState('');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [creatingDataset, setCreatingDataset] = useState(false);
  const [createError, setCreateError] = useState('');
  const [datasetForm, setDatasetForm] = useState<DatasetForm>(INITIAL_FORM);

  const requestIdRef = useRef(0);
  const noticeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleDatasetFormChange = useCallback((field: keyof DatasetForm, value: string) => {
    setDatasetForm((prev) => ({ ...prev, [field]: value }));
    setCreateError('');
  }, []);

  const similarityHelpText = SIMILARITY_HELP[datasetForm.similarityType] || '';

  // The benchmark-tools request this page also made was never used, so it is gone.
  const loadDatasets = useCallback(async (signal?: AbortSignal): Promise<boolean> => {
    const requestId = ++requestIdRef.current;
    try {
      const res = await apiClient.get('/api/benchmark-datasets', { signal });
      if (requestId !== requestIdRef.current) return false;
      setDatasets(normalizeDatasets(res.data));
      setLoadError('');
      return true;
    } catch (err) {
      if (signal?.aborted || requestId !== requestIdRef.current) return false;
      setLoadError(describeError(err, 'Failed to load datasets. Please try again.'));
      return false;
    } finally {
      if (requestId === requestIdRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Without a user the page used to sit on "Loading datasets…" forever.
    if (authLoading) return;
    if (!userId) {
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    loadDatasets(controller.signal);
    return () => controller.abort();
  }, [authLoading, userId, loadDatasets]);

  // Restore the chosen layout.
  useEffect(() => {
    const saved = safeStorage.get(VIEW_STORAGE_KEY);
    if (saved === 'grid' || saved === 'list') setViewMode(saved);
  }, []);

  const changeView = (mode: 'grid' | 'list') => {
    setViewMode(mode);
    safeStorage.set(VIEW_STORAGE_KEY, mode);
  };

  useEffect(() => () => {
    if (noticeTimerRef.current) clearTimeout(noticeTimerRef.current);
  }, []);

  const showNotice = (tone: 'success' | 'warning', text: string) => {
    setNotice({ tone, text });
    if (noticeTimerRef.current) clearTimeout(noticeTimerRef.current);
    noticeTimerRef.current = setTimeout(() => setNotice(null), 6000);
  };

  const filteredDatasets = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return datasets;
    return datasets.filter((d) =>
      [d.name, d.desc, d.language, d.created_by].some((value) => String(value || '').toLowerCase().includes(q))
    );
  }, [datasets, query]);

  const openCreateModal = () => {
    setCreateError('');
    setDatasetForm(INITIAL_FORM);
    setShowCreateModal(true);
  };

  const closeCreateModal = () => {
    // Closing mid-request would hide the outcome of a creation that is still running.
    if (creatingDataset) return;
    setShowCreateModal(false);
    setCreateError('');
    setDatasetForm(INITIAL_FORM);
  };

  const createDemoDataset = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (creatingDataset) return;

    const problem = validateForm(datasetForm, datasets);
    if (problem) {
      setCreateError(problem);
      return;
    }

    setCreatingDataset(true);
    setCreateError('');

    try {
      await apiClient.post('/api/admin/create-demo-dataset', {
        ...datasetForm,
        name: datasetForm.name.trim(),
        description: datasetForm.description.trim(),
        numFiles: Number(datasetForm.numFiles),
      });
    } catch (err) {
      // Shown inside the dialog. It used to go to the page banner, behind the open modal, so a failed
      // creation looked like nothing had happened.
      setCreateError(describeError(err, 'Failed to create the demo dataset. Please try again.'));
      setCreatingDataset(false);
      return;
    }

    // The list is always refreshed after a successful creation (it only was if the response contained
    // a `files_created` field).
    setShowCreateModal(false);
    setDatasetForm(INITIAL_FORM);
    setCreatingDataset(false);
    const refreshed = await loadDatasets();
    showNotice(
      refreshed ? 'success' : 'warning',
      refreshed ? 'Dataset created.' : 'Dataset created, but the list couldn’t refresh. Reload the page to see it.'
    );
  };

  return (
    <DashboardLayout>
      <div className="theme-page-container space-y-6">
        <PageHeader
          eyebrow="Datasets"
          eyebrowStyle="badge"
          title="Dataset Manager"
          description="Manage benchmark and demonstration datasets for testing detection engines."
          action={
            isAdmin ? (
              <button
                type="button"
                onClick={openCreateModal}
                className="theme-button-primary inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition"
              >
                <Plus size={16} aria-hidden="true" />
                Create New Dataset
              </button>
            ) : null
          }
        />

        <div className="space-y-3">
          {loadError && (
            <div
              role="alert"
              className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300"
            >
              <AlertCircle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
              <span className="flex-1">{loadError}</span>
              <button
                type="button"
                onClick={() => {
                  setLoading(true);
                  loadDatasets();
                }}
                className="inline-flex h-10 shrink-0 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
              >
                Retry
              </button>
            </div>
          )}

          {notice && (
            <div
              role="status"
              className={`flex items-start gap-3 rounded-2xl border px-4 py-3 text-sm ${
                notice.tone === 'success'
                  ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-300'
                  : 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-300'
              }`}
            >
              {notice.tone === 'success' ? (
                <CheckCircle2 size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
              ) : (
                <AlertCircle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
              )}
              {notice.text}
            </div>
          )}
        </div>

        {/* Search + view toggle */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <p className="text-sm text-slate-600 dark:text-slate-400" aria-live="polite">
              {query.trim()
                ? `${filteredDatasets.length} of ${datasets.length} dataset${datasets.length !== 1 ? 's' : ''}`
                : `${datasets.length} dataset${datasets.length !== 1 ? 's' : ''} available`}
            </p>
            {datasets.length > 0 && (
              <label className="flex w-full items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-500 focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-500/20 sm:w-64 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
                <Search size={14} aria-hidden="true" />
                <input
                  type="search"
                  name="dataset-search"
                  autoComplete="off"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search datasets…"
                  aria-label="Search datasets"
                  className="w-full bg-transparent text-slate-900 placeholder:text-slate-400 focus:outline-none dark:text-white dark:placeholder:text-slate-500"
                />
              </label>
            )}
          </div>
          <div className="flex items-center self-start bg-slate-100 rounded-xl p-1 dark:bg-slate-900 sm:self-auto" role="group" aria-label="Layout">
            <button
              type="button"
              onClick={() => changeView('grid')}
              aria-pressed={viewMode === 'grid'}
              className={`p-2 rounded-lg transition ${
                viewMode === 'grid' ? 'bg-white shadow-sm text-blue-600 dark:bg-slate-800' : 'text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'
              }`}
              aria-label="Grid view"
            >
              <Grid size={18} aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={() => changeView('list')}
              aria-pressed={viewMode === 'list'}
              className={`p-2 rounded-lg transition ${
                viewMode === 'list' ? 'bg-white shadow-sm text-blue-600 dark:bg-slate-800' : 'text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'
              }`}
              aria-label="List view"
            >
              <List size={18} aria-hidden="true" />
            </button>
          </div>
        </div>

        {loading ? (
          <div role="status" className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            <span className="sr-only">Loading datasets…</span>
            {[0, 1, 2].map((index) => (
              <div
                key={index}
                className="rounded-[24px] border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950"
              >
                <div className="h-4 w-36 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
                <div className="mt-3 h-4 w-44 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
                <div className="mt-3 h-4 w-24 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
              </div>
            ))}
          </div>
        ) : datasets.length === 0 ? (
          !loadError && (
            <div className="px-5 py-16 text-center">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-slate-100 text-slate-500 dark:bg-slate-900 dark:text-slate-400">
                <Database size={22} aria-hidden="true" />
              </div>
              <h3 className="mt-4 text-base font-semibold text-slate-900 dark:text-white">No datasets found</h3>
              <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500 dark:text-slate-400">
                {isAdmin
                  ? 'Create your first demo dataset, or add one to the benchmark library.'
                  : 'No datasets have been added to the benchmark library yet.'}
              </p>
            </div>
          )
        ) : filteredDatasets.length === 0 ? (
          <div className="px-5 py-16 text-center">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-slate-100 text-slate-500 dark:bg-slate-900 dark:text-slate-400">
              <Search size={22} aria-hidden="true" />
            </div>
            <h3 className="mt-4 text-base font-semibold text-slate-900 dark:text-white">No datasets match your search</h3>
            <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500 dark:text-slate-400">
              Try a different name, language or creator.
            </p>
          </div>
        ) : viewMode === 'grid' ? (
          // Grid View
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {filteredDatasets.map((dataset) => (
              <div
                key={dataset.id}
                className="rounded-[24px] border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md dark:border-slate-800 dark:bg-slate-950"
              >
                {/* The Edit, Delete and Open buttons that used to sit here had no handlers: they looked
                    active and did nothing. They are removed until those actions exist. */}
                <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-blue-100 dark:bg-blue-500/15">
                  <Database size={18} className="text-blue-600 dark:text-blue-400" aria-hidden="true" />
                </div>

                <h3 className="text-base font-semibold text-slate-900 dark:text-white">{dataset.name}</h3>
                <p className="mt-1 line-clamp-2 text-sm leading-6 text-slate-500 dark:text-slate-400">{dataset.desc}</p>

                <div className="mt-4 flex flex-wrap gap-2">
                  <DatasetBadges dataset={dataset} />
                </div>

                <div className="mt-4 flex items-center justify-between border-t border-slate-200 pt-4 text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400">
                  <span>Created by {dataset.created_by || 'System'}</span>
                  {formatDate(dataset.created_at) && <span>{formatDate(dataset.created_at)}</span>}
                </div>
              </div>
            ))}
          </div>
        ) : (
          // List View
          <div className="space-y-3">
            {filteredDatasets.map((dataset) => (
              <div
                key={dataset.id}
                className="flex items-center gap-4 rounded-3xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-slate-300 hover:shadow-md dark:border-slate-800 dark:bg-slate-950 dark:hover:border-slate-700"
              >
                {/* Icon */}
                <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-xl bg-blue-100 dark:bg-blue-500/15">
                  <Database size={20} className="text-blue-600 dark:text-blue-400" aria-hidden="true" />
                </div>

                {/* Main Content */}
                <div className="min-w-0 flex-1">
                  <h3 className="truncate text-base font-semibold text-slate-900 dark:text-white">{dataset.name}</h3>
                  <p className="mt-0.5 truncate text-sm leading-6 text-slate-500 dark:text-slate-400">{dataset.desc}</p>

                  <div className="mt-2 flex flex-wrap items-center gap-3">
                    <DatasetBadges dataset={dataset} />
                    <span className="text-xs text-slate-500 dark:text-slate-400">
                      Created by {dataset.created_by || 'System'}
                      {formatDate(dataset.created_at) ? ` • ${formatDate(dataset.created_at)}` : ''}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create Dataset Modal */}
      {isAdmin && showCreateModal && (
        <Modal
          open={showCreateModal}
          title="Demo dataset creation"
          description="Generate synthetic datasets for testing plagiarism detection algorithms. Create custom datasets with controlled similarity patterns."
          onClose={closeCreateModal}
        >
          <form className="space-y-6" onSubmit={createDemoDataset} noValidate>
            {createError && (
              <div
                role="alert"
                className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300"
              >
                <AlertCircle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
                <span>{createError}</span>
              </div>
            )}

            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Dataset Name">
                <input
                  type="text"
                  name="dataset-name"
                  value={datasetForm.name}
                  onChange={(event) => handleDatasetFormChange('name', event.target.value)}
                  className={FIELD_CLASS}
                  placeholder="my_test_dataset"
                  maxLength={64}
                  autoComplete="off"
                  autoFocus
                  required
                />
              </Field>
              <Field label="Programming Language">
                <select
                  value={datasetForm.language}
                  onChange={(event) => handleDatasetFormChange('language', event.target.value)}
                  className={FIELD_CLASS}
                >
                  <option value="python">Python</option>
                  <option value="java">Java</option>
                  <option value="javascript">JavaScript</option>
                  <option value="cpp">C++</option>
                </select>
              </Field>
            </div>

            <Field label="Description">
              <input
                type="text"
                name="dataset-description"
                value={datasetForm.description}
                onChange={(event) => handleDatasetFormChange('description', event.target.value)}
                className={FIELD_CLASS}
                placeholder="Dataset for testing plagiarism detection"
                maxLength={500}
                autoComplete="off"
              />
            </Field>

            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Number of Files" hint={`Between ${MIN_FILES} and ${MAX_FILES}.`}>
                <input
                  type="number"
                  name="dataset-files"
                  inputMode="numeric"
                  min={MIN_FILES}
                  max={MAX_FILES}
                  step={1}
                  value={datasetForm.numFiles}
                  onChange={(event) => handleDatasetFormChange('numFiles', event.target.value)}
                  className={FIELD_CLASS}
                />
              </Field>
              <Field label="Similarity Type" hint={similarityHelpText}>
                <select
                  value={datasetForm.similarityType}
                  onChange={(event) => handleDatasetFormChange('similarityType', event.target.value)}
                  className={FIELD_CLASS}
                >
                  <option value="type1_exact">Type 1 - Exact Copy (Direct copy-paste)</option>
                  <option value="type2_renamed">Type 2 - Renamed Identifiers (Variable renaming)</option>
                  <option value="type3_modified">Type 3 - Modified Structure (Added/removed code)</option>
                  <option value="type4_semantic">Type 4 - Semantic Equivalence (Different syntax, same behavior)</option>
                  <option value="token_similarity">Token-Level Similarity (Programming style patterns)</option>
                  <option value="structural_similarity">Structural Similarity (Code organization)</option>
                  <option value="semantic_similarity">Semantic Similarity (Conceptual equivalence)</option>
                </select>
              </Field>
            </div>

            <div className="mt-6 flex justify-end gap-2">
              <button
                type="button"
                onClick={closeCreateModal}
                disabled={creatingDataset}
                className="inline-flex h-10 items-center rounded-xl px-4 text-sm font-medium text-slate-600 transition hover:bg-slate-100 disabled:opacity-60 dark:text-slate-300 dark:hover:bg-slate-900"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={creatingDataset || !datasetForm.name.trim()}
                className="inline-flex h-10 items-center gap-2 rounded-xl bg-slate-950 px-4 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:opacity-60 dark:bg-white dark:text-slate-950"
              >
                {creatingDataset ? (
                  <>
                    <Loader2 size={16} className="animate-spin" aria-hidden="true" />
                    Generating code samples...
                  </>
                ) : (
                  'Create Demo Dataset'
                )}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </DashboardLayout>
  );
}
