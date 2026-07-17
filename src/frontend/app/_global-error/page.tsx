'use client';

import Link from 'next/link';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  console.error('Global error:', error);

  return (
    <html lang="en">
      <head>
        <title>Something went wrong - IntegrityDesk</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </head>
      <body className="bg-[var(--background)] text-[var(--text-primary)]">
        <div className="flex min-h-screen flex-col items-center justify-center px-8 py-12">
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
              >
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
            </div>

            <h1 className="font-display mt-5 text-2xl font-semibold text-[var(--text-primary)]">
              Something went wrong
            </h1>

            <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">
              An unexpected error occurred. This has been logged and will be investigated.
            </p>

            <div className="mt-6 flex items-center justify-center gap-3">
              <button
                type="button"
                onClick={reset}
                className="theme-button-primary inline-flex items-center gap-2 rounded-2xl px-6 py-3 text-sm font-semibold"
              >
                Try Again
              </button>

              <Link
                href="/"
                className="theme-button-secondary inline-flex items-center gap-2 rounded-2xl px-6 py-3 text-sm font-semibold"
              >
                Go to Dashboard
              </Link>
            </div>

            <details className="mt-8 text-left">
              <summary className="cursor-pointer text-xs font-semibold uppercase tracking-[0.15em] text-[var(--text-muted)]">
                Error details
              </summary>
              <pre className="theme-card-muted mt-3 max-h-48 overflow-auto rounded-2xl p-4 text-xs leading-5 text-[var(--text-muted)]">
                {error.message}
                {error.stack && `\n\n${error.stack}`}
              </pre>
            </details>
          </div>
        </div>
      </body>
    </html>
  );
}
