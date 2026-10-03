'use client';

import { useEffect, useRef, useState } from 'react';
// global-error replaces the root layout, so the stylesheet imported there is not applied here unless it is
// imported again. Without this line the page can render unstyled (Tailwind classes and the theme variables missing).
import './globals.css';

// Technical details (message, stack) are shown only while developing. In production they used to be
// printed for every user: stack traces expose file paths and code, and messages can carry data from the page
// (a file name, part of an API response) that the person shouldn't be shown or asked to copy into an email.
const SHOW_TECHNICAL_DETAILS = process.env.NODE_ENV === 'development';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const [copied, setCopied] = useState(false);
  const [occurredAt, setOccurredAt] = useState('');

  useEffect(() => {
    // This was a console.error in the component body, so it ran on every render and printed the whole error
    // (stack and message included). It now logs once, and in production only the error type and its digest.
    if (SHOW_TECHNICAL_DETAILS) {
      console.error('Global error:', error);
    } else {
      console.error('Application error:', error?.name || 'Error', error?.digest || '(no digest)');
    }
    // Hook for an error-reporting service (Sentry, an /api/client-errors endpoint, ...) goes here.

    setOccurredAt(new Intl.DateTimeFormat('en-CA', { dateStyle: 'medium', timeStyle: 'medium' }).format(new Date()));
    // Move focus to the message so keyboard and screen-reader users land on it.
    headingRef.current?.focus();
  }, [error]);

  const reference = error?.digest;

  const copyReference = async () => {
    if (!reference) return;
    try {
      await navigator.clipboard.writeText(reference);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard unavailable; the reference is visible and can be selected by hand */
    }
  };

  return (
    <html lang="en-CA">
      <head>
        <title>Something went wrong | IntegrityDesk</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta name="robots" content="noindex, nofollow" />
      </head>
      <body className="bg-[var(--background)] text-[var(--text-primary)]">
        <main className="flex min-h-screen flex-col items-center justify-center px-8 py-12">
          <div className="theme-card w-full max-w-lg rounded-[30px] p-8 text-center">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-red-500/10 text-red-500">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
            </div>

            <div role="alert">
              <h1
                ref={headingRef}
                tabIndex={-1}
                className="font-display mt-5 text-2xl font-semibold text-[var(--text-primary)] outline-none"
              >
                Something went wrong
              </h1>

              {/* The old text said "This has been logged and will be investigated", but nothing here sends the
                  error anywhere, so it promised something that wasn't happening. */}
              <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">
                An unexpected error occurred. You can try again, reload the page, or return to the dashboard.
                If it keeps happening, contact support and tell them what you were doing
                {reference ? ' along with the reference below' : ' and the time shown below'}.
              </p>
            </div>

            <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
              <button
                type="button"
                onClick={reset}
                className="theme-button-primary inline-flex items-center gap-2 rounded-2xl px-6 py-3 text-sm font-semibold"
              >
                Try Again
              </button>

              {/* A full reload: "Try Again" re-renders the same broken tree, which often fails the same way. */}
              <button
                type="button"
                onClick={() => window.location.reload()}
                className="theme-button-secondary inline-flex items-center gap-2 rounded-2xl px-6 py-3 text-sm font-semibold"
              >
                Reload Page
              </button>

              {/* A plain link on purpose. This page replaces the whole app shell, so a client-side <Link>
                  navigation can keep the broken state; a normal navigation starts clean. */}
              <a
                href="/"
                className="theme-button-secondary inline-flex items-center gap-2 rounded-2xl px-6 py-3 text-sm font-semibold"
              >
                Go to Dashboard
              </a>
            </div>

            <dl className="mt-8 space-y-1 text-xs text-[var(--text-muted)]">
              {reference && (
                <div className="flex items-center justify-center gap-2">
                  <dt className="font-semibold uppercase tracking-[0.15em]">Reference</dt>
                  <dd className="font-mono select-all">{reference}</dd>
                  <button
                    type="button"
                    onClick={copyReference}
                    className="rounded-lg border border-current/20 px-2 py-0.5 font-semibold hover:opacity-80"
                  >
                    {copied ? 'Copied' : 'Copy'}
                  </button>
                </div>
              )}
              {occurredAt && (
                <div className="flex items-center justify-center gap-2">
                  <dt className="font-semibold uppercase tracking-[0.15em]">Time</dt>
                  <dd>{occurredAt}</dd>
                </div>
              )}
            </dl>

            {SHOW_TECHNICAL_DETAILS && (
              <details className="mt-8 text-left">
                <summary className="cursor-pointer text-xs font-semibold uppercase tracking-[0.15em] text-[var(--text-muted)]">
                  Error details (development only)
                </summary>
                <pre className="theme-card-muted mt-3 max-h-48 overflow-auto rounded-2xl p-4 text-xs leading-5 text-[var(--text-muted)]">
                  {error.message}
                  {error.stack && `\n\n${error.stack}`}
                </pre>
              </details>
            )}
          </div>
        </main>
      </body>
    </html>
  );
}
