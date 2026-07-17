'use client';

import React, { Component, ErrorInfo, ReactNode } from 'react';
import Link from 'next/link';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  route?: string;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="flex min-h-[400px] items-center justify-center px-4 py-12">
          <div className="theme-card w-full max-w-md rounded-[30px] p-8 text-center">
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
                <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
                <line x1="12" y1="9" x2="12" y2="13" />
                <line x1="12" y1="17" x2="12.01" y2="17" />
              </svg>
            </div>

            <h2 className="font-display mt-5 text-xl font-semibold text-[var(--text-primary)]">
              Something went wrong
            </h2>

            {this.props.route && (
              <p className="mt-2 text-xs font-medium text-[var(--text-muted)]">
                Route: {this.props.route}
              </p>
            )}

            <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">
              An error occurred while rendering this section. Please try again or return to the dashboard.
            </p>

            <div className="mt-6 flex items-center justify-center gap-3">
              <button
                type="button"
                onClick={this.handleReset}
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

            {this.state.error && (
              <details className="mt-8 text-left">
                <summary className="cursor-pointer text-xs font-semibold uppercase tracking-[0.15em] text-[var(--text-muted)]">
                  Error details
                </summary>
                <pre className="theme-card-muted mt-3 max-h-48 overflow-auto rounded-2xl p-4 text-xs leading-5 text-[var(--text-muted)]">
                  {this.state.error.message}
                  {this.state.error.stack && `\n\n${this.state.error.stack}`}
                </pre>
              </details>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
