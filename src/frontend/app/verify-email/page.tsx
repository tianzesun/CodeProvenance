'use client';

import { ReactNode, Suspense, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { apiClient } from '@/lib/apiClient';
import { AlertTriangle, ArrowLeft, CheckCircle, Loader2 } from 'lucide-react';

/* -------------------------------------------------------------------------- */
/* Helpers                                                                    */
/* -------------------------------------------------------------------------- */

const REFERENCE_HEADERS = ['x-correlation-id', 'x-request-id'];

function getErrorInfo(error: unknown): { status?: number; reference?: string; retryAfter?: number } {
  const response = (error as { response?: { status?: unknown; headers?: unknown } } | null)?.response;
  if (!response || typeof response !== 'object') {
    return {};
  }

  const status = typeof response.status === 'number' ? response.status : undefined;
  const headers = (response.headers ?? {}) as Record<string, unknown>;
  const reference = REFERENCE_HEADERS.map((name) => headers[name]).find(
    (value): value is string => typeof value === 'string' && value.length > 0
  );
  const retryHeader = Number(headers['retry-after']);
  const retryAfter =
    Number.isFinite(retryHeader) && retryHeader > 0 ? Math.min(Math.ceil(retryHeader), 300) : undefined;

  return { status, reference, retryAfter };
}

/**
 * Generic, status-keyed messages; server text is never echoed. A correlation /
 * request id header, when the backend sends one, is appended for support.
 */
function describeFailure(error: unknown): { kind: 'invalid' | 'retry'; message: string; retryAfter?: number } {
  const { status, reference, retryAfter } = getErrorInfo(error);
  const withReference = (message: string) => (reference ? `${message} (Reference: ${reference})` : message);

  if (status === undefined) {
    return { kind: 'retry', message: withReference('Something went wrong. Please try again.') };
  }
  if (status === 429) {
    return { kind: 'retry', message: withReference('Too many attempts. Please wait a moment and try again.'), retryAfter };
  }
  if (status >= 500) {
    return { kind: 'retry', message: withReference('Something went wrong on our side. Please try again.') };
  }

  // Any other 4xx: the server answers "already redeemed" with success, so what
  // is left is a token that is wrong or has expired.
  return { kind: 'invalid', message: withReference('This verification link is invalid or has expired.') };
}

/* -------------------------------------------------------------------------- */
/* Layout                                                                     */
/* -------------------------------------------------------------------------- */

function PageShell({ children }: { children: ReactNode }) {
  return (
    <main className="min-h-screen bg-slate-950 px-4 py-10 text-slate-100">
      <div className="mx-auto max-w-md">
        <div className="rounded-[32px] border border-slate-200 bg-white p-8 text-center shadow-xl">{children}</div>
      </div>
    </main>
  );
}

const PRIMARY_LINK =
  'theme-button-primary mt-6 inline-flex items-center justify-center gap-2 rounded-2xl px-5 py-3 text-sm font-semibold transition';
const DARK_BUTTON =
  'mt-6 inline-flex items-center justify-center gap-2 rounded-2xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60';

/* -------------------------------------------------------------------------- */
/* Page                                                                       */
/* -------------------------------------------------------------------------- */

type Status = 'loading' | 'verified' | 'invalid' | 'retry';

/**
 * Redeem the emailed verification link.
 *
 * The POST runs once per attempt; the server treats a link that was already
 * redeemed as success, so a mail scanner pre-fetching the URL cannot break the
 * page. Only an invalid or expired token is a dead end. Network failures,
 * rate limits and server errors offer a retry instead of telling the user their
 * (still valid) link has expired.
 */
function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const token = searchParams?.get('token')?.trim() || null;

  const [status, setStatus] = useState<Status>(token ? 'loading' : 'invalid');
  const [message, setMessage] = useState('');
  const [attempt, setAttempt] = useState(0);
  const [cooldown, setCooldown] = useState(0);
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    if (!token) {
      return;
    }

    let cancelled = false;
    setStatus('loading');

    apiClient
      .post('/api/auth/verify-email', { token }, { timeout: 15000 })
      .then(() => {
        if (!cancelled) setStatus('verified');
      })
      .catch((error) => {
        if (cancelled) return;
        const failure = describeFailure(error);
        setMessage(failure.message);
        setStatus(failure.kind);
        if (failure.retryAfter) setCooldown(failure.retryAfter);
      });

    return () => {
      cancelled = true;
    };
  }, [token, attempt]);

  // Rate-limit countdown for the retry button.
  useEffect(() => {
    if (cooldown <= 0) {
      return;
    }
    const timer = setTimeout(() => setCooldown((seconds) => seconds - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  // Move focus to the result heading so screen-reader and keyboard users land on it.
  useEffect(() => {
    if (status !== 'loading') {
      headingRef.current?.focus();
    }
  }, [status]);

  if (status === 'loading') {
    return (
      <div role="status">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-100 text-blue-600">
          <Loader2 size={20} className="animate-spin" aria-hidden="true" />
        </div>
        <p className="mt-4 text-sm text-slate-600">Verifying your email…</p>
      </div>
    );
  }

  if (status === 'verified') {
    return (
      <>
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-3xl bg-emerald-100 text-emerald-600">
          <CheckCircle size={24} aria-hidden="true" />
        </div>
        <h1 ref={headingRef} tabIndex={-1} className="mt-4 text-xl font-semibold text-slate-900 outline-none">
          Email verified
        </h1>
        <p className="mt-2 text-sm text-slate-600">
          Your account is active. Sign in with your email and password to get started.
        </p>
        {/* method=email opens the email form, which is where a self-registered account signs in. */}
        <Link href="/login?method=email" className={PRIMARY_LINK}>
          Continue to sign in
        </Link>
      </>
    );
  }

  const retryable = status === 'retry';

  return (
    <>
      <div
        className={`mx-auto flex h-16 w-16 items-center justify-center rounded-3xl ${
          retryable ? 'bg-amber-100 text-amber-600' : 'bg-red-100 text-red-600'
        }`}
      >
        <AlertTriangle size={24} aria-hidden="true" />
      </div>
      <h1 ref={headingRef} tabIndex={-1} className="mt-4 text-xl font-semibold text-slate-900 outline-none">
        {retryable ? 'We couldn’t verify your email yet' : 'Verification failed'}
      </h1>
      <p className="mt-2 text-sm text-slate-600">
        {token ? message : 'This verification link is missing its token.'}
      </p>

      {retryable ? (
        <>
          <p className="mt-2 text-sm text-slate-500">Your link is probably still valid, so you can try again.</p>
          <button
            type="button"
            onClick={() => setAttempt((count) => count + 1)}
            disabled={cooldown > 0}
            className={DARK_BUTTON}
          >
            {cooldown > 0 ? `Try again in ${cooldown}s` : 'Try again'}
          </button>
          <div className="mt-4">
            <Link href="/login" className="text-sm text-slate-500 underline hover:text-slate-700">
              Back to sign in
            </Link>
          </div>
        </>
      ) : (
        <>
          <p className="mt-2 text-sm text-slate-500">
            Verification links expire after 24 hours — create the account again from the sign-in page to have a
            fresh link sent.
          </p>
          <Link href="/login" className={DARK_BUTTON}>
            <ArrowLeft size={16} aria-hidden="true" />
            Back to sign in
          </Link>
        </>
      )}
    </>
  );
}

export default function VerifyEmailPage() {
  return (
    <PageShell>
      <Suspense
        fallback={
          <div role="status">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-100 text-blue-600">
              <Loader2 size={20} className="animate-spin" aria-hidden="true" />
            </div>
            <p className="mt-4 text-sm text-slate-600">Loading...</p>
          </div>
        }
      >
        <VerifyEmailContent />
      </Suspense>
    </PageShell>
  );
}
