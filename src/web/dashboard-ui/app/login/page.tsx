'use client';

import { FormEvent, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertTriangle, LockKeyhole, ShieldCheck } from 'lucide-react';

import { useAuth } from '@/components/AuthProvider';

function getErrorMessage(error: any): string {
  return error?.response?.data?.detail || 'Something went wrong. Please try again.';
}

function validatePasswordInput(password: string): string | null {
  if (password.length < 8) {
    return 'Password must be at least 8 characters long.';
  }

  return null;
}

export default function LoginPage() {
  const router = useRouter();
  const { user, loading, bootstrapped, login, bootstrapAdmin } = useAuth();

  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [tenantName, setTenantName] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [nextPath, setNextPath] = useState('/');

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setNextPath(params.get('next') || '/');
  }, []);

  useEffect(() => {
    if (!loading && user) {
      router.replace(nextPath);
    }
  }, [loading, nextPath, router, user]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');

    const passwordError = validatePasswordInput(password);
    if (passwordError) {
      setError(passwordError);
      return;
    }

    setSubmitting(true);

    try {
      if (bootstrapped) {
        await login(email, password);
      } else {
        await bootstrapAdmin({
          email,
          full_name: fullName,
          password,
          tenant_name: tenantName,
        });
      }
      router.replace(nextPath);
    } catch (authError) {
      setError(getErrorMessage(authError));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 px-4 py-10 text-slate-100">
      <div className="mx-auto grid min-h-[calc(100vh-5rem)] max-w-6xl gap-8 lg:grid-cols-[1.1fr_0.9fr]">
        <section className="relative overflow-hidden rounded-[36px] border border-white/10 bg-gradient-to-br from-slate-900 via-slate-950 to-blue-950 px-8 py-10 shadow-2xl">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(59,130,246,0.18),_transparent_45%),radial-gradient(circle_at_bottom_right,_rgba(14,165,233,0.12),_transparent_40%)]" />
          <div className="relative space-y-8">
            <div className="inline-flex items-center gap-2 rounded-full border border-blue-400/20 bg-blue-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-blue-200">
              <ShieldCheck size={14} />
              IntegrityDesk Access
            </div>
            <div className="space-y-4">
              <h1 className="max-w-xl font-display text-4xl font-semibold leading-tight sm:text-5xl">
                {bootstrapped ? 'Sign in to the review workspace.' : 'Create the first administrator account.'}
              </h1>
              <p className="max-w-2xl text-sm leading-7 text-slate-300 sm:text-base">
                {bootstrapped
                  ? 'Professors get a private assignment-review workspace. Admins can also manage accounts and system-wide settings.'
                  : 'The first account becomes the administrator for this deployment and gets a dedicated workspace tenant.'}
              </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <div className="rounded-3xl border border-white/10 bg-white/5 p-4">
                <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Role Model</div>
                <div className="mt-3 text-lg font-semibold">Admin + Professor</div>
                <div className="mt-2 text-sm text-slate-300">Admins manage users. Professors run checks and review findings.</div>
              </div>
              <div className="rounded-3xl border border-white/10 bg-white/5 p-4">
                <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Session</div>
                <div className="mt-3 text-lg font-semibold">HTTP-only cookie</div>
                <div className="mt-2 text-sm text-slate-300">The browser never receives the stored password hash or auth secret.</div>
              </div>
              <div className="rounded-3xl border border-white/10 bg-white/5 p-4">
                <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Isolation</div>
                <div className="mt-3 text-lg font-semibold">Per-user workspace</div>
                <div className="mt-2 text-sm text-slate-300">Job lists and reports are scoped to the authenticated account.</div>
              </div>
            </div>
          </div>
        </section>

        <section className="flex items-center">
          <div className="w-full rounded-[32px] border border-slate-200 bg-white p-8 shadow-xl">
            <div className="mb-6">
              <div className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-slate-600">
                <LockKeyhole size={14} />
                {bootstrapped ? 'Secure Sign In' : 'Bootstrap'}
              </div>
              <h2 className="mt-4 text-2xl font-semibold text-slate-900">
                {bootstrapped ? 'Welcome back' : 'Set up the first admin'}
              </h2>
              <p className="mt-2 text-sm leading-6 text-slate-500">
                {bootstrapped
                  ? 'Use your email and password to open the dashboard.'
                  : 'This only appears until the first administrator account exists.'}
              </p>
            </div>

            <form className="space-y-4" onSubmit={handleSubmit}>
              {!bootstrapped && (
                <>
                  <div>
                    <label className="mb-1.5 block text-sm font-medium text-slate-700">Full Name</label>
                    <input
                      value={fullName}
                      onChange={(event) => setFullName(event.target.value)}
                      className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-slate-900 placeholder:text-slate-400 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                      placeholder="Professor Ada Lovelace"
                    />
                  </div>
                  <div>
                    <label className="mb-1.5 block text-sm font-medium text-slate-700">Workspace Name</label>
                    <input
                      value={tenantName}
                      onChange={(event) => setTenantName(event.target.value)}
                      className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-slate-900 placeholder:text-slate-400 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                      placeholder="Computer Science Department"
                    />
                  </div>
                </>
              )}

              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-slate-900 placeholder:text-slate-400 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                  placeholder="name@university.edu"
                />
              </div>

              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-slate-900 placeholder:text-slate-400 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                  placeholder="At least 8 characters"
                />
                <p className="mt-2 text-xs text-slate-400">
                  Use at least 8 characters.
                </p>
              </div>

              {error && (
                <div className="flex items-start gap-2 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              <button
                type="submit"
                disabled={loading || submitting}
                className="inline-flex w-full items-center justify-center rounded-2xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? 'Working...' : bootstrapped ? 'Sign In' : 'Create Admin Account'}
              </button>
            </form>
          </div>
        </section>
      </div>
    </div>
  );
}
