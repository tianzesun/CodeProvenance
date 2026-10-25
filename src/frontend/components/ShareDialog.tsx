'use client';

import { useEffect, useMemo, useState } from 'react';
import { Modal } from '@/components/saas/SaaSPrimitives';
import { apiClient } from '@/lib/apiClient';

type Audience = 'private' | 'people' | 'organization';

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
  /** What sharing reaches, shown under the choices. */
  scopeNote?: string;
}

function describeShareError(err: unknown, fallback: string): string {
  const status = (err as { response?: { status?: number } })?.response?.status;
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (status === 400 && typeof detail === 'string') return detail;
  if (status === 401) return 'Your session has expired. Please sign in again.';
  if (status === 403) return 'You can view this item’s sharing, but only its owners can change it.';
  return fallback;
}

/**
 * Share a course, analysis or case: private to its owners, with selected
 * faculty, or with everyone in the organization. Shared faculty get the same
 * access as owners; sharing a course reaches everything under it.
 */
export default function ShareDialog({ open, onClose, endpoint, itemLabel, scopeNote }: ShareDialogProps) {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const [canManage, setCanManage] = useState(false);
  const [audience, setAudience] = useState<Audience>('private');
  const [selected, setSelected] = useState<string[]>([]);
  const [faculty, setFaculty] = useState<Faculty[]>([]);
  const [query, setQuery] = useState('');

  useEffect(() => {
    if (!open) return;
    let active = true;
    setLoading(true);
    setError('');
    setSaved(false);
    Promise.all([
      apiClient.get(endpoint),
      // The picker lists the caller's organization; a failure leaves it empty.
      apiClient.get('/api/users').catch(() => ({ data: [] })),
    ])
      .then(([shareRes, usersRes]) => {
        if (!active) return;
        const data = shareRes.data as SharingState;
        setCanManage(Boolean(data?.can_manage));
        const ids = Array.isArray(data?.user_ids) ? data.user_ids.map(String) : [];
        setSelected(ids);
        setAudience(data?.workspace ? 'organization' : ids.length ? 'people' : 'private');
        setFaculty(Array.isArray(usersRes.data) ? (usersRes.data as Faculty[]) : []);
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

  const nameOf = useMemo(() => {
    const byId = new Map(faculty.map((f) => [f.id, f.name || f.email]));
    return (id: string) => byId.get(id) || 'A colleague';
  }, [faculty]);

  const matches = faculty.filter((f) => {
    const q = query.trim().toLowerCase();
    return !q || (f.name || '').toLowerCase().includes(q) || f.email.toLowerCase().includes(q);
  });

  const toggle = (id: string) =>
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

  const save = async () => {
    setSaving(true);
    setError('');
    setSaved(false);
    try {
      await apiClient.put(endpoint, {
        workspace: audience === 'organization',
        user_ids: audience === 'people' ? selected : [],
      });
      setSaved(true);
    } catch (err) {
      setError(describeShareError(err, 'Couldn’t save sharing. Nothing was changed.'));
    } finally {
      setSaving(false);
    }
  };

  const summary =
    audience === 'organization'
      ? 'Everyone in your organization'
      : audience === 'people'
        ? selected.map(nameOf).join(', ') || 'No one yet'
        : 'Only its owners (private)';

  const choices: { value: Audience; label: string; hint: string }[] = [
    { value: 'private', label: 'Private', hint: 'Only its owners can see it.' },
    { value: 'people', label: 'Selected faculty', hint: 'Choose colleagues from your organization.' },
    { value: 'organization', label: 'Everyone in your organization', hint: 'All faculty in your organization.' },
  ];

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Share ${itemLabel}`}
      description="People you share with get the same access as you: they can view and edit."
      footer={
        canManage ? (
          <>
            <button type="button" onClick={onClose} className="theme-button-secondary rounded-xl px-4 py-2 text-sm">
              Close
            </button>
            <button
              type="button"
              onClick={save}
              disabled={saving || loading || (audience === 'people' && selected.length === 0)}
              className="theme-button-primary rounded-xl px-4 py-2 text-sm disabled:opacity-50"
            >
              {saving ? 'Saving…' : 'Save sharing'}
            </button>
          </>
        ) : (
          <button type="button" onClick={onClose} className="theme-button-secondary rounded-xl px-4 py-2 text-sm">
            Close
          </button>
        )
      }
    >
      {loading ? (
        <p className="text-sm text-[var(--text-muted)]">Loading sharing settings…</p>
      ) : !canManage ? (
        <div className="space-y-2 text-sm">
          <p>
            <span className="font-semibold">Shared with:</span> {summary}
          </p>
          <p className="text-[var(--text-muted)]">Only its owners can change who it is shared with.</p>
        </div>
      ) : (
        <div className="space-y-4">
          <fieldset className="space-y-2">
            <legend className="sr-only">Who can see {itemLabel}</legend>
            {choices.map((choice) => (
              <label key={choice.value} className="flex cursor-pointer items-start gap-3 rounded-xl border border-slate-200 px-3.5 py-2.5 dark:border-slate-800">
                <input
                  type="radio"
                  name="share-audience"
                  value={choice.value}
                  checked={audience === choice.value}
                  onChange={() => setAudience(choice.value)}
                  className="mt-1"
                />
                <span>
                  <span className="block text-sm font-semibold">{choice.label}</span>
                  <span className="block text-xs text-[var(--text-muted)]">{choice.hint}</span>
                </span>
              </label>
            ))}
          </fieldset>

          {audience === 'people' && (
            <div className="space-y-2">
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search faculty by name or email"
                aria-label="Search faculty"
                className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm dark:border-slate-800 dark:bg-slate-900"
              />
              <ul className="max-h-48 space-y-1 overflow-y-auto">
                {matches.length === 0 && (
                  <li className="text-xs text-[var(--text-muted)]">No faculty match.</li>
                )}
                {matches.map((person) => (
                  <li key={person.id}>
                    <label className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-slate-50 dark:hover:bg-slate-900">
                      <input type="checkbox" checked={selected.includes(person.id)} onChange={() => toggle(person.id)} />
                      <span className="font-medium">{person.name || person.email}</span>
                      {person.name && <span className="text-xs text-[var(--text-muted)]">{person.email}</span>}
                    </label>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {scopeNote && <p className="text-xs text-[var(--text-muted)]">{scopeNote}</p>}
        </div>
      )}

      {error && (
        <p role="alert" className="mt-4 text-sm text-red-600">
          {error}
        </p>
      )}
      {saved && !error && (
        <p role="status" className="mt-4 text-sm text-emerald-600">
          Sharing saved.
        </p>
      )}
    </Modal>
  );
}
