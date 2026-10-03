'use client';

import { FormEvent, ReactNode, Suspense, useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { apiClient } from '@/lib/apiClient';
import { AlertTriangle, CheckCircle, Eye, EyeOff, Loader2, LockKeyhole } from 'lucide-react';

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
 * User-facing errors are generic and keyed off the HTTP status; server
 * messages are never echoed. A correlation / request id header, when the
 * backend sends one, is appended so support can find the matching log line.
 */
function getErrorMessage(error: unknown): string {
  const { status, reference } = getErrorInfo(error);

  let message: string;
  if (status === undefined) {
    message = 'Something went wrong. Please try again.';
  } else if (status === 429) {
    message = 'Too many attempts. Please wait a moment and try again.';
  } else if (status >= 500) {
    message = 'Something went wrong on our side. Please try again.';
  } else {
    message =
      'We couldn’t reset your password. The link may have expired or already been used, or the password may not meet the requirements. If this keeps happening, request a new link from the sign-in page.';
  }

  return reference ? `${message} (Reference: ${reference})` : message;
}

function validatePassword(password: string): string | null {
  // Mirror of the server's policy (validate_password_strength): the page
  // must not accept a password the API will reject after submit.
  if (password.length < 12) {
    return 'Password must be at least 12 characters long.';
  }
  if (!/[A-Z]/.test(password)) {
    return 'Password must contain at least one uppercase letter.';
  }
  if (!/[a-z]/.test(password)) {
    return 'Password must contain at least one lowercase letter.';
  }
  if (!/[0-9]/.test(password)) {
    return 'Password must contain at least one number.';
  }
  return null;
}

// Full class names are written out so Tailwind can see them. (The old code built
// `bg-*` names with string.replace('text-', 'bg-'), which Tailwind never generates,
// so the strength bars had no colour.)
const STRENGTH_STYLES = {
  Weak: { text: 'text-red-700', bar: 'bg-red-500' },
  Medium: { text: 'text-amber-700', bar: 'bg-amber-500' },
  Strong: { text: 'text-emerald-700', bar: 'bg-emerald-500' },
} as const;

function calculatePasswordStrength(password: string): { score: number; label: keyof typeof STRENGTH_STYLES } {
  let score = 0;

  if (password.length >= 8) score += 1;
  if (password.length >= 12) score += 1;
  if (/[a-z]/.test(password)) score += 1;
  if (/[A-Z]/.test(password)) score += 1;
  if (/[0-9]/.test(password)) score += 1;
  if (/[^A-Za-z0-9]/.test(password)) score += 1;

  // Never call a password "Medium" or "Strong" when the server would reject it.
  if (validatePassword(password) !== null) {
    score = Math.min(score, 2);
  }

  if (score <= 2) return { score, label: 'Weak' };
  if (score <= 4) return { score, label: 'Medium' };
  return { score, label: 'Strong' };
}

function focusField(id: string) {
  window.requestAnimationFrame(() => document.getElementById(id)?.focus());
}

/* -------------------------------------------------------------------------- */
/* Components (outside the page so they don't remount on every keystroke)     */
/* -------------------------------------------------------------------------- */

function PageShell({ children }: { children: ReactNode }) {
  return (
    <main className="min-h-screen bg-slate-950 px-4 py-10 text-slate-100">
      <div className="mx-auto max-w-md">{children}</div>
    </main>
  );
}

function PasswordInput({
  id,
  label,
  value,
  onChange,
  show,
  onToggleShow,
  error,
  placeholder,
  autoFocus,
  children,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  show: boolean;
  onToggleShow: () => void;
  error: string;
  placeholder: string;
  autoFocus?: boolean;
  children?: ReactNode;
}) {
  const [capsLock, setCapsLock] = useState(false);
  const errorId = `${id}-error`;

  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-slate-700">
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          name={id}
          type={show ? 'text' : 'password'}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => setCapsLock(event.getModifierState('CapsLock'))}
          onKeyUp={(event) => setCapsLock(event.getModifierState('CapsLock'))}
          onBlur={() => setCapsLock(false)}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : undefined}
          autoComplete="new-password"
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          autoFocus={autoFocus}
          className={`w-full rounded-2xl border px-4 py-3 pr-12 text-slate-900 placeholder:text-slate-400 outline-none transition focus:ring-2 ${
            error
              ? 'border-red-300 focus:border-red-500 focus:ring-red-500/20'
              : 'border-slate-200 focus:border-blue-500 focus:ring-blue-500/20'
          }`}
          placeholder={placeholder}
        />
        <button
          type="button"
          aria-label={show ? 'Hide password' : 'Show password'}
          onClick={onToggleShow}
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg p-2 text-slate-400 hover:text-slate-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40"
        >
          {show ? <EyeOff size={16} aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}
        </button>
      </div>

      {capsLock && (
        <p role="status" className="mt-2 text-xs font-medium text-amber-700">
          Caps Lock is on.
        </p>
      )}

      {children}

      {error && (
        <p id={errorId} role="alert" className="mt-2 text-xs text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}

function StrengthMeter({ password }: { password: string }) {
  // Computed once per render (the old code recomputed it ~10 times).
  const strength = useMemo(() => calculatePasswordStrength(password), [password]);
  const styles = STRENGTH_STYLES[strength.label];

  return (
    <div className="mt-2 flex items-center justify-between">
      <div className="flex items-center gap-2">
        <div className={`text-xs font-medium ${styles.text}`}>{strength.label}</div>
        <div className="flex gap-1" aria-hidden="true">
          {[1, 2, 3, 4, 5, 6].map((level) => (
            <div
              key={level}
              className={`h-1 w-4 rounded-full ${level <= strength.score ? styles.bar : 'bg-slate-200'}`}
            />
          ))}
        </div>
      </div>
      <p className="text-xs text-slate-500">{password.length}/12 min</p>
    </div>
  );
}

function Requirements({ password }: { password: string }) {
  const rules = [
    { label: 'At least 12 characters', ok: password.length >= 12 },
    { label: 'An uppercase letter', ok: /[A-Z]/.test(password) },
    { label: 'A lowercase letter', ok: /[a-z]/.test(password) },
    { label: 'A number', ok: /[0-9]/.test(password) },
  ];

  return (
    <ul className="mt-2 space-y-1 text-xs" aria-label="Password requirements">
      {rules.map((rule) => (
        <li key={rule.label} className={`flex items-center gap-2 ${rule.ok ? 'text-emerald-700' : 'text-slate-500'}`}>
          {rule.ok ? (
            <CheckCircle size={13} aria-hidden="true" />
          ) : (
            <span className="inline-block h-[13px] w-[13px] rounded-full border border-slate-300" aria-hidden="true" />
          )}
          <span className="sr-only">{rule.ok ? 'Met: ' : 'Not met: '}</span>
          {rule.label}
        </li>
      ))}
    </ul>
  );
}

/* -------------------------------------------------------------------------- */
/* Page                                                                       */
/* -------------------------------------------------------------------------- */

function ResetPasswordContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // Read the token once, then take it out of the address bar. Left in the URL it
  // ends up in browser history and can leak through the Referer header. It is
  // kept in state, so a reload of the cleaned URL needs a fresh link.
  const [token] = useState<string | null>(() => searchParams?.get('token')?.trim() || null);

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [passwordError, setPasswordError] = useState('');
  const [confirmError, setConfirmError] = useState('');
  const [formError, setFormError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    if (token) {
      window.history.replaceState(window.history.state, '', window.location.pathname);
    }
  }, [token]);

  // Send the user back to sign-in after success. The cleanup stops the redirect
  // firing if they navigate away first (the old setTimeout was never cancelled).
  useEffect(() => {
    if (!success) {
      return;
    }
    const timer = setTimeout(() => {
      router.replace('/login?reason=password_reset&method=email');
    }, 3000);
    return () => clearTimeout(timer);
  }, [success, router]);

  // Rate-limit countdown: the submit button stays locked until it reaches zero.
  useEffect(() => {
    if (cooldown <= 0) {
      return;
    }
    const timer = setTimeout(() => setCooldown((seconds) => seconds - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  const handlePasswordChange = (value: string) => {
    setPassword(value);
    if (passwordError) setPasswordError('');
    if (confirmError) setConfirmError('');
  };

  const handleConfirmChange = (value: string) => {
    setConfirmPassword(value);
    if (confirmError) setConfirmError('');
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submitting || cooldown > 0 || !token) return;

    setFormError('');
    setPasswordError('');
    setConfirmError('');

    const policyError = validatePassword(password);
    if (policyError) {
      setPasswordError(policyError);
      focusField('new-password');
      return;
    }

    if (password !== confirmPassword) {
      setConfirmError('Passwords do not match.');
      focusField('confirm-password');
      return;
    }

    setSubmitting(true);

    try {
      await apiClient.post('/api/auth/reset-password', {
        token,
        new_password: password,
      });

      // Don't keep the new password in memory once it has been accepted.
      setPassword('');
      setConfirmPassword('');
      setSuccess(true);
    } catch (authError) {
      setFormError(getErrorMessage(authError));
      const { status, retryAfter } = getErrorInfo(authError);
      if (status === 429) {
        setCooldown(retryAfter ?? 30);
      }
    } finally {
      setSubmitting(false);
    }
  };

  // No token: show what happened instead of silently bouncing to /login.
  if (!token) {
    return (
      <PageShell>
        <div className="rounded-[32px] border border-slate-200 bg-white p-8 text-center shadow-xl">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-3xl bg-amber-100 text-amber-600">
            <AlertTriangle size={24} aria-hidden="true" />
          </div>
          <h1 className="mt-4 text-xl font-semibold text-slate-900">This reset link isn’t valid</h1>
          <p className="mt-2 text-sm text-slate-600">
            The link is missing its token, or the address was changed. Request a new reset link from the sign-in page.
          </p>
          <Link
            href="/login"
            className="mt-6 inline-flex items-center gap-2 rounded-2xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800"
          >
            Back to login
          </Link>
        </div>
      </PageShell>
    );
  }

  if (success) {
    return (
      <PageShell>
        <div role="status" className="rounded-[32px] border border-slate-200 bg-white p-8 text-center shadow-xl">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-3xl bg-green-100 text-green-600">
            <CheckCircle size={24} aria-hidden="true" />
          </div>
          <h1 className="mt-4 text-xl font-semibold text-slate-900">Password reset successful!</h1>
          <p className="mt-2 text-sm text-slate-600">
            Your password has been updated. You will be redirected to the login page shortly.
          </p>
          <Link
            href="/login?reason=password_reset&method=email"
            className="mt-6 inline-flex items-center gap-2 rounded-2xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800"
          >
            Go to Login
          </Link>
        </div>
      </PageShell>
    );
  }

  return (
    <PageShell>
      <div className="rounded-[32px] border border-slate-200 bg-white p-8 shadow-xl">
        <div className="text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-100 text-blue-600">
            <LockKeyhole size={20} aria-hidden="true" />
          </div>
          <h1 className="mt-4 text-lg font-semibold text-slate-900">Set new password</h1>
          <p className="mt-2 text-sm text-slate-600">Enter your new password below.</p>
        </div>

        <form className="mt-6 space-y-4" onSubmit={handleSubmit} noValidate>
          <PasswordInput
            id="new-password"
            label="New Password"
            value={password}
            onChange={handlePasswordChange}
            show={showPassword}
            onToggleShow={() => setShowPassword((value) => !value)}
            error={passwordError}
            placeholder="At least 12 characters"
            autoFocus
          >
            {password ? (
              <>
                <StrengthMeter password={password} />
                <Requirements password={password} />
              </>
            ) : (
              <p className="mt-2 text-xs text-slate-500">
                Use at least 12 characters with an uppercase letter, a lowercase letter, and a number.
              </p>
            )}
          </PasswordInput>

          <PasswordInput
            id="confirm-password"
            label="Confirm Password"
            value={confirmPassword}
            onChange={handleConfirmChange}
            show={showConfirmPassword}
            onToggleShow={() => setShowConfirmPassword((value) => !value)}
            error={confirmError}
            placeholder="Confirm your password"
          >
            {confirmPassword && !confirmError && password === confirmPassword && (
              <p role="status" className="mt-2 flex items-center gap-1.5 text-xs text-emerald-700">
                <CheckCircle size={13} aria-hidden="true" />
                Passwords match
              </p>
            )}
          </PasswordInput>

          {formError && (
            <div
              role="alert"
              className="flex items-start gap-2 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
            >
              <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
              <span>{formError}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={submitting || cooldown > 0}
            className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting && <Loader2 size={16} className="animate-spin" aria-hidden="true" />}
            {submitting ? 'Updating...' : cooldown > 0 ? `Try again in ${cooldown}s` : 'Update Password'}
          </button>
        </form>

        <div className="mt-6 text-center">
          <Link href="/login" className="text-sm text-slate-500 hover:text-slate-700 underline">
            Back to login
          </Link>
        </div>
      </div>
    </PageShell>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense
      fallback={
        <PageShell>
          <div role="status" className="rounded-[32px] border border-slate-200 bg-white p-8 text-center shadow-xl">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-100 text-blue-600">
              <Loader2 size={20} className="animate-spin" aria-hidden="true" />
            </div>
            <p className="mt-4 text-sm text-slate-600">Loading...</p>
          </div>
        </PageShell>
      }
    >
      <ResetPasswordContent />
    </Suspense>
  );
}
