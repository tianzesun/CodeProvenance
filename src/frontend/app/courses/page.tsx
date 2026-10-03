'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { useAuth } from '@/components/AuthProvider';
import { Card, CardHeader, Modal, PageHeader, StatusBadge } from '@/components/saas/SaaSPrimitives';
import { apiClient } from '@/lib/apiClient';
import { buildTermOptions, courseTermLabel, type Term } from '@/lib/terms';
import { AlertTriangle, BookOpen, ChevronRight, Loader2, Pencil, Plus, Search, Trash2, X } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';

// ─── Types ─────────────────────────────────────────────────────────────────────

type Assignment = {
  id: string;
  name: string;
  term: string | null;
  assignment_type: string;
  due_at?: string | null;
};

type Course = {
  id: string;
  name: string;
  code: string | null;
  term: string | null;
  year: number | null;
  term_id: string | null;
  department: string | null;
  description?: string | null;
  assignment_count: number;
};

type Form = {
  name: string;
  code: string;
  term: string;
  year: string;
  department: string;
  description: string;
  term_id: string;
};

type AssignmentForm = { name: string; assignment_type: string; due_at: string };

/** A delete waiting for confirmation in the designed dialog (never a native confirm()). */
type PendingDelete =
  | { kind: 'course'; id: string; label: string; assignmentCount: number }
  | { kind: 'assignment'; id: string; label: string; onDeleted: () => void };

// ─── Constants ─────────────────────────────────────────────────────────────────

const EMPTY: Form = {
  name: '',
  code: '',
  term: '',
  year: '',
  department: 'Computer Science',
  description: '',
  term_id: '',
};

/** Assignment types selectable when creating an assignment. */
const ASSIGNMENT_TYPES = [
  { id: 'programming', label: 'Programming' },
  { id: 'project', label: 'Project' },
  { id: 'written', label: 'Written report' },
  { id: 'notebook', label: 'Notebook' },
  { id: 'sql', label: 'SQL / Database' },
  { id: 'quiz', label: 'Quiz' },
  { id: 'exam', label: 'Exam' },
  { id: 'lab', label: 'Lab' },
];

const EMPTY_ASSIGNMENT: AssignmentForm = { name: '', assignment_type: 'programming', due_at: '' };

const COURSE_LIMIT = 200;

const INPUT_CLASS =
  'w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white dark:placeholder:text-slate-500';

// ─── Helpers ───────────────────────────────────────────────────────────────────

const REFERENCE_HEADERS = ['x-correlation-id', 'x-request-id'];

function getErrorInfo(error: unknown): { status?: number; reference?: string } {
  const response = (error as { response?: { status?: unknown; headers?: unknown } } | null)?.response;
  if (!response || typeof response !== 'object') {
    return {};
  }

  const status = typeof response.status === 'number' ? response.status : undefined;
  const headers = (response.headers ?? {}) as Record<string, unknown>;
  const reference = REFERENCE_HEADERS.map((name) => headers[name]).find(
    (value): value is string => typeof value === 'string' && value.length > 0
  );

  return { status, reference };
}

/**
 * Generic, status-keyed text; the server's own wording is no longer echoed. A 409 (the
 * delete is refused because checks or cases still reference the item) keeps its useful
 * explanation through `conflict`. A correlation id is appended when the backend sends one.
 */
function describeError(error: unknown, fallback: string, conflict?: string): string {
  const { status, reference } = getErrorInfo(error);

  let message = fallback;
  if (status === 401) {
    message = 'Your session has expired. Please sign in again.';
  } else if (status === 403) {
    message = 'You don’t have permission to do that.';
  } else if (status === 404) {
    message = 'That item no longer exists. Refresh the page and try again.';
  } else if (status === 409) {
    message = conflict ?? 'This conflicts with existing data. Refresh the page and try again.';
  } else if (status === 429) {
    message = 'Too many requests. Please wait a moment and try again.';
  }

  return reference ? `${message} (Reference: ${reference})` : message;
}

/** The API returns either `[...]` or `{ [key]: [...] }`; always hand back an array. */
function asArray<T>(data: unknown, key: string): T[] {
  if (Array.isArray(data)) return data as T[];
  const nested = (data as Record<string, unknown> | null | undefined)?.[key];
  return Array.isArray(nested) ? (nested as T[]) : [];
}

function validateYear(value: string): string | null {
  if (!value) return null;
  const year = Number(value);
  if (!Number.isInteger(year) || year < 1900 || year > 2100) {
    return 'Year must be a whole number between 1900 and 2100.';
  }
  return null;
}

function formatDue(value?: string | null): string {
  if (!value) return 'No due date';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'No due date';
  return `Due ${new Intl.DateTimeFormat('en-US', { dateStyle: 'medium', timeStyle: 'short' }).format(date)}`;
}

// ─── Page ──────────────────────────────────────────────────────────────────────

export default function CoursesPage() {
  // Course maintenance (create / edit / delete) belongs to admins and lives in
  // Administration → Users & courses; admins are redirected off this page.
  // What remains here for professors is browsing courses and maintaining the
  // assignments inside them.
  const { user, loading: authLoading } = useAuth();
  const canManageCourses = user?.role === 'admin';

  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [termFilter, setTermFilter] = useState('all');
  const [terms, setTerms] = useState<Term[]>([]);

  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<Form>(EMPTY);
  const [descriptionTouched, setDescriptionTouched] = useState(false);
  const [formError, setFormError] = useState('');
  const [saving, setSaving] = useState(false);

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<PendingDelete | null>(null);
  const [deleteError, setDeleteError] = useState('');
  const [deleting, setDeleting] = useState(false);

  // ── Data loading ─────────────────────────────────────────────────────────────

  const loadCourses = useCallback(async (signal?: AbortSignal) => {
    try {
      const res = await apiClient.get('/api/courses', { params: { limit: COURSE_LIMIT }, signal });
      setCourses(asArray<Course>(res.data, 'courses'));
      setLoadError(null);
    } catch (err) {
      if (signal?.aborted) return;
      setLoadError(describeError(err, 'Failed to load courses. Please try again.'));
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    loadCourses(controller.signal);
    return () => controller.abort();
  }, [loadCourses]);

  useEffect(() => {
    const controller = new AbortController();

    apiClient
      .get('/api/terms', { signal: controller.signal })
      .then((res) => setTerms(Array.isArray(res.data) ? (res.data as Term[]) : []))
      .catch(() => {
        // Term registry is optional UI sugar; the course form still accepts a
        // free-text term when the endpoint is unavailable.
        if (!controller.signal.aborted) setTerms([]);
      });

    return () => controller.abort();
  }, []);

  const retryLoad = () => {
    setLoading(true);
    loadCourses();
  };

  // ── Course form ──────────────────────────────────────────────────────────────

  const openCreate = () => {
    setEditingId(null);
    setForm(EMPTY);
    setDescriptionTouched(false);
    setFormError('');
    setShowForm(true);
  };

  const openEdit = (c: Course) => {
    setEditingId(c.id);
    setForm({
      name: c.name,
      code: c.code || '',
      term: c.term || '',
      year: c.year ? String(c.year) : '',
      department: c.department || '',
      description: c.description || '',
      term_id: c.term_id || '',
    });
    setDescriptionTouched(false);
    setFormError('');
    setShowForm(true);
  };

  const closeForm = () => {
    setShowForm(false);
    setEditingId(null);
    setForm(EMPTY);
    setDescriptionTouched(false);
    setFormError('');
  };

  const updateForm = (patch: Partial<Form>) => {
    if ('description' in patch) setDescriptionTouched(true);
    setForm((f) => ({ ...f, ...patch }));
    if (formError) setFormError('');
  };

  // Picking a registered term fills in the mirrored season/year text. Picking
  // "none" clears both so the course is created without a term.
  const selectTerm = (value: string) => {
    if (!value) {
      updateForm({ term_id: '', term: '', year: '' });
      return;
    }
    const term = terms.find((t) => t.id === value);
    if (!term) {
      updateForm({ term_id: value });
      return;
    }
    updateForm({ term_id: term.id, term: term.name, year: String(term.year) });
  };

  const saveCourse = async () => {
    if (saving) return;

    if (!form.name.trim()) {
      setFormError('Course name is required.');
      return;
    }
    const yearError = validateYear(form.year);
    if (yearError) {
      setFormError(yearError);
      return;
    }

    setSaving(true);
    setFormError('');

    try {
      const payload: Record<string, unknown> = {
        name: form.name.trim(),
        code: form.code.trim() || null,
        term_id: form.term_id || null,
        term: form.term.trim() || null,
        year: form.year ? Number(form.year) : null,
        department: form.department.trim() || null,
      };
      // Editing used to always send `description: null` (the form can't know the stored
      // text), which wiped it on every save. On edit it is only sent once the user touches it.
      if (!editingId || descriptionTouched) {
        payload.description = form.description.trim() || null;
      }

      if (editingId) {
        await apiClient.put(`/api/courses/${encodeURIComponent(editingId)}`, payload);
      } else {
        await apiClient.post('/api/courses', payload);
      }
      closeForm();
      await loadCourses();
    } catch (err) {
      // Shown inside the form, next to the button that was just pressed.
      setFormError(describeError(err, 'Failed to save course.'));
    } finally {
      setSaving(false);
    }
  };

  // ── Deleting ─────────────────────────────────────────────────────────────────

  const closeDeleteDialog = () => {
    if (deleting) return;
    setPendingDelete(null);
    setDeleteError('');
  };

  /** Runs the delete the confirmation dialog was opened for. */
  const confirmDelete = async () => {
    if (!pendingDelete || deleting) return;

    const target = pendingDelete;
    setDeleting(true);
    setDeleteError('');

    try {
      if (target.kind === 'course') {
        await apiClient.delete(`/api/courses/${encodeURIComponent(target.id)}`);
        setExpandedId((current) => (current === target.id ? null : current));
      } else {
        await apiClient.delete(`/api/assignments/${encodeURIComponent(target.id)}`);
        target.onDeleted();
      }
      setPendingDelete(null);
      await loadCourses();
    } catch (err) {
      // Stay open and show the reason here. The old code closed the dialog and put the error
      // in a banner at the top of the page, which is off-screen on a long list.
      const what = target.kind === 'course' ? 'course' : 'assignment';
      setDeleteError(
        describeError(
          err,
          `Failed to delete ${what}.`,
          `This ${what} can’t be deleted while checks or cases still reference it.`
        )
      );
    } finally {
      setDeleting(false);
    }
  };

  // ── Filtering ────────────────────────────────────────────────────────────────

  const termOptions = useMemo(() => buildTermOptions(courses), [courses]);

  // Reset the term filter when the selected term no longer exists
  // (e.g. its last course was deleted or renamed).
  useEffect(() => {
    if (termFilter === 'all') return;
    if (!termOptions.some((option) => option.value === termFilter)) setTermFilter('all');
  }, [termOptions, termFilter]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return courses.filter((c) => {
      if (termFilter !== 'all' && courseTermLabel(c) !== termFilter) return false;
      if (!q) return true;
      return (
        c.name.toLowerCase().includes(q) ||
        (c.code || '').toLowerCase().includes(q) ||
        (c.department || '').toLowerCase().includes(q) ||
        courseTermLabel(c).toLowerCase().includes(q)
      );
    });
  }, [courses, search, termFilter]);

  const hasFilters = Boolean(search.trim()) || termFilter !== 'all';

  const deleteWarning = !pendingDelete
    ? ''
    : pendingDelete.kind === 'course'
      ? `This removes the course and its ${pendingDelete.assignmentCount} assignment${pendingDelete.assignmentCount === 1 ? '' : 's'}. Check history and cases keep their evidence — the delete is refused while any still reference them.`
      : 'This removes the assignment from its course. Existing checks and cases keep their evidence — the delete is refused while any still reference it.';

  // ── Render ───────────────────────────────────────────────────────────────────

  return (
    <DashboardLayout>
      <div className="theme-page-container space-y-6">
        <PageHeader
          eyebrow="Courses"
          eyebrowStyle="badge"
          title="Manage courses and assignments"
          description={
            canManageCourses
              ? 'Manage your courses and their assignments.'
              : 'Your courses and their assignments. Course details are maintained by an administrator.'
          }
          action={
            <div className="flex flex-wrap items-center gap-2">
              {canManageCourses && !showForm && (
                // The only other "add" control is at the very bottom of the list.
                <button
                  type="button"
                  onClick={openCreate}
                  className="inline-flex h-9 items-center gap-1.5 rounded-xl bg-blue-600 px-3.5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50"
                >
                  <Plus size={15} aria-hidden="true" />
                  Add course
                </button>
              )}
            </div>
          }
        />

        <div className="space-y-3">
          {loadError && courses.length > 0 && (
            <Banner
              message={loadError}
              actionLabel="Retry"
              onAction={retryLoad}
              onDismiss={() => setLoadError(null)}
            />
          )}
          {courses.length >= COURSE_LIMIT && (
            <div
              role="status"
              className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-300"
            >
              <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
              <span className="flex-1">
                Only the first {COURSE_LIMIT} courses are loaded, so some courses may be missing from this list.
              </span>
            </div>
          )}
        </div>

        <Card className="divide-y divide-slate-200 overflow-hidden dark:divide-slate-800">
          <div className="px-6 pt-6 lg:px-7 lg:pt-7">
            <CardHeader
              title="Courses"
              action={
                <div className="flex flex-wrap items-center gap-3">
                  <label className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-500 shadow-sm focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-500/20 lg:w-72 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
                    <Search size={15} aria-hidden="true" />
                    <input
                      type="search"
                      name="course-search"
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      placeholder="Search courses..."
                      autoComplete="off"
                      className="w-full bg-transparent text-slate-900 placeholder:text-slate-400 focus:outline-none dark:text-white dark:placeholder:text-slate-500"
                      aria-label="Search courses"
                    />
                  </label>
                  {termOptions.length > 1 && (
                    <select
                      value={termFilter}
                      onChange={(e) => setTermFilter(e.target.value)}
                      aria-label="Filter courses by term"
                      className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white"
                    >
                      <option value="all">All terms</option>
                      {termOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.value} ({option.count})
                        </option>
                      ))}
                    </select>
                  )}
                </div>
              }
            />
            <p role="status" className="sr-only">
              {loading ? '' : `${filtered.length} of ${courses.length} courses shown`}
            </p>
          </div>

          {showForm && (
            <CourseForm
              key={editingId ?? 'new'}
              editing={Boolean(editingId)}
              form={form}
              terms={terms}
              saving={saving}
              error={formError}
              onChange={updateForm}
              onSelectTerm={selectTerm}
              onSubmit={saveCourse}
              onCancel={closeForm}
            />
          )}

          <div>
            {loading ? (
              <div role="status" className="space-y-4 px-6 py-6 lg:px-7">
                <span className="sr-only">Loading courses…</span>
                <div className="h-4 w-36 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
                <div className="h-4 w-36 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
                <div className="h-4 w-36 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
              </div>
            ) : loadError && courses.length === 0 ? (
              // A failed load must not look like "no courses yet".
              <div className="flex flex-col items-center px-6 py-14 text-center lg:px-7">
                <div
                  role="alert"
                  className="flex w-full items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-left text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300"
                >
                  <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
                  <span className="flex-1">{loadError}</span>
                </div>
                <button
                  type="button"
                  onClick={retryLoad}
                  className="mt-4 inline-flex h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
                >
                  Try again
                </button>
              </div>
            ) : filtered.length === 0 && hasFilters ? (
              <NoMatches />
            ) : (
              <>
                {filtered.map((c) => (
                  <CourseRow
                    key={c.id}
                    course={c}
                    canManageCourses={canManageCourses}
                    expanded={expandedId === c.id}
                    onToggle={() => setExpandedId((current) => (current === c.id ? null : c.id))}
                    onEdit={() => openEdit(c)}
                    onDelete={() => {
                      setDeleteError('');
                      setPendingDelete({ kind: 'course', id: c.id, label: c.name, assignmentCount: c.assignment_count ?? 0 });
                    }}
                  >
                    {/* Mounted only while expanded, so each course loads and owns its own
                        assignment list (one shared list used to show the wrong course's
                        assignments when you expanded rows quickly). */}
                    <AssignmentPanel
                      courseId={c.id}
                      onChanged={() => loadCourses()}
                      onRequestDelete={(target) => {
                        setDeleteError('');
                        setPendingDelete({ kind: 'assignment', ...target });
                      }}
                    />
                  </CourseRow>
                ))}
                {canManageCourses ? (
                  <AddCourseCard onAdd={openCreate} />
                ) : filtered.length === 0 && !authLoading ? (
                  <CoursesReadOnlyHint />
                ) : null}
              </>
            )}
          </div>
        </Card>

        <Modal
          open={pendingDelete !== null}
          title={pendingDelete?.kind === 'course' ? 'Delete course' : 'Delete assignment'}
          onClose={closeDeleteDialog}
          footer={
            <>
              <button
                type="button"
                onClick={closeDeleteDialog}
                disabled={deleting}
                className="inline-flex h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={confirmDelete}
                disabled={deleting}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-red-600 px-4 text-sm font-semibold text-white transition hover:bg-red-700 disabled:opacity-70"
              >
                {deleting ? 'Deleting…' : 'Delete'}
              </button>
            </>
          }
        >
          <div className="flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-red-50 text-red-600 dark:bg-red-500/15 dark:text-red-300">
              <Trash2 size={18} aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-slate-900 dark:text-white">{pendingDelete?.label}</p>
              <p className="mt-1 text-sm leading-6 text-slate-600 dark:text-slate-400">{deleteWarning}</p>
              {deleteError && (
                <p
                  role="alert"
                  className="mt-3 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300"
                >
                  <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
                  <span className="flex-1">{deleteError}</span>
                </p>
              )}
            </div>
          </div>
        </Modal>
      </div>
    </DashboardLayout>
  );
}

// ─── Banner ────────────────────────────────────────────────────────────────────

function Banner({
  message,
  onDismiss,
  actionLabel,
  onAction,
}: {
  message: string;
  onDismiss: () => void;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300"
    >
      <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
      <span className="flex-1">{message}</span>
      {actionLabel && onAction && (
        <button type="button" onClick={onAction} className="shrink-0 font-semibold underline underline-offset-2">
          {actionLabel}
        </button>
      )}
      <button
        type="button"
        onClick={onDismiss}
        aria-label="Dismiss message"
        className="shrink-0 rounded p-0.5 text-red-500 opacity-60 transition hover:opacity-100 dark:text-red-400"
      >
        <X size={14} aria-hidden="true" />
      </button>
    </div>
  );
}

// ─── Form pieces ───────────────────────────────────────────────────────────────

/** The control sits inside the <label>, so the two are associated for screen readers. */
function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">{label}</span>
      {children}
    </label>
  );
}

function CourseForm({
  editing,
  form,
  terms,
  saving,
  error,
  onChange,
  onSelectTerm,
  onSubmit,
  onCancel,
}: {
  editing: boolean;
  form: Form;
  terms: Term[];
  saving: boolean;
  error: string;
  onChange: (patch: Partial<Form>) => void;
  onSelectTerm: (value: string) => void;
  onSubmit: () => void;
  onCancel: () => void;
}) {
  const ref = useRef<HTMLFormElement>(null);

  // The form opens at the top of the list, which can be far from the "Add course" card.
  useEffect(() => {
    ref.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, []);

  // A course whose term is free text (not in the term registry) used to look like "No term".
  const legacyTerm = form.term && !form.term_id ? `${form.term}${form.year ? ` ${form.year}` : ''}` : '';

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSubmit();
  };

  return (
    <form
      ref={ref}
      onSubmit={handleSubmit}
      onKeyDown={(e) => {
        if (e.key === 'Escape') onCancel();
      }}
      noValidate
      className="bg-slate-50/60 px-6 py-4 lg:px-7 dark:bg-slate-900/60"
    >
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Field label="Name *">
          <input
            type="text"
            name="name"
            value={form.name}
            onChange={(e) => onChange({ name: e.target.value })}
            placeholder="Introduction to Computer Science"
            required
            aria-required="true"
            autoFocus
            className={INPUT_CLASS}
          />
        </Field>
        <Field label="Code">
          <input
            type="text"
            name="code"
            value={form.code}
            onChange={(e) => onChange({ code: e.target.value })}
            placeholder="CSC108"
            className={INPUT_CLASS}
          />
        </Field>
        <Field label="Term">
          {terms.length > 0 ? (
            <select
              value={form.term_id}
              onChange={(e) => onSelectTerm(e.target.value)}
              className={INPUT_CLASS}
            >
              <option value="">{legacyTerm ? `${legacyTerm} (not a registered term)` : 'No term'}</option>
              {terms.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.label}
                </option>
              ))}
            </select>
          ) : (
            <input
              type="text"
              name="term"
              value={form.term}
              onChange={(e) => onChange({ term: e.target.value })}
              placeholder="Fall"
              className={INPUT_CLASS}
            />
          )}
        </Field>
        <Field label="Year">
          <input
            type="number"
            name="year"
            inputMode="numeric"
            min={1900}
            max={2100}
            step={1}
            value={form.year}
            onChange={(e) => onChange({ year: e.target.value })}
            placeholder="2026"
            disabled={terms.length > 0}
            className={`${INPUT_CLASS} disabled:bg-slate-100 disabled:text-slate-500 dark:disabled:bg-slate-800 dark:disabled:text-slate-400`}
          />
        </Field>
        <Field label="Department">
          <input
            type="text"
            name="department"
            value={form.department}
            onChange={(e) => onChange({ department: e.target.value })}
            placeholder="Computer Science"
            className={INPUT_CLASS}
          />
        </Field>
        <Field label="Description">
          <input
            type="text"
            name="description"
            value={form.description}
            onChange={(e) => onChange({ description: e.target.value })}
            placeholder="Optional"
            className={INPUT_CLASS}
          />
        </Field>
      </div>

      {error && (
        <p
          role="alert"
          className="mt-3 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300"
        >
          <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
          <span className="flex-1">{error}</span>
        </p>
      )}

      <div className="mt-4 flex items-center gap-2">
        <button
          type="submit"
          disabled={saving || !form.name.trim()}
          className="inline-flex h-10 items-center gap-2 rounded-xl bg-blue-600 px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50 disabled:opacity-50"
        >
          {saving ? 'Saving...' : editing ? 'Update' : 'Create'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="inline-flex h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

// ─── List pieces ───────────────────────────────────────────────────────────────

function AddCourseCard({ onAdd }: { onAdd: () => void }) {
  return (
    <button
      type="button"
      onClick={onAdd}
      aria-label="Add a new course"
      className="group flex w-full flex-col items-center justify-center gap-2 px-6 py-14 text-center transition hover:bg-blue-50/50 lg:px-7 dark:hover:bg-blue-500/5"
    >
      <span className="flex h-16 w-16 items-center justify-center rounded-2xl border-2 border-dashed border-slate-300 text-slate-400 transition group-hover:border-blue-400 group-hover:bg-white group-hover:text-blue-600 dark:border-slate-700 dark:group-hover:bg-slate-800 dark:group-hover:text-blue-400">
        <Plus size={36} strokeWidth={2} aria-hidden="true" />
      </span>
      <span className="mt-1 text-sm font-semibold text-slate-600 group-hover:text-blue-700 dark:text-slate-200 dark:group-hover:text-blue-400">
        Add course
      </span>
      <span className="text-xs text-slate-500 dark:text-slate-400">Create a course to organise its assignments</span>
    </button>
  );
}

/**
 * Stands in for the "Add course" card when the viewer may not create courses.
 * It keeps the empty state actionable instead of silently blank.
 */
function CoursesReadOnlyHint() {
  return (
    <div className="px-5 py-16 text-center">
      <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-slate-100 text-slate-500 dark:bg-slate-900 dark:text-slate-400">
        <BookOpen size={22} aria-hidden="true" />
      </div>
      <h3 className="mt-4 text-base font-semibold text-slate-900 dark:text-white">No courses yet</h3>
      <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500 dark:text-slate-400">
        An administrator creates and maintains courses. Once a course exists you can add
        and remove its assignments from here.
      </p>
    </div>
  );
}

function NoMatches() {
  return (
    <div className="px-5 py-16 text-center">
      <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-slate-100 text-slate-500 dark:bg-slate-900 dark:text-slate-400">
        <Search size={22} aria-hidden="true" />
      </div>
      <h3 className="mt-4 text-base font-semibold text-slate-900 dark:text-white">No courses match your filters.</h3>
      <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500 dark:text-slate-400">
        Try a different search term or term filter.
      </p>
    </div>
  );
}

function CourseRow({
  course: c,
  canManageCourses,
  expanded,
  onToggle,
  onEdit,
  onDelete,
  children,
}: {
  course: Course;
  canManageCourses: boolean;
  expanded: boolean;
  onToggle: () => void;
  onEdit: () => void;
  onDelete: () => void;
  children: ReactNode;
}) {
  const count = c.assignment_count ?? 0;
  // The term filter existed but rows never showed a term.
  const termLabel = courseTermLabel(c);
  const meta = [c.department, termLabel, `${count} ${count === 1 ? 'assignment' : 'assignments'}`].filter(Boolean);

  return (
    <div>
      <div className="flex items-center gap-4 px-6 py-4 transition hover:bg-slate-50 lg:px-7 dark:hover:bg-slate-900/50">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-700 dark:bg-blue-500/10 dark:text-blue-400">
          <BookOpen size={18} aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-semibold text-slate-900 dark:text-white">{c.name}</span>
            {c.code && (
              <span className="shrink-0 rounded bg-slate-100 px-1.5 py-0.5 text-[11px] font-bold text-slate-500 dark:bg-slate-900 dark:text-slate-400">
                {c.code}
              </span>
            )}
          </div>
          <div className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{meta.join(' · ')}</div>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {canManageCourses && (
            <>
              <button
                type="button"
                onClick={onEdit}
                aria-label={`Edit ${c.name}`}
                title="Edit course"
                className="rounded-md p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800"
              >
                <Pencil size={15} aria-hidden="true" />
              </button>
              <button
                type="button"
                onClick={onDelete}
                aria-label={`Delete ${c.name}`}
                title="Delete course"
                className="rounded-md p-2 text-slate-400 transition hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-500/10 dark:hover:text-red-400"
              >
                <Trash2 size={15} aria-hidden="true" />
              </button>
            </>
          )}
          <button
            type="button"
            onClick={onToggle}
            aria-expanded={expanded}
            aria-controls={`assignments-${c.id}`}
            aria-label={`${expanded ? 'Hide' : 'Show'} assignments for ${c.name}`}
            title={expanded ? 'Hide assignments' : 'Show assignments'}
            className="rounded-md p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800"
          >
            <ChevronRight size={15} className={`transition-transform ${expanded ? 'rotate-90' : ''}`} aria-hidden="true" />
          </button>
        </div>
      </div>
      {expanded && children}
    </div>
  );
}

/**
 * The assignments of one course: list, add form and delete requests. It loads its own data
 * when it mounts (i.e. when the row is expanded) and cancels the request when it unmounts.
 */
function AssignmentPanel({
  courseId,
  onChanged,
  onRequestDelete,
}: {
  courseId: string;
  onChanged: () => void;
  onRequestDelete: (target: { id: string; label: string; onDeleted: () => void }) => void;
}) {
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<AssignmentForm>(EMPTY_ASSIGNMENT);
  const [formError, setFormError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setLoadError(null);

    apiClient
      .get('/api/assignments', { params: { course_id: courseId }, signal: controller.signal })
      .then((res) => setAssignments(asArray<Assignment>(res.data, 'assignments')))
      .catch((err) => {
        // This used to fall back to an empty list, so a failure read as "No assignments yet."
        if (controller.signal.aborted) return;
        setLoadError(describeError(err, 'Failed to load assignments.'));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [courseId, reloadKey]);

  const closeForm = () => {
    setShowForm(false);
    setForm(EMPTY_ASSIGNMENT);
    setFormError('');
  };

  const toggleForm = () => {
    if (showForm) closeForm();
    else setShowForm(true);
  };

  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (saving) return;

    if (!form.name.trim()) {
      setFormError('Assignment name is required.');
      return;
    }

    // Send a datetime-local value as ISO-8601 so the backend can parse it.
    let due: string | null = null;
    if (form.due_at) {
      const parsed = new Date(form.due_at);
      if (Number.isNaN(parsed.getTime())) {
        setFormError('Enter a valid due date.');
        return;
      }
      due = parsed.toISOString();
    }

    setSaving(true);
    setFormError('');

    try {
      await apiClient.post(`/api/courses/${encodeURIComponent(courseId)}/assignments`, {
        name: form.name.trim(),
        assignment_type: form.assignment_type,
        due_at: due,
      });
    } catch (err) {
      setFormError(describeError(err, 'Failed to create assignment.'));
      setSaving(false);
      return;
    }

    closeForm();
    setSaving(false);
    // Reload so the list and the course's assignment count both reflect the server state.
    setReloadKey((key) => key + 1);
    onChanged();
  };

  const requestDelete = (a: Assignment) => {
    onRequestDelete({
      id: a.id,
      label: a.name,
      onDeleted: () => setAssignments((prev) => prev.filter((item) => item.id !== a.id)),
    });
  };

  return (
    <div
      id={`assignments-${courseId}`}
      className="border-t border-slate-200 bg-slate-50/40 px-6 py-4 lg:px-7 dark:border-slate-800 dark:bg-slate-900/40"
    >
      <div className="mb-3 flex items-center justify-between gap-3">
        <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
          Assignments
        </span>
        <button
          type="button"
          onClick={toggleForm}
          className="inline-flex items-center gap-1.5 rounded-xl border border-blue-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-blue-700 transition hover:bg-blue-50 dark:border-blue-500/30 dark:bg-slate-900 dark:text-blue-400 dark:hover:bg-blue-500/10"
        >
          <Plus size={13} aria-hidden="true" />
          {showForm ? 'Cancel' : 'Add assignment'}
        </button>
      </div>

      {showForm && (
        <form
          onSubmit={save}
          onKeyDown={(e) => {
            if (e.key === 'Escape') closeForm();
          }}
          noValidate
          className="mb-3 rounded-lg border border-blue-200 bg-white p-3 dark:border-blue-500/30 dark:bg-slate-900"
        >
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Name *">
              <input
                type="text"
                name="assignment-name"
                value={form.name}
                onChange={(e) => {
                  setForm({ ...form, name: e.target.value });
                  if (formError) setFormError('');
                }}
                placeholder="Assignment 1"
                required
                aria-required="true"
                autoFocus
                className={INPUT_CLASS}
              />
            </Field>
            <Field label="Type">
              <select
                value={form.assignment_type}
                onChange={(e) => setForm({ ...form, assignment_type: e.target.value })}
                className={INPUT_CLASS}
              >
                {ASSIGNMENT_TYPES.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Due">
              <input
                type="datetime-local"
                value={form.due_at}
                onChange={(e) => {
                  setForm({ ...form, due_at: e.target.value });
                  if (formError) setFormError('');
                }}
                className={INPUT_CLASS}
              />
            </Field>
          </div>

          {formError && (
            <p
              role="alert"
              className="mt-3 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300"
            >
              <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
              <span className="flex-1">{formError}</span>
            </p>
          )}

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button
              type="submit"
              disabled={saving || !form.name.trim()}
              className="inline-flex h-9 items-center gap-2 rounded-xl bg-blue-600 px-3.5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50 disabled:opacity-50"
            >
              {saving ? 'Adding…' : 'Add assignment'}
            </button>
            <button
              type="button"
              onClick={closeForm}
              className="inline-flex h-9 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
            >
              Cancel
            </button>
            <span className="text-xs text-slate-500 dark:text-slate-400">
              The type selects the detection mode and engine weights used for analysis.
            </span>
          </div>
        </form>
      )}

      {loading ? (
        <div
          role="status"
          className="flex items-center gap-2 py-4 text-sm text-slate-500 dark:text-slate-400"
        >
          <Loader2 size={16} className="animate-spin" aria-hidden="true" />
          Loading…
        </div>
      ) : loadError ? (
        <div className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
          <span role="alert" className="flex-1">
            {loadError}
          </span>
          <button
            type="button"
            onClick={() => setReloadKey((key) => key + 1)}
            className="shrink-0 font-semibold underline underline-offset-2"
          >
            Retry
          </button>
        </div>
      ) : assignments.length === 0 ? (
        <div className="rounded-lg border border-dashed border-slate-200 py-6 text-center text-sm leading-6 text-slate-500 dark:border-slate-700 dark:text-slate-400">
          No assignments yet.
        </div>
      ) : (
        <ul className="space-y-2">
          {assignments.map((a) => (
            <li
              key={a.id}
              className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-3 py-2 dark:border-slate-800 dark:bg-slate-950"
            >
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium text-slate-900 dark:text-white">{a.name}</div>
                {/* The type used to be printed here and again in the badge; the due date was never shown. */}
                <div className="text-xs text-slate-500 dark:text-slate-400">{formatDue(a.due_at)}</div>
              </div>
              <StatusBadge status={a.assignment_type} />
              <button
                type="button"
                onClick={() => requestDelete(a)}
                aria-label={`Delete ${a.name}`}
                title="Delete assignment"
                className="rounded-md p-1.5 text-slate-400 transition hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-500/10 dark:hover:text-red-400"
              >
                <Trash2 size={14} aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
