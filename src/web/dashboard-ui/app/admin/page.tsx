'use client';

import { FormEvent, useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { AlertTriangle, ShieldCheck, UserPlus, Users, Database, Download, FileText, Play, Loader2 } from 'lucide-react';
import axios from 'axios';

import DashboardLayout from '@/components/DashboardLayout';
import { AuthRole, AuthUser, useAuth } from '@/components/AuthProvider';

function formatDate(value: string | null) {
  if (!value) {
    return 'Never';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);
}

function getErrorMessage(error: unknown): string {
  if (
    typeof error === 'object' &&
    error !== null &&
    'response' in error &&
    typeof error.response === 'object' &&
    error.response !== null &&
    'data' in error.response &&
    typeof error.response.data === 'object' &&
    error.response.data !== null &&
    'detail' in error.response.data &&
    typeof error.response.data.detail === 'string'
  ) {
    return error.response.data.detail;
  }

  return 'Unable to complete that action right now.';
}

function validatePasswordInput(password: string): string | null {
  if (password.length < 8) {
    return 'Password must be at least 8 characters long.';
  }

  return null;
}

export default function AdminPage() {
  const { listUsers, createUser, user, loading: authLoading } = useAuth();
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [form, setForm] = useState({
    full_name: '',
    email: '',
    password: '',
    role: 'professor' as AuthRole,
    tenant_name: '',
  });

  const loadUsers = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setUsers(await listUsers());
    } catch (loadError) {
      setError(getErrorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, [listUsers]);

  useEffect(() => {
    if (authLoading || !user || user.role !== 'admin') {
      return;
    }
    loadUsers();
  }, [authLoading, loadUsers, user]);

  // Dataset creation state - optimized with refs to prevent unnecessary re-renders
  const datasetFormRef = useRef({
    name: '',
    description: '',
    language: 'python',
    numFiles: 10,
    similarityType: 'type1_exact',
  });

  const [datasetForm, setDatasetForm] = useState(datasetFormRef.current);
  const [creatingDataset, setCreatingDataset] = useState(false);

  // Notification system
  const [notifications, setNotifications] = useState<Array<{
    id: string;
    type: 'success' | 'error' | 'info';
    title: string;
    message: string;
    timestamp: number;
  }>>([]);

  // Notification management functions
  const addNotification = useCallback((type: 'success' | 'error' | 'info', title: string, message: string) => {
    const id = Date.now().toString();
    const notification = {
      id,
      type,
      title,
      message,
      timestamp: Date.now()
    };

    setNotifications(prev => [...prev, notification]);

    // Auto-remove after 5 seconds
    setTimeout(() => {
      removeNotification(id);
    }, 5000);
  }, []);

  const removeNotification = useCallback((id: string) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
  }, []);

  // Optimized form change handlers to prevent unnecessary re-renders
  const handleDatasetFormChange = useCallback((field: string, value: string | number) => {
    setDatasetForm(prev => ({ ...prev, [field]: value }));
  }, []);

  // Update ref when form changes
  useEffect(() => {
    datasetFormRef.current = datasetForm;
  }, [datasetForm]);

  const similarityHelpText = useMemo(() => {
    const helpTexts: Record<string, string> = {
      type1_exact: 'Creates identical code segments for testing exact copy detection.',
      type2_renamed: 'Generates code with renamed variables and functions.',
      type3_modified: 'Produces code with added comments, reordered statements, or modified structure.',
      type4_semantic: 'Creates functionally equivalent code with different algorithms or syntax.',
      token_similarity: 'Focuses on programming-language token patterns and usage.',
      structural_similarity: 'Emphasizes code organization and structural similarities.',
      semantic_similarity: 'Generates conceptually similar solutions using different approaches.',
    };
    return helpTexts[datasetForm.similarityType] || '';
  }, [datasetForm.similarityType]);

  const handleCreateUser = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const passwordError = validatePasswordInput(form.password);
    if (!form.full_name.trim() || !form.email.trim()) {
      setError('Full name and email are required.');
      return;
    }
    if (passwordError) {
      setError(passwordError);
      return;
    }

    setSaving(true);
    setError('');
    try {
      await createUser({
        full_name: form.full_name.trim(),
        email: form.email.trim(),
        password: form.password,
        role: form.role,
        tenant_name: form.tenant_name.trim(),
      });
      setForm({
        full_name: '',
        email: '',
        password: '',
        role: 'professor',
        tenant_name: '',
      });
      await loadUsers();
      addNotification('success', 'User Created', 'The new account is ready to use.');
    } catch (createError) {
      const message = getErrorMessage(createError);
      setError(message);
      addNotification('error', 'User Creation Failed', message);
    } finally {
      setSaving(false);
    }
  };

  const createDemoDataset = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setCreatingDataset(true);

    try {
      const result = await axios.post('/api/admin/create-demo-dataset', datasetForm);

      if (result.data && result.data.files_created) {
        const datasetName = result.data.dataset?.name || datasetForm.name;
        const filesCreated = result.data.files_created;
        const language = datasetForm.language;
        const similarityType = datasetForm.similarityType
          .replace(/_/g, ' ')
          .replace(/\b\w/g, l => l.toUpperCase())
          .replace(/Type (\d)/g, 'Type-$1');

        const successMessage = `Dataset: ${datasetName} | Language: ${language.charAt(0).toUpperCase() + language.slice(1)} | Type: ${similarityType} | Files: ${filesCreated}`;

        addNotification('success', 'Demo Dataset Created!', successMessage);
      } else {
        addNotification('success', 'Dataset Created', 'Demo dataset has been created successfully.');
      }

      // Reset form
      setDatasetForm({
        name: '',
        description: '',
        language: 'python',
        numFiles: 10,
        similarityType: 'type1_exact',
      });
    } catch (error: unknown) {
      console.error('Demo dataset creation error:', error);

      let errorTitle = 'Creation Failed';
      let errorMessage = 'Failed to create demo dataset.';

      if (
        typeof error === 'object' &&
        error !== null &&
        'response' in error &&
        typeof error.response === 'object' &&
        error.response !== null &&
        'status' in error.response &&
        (error.response.status === 401 || error.response.status === 403)
      ) {
        errorTitle = 'Authentication Required';
        errorMessage = 'Please ensure you are logged in as an administrator.';
      } else if (
        typeof error === 'object' &&
        error !== null &&
        'response' in error &&
        typeof error.response === 'object' &&
        error.response !== null &&
        'data' in error.response &&
        typeof error.response.data === 'object' &&
        error.response.data !== null &&
        'detail' in error.response.data &&
        typeof error.response.data.detail === 'string'
      ) {
        errorMessage = error.response.data.detail;
      } else if (
        typeof error === 'object' &&
        error !== null &&
        'response' in error &&
        typeof error.response === 'object' &&
        error.response !== null &&
        'data' in error.response &&
        typeof error.response.data === 'object' &&
        error.response.data !== null &&
        'message' in error.response.data &&
        typeof error.response.data.message === 'string'
      ) {
        errorMessage = error.response.data.message;
      } else if (error instanceof Error) {
        errorMessage = 'Please check your connection and try again.';
      } else {
        errorMessage = 'Please check your permissions and try again.';
      }

      addNotification('error', errorTitle, errorMessage);
    } finally {
      setCreatingDataset(false);
    }
  };

  return (
    <DashboardLayout requiredRole="admin">
      <div className="px-4 py-4 lg:px-6 lg:py-6">
        {notifications.length > 0 && (
          <div className="fixed top-4 right-4 z-50 space-y-2 max-w-sm">
            {notifications.map((notification) => (
              <div
                key={notification.id}
                className={`p-4 rounded-lg shadow-lg border backdrop-blur-sm transition-all duration-300 animate-in slide-in-from-right-2 ${
                  notification.type === 'success'
                    ? 'bg-green-50 border-green-200 text-green-800'
                    : notification.type === 'error'
                    ? 'bg-red-50 border-red-200 text-red-800'
                    : 'bg-blue-50 border-blue-200 text-blue-800'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-start space-x-3">
                    <div className={`flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center ${
                      notification.type === 'success'
                        ? 'bg-green-100'
                        : notification.type === 'error'
                        ? 'bg-red-100'
                        : 'bg-blue-100'
                    }`}>
                      {notification.type === 'success' ? '✅' :
                       notification.type === 'error' ? '❌' : 'ℹ️'}
                    </div>
                    <div className="flex-1">
                      <h4 className="text-sm font-semibold">{notification.title}</h4>
                      <p className="text-sm mt-1">{notification.message}</p>
                    </div>
                  </div>
                  <button
                    onClick={() => removeNotification(notification.id)}
                    className="flex-shrink-0 ml-4 text-current hover:opacity-70 transition-opacity"
                  >
                    ×
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
        <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
          <section className="theme-card-strong theme-section-line rounded-[30px] p-6 lg:p-8">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="inline-flex items-center gap-2 rounded-full border border-blue-600/10 bg-blue-600/[0.06] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-blue-600">
                  <Users size={14} />
                  Account Directory
                </div>
                <h1 className="mt-4 text-3xl font-semibold text-[var(--text-primary)]">User administration</h1>
                <p className="mt-2 max-w-2xl text-sm leading-7 text-[var(--text-secondary)]">
                  Create professor and admin accounts, review last sign-in activity, and keep the deployment owned by real users instead of shared credentials.
                </p>
              </div>
              <div className="rounded-3xl border border-[color:var(--border)] bg-[var(--surface-muted)] px-5 py-4">
                <div className="text-[11px] uppercase tracking-[0.2em] text-[var(--text-muted)]">Accounts</div>
                <div className="mt-2 text-3xl font-semibold text-[var(--text-primary)]">{users.length}</div>
              </div>
            </div>

            {error && (
              <div className="mt-6 flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <div className="mt-6 overflow-hidden rounded-[28px] border border-[color:var(--border)] bg-[var(--surface)]">
              <div className="grid grid-cols-[1.4fr_1fr_1fr_1.1fr] gap-4 border-b border-[color:var(--border)] px-5 py-3 text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                <div>User</div>
                <div>Role</div>
                <div>Workspace</div>
                <div>Last Login</div>
              </div>
              {loading ? (
                <div className="px-5 py-8 text-sm text-[var(--text-muted)]">Loading users...</div>
              ) : users.length === 0 ? (
                <div className="px-5 py-8 text-sm text-[var(--text-muted)]">No users found yet.</div>
              ) : (
                <div className="divide-y divide-[color:var(--border)]">
                  {users.map((user) => (
                    <div key={user.id} className="grid grid-cols-[1.4fr_1fr_1fr_1.1fr] gap-4 px-5 py-4 text-sm">
                      <div className="min-w-0">
                        <div className="truncate font-medium text-[var(--text-primary)]">{user.full_name}</div>
                        <div className="truncate text-[var(--text-muted)]">{user.email}</div>
                      </div>
                      <div>
                        <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${user.role === 'admin' ? 'bg-violet-100 text-violet-700' : 'bg-blue-100 text-blue-700'}`}>
                          {user.role === 'admin' ? 'Admin' : 'Professor'}
                        </span>
                      </div>
                      <div className="text-[var(--text-secondary)]">{user.tenant_name || 'No workspace'}</div>
                      <div className="text-[var(--text-secondary)]">{formatDate(user.last_login_at)}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>

          <section className="theme-card rounded-[30px] p-6 lg:p-8">
            <div className="inline-flex items-center gap-2 rounded-full border border-[color:var(--border)] bg-[var(--surface-muted)] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
              <UserPlus size={14} />
              Create Account
            </div>
            <h2 className="mt-4 text-2xl font-semibold text-[var(--text-primary)]">Add a new user</h2>
            <p className="mt-2 text-sm leading-7 text-[var(--text-secondary)]">
              Every new account gets its own workspace tenant by default so professor results stay separated.
            </p>

            <form className="mt-6 space-y-6" onSubmit={handleCreateUser}>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-[var(--text-secondary)]">Full Name</label>
                <input
                  value={form.full_name}
                  onChange={(event) => setForm((current) => ({ ...current, full_name: event.target.value }))}
                  className="w-full rounded-2xl border border-[color:var(--border)] bg-[var(--surface)] px-4 py-3 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                  placeholder="Professor Grace Hopper"
                />
              </div>

              <div>
                <label className="mb-1.5 block text-sm font-medium text-[var(--text-secondary)]">Email</label>
                <input
                  type="email"
                  value={form.email}
                  onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
                  className="w-full rounded-2xl border border-[color:var(--border)] bg-[var(--surface)] px-4 py-3 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                  placeholder="name@university.edu"
                />
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-[var(--text-secondary)]">Role</label>
                  <select
                    value={form.role}
                    onChange={(event) => setForm((current) => ({ ...current, role: event.target.value as AuthRole }))}
                    className="w-full rounded-2xl border border-[color:var(--border)] bg-[var(--surface)] px-4 py-3 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                  >
                    <option value="professor">Professor</option>
                    <option value="admin">Admin</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-[var(--text-secondary)]">Workspace Name</label>
                  <input
                    value={form.tenant_name}
                    onChange={(event) => setForm((current) => ({ ...current, tenant_name: event.target.value }))}
                    className="w-full rounded-2xl border border-[color:var(--border)] bg-[var(--surface)] px-4 py-3 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                    placeholder="Optional custom workspace"
                  />
                </div>
              </div>

              <div>
                <label className="mb-1.5 block text-sm font-medium text-[var(--text-secondary)]">Temporary Password</label>
                <input
                  type="password"
                  value={form.password}
                  onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
                  className="w-full rounded-2xl border border-[color:var(--border)] bg-[var(--surface)] px-4 py-3 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                  placeholder="At least 8 characters"
                />
                <p className="mt-2 text-xs text-[var(--text-muted)]">
                  Use at least 8 characters for new accounts.
                </p>
              </div>

              <button
                type="submit"
                disabled={saving}
                className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <ShieldCheck size={16} />
                {saving ? 'Creating user...' : 'Create user'}
              </button>
            </form>
          </section>

          <section className="theme-card-strong theme-section-line rounded-[30px] p-6 lg:p-8">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="inline-flex items-center gap-2 rounded-full border border-emerald-600/10 bg-emerald-600/[0.06] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-emerald-600">
                  <Database size={14} />
                  Dataset Tools
                </div>
                <h1 className="mt-4 text-3xl font-semibold text-[var(--text-primary)]">Demo dataset creation</h1>
                <p className="mt-2 max-w-2xl text-sm leading-7 text-[var(--text-secondary)]">
                  Generate synthetic datasets for testing plagiarism detection algorithms. Create custom datasets with controlled similarity patterns.
                </p>
              </div>
              <div className="rounded-3xl border border-[color:var(--border)] bg-[var(--surface-muted)] px-5 py-4">
                <div className="text-[11px] uppercase tracking-[0.2em] text-[var(--text-muted)]">Available</div>
                <div className="mt-2 text-3xl font-semibold text-[var(--text-primary)]">∞</div>
              </div>
            </div>

            <form className="mt-6 space-y-6" onSubmit={createDemoDataset}>
              <div className="grid gap-6 sm:grid-cols-2">
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-[var(--text-secondary)]">Dataset Name</label>
                  <input
                    type="text"
                    value={datasetForm.name}
                    onChange={(event) => handleDatasetFormChange('name', event.target.value)}
                    className="w-full rounded-2xl border border-[color:var(--border)] bg-[var(--surface)] px-4 py-3 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                    placeholder="my_test_dataset"
                    required
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-[var(--text-secondary)]">Programming Language</label>
                  <select
                    value={datasetForm.language}
                    onChange={(event) => handleDatasetFormChange('language', event.target.value)}
                    className="w-full rounded-2xl border border-[color:var(--border)] bg-[var(--surface)] px-4 py-3 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                  >
                    <option value="python">Python</option>
                    <option value="java">Java</option>
                    <option value="javascript">JavaScript</option>
                    <option value="cpp">C++</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="mb-1.5 block text-sm font-medium text-[var(--text-secondary)]">Description</label>
                  <input
                    type="text"
                    value={datasetForm.description}
                    onChange={(event) => handleDatasetFormChange('description', event.target.value)}
                    className="w-full rounded-2xl border border-[color:var(--border)] bg-[var(--surface)] px-4 py-3 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                    placeholder="Dataset for testing plagiarism detection"
                  />
              </div>

              <div className="grid gap-6 sm:grid-cols-2">
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-[var(--text-secondary)]">Number of Files</label>
                  <input
                    type="number"
                    min="5"
                    max="100"
                    value={datasetForm.numFiles}
                    onChange={(event) => handleDatasetFormChange('numFiles', parseInt(event.target.value) || 10)}
                    className="w-full rounded-2xl border border-[color:var(--border)] bg-[var(--surface)] px-4 py-3 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-[var(--text-secondary)]">Similarity Type</label>
                  <select
                    value={datasetForm.similarityType}
                    onChange={(event) => handleDatasetFormChange('similarityType', event.target.value)}
                    className="w-full rounded-2xl border border-[color:var(--border)] bg-[var(--surface)] px-4 py-3 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                  >
                    <option value="type1_exact">Type 1 - Exact Copy (Direct copy-paste)</option>
                    <option value="type2_renamed">Type 2 - Renamed Identifiers (Variable renaming)</option>
                    <option value="type3_modified">Type 3 - Modified Structure (Added/removed code)</option>
                    <option value="type4_semantic">Type 4 - Semantic Equivalence (Different syntax, same behavior)</option>
                    <option value="token_similarity">Token-Level Similarity (Programming style patterns)</option>
                    <option value="structural_similarity">Structural Similarity (Code organization)</option>
                    <option value="semantic_similarity">Semantic Similarity (Conceptual equivalence)</option>
                  </select>
                  <p className="mt-2 text-xs text-slate-500">
                    {similarityHelpText}
                  </p>
                </div>
              </div>



              <button
                type="submit"
                disabled={creatingDataset}
                className="inline-flex w-full items-center justify-center gap-3 rounded-2xl bg-emerald-600 px-8 py-5 text-base font-semibold text-white transition-colors duration-200 hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {creatingDataset && <Loader2 size={18} className="animate-spin" />}
                {creatingDataset ? 'Generating code samples...' : 'Create Demo Dataset'}
              </button>
            </form>
          </section>
        </div>
      </div>
    </DashboardLayout>
  );
}
