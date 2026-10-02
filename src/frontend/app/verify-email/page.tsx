'use client';

import { useEffect, useState, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { apiClient } from '@/lib/apiClient';
import { AlertTriangle, ArrowLeft, CheckCircle, Loader2 } from 'lucide-react';

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

  return 'Something went wrong. Please try again.';
}

/**
 * Redeem the emailed verification link.
 *
 * The POST runs once on mount; the server treats a link that was already
 * redeemed as success, so a mail scanner pre-fetching the URL cannot break
 * the page. Only an invalid or expired token lands in the error state.
 */
function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const token = searchParams?.get('token') ?? null;

  const [status, setStatus] = useState<'loading' | 'verified' | 'error'>(
    token ? 'loading' : 'error'
  );
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!token) {
      setMessage('This verification link is missing its token.');
      return;
    }

    let cancelled = false;

    apiClient
      .post('/api/auth/verify-email', { token })
      .then(() => {
        if (!cancelled) setStatus('verified');
      })
      .catch((error) => {
        if (!cancelled) {
          setStatus('error');
          setMessage(getErrorMessage(error));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [token]);

  if (status === 'loading') {
    return (
      <>
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-100 text-blue-600">
          <Loader2 size={20} className="animate-spin" aria-hidden="true" />
        </div>
        <p className="mt-4 text-sm text-slate-600">Verifying your email…</p>
      </>
    );
  }

  if (status === 'verified') {
    return (
      <>
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-3xl bg-emerald-100 text-emerald-600">
          <CheckCircle size={24} aria-hidden="true" />
        </div>
        <h2 className="mt-4 text-xl font-semibold text-slate-900">Email verified</h2>
        <p className="mt-2 text-sm text-slate-600">
          Your account is active. Sign in with your email and password to get started.
        </p>
        <Link
          href="/login"
          className="theme-button-primary mt-6 inline-flex items-center justify-center gap-2 rounded-2xl px-5 py-3 text-sm font-semibold transition"
        >
          Continue to sign in
        </Link>
      </>
    );
  }

  return (
    <>
      <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-3xl bg-red-100 text-red-600">
        <AlertTriangle size={24} aria-hidden="true" />
      </div>
      <h2 className="mt-4 text-xl font-semibold text-slate-900">Verification failed</h2>
      <p className="mt-2 text-sm text-slate-600">{message}</p>
      <p className="mt-2 text-sm text-slate-500">
        Verification links expire after 24 hours — create the account again from the sign-in
        page to have a fresh link sent.
      </p>
      <Link
        href="/login"
        className="mt-6 inline-flex items-center justify-center gap-2 rounded-2xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800"
      >
        <ArrowLeft size={16} aria-hidden="true" />
        Back to sign in
      </Link>
    </>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-slate-950 px-4 py-10 text-slate-100">
        <div className="mx-auto max-w-md">
          <div className="rounded-[32px] border border-slate-200 bg-white p-8 text-center shadow-xl">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-100 text-blue-600">
              <Loader2 size={20} className="animate-spin" />
            </div>
            <p className="mt-4 text-sm text-slate-600">Loading...</p>
          </div>
        </div>
      </div>
    }>
      <div className="min-h-screen bg-slate-950 px-4 py-10 text-slate-100">
        <div className="mx-auto max-w-md">
          <div className="rounded-[32px] border border-slate-200 bg-white p-8 text-center shadow-xl">
            <VerifyEmailContent />
          </div>
        </div>
      </div>
    </Suspense>
  );
}
