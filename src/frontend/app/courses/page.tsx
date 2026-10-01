'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { Card, CardHeader, StatusBadge } from '@/components/saas/SaaSPrimitives';
import { apiClient } from '@/lib/apiClient';
import { buildTermLabel, buildTermOptions, courseTermLabel, type Term } from '@/lib/terms';
import { BookOpen, ChevronRight, Pencil, Plus, Search, Trash2 } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';

type Assignment = { id: string; name: string; term: string | null; assignment_type: string; due_at?: string | null };
type Course = { id: string; name: string; code: string | null; term: string | null; year: number | null; term_id: string | null; department: string | null; assignment_count: number };
type Form = { name: string; code: string; term: string; year: string; department: string; description: string; term_id: string };
const EMPTY: Form = { name: '', code: '', term: '', year: '', department: 'Computer Science', description: '', term_id: '' };

/**
 * Prefer the API's own reason when an action is refused — a 409 explains which
 * check history blocks a delete — falling back to a fixed message.
 */
function errorMessage(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof detail === 'string' && detail ? detail : fallback;
}

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

type AssignmentForm = { name: string; assignment_type: string; due_at: string };
const EMPTY_ASSIGNMENT: AssignmentForm = { name: '', assignment_type: 'programming', due_at: '' };

/** A delete waiting for confirmation in the designed dialog (never a native confirm()). */
type PendingDelete =
  | { kind: 'course'; id: string; label: string; assignmentCount: number }
  | { kind: 'assignment'; id: string; label: string };

export default function CoursesPage() {
  // Course maintenance (create / edit / delete) belongs to admins and lives in
  // Administration → Users & courses; admins are redirected off this page.
  // What remains here for professors is browsing courses and maintaining the
  // assignments inside them.
  const { user } = useAuth();
  const canManageCourses = user?.role === 'admin';

  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [termFilter, setTermFilter] = useState('all');
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<Form>(EMPTY);
  const [saving, setSaving] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [assignmentsLoading, setAssignmentsLoading] = useState(false);
  const [terms, setTerms] = useState<Term[]>([]);
  const [assignmentCourseId, setAssignmentCourseId] = useState<string | null>(null);
  const [assignmentForm, setAssignmentForm] = useState<AssignmentForm>(EMPTY_ASSIGNMENT);
  const [assignmentSaving, setAssignmentSaving] = useState(false);

  const fetchTerms = useCallback(async () => {
    try {
      const res = await apiClient.get('/api/terms');
      setTerms((res.data || []) as Term[]);
    } catch {
      // Term registry is optional UI sugar; the course form still accepts a
      // free-text term when the endpoint is unavailable.
      setTerms([]);
    }
  }, []);

  useEffect(() => { fetchTerms(); }, [fetchTerms]);

  const fetchCourses = useCallback(async () => {
    try {
      const res = await apiClient.get('/api/courses', { params: { limit: 200 } });
      setCourses((res.data?.courses || res.data || []) as Course[]);
      setError(null);
    } catch { setError('Failed to load courses. Please try again.'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchCourses(); }, [fetchCourses]);

  const openCreate = () => { setEditingId(null); setForm(EMPTY); setShowForm(true); };
  const openEdit = (c: Course) => {
    setEditingId(c.id);
    setForm({ name: c.name, code: c.code || '', term: c.term || '', year: c.year ? String(c.year) : '', department: c.department || '', description: '', term_id: c.term_id || '' });
    setShowForm(true);
  };
  const closeForm = () => { setShowForm(false); setEditingId(null); setForm(EMPTY); };

  // Picking a registered term fills in the mirrored season/year text. Picking
  // "none" clears both so the course is created without a term.
  const selectTerm = (value: string) => {
    if (!value) { setForm((f) => ({ ...f, term_id: '', term: '', year: '' })); return; }
    const term = terms.find((t) => t.id === value);
    if (!term) { setForm((f) => ({ ...f, term_id: value })); return; }
    setForm((f) => ({ ...f, term_id: term.id, term: term.name, year: String(term.year) }));
  };

  const saveCourse = async () => {
    if (!form.name.trim()) return;
    setSaving(true);
    try {
      const p = { name: form.name.trim(), code: form.code.trim() || null, term_id: form.term_id || null, term: form.term.trim() || null, year: form.year ? Number(form.year) : null, department: form.department.trim() || null, description: form.description.trim() || null };
      if (editingId) await apiClient.put(`/api/courses/${editingId}`, p); else await apiClient.post('/api/courses', p);
      closeForm(); await fetchCourses();
    } catch (error) { setError(errorMessage(error, 'Failed to save course.')); }
    finally { setSaving(false); }
  };

  const deleteCourse = (id: string, label: string, assignmentCount: number) => {
    setPendingDelete({ kind: 'course', id, label, assignmentCount });
  };

  const toggleExpand = async (cid: string) => {
    if (expandedId === cid) { setExpandedId(null); return; }
    setExpandedId(cid); setAssignmentsLoading(true);
    try { const r = await apiClient.get('/api/assignments', { params: { course_id: cid } }); setAssignments((r.data?.assignments || r.data || []) as Assignment[]); }
    catch { setAssignments([]); }
    finally { setAssignmentsLoading(false); }
  };

  const deleteAssignment = (id: string, label: string) => {
    setPendingDelete({ kind: 'assignment', id, label });
  };

  /** Runs the delete the confirmation dialog was opened for. */
  const confirmDelete = async () => {
    if (!pendingDelete) return;
    const target = pendingDelete;
    setDeleting(true);
    try {
      if (target.kind === 'course') {
        await apiClient.delete(`/api/courses/${target.id}`);
        if (expandedId === target.id) setExpandedId(null);
      } else {
        await apiClient.delete(`/api/assignments/${target.id}`);
        setAssignments((prev) => prev.filter((a) => a.id !== target.id));
      }
      await fetchCourses();
    } catch (error) {
      setError(errorMessage(
        error,
        target.kind === 'course' ? 'Failed to delete course.' : 'Failed to delete assignment.'
      ));
    } finally {
      setDeleting(false);
      setPendingDelete(null);
    }
  };

  const openAssignmentForm = (cid: string) => {
    setAssignmentCourseId((prev) => (prev === cid ? null : cid));
    setAssignmentForm(EMPTY_ASSIGNMENT);
  };

  const closeAssignmentForm = () => { setAssignmentCourseId(null); setAssignmentForm(EMPTY_ASSIGNMENT); };

  const saveAssignment = async (cid: string) => {
    if (!assignmentForm.name.trim()) return;
    setAssignmentSaving(true);
    try {
      // Send a datetime-local value as ISO-8601 so the backend can parse it.
      const due = assignmentForm.due_at
        ? new Date(assignmentForm.due_at).toISOString()
        : null;
      await apiClient.post(`/api/courses/${cid}/assignments`, {
        name: assignmentForm.name.trim(),
        assignment_type: assignmentForm.assignment_type,
        due_at: due,
      });
      closeAssignmentForm();
      // Reload the expanded list so the new assignment and the course's
      // assignment count both reflect the server state.
      const r = await apiClient.get('/api/assignments', { params: { course_id: cid } });
      setAssignments((r.data?.assignments || r.data || []) as Assignment[]);
      await fetchCourses();
    } catch (error) { setError(errorMessage(error, 'Failed to create assignment.')); }
    finally { setAssignmentSaving(false); }
  };

  const termOptions = useMemo(() => buildTermOptions(courses), [courses]);

  // Reset the term filter when the selected term no longer exists
  // (e.g. its last course was deleted or renamed).
  useEffect(() => {
    if (termFilter === 'all') return;
    if (!termOptions.some((option) => option.value === termFilter)) setTermFilter('all');
  }, [termOptions, termFilter]);

  const filtered = courses.filter((c) => {
    if (termFilter !== 'all' && courseTermLabel(c) !== termFilter) return false;
    if (!search) return true;
    const q = search.toLowerCase();
    return c.name.toLowerCase().includes(q) || (c.code || '').toLowerCase().includes(q) || (c.department || '').toLowerCase().includes(q) || courseTermLabel(c).toLowerCase().includes(q);
  });

  const deleteWarning = !pendingDelete
    ? ''
    : pendingDelete.kind === 'course'
      ? `This removes the course and its ${pendingDelete.assignmentCount} assignment${pendingDelete.assignmentCount === 1 ? '' : 's'}. Check history and cases keep their evidence — the delete is refused while any still reference them.`
      : 'This removes the assignment from its course. Existing checks and cases keep their evidence — the delete is refused while any still reference it.';

  return (
    <DashboardLayout>
      <div className="theme-page-container">
        {error && <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
        <Card>
          <CardHeader title="Courses" description="Manage your courses and assignments." action={
            <div className="flex flex-wrap items-center gap-3">
              <label className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-500 shadow-sm lg:w-72">
                <Search size={15} />
                <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search courses..." className="w-full bg-transparent text-slate-900 placeholder:text-slate-400 focus:outline-none" aria-label="Search courses" />
              </label>
              {termOptions.length > 1 && (
                <select
                  value={termFilter}
                  onChange={(e) => setTermFilter(e.target.value)}
                  aria-label="Filter courses by term"
                  className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-50"
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
          } />

          {showForm && isAdmin && (
            <div className="border-b border-slate-200 bg-slate-50/60 px-5 py-4">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                <Field label="Name *">
                  <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Introduction to Computer Science" className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:border-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-50" />
                </Field>
                <Field label="Code">
                  <input type="text" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} placeholder="CSC108" className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:border-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-50" />
                </Field>
                <Field label="Term">
                  {terms.length > 0 ? (
                    <select
                      value={form.term_id}
                      onChange={(e) => selectTerm(e.target.value)}
                      aria-label="Select term"
                      className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:border-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-50"
                    >
                      <option value="">No term</option>
                      {terms.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.label}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type="text"
                      value={form.term}
                      onChange={(e) => setForm({ ...form, term: e.target.value })}
                      placeholder="Fall"
                      className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:border-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-50"
                    />
                  )}
                </Field>
                <Field label="Year">
                  <input
                    type="number"
                    value={form.year}
                    onChange={(e) => setForm({ ...form, year: e.target.value })}
                    placeholder="2026"
                    disabled={terms.length > 0}
                    className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:border-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-50 disabled:bg-slate-100 disabled:text-slate-500"
                  />
                </Field>
                <Field label="Department">
                  <input type="text" value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} placeholder="Computer Science" className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:border-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-50" />
                </Field>
                <Field label="Description">
                  <input type="text" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Optional" className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:border-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-50" />
                </Field>
              </div>
              <div className="mt-4 flex items-center gap-2">
                <button type="button" onClick={saveCourse} disabled={saving || !form.name.trim()} className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50">{saving ? 'Saving...' : editingId ? 'Update' : 'Create'}</button>
                <button type="button" onClick={closeForm} className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">Cancel</button>
              </div>
            </div>
          )}

          <div className="divide-y divide-slate-100">
            {loading ? <div className="px-5 py-12 text-center text-sm text-slate-500">Loading courses…</div>
            : filtered.length === 0 && (Boolean(search) || termFilter !== 'all') ? <NoMatches />
            : <>{filtered.map((c) => <CourseRow key={c.id} course={c} expanded={expandedId === c.id} assignments={assignments} assignmentsLoading={assignmentsLoading} onEdit={() => openEdit(c)} onDelete={() => deleteCourse(c.id)} onToggle={() => toggleExpand(c.id)} onDeleteAssignment={deleteAssignment} showAssignmentForm={assignmentCourseId === c.id} assignmentForm={assignmentForm} assignmentSaving={assignmentSaving} onAssignmentFormChange={setAssignmentForm} onOpenAssignmentForm={() => openAssignmentForm(c.id)} onCloseAssignmentForm={closeAssignmentForm} onSaveAssignment={() => saveAssignment(c.id)} />)}<AddCourseCard onAdd={openCreate} /></>}
          </div>
        </Card>

        <Modal
          open={pendingDelete !== null}
          title={pendingDelete?.kind === 'course' ? 'Delete course' : 'Delete assignment'}
          onClose={() => setPendingDelete(null)}
          footer={
            <>
              <button
                type="button"
                onClick={() => setPendingDelete(null)}
                className="theme-button-secondary rounded-xl px-4 py-2 text-sm font-semibold"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={confirmDelete}
                disabled={deleting}
                className="rounded-xl bg-red-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-red-700 disabled:opacity-60"
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
              <p className="truncate text-sm font-semibold text-slate-900 dark:text-white">
                {pendingDelete?.label}
              </p>
              <p className="mt-1 text-sm leading-6 text-slate-600 dark:text-slate-300">
                {deleteWarning}
              </p>
            </div>
          </div>
        </Modal>
      </div>
    </DashboardLayout>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-slate-600">{label}</label>
      {children}
    </div>
  );
}

function AddCourseCard({ onAdd }: { onAdd: () => void }) {
  return (
    <button
      type="button"
      onClick={onAdd}
      aria-label="Add a new course"
      className="group flex w-full flex-col items-center justify-center gap-2 px-5 py-14 text-center transition hover:bg-blue-50/50"
    >
      <span className="flex h-16 w-16 items-center justify-center rounded-2xl border-2 border-dashed border-slate-300 text-slate-400 transition group-hover:border-blue-400 group-hover:bg-white group-hover:text-blue-600">
        <Plus size={36} strokeWidth={2} aria-hidden="true" />
      </span>
      <span className="mt-1 text-sm font-semibold text-slate-600 group-hover:text-blue-700">Add course</span>
      <span className="text-xs text-slate-400">Create a course to organise its assignments</span>
    </button>
  );
}

function NoMatches() {
  return (
    <div className="flex flex-col items-center px-5 py-16 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-100"><BookOpen size={22} className="text-slate-400" /></div>
      <p className="mt-3 text-sm font-medium text-slate-700">No courses match your filters.</p>
      <p className="mt-1 text-xs text-slate-500">Try a different search term or term filter.</p>
    </div>
  );
}

function CourseRow({ course: c, expanded, assignments, assignmentsLoading, onEdit, onDelete, onToggle, onDeleteAssignment, showAssignmentForm, assignmentForm, assignmentSaving, onAssignmentFormChange, onOpenAssignmentForm, onCloseAssignmentForm, onSaveAssignment }: {
  course: Course; expanded: boolean; assignments: Assignment[]; assignmentsLoading: boolean;
  onEdit: () => void; onDelete: () => void; onToggle: () => void; onDeleteAssignment: (id: string) => void;
  showAssignmentForm: boolean; assignmentForm: AssignmentForm; assignmentSaving: boolean;
  onAssignmentFormChange: (form: AssignmentForm) => void;
  onOpenAssignmentForm: () => void; onCloseAssignmentForm: () => void; onSaveAssignment: () => void;
}) {
  return (
    <div>
      <div className="flex items-center gap-4 px-5 py-4 transition hover:bg-slate-50/60">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-700"><BookOpen size={18} /></div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2"><span className="truncate text-sm font-semibold text-slate-900">{c.name}</span>{c.code && <span className="shrink-0 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold text-slate-500">{c.code}</span>}</div>
          <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">{c.department && <span>{c.department}</span>}<span>{c.department ? '· ' : ''}{c.assignment_count ?? 0} {c.assignment_count === 1 ? 'assignment' : 'assignments'}</span></div>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <button type="button" onClick={onEdit} aria-label={`Edit ${c.name}`} className="rounded-md p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700"><Pencil size={15} /></button>
          <button type="button" onClick={onDelete} aria-label={`Delete ${c.name}`} className="rounded-md p-2 text-slate-400 hover:bg-red-50 hover:text-red-600"><Trash2 size={15} /></button>
          <button type="button" onClick={onToggle} aria-label="Toggle" className="rounded-md p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700"><ChevronRight size={15} className={`transition-transform ${expanded ? 'rotate-90' : ''}`} /></button>
        </div>
      </div>
      {expanded && (
        <div className="border-t border-slate-100 bg-slate-50/40 px-5 py-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Assignments
            </span>
            {canManageAssignments && (
              <button
                type="button"
                onClick={onOpenAssignmentForm}
                className="inline-flex items-center gap-1.5 rounded-lg border border-blue-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-blue-700 hover:bg-blue-50"
              >
                <Plus size={13} />
                {showAssignmentForm ? 'Cancel' : 'Add assignment'}
              </button>
            )}
          </div>
          {showAssignmentForm && canManageAssignments && (
            <div className="mb-3 rounded-lg border border-blue-200 bg-white p-3">
              <div className="grid gap-3 sm:grid-cols-3">
                <Field label="Name *">
                  <input
                    type="text"
                    value={assignmentForm.name}
                    onChange={(e) => onAssignmentFormChange({ ...assignmentForm, name: e.target.value })}
                    placeholder="Assignment 1"
                    className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:border-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-50"
                  />
                </Field>
                <Field label="Type">
                  <select
                    value={assignmentForm.assignment_type}
                    onChange={(e) => onAssignmentFormChange({ ...assignmentForm, assignment_type: e.target.value })}
                    aria-label="Assignment type"
                    className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:border-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-50"
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
                    value={assignmentForm.due_at}
                    onChange={(e) => onAssignmentFormChange({ ...assignmentForm, due_at: e.target.value })}
                    className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:border-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-50"
                  />
                </Field>
              </div>
              <div className="mt-3 flex items-center gap-2">
                <button
                  type="button"
                  onClick={onSaveAssignment}
                  disabled={assignmentSaving || !assignmentForm.name.trim()}
                  className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  {assignmentSaving ? 'Adding…' : 'Add assignment'}
                </button>
                <button
                  type="button"
                  onClick={onCloseAssignmentForm}
                  className="rounded-lg border border-slate-200 bg-white px-3.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <span className="text-[11px] text-slate-500">
                  The type selects the detection mode and engine weights used for analysis.
                </span>
              </div>
            </div>
          )}
          {assignmentsLoading ? <div className="py-4 text-xs text-slate-500">Loading…</div>
          : assignments.length === 0 ? <div className="rounded-lg border border-dashed border-slate-200 py-6 text-center text-xs text-slate-500">{canManageAssignments ? 'No assignments yet.' : 'No assignments yet. The professor teaching this course creates them.'}</div>
          : <div className="space-y-2">{assignments.map((a) => (
            <div key={a.id} className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-3 py-2">
              <div className="min-w-0 flex-1"><div className="truncate text-sm font-medium text-slate-800">{a.name}</div><div className="text-xs text-slate-500">{a.assignment_type}</div></div>
              <StatusBadge status={a.assignment_type} />
              <button type="button" onClick={() => onDeleteAssignment(a.id)} aria-label={`Delete ${a.name}`} className="rounded-md p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-600"><Trash2 size={14} /></button>
            </div>
          ))}</div>}
        </div>
      )}
    </div>
  );
}
