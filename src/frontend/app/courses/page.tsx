'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { Card, CardHeader, StatusBadge } from '@/components/saas/SaaSPrimitives';
import { apiClient } from '@/lib/apiClient';
import { BookOpen, ChevronRight, Pencil, Plus, Search, Trash2 } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

type Assignment = { id: string; name: string; term: string | null; assignment_type: string };
type Course = { id: string; name: string; code: string | null; term: string | null; year: number | null; department: string | null; assignmentCount: number };
type Form = { name: string; code: string; term: string; year: string; department: string; description: string };
const EMPTY: Form = { name: '', code: '', term: 'Fall', year: '2026', department: 'Computer Science', description: '' };

export default function CoursesPage() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<Form>(EMPTY);
  const [saving, setSaving] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [assignmentsLoading, setAssignmentsLoading] = useState(false);

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
    setForm({ name: c.name, code: c.code || '', term: c.term || 'Fall', year: String(c.year || 2026), department: c.department || '', description: '' });
    setShowForm(true);
  };
  const closeForm = () => { setShowForm(false); setEditingId(null); setForm(EMPTY); };

  const saveCourse = async () => {
    if (!form.name.trim()) return;
    setSaving(true);
    try {
      const p = { name: form.name.trim(), code: form.code.trim() || null, term: form.term.trim() || null, year: form.year ? Number(form.year) : null, department: form.department.trim() || null, description: form.description.trim() || null };
      if (editingId) await apiClient.put(`/api/courses/${editingId}`, p); else await apiClient.post('/api/courses', p);
      closeForm(); await fetchCourses();
    } catch { setError('Failed to save course.'); }
    finally { setSaving(false); }
  };

  const deleteCourse = async (id: string) => {
    if (!confirm('Delete this course and all its assignments?')) return;
    try { await apiClient.delete(`/api/courses/${id}`); if (expandedId === id) setExpandedId(null); await fetchCourses(); }
    catch { setError('Failed to delete course.'); }
  };

  const toggleExpand = async (cid: string) => {
    if (expandedId === cid) { setExpandedId(null); return; }
    setExpandedId(cid); setAssignmentsLoading(true);
    try { const r = await apiClient.get(`/api/courses/${cid}/assignments`); setAssignments((r.data?.assignments || r.data || []) as Assignment[]); }
    catch { setAssignments([]); }
    finally { setAssignmentsLoading(false); }
  };

  const deleteAssignment = async (aid: string) => {
    if (!confirm('Delete this assignment?')) return;
    try { await apiClient.delete(`/api/assignments/${aid}`); setAssignments((p) => p.filter((a) => a.id !== aid)); await fetchCourses(); }
    catch { setError('Failed to delete assignment.'); }
  };

  const filtered = courses.filter((c) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return c.name.toLowerCase().includes(q) || (c.code || '').toLowerCase().includes(q) || (c.department || '').toLowerCase().includes(q);
  });

  return (
    <DashboardLayout>
      <div className="max-w-none px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        {error && <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
        <Card>
          <CardHeader title="Courses" description="Manage your courses and assignments." action={
            <div className="flex flex-wrap items-center gap-3">
              <label className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-500 shadow-sm lg:w-72">
                <Search size={15} />
                <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search courses..." className="w-full bg-transparent text-slate-900 placeholder:text-slate-400 focus:outline-none" aria-label="Search courses" />
              </label>
              <button type="button" onClick={openCreate} className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"><Plus size={16} />New Course</button>
            </div>
          } />

          {showForm && (
            <div className="border-b border-slate-200 bg-slate-50/60 px-5 py-4">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                <Field label="Name *">
                  <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Introduction to Computer Science" className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:border-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-50" />
                </Field>
                <Field label="Code">
                  <input type="text" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} placeholder="CSC108" className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:border-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-50" />
                </Field>
                <Field label="Term">
                  <select value={form.term} onChange={(e) => setForm({ ...form, term: e.target.value })} className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:border-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-50"><option>Fall</option><option>Winter</option><option>Summer</option></select>
                </Field>
                <Field label="Year">
                  <input type="number" value={form.year} onChange={(e) => setForm({ ...form, year: e.target.value })} placeholder="2026" className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:border-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-50" />
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
            : filtered.length === 0 ? <EmptyState search={search} onNewCourse={openCreate} />
            : filtered.map((c) => <CourseRow key={c.id} course={c} expanded={expandedId === c.id} assignments={assignments} assignmentsLoading={assignmentsLoading} onEdit={() => openEdit(c)} onDelete={() => deleteCourse(c.id)} onToggle={() => toggleExpand(c.id)} onDeleteAssignment={deleteAssignment} />)}
          </div>
        </Card>
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

function EmptyState({ search, onNewCourse }: { search: string; onNewCourse: () => void }) {
  return (
    <div className="flex flex-col items-center px-5 py-16 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-100"><BookOpen size={22} className="text-slate-400" /></div>
      <p className="mt-3 text-sm font-medium text-slate-700">{search ? 'No courses match your search.' : 'No courses yet.'}</p>
      <p className="mt-1 text-xs text-slate-500">{search ? 'Try a different search term.' : 'Create your first course to get started.'}</p>
      {!search && <button type="button" onClick={onNewCourse} className="mt-4 inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"><Plus size={16} />New Course</button>}
    </div>
  );
}

function CourseRow({ course: c, expanded, assignments, assignmentsLoading, onEdit, onDelete, onToggle, onDeleteAssignment }: {
  course: Course; expanded: boolean; assignments: Assignment[]; assignmentsLoading: boolean;
  onEdit: () => void; onDelete: () => void; onToggle: () => void; onDeleteAssignment: (id: string) => void;
}) {
  return (
    <div>
      <div className="flex items-center gap-4 px-5 py-4 transition hover:bg-slate-50/60">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-700"><BookOpen size={18} /></div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2"><span className="truncate text-sm font-semibold text-slate-900">{c.name}</span>{c.code && <span className="shrink-0 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold text-slate-500">{c.code}</span>}</div>
          <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">{c.term && <span>{c.term} {c.year}</span>}{c.department && <span>· {c.department}</span>}<span>· {c.assignmentCount} {c.assignmentCount === 1 ? 'assignment' : 'assignments'}</span></div>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <button type="button" onClick={onEdit} aria-label={`Edit ${c.name}`} className="rounded-md p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700"><Pencil size={15} /></button>
          <button type="button" onClick={onDelete} aria-label={`Delete ${c.name}`} className="rounded-md p-2 text-slate-400 hover:bg-red-50 hover:text-red-600"><Trash2 size={15} /></button>
          <button type="button" onClick={onToggle} aria-label="Toggle" className="rounded-md p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700"><ChevronRight size={15} className={`transition-transform ${expanded ? 'rotate-90' : ''}`} /></button>
        </div>
      </div>
      {expanded && (
        <div className="border-t border-slate-100 bg-slate-50/40 px-5 py-4">
          <div className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">Assignments</div>
          {assignmentsLoading ? <div className="py-4 text-xs text-slate-500">Loading…</div>
          : assignments.length === 0 ? <div className="rounded-lg border border-dashed border-slate-200 py-6 text-center text-xs text-slate-500">No assignments yet.</div>
          : <div className="space-y-2">{assignments.map((a) => (
            <div key={a.id} className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-3 py-2">
              <div className="min-w-0 flex-1"><div className="truncate text-sm font-medium text-slate-800">{a.name}</div><div className="text-xs text-slate-500">{a.assignment_type}{a.term && ` · ${a.term}`}</div></div>
              <StatusBadge status={a.assignment_type} />
              <button type="button" onClick={() => onDeleteAssignment(a.id)} aria-label={`Delete ${a.name}`} className="rounded-md p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-600"><Trash2 size={14} /></button>
            </div>
          ))}</div>}
        </div>
      )}
    </div>
  );
}
