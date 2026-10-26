'use client';

import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { Building2, Lock, Search, UserPlus, X } from 'lucide-react';
import { useAuth } from '@/components/AuthProvider';
import { Modal } from '@/components/saas/SaaSPrimitives';
import { apiClient } from '@/lib/apiClient';

interface SharingState {
  workspace: boolean;
  user_ids: string[];
  can_manage: boolean;
}

interface Faculty {
  id: string;
  name?: string | null;
  email: string;
}

interface ShareDialogProps {
  open: boolean;
  onClose: () => void;
  /** e.g. `/api/courses/${id}/sharing`: GET and PUT `{workspace, user_ids}`. */
  endpoint: string;
  /** What is being shared, for the title ("CSC108", "this analysis"). */
  itemLabel: string;
  /** Who can always see it, shown under General access. */
  ownersNote?: string;
}

const MAX_SUGGESTIONS = 6;

function describeShareError(err: unknown, fallback: string): string {
  const status = (err as { response?: { status?: number } })?.response?.status;
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (status === 400 && typeof detail === 'string') return detail;
  if (status === 401) return 'Your session has expired. Please sign in again.';
  if (status === 403) return 'Only the owners can change who this is shared with.';
  return fallback;
}

function initials(label: string): string {
  const parts = label.replace(/@.*/, '').split(/[\s._-]+/).filter(Boolean);
  return (parts[0]?.[0] ?? '?').toUpperCase() + (parts[1]?.[0] ?? '').toUpperCase();
}

/**
 * Share a course, analysis or case, in the familiar "add people + general
 * access" layout: add colleagues by name, and choose whether everyone in the
 * organization can open it. Shared people get the same access as owners.
 */
export default function ShareDialog({
  open,
  onClose,
  endpoint,
  itemLabel,
  ownersNote = 'Its owners always have access.',
}: ShareDialogProps) {
  const { user } = useAuth();
  // Rendered into <body>: opened from inside a card, the fixed overlay was
  // clipped to that card (a transformed ancestor contains fixed elements).
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [canManage, setCanManage] = useState(false);
  const [faculty, setFaculty] = useState<Faculty[]>([]);
  const [facultyError, setFacultyError] = useState(false);
  const [query, setQuery] = useState('');
  // What is saved, and what the dialog currently shows.
  const [savedPeople, setSavedPeople] = useState<string[]>([]);
  const [savedEveryone, setSavedEveryone] = useState(false);
  const [people, setPeople] = useState<string[]>([]);
  const [everyone, setEveryone] = useState(false);

  useEffect(() => {
    if (!open) return;
    let active = true;
    setLoading(true);
    setError('');
    setQuery('');
    setFacultyError(false);
    Promise.all([
      apiClient.get(endpoint),
      apiClient.get('/api/users').catch(() => null),
    ])
      .then(([shareRes, usersRes]) => {
        if (!active) return;
        const data = shareRes.data as SharingState;
        const ids = Array.isArray(data?.user_ids) ? data.user_ids.map(String) : [];
        setCanManage(Boolean(data?.can_manage));
        setSavedPeople(ids);
        setPeople(ids);
        setSavedEveryone(Boolean(data?.workspace));
        setEveryone(Boolean(data?.workspace));
        if (usersRes && Array.isArray(usersRes.data)) {
          setFaculty(usersRes.data as Faculty[]);
        } else {
          setFaculty([]);
          setFacultyError(true);
        }
      })
      .catch((err) => {
        if (active) setError(describeShareError(err, 'Couldn’t load sharing settings. Please try again.'));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [open, endpoint]);

  const byId = useMemo(() => new Map(faculty.map((f) => [f.id, f])), [faculty]);
  const labelOf = (id: string) => {
    const person = byId.get(id);
    return person ? person.name || person.email : 'A colleague';
  };

  const suggestions = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return faculty
      .filter((f) => f.id !== user?.id && !people.includes(f.id))
      .filter((f) => (f.name || '').toLowerCase().includes(q) || f.email.toLowerCase().includes(q))
      .slice(0, MAX_SUGGESTIONS);
  }, [query, faculty, people, user?.id]);

  const dirty =
    everyone !== savedEveryone ||
    people.length !== savedPeople.length ||
    people.some((id) => !savedPeople.includes(id));

  const addPerson = (id: string) => {
    setPeople((prev) => (prev.includes(id) ? prev : [...prev, id]));
    setQuery('');
  };

  const save = async () => {
    setSaving(true);
    setError('');
    try {
      await apiClient.put(endpoint, { workspace: everyone, user_ids: people });
      onClose();
    } catch (err) {
      setError(describeShareError(err, 'Couldn’t save sharing. Nothing was changed.'));
    } finally {
      setSaving(false);
    }
  };

  const footer = canManage ? (
    <>
      <button type="button" onClick={onClose} className="theme-button-secondary rounded-xl px-4 py-2 text-sm">
        Cancel
      </button>
      <button
        type="button"
        onClick={save}
        disabled={!dirty || saving || loading}
        className="theme-button-primary rounded-xl px-4 py-2 text-sm disabled:opacity-50"
      >
        {saving ? 'Saving…' : 'Save'}
      </button>
    </>
  ) : (
    <button type="button" onClick={onClose} className="theme-button-secondary rounded-xl px-4 py-2 text-sm">
      Done
    </button>
  );

  if (!mounted) return null;
  return createPortal(
    <Modal
      open={open}
      onClose={onClose}
      title={`Share ${itemLabel}`}
      description="People you add can view and edit it, just like you."
      footer={footer}
    >
      {loading ? (
        <p className="text-sm text-[var(--text-muted)]">Loading…</p>
      ) : (
        <div className="space-y-5">
          {canManage && (
            <div>
              <label htmlFor="share-search" className="mb-1.5 block text-sm font-semibold">
                Add people
              </label>
              <div className="relative">
                <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" aria-hidden="true" />
                <input
                  id="share-search"
                  type="search"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && suggestions[0]) {
                      e.preventDefault();
                      addPerson(suggestions[0].id);
                    }
                  }}
                  placeholder="Type a colleague’s name or email"
                  autoComplete="off"
                  disabled={facultyError}
                  className="w-full rounded-xl border border-slate-200 py-2 pl-9 pr-3 text-sm disabled:opacity-60 dark:border-slate-800 dark:bg-slate-900"
                />
              </div>
              {facultyError && (
                <p className="mt-1.5 text-xs text-[var(--text-muted)]">
                  Your colleagues couldn’t be loaded, so people can’t be added right now.
                </p>
              )}
              {query.trim() && !facultyError && (
                <ul className="mt-1.5 overflow-hidden rounded-xl border border-slate-200 dark:border-slate-800" role="listbox" aria-label="Matching colleagues">
                  {suggestions.length === 0 ? (
                    <li className="px-3 py-2 text-xs text-[var(--text-muted)]">No one in your organization matches “{query.trim()}”.</li>
                  ) : (
                    suggestions.map((person) => (
                      <li key={person.id}>
                        <button
                          type="button"
                          onClick={() => addPerson(person.id)}
                          className="flex w-full items-center gap-3 px-3 py-2 text-left text-sm hover:bg-slate-50 dark:hover:bg-slate-900"
                        >
                          <UserPlus size={15} className="shrink-0 text-blue-600" aria-hidden="true" />
                          <span className="min-w-0 flex-1 truncate">
                            <span className="font-medium">{person.name || person.email}</span>
                            {person.name && <span className="ml-2 text-xs text-[var(--text-muted)]">{person.email}</span>}
                          </span>
                          <span className="text-xs font-semibold text-blue-600">Add</span>
                        </button>
                      </li>
                    ))
                  )}
                </ul>
              )}
            </div>
          )}

          <div>
            <p className="mb-1.5 text-sm font-semibold">People with access</p>
            {people.length === 0 ? (
              <p className="rounded-xl border border-dashed border-slate-200 px-3 py-3 text-sm text-[var(--text-muted)] dark:border-slate-800">
                {canManage ? 'Not shared with anyone yet. Add people above.' : 'Not shared with any individual.'}
              </p>
            ) : (
              <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 dark:divide-slate-800 dark:border-slate-800">
                {people.map((id) => {
                  const label = labelOf(id);
                  const email = byId.get(id)?.name ? byId.get(id)?.email : null;
                  return (
                    <li key={id} className="flex items-center gap-3 px-3 py-2">
                      <span aria-hidden="true" className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-50 text-xs font-bold text-blue-700 dark:bg-blue-500/10 dark:text-blue-300">
                        {initials(label)}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium">{label}</span>
                        {email && <span className="block truncate text-xs text-[var(--text-muted)]">{email}</span>}
                      </span>
                      {canManage && (
                        <button
                          type="button"
                          onClick={() => setPeople((prev) => prev.filter((x) => x !== id))}
                          aria-label={`Remove ${label}`}
                          title="Remove access"
                          className="theme-icon-button"
                        >
                          <X size={14} />
                        </button>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          <div>
            <p className="mb-1.5 text-sm font-semibold">General access</p>
            <div className="flex items-start gap-3 rounded-xl border border-slate-200 px-3 py-2.5 dark:border-slate-800">
              <span aria-hidden="true" className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${everyone ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300' : 'bg-slate-100 text-slate-500 dark:bg-slate-800'}`}>
                {everyone ? <Building2 size={15} /> : <Lock size={15} />}
              </span>
              <div className="min-w-0 flex-1">
                {canManage ? (
                  <select
                    value={everyone ? 'everyone' : 'restricted'}
                    onChange={(e) => setEveryone(e.target.value === 'everyone')}
                    aria-label="General access"
                    className="w-full rounded-lg border border-slate-200 bg-transparent px-2 py-1 text-sm font-medium dark:border-slate-800"
                  >
                    <option value="restricted">Restricted</option>
                    <option value="everyone">Everyone in your organization</option>
                  </select>
                ) : (
                  <p className="text-sm font-medium">{everyone ? 'Everyone in your organization' : 'Restricted'}</p>
                )}
                <p className="mt-1 text-xs text-[var(--text-muted)]">
                  {everyone
                    ? 'Any faculty member in your organization can open and edit it.'
                    : 'Only the people listed above can open it.'}{' '}
                  {ownersNote}
                </p>
              </div>
            </div>
          </div>

          {!canManage && (
            <p className="text-xs text-[var(--text-muted)]">Only its owners can change who it’s shared with.</p>
          )}
        </div>
      )}

      {error && (
        <p role="alert" className="mt-4 text-sm text-red-600">
          {error}
        </p>
      )}
    </Modal>,
    document.body,
  );
}
