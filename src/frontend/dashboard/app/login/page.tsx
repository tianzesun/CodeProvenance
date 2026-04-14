'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  AlertTriangle,
  LockKeyhole,
  ShieldCheck,
  Eye,
  EyeOff,
  CheckCircle,
  XCircle,
  Loader2,
  ArrowLeft,
} from 'lucide-react';
import axios from 'axios';
import { useAuth } from '@/components/AuthProvider';

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

function validatePasswordInput(password: string): string | null {
  if (password.length < 8) {
    return 'Password must be at least 8 characters long.';
  }
  return null;
}

function calculatePasswordStrength(password: string): {
  score: number;
  label: string;
  tone: string;
  bar: string;
} {
  let score = 0;

  if (password.length >= 8) score += 1;
  if (password.length >= 12) score += 1;
  if (/[a-z]/.test(password)) score += 1;
  if (/[A-Z]/.test(password)) score += 1;
  if (/[0-9]/.test(password)) score += 1;
  if (/[^A-Za-z0-9]/.test(password)) score += 1;

  if (score <= 2) {
    return {
      score,
      label: 'Weak',
      tone: 'text-red-700',
      bar: 'bg-red-500',
    };
  }

  if (score <= 4) {
    return {
      score,
      label: 'Medium',
      tone: 'text-amber-700',
      bar: 'bg-amber-500',
    };
  }

  return {
    score,
    label: 'Strong',
    tone: 'text-emerald-700',
    bar: 'bg-emerald-500',
  };
}

function validateEmail(email: string): string | null {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!email) return null;
  if (!emailRegex.test(email)) return 'Please enter a valid email address.';
  return null;
}

export default function LoginPage() {
  const router = useRouter();
  const { user, loading, bootstrapped, login, bootstrapAdmin } = useAuth();

  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [tenantName, setTenantName] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);

  const [emailError, setEmailError] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [formError, setFormError] = useState('');

  const [submitting, setSubmitting] = useState(false);
  const [nextPath, setNextPath] = useState('/');
  const [showForgotPassword, setShowForgotPassword] = useState(false);
  const [resetEmailSent, setResetEmailSent] = useState(false);

  const passwordStrength = useMemo(
    () => calculatePasswordStrength(password),
    [password]
  );

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setNextPath(params.get('next') || '/');
  }, []);

  useEffect(() => {
    if (!loading && user) {
      router.replace(nextPath);
    }
  }, [loading, user, nextPath, router]);

  const handleEmailChange = (value: string) => {
    setEmail(value);
    setEmailError(validateEmail(value.trim()) || '');
  };

  const handlePasswordChange = (value: string) => {
    setPassword(value);
    if (passwordError) setPasswordError('');
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    setFormError('');
    setEmailError('');
    setPasswordError('');

    const trimmedEmail = email.trim();
    const trimmedFullName = fullName.trim();
    const trimmedTenantName = tenantName.trim();

    const emailValidationError = validateEmail(trimmedEmail);
    if (emailValidationError) {
      setEmailError(emailValidationError);
      return;
    }

    if (!bootstrapped) {
      if (!trimmedFullName) {
        setFormError('Full name is required.');
        return;
      }

      if (!trimmedTenantName) {
        setFormError('Workspace name is required.');
        return;
      }

      const validatedPasswordError = validatePasswordInput(password);
      if (validatedPasswordError) {
        setPasswordError(validatedPasswordError);
        return;
      }
    }

    setSubmitting(true);

    try {
      if (bootstrapped) {
        await login(trimmedEmail, password);
      } else {
        await bootstrapAdmin({
          email: trimmedEmail,
          full_name: trimmedFullName,
          password,
          tenant_name: trimmedTenantName,
        });
      }

      router.replace(nextPath);
    } catch (authError) {
      setFormError(getErrorMessage(authError));
    } finally {
      setSubmitting(false);
    }
  };

  const handleForgotPasswordSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    setFormError('');
    setEmailError('');

    const trimmedEmail = email.trim();
    const emailValidationError = validateEmail(trimmedEmail);

    if (emailValidationError) {
      setEmailError(emailValidationError);
      return;
    }

    setSubmitting(true);

    try {
      await axios.post('/api/auth/forgot-password', { email: trimmedEmail });
      setResetEmailSent(true);
    } catch {
      setResetEmailSent(true);
    } finally {
      setSubmitting(false);
    }
  };

  const handleBackToLogin = () => {
    setShowForgotPassword(false);
    setResetEmailSent(false);
    setFormError('');
    setEmailError('');
    setPasswordError('');
  };

  return (
    <div className="min-h-screen bg-slate-100 px-4 py-8 text-slate-900 sm:px-6 lg:px-8">
      <div className="mx-auto grid min-h-[calc(100vh-4rem)] max-w-6xl overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-xl lg:grid-cols-[1fr_520px]">
        <section className="hidden border-r border-slate-200 bg-slate-950 text-white lg:flex">
          <div className="flex w-full flex-col justify-between p-12">
            <div>
              <div className="flex items-center gap-4">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white/10 ring-1 ring-white/15">
                  <ShieldCheck size={22} aria-hidden="true" />
                </div>
                <div>
                  <h1 className="text-xl font-semibold tracking-tight">IntegrityDesk</h1>
                  <p className="mt-1 text-sm text-slate-300">Academic integrity operations</p>
                </div>
              </div>

              <div className="mt-16 max-w-md">
                <h2 className="text-4xl font-semibold tracking-tight text-white">
                  {bootstrapped ? 'Secure sign in for your workspace' : 'Initialize your workspace'}
                </h2>
                <p className="mt-4 text-base leading-7 text-slate-300">
                  {bootstrapped
                    ? 'Access reports, similarity reviews, policies, and administrative controls from one secure dashboard.'
                    : 'Create the first administrator account and configure the workspace for your institution.'}
                </p>
              </div>
            </div>

            <div className="space-y-4 border-t border-white/10 pt-8 text-sm text-slate-300">
              <div className="flex items-start gap-3">
                <CheckCircle size={16} className="mt-0.5 shrink-0 text-emerald-400" aria-hidden="true" />
                <span>Protected access for academic and administrative workflows.</span>
              </div>
              <div className="flex items-start gap-3">
                <CheckCircle size={16} className="mt-0.5 shrink-0 text-emerald-400" aria-hidden="true" />
                <span>Designed for clarity, accessibility, and low-friction operations.</span>
              </div>
            </div>
          </div>
        </section>

        <section className="flex items-center justify-center bg-white">
          <div className="w-full max-w-md px-6 py-10 sm:px-10">
            <div className="mb-8 lg:hidden">
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-slate-900 text-white">
                  <ShieldCheck size={20} aria-hidden="true" />
                </div>
                <div>
                  <h1 className="text-lg font-semibold tracking-tight text-slate-900">IntegrityDesk</h1>
                  <p className="text-sm text-slate-500">Academic integrity operations</p>
                </div>
              </div>
            </div>

            <div className="mb-8">
              <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 text-slate-700">
                <LockKeyhole size={20} aria-hidden="true" />
              </div>
              <h2 className="text-2xl font-semibold tracking-tight text-slate-900">
                {showForgotPassword
                  ? resetEmailSent
                    ? 'Check your email'
                    : 'Reset password'
                  : bootstrapped
                    ? 'Sign in'
                    : 'Create administrator account'}
              </h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                {showForgotPassword
                  ? resetEmailSent
                    ? 'If the account exists, password reset instructions have been sent.'
                    : 'Enter your email address and we’ll send reset instructions.'
                  : bootstrapped
                    ? 'Use your organization credentials to continue.'
                    : 'Set up the first administrator account for this workspace.'}
              </p>
            </div>

            {showForgotPassword ? (
              resetEmailSent ? (
                <div className="space-y-6">
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
                    <div className="flex items-start gap-3">
                      <CheckCircle size={18} className="mt-0.5 shrink-0 text-emerald-600" aria-hidden="true" />
                      <div>
                        <p className="text-sm font-medium text-slate-900">
                          Reset instructions sent
                        </p>
                        <p className="mt-1 text-sm text-slate-600">
                          If an account exists for <strong>{email.trim()}</strong>, you’ll receive an email shortly.
                        </p>
                      </div>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={handleBackToLogin}
                    className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-slate-900 px-5 py-3.5 text-sm font-semibold text-white transition hover:bg-slate-800"
                  >
                    <ArrowLeft size={16} aria-hidden="true" />
                    Return to sign in
                  </button>
                </div>
              ) : (
                <form className="space-y-5" onSubmit={handleForgotPasswordSubmit} noValidate>
                  <div className="space-y-2">
                    <label htmlFor="forgot-email" className="block text-sm font-medium text-slate-700">
                      Email address
                    </label>
                    <div className="relative">
                      <input
                        id="forgot-email"
                        type="email"
                        value={email}
                        onChange={(event) => handleEmailChange(event.target.value)}
                        aria-invalid={emailError ? true : undefined}
                        aria-describedby={emailError ? 'forgot-email-error' : undefined}
                        autoComplete="email"
                        placeholder="name@institution.edu"
                        className={`w-full rounded-2xl border bg-white px-4 py-3.5 pr-11 text-slate-900 outline-none transition focus:ring-4 ${emailError
                          ? 'border-red-300 focus:border-red-500 focus:ring-red-500/10'
                          : 'border-slate-300 focus:border-slate-900 focus:ring-slate-900/10'
                          }`}
                      />
                      {email && (
                        <div className="absolute right-3 top-1/2 -translate-y-1/2" aria-hidden="true">
                          {emailError ? (
                            <XCircle size={16} className="text-red-500" />
                          ) : (
                            <CheckCircle size={16} className="text-emerald-600" />
                          )}
                        </div>
                      )}
                    </div>
                    {emailError && (
                      <p id="forgot-email-error" role="alert" className="text-xs text-red-600">
                        {emailError}
                      </p>
                    )}
                  </div>

                  {formError && (
                    <div className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                      <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
                      <span>{formError}</span>
                    </div>
                  )}

                  <button
                    type="submit"
                    disabled={loading || submitting}
                    className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-slate-900 px-5 py-3.5 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {submitting && <Loader2 size={16} className="animate-spin" aria-hidden="true" />}
                    {submitting ? 'Sending reset link...' : 'Send reset link'}
                  </button>

                  <button
                    type="button"
                    onClick={handleBackToLogin}
                    className="inline-flex w-full items-center justify-center gap-2 rounded-2xl border border-slate-300 bg-white px-5 py-3.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
                  >
                    <ArrowLeft size={16} aria-hidden="true" />
                    Back to sign in
                  </button>
                </form>
              )
            ) : (
              <form className="space-y-5" onSubmit={handleSubmit} noValidate>
                {!bootstrapped && (
                  <>
                    <div className="space-y-2">
                      <label htmlFor="full-name" className="block text-sm font-medium text-slate-700">
                        Full name
                      </label>
                      <input
                        id="full-name"
                        value={fullName}
                        onChange={(event) => setFullName(event.target.value)}
                        autoComplete="name"
                        placeholder="Professor Ada Lovelace"
                        className="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3.5 text-slate-900 outline-none transition focus:border-slate-900 focus:ring-4 focus:ring-slate-900/10"
                      />
                    </div>

                    <div className="space-y-2">
                      <label htmlFor="tenant-name" className="block text-sm font-medium text-slate-700">
                        Workspace name
                      </label>
                      <input
                        id="tenant-name"
                        value={tenantName}
                        onChange={(event) => setTenantName(event.target.value)}
                        autoComplete="organization"
                        placeholder="Computer Science Department"
                        className="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3.5 text-slate-900 outline-none transition focus:border-slate-900 focus:ring-4 focus:ring-slate-900/10"
                      />
                    </div>
                  </>
                )}

                <div className="space-y-2">
                  <label htmlFor="email" className="block text-sm font-medium text-slate-700">
                    Email address
                  </label>
                  <div className="relative">
                    <input
                      id="email"
                      type="email"
                      value={email}
                      onChange={(event) => handleEmailChange(event.target.value)}
                      aria-invalid={emailError ? true : undefined}
                      aria-describedby={emailError ? 'login-email-error' : undefined}
                      autoComplete="email"
                      placeholder="name@institution.edu"
                      className={`w-full rounded-2xl border bg-white px-4 py-3.5 pr-11 text-slate-900 outline-none transition focus:ring-4 ${emailError
                        ? 'border-red-300 focus:border-red-500 focus:ring-red-500/10'
                        : 'border-slate-300 focus:border-slate-900 focus:ring-slate-900/10'
                        }`}
                    />
                    {email && (
                      <div className="absolute right-3 top-1/2 -translate-y-1/2" aria-hidden="true">
                        {emailError ? (
                          <XCircle size={16} className="text-red-500" />
                        ) : (
                          <CheckCircle size={16} className="text-emerald-600" />
                        )}
                      </div>
                    )}
                  </div>
                  {emailError && (
                    <p id="login-email-error" role="alert" className="text-xs text-red-600">
                      {emailError}
                    </p>
                  )}
                </div>

                <div className="space-y-2">
                  <label htmlFor="password" className="block text-sm font-medium text-slate-700">
                    Password
                  </label>
                  <div className="relative">
                    <input
                      id="password"
                      type={showPassword ? 'text' : 'password'}
                      value={password}
                      onChange={(event) => handlePasswordChange(event.target.value)}
                      aria-invalid={passwordError ? true : undefined}
                      aria-describedby={passwordError ? 'password-error' : undefined}
                      autoComplete={bootstrapped ? 'current-password' : 'new-password'}
                      placeholder="Enter your password"
                      className={`w-full rounded-2xl border bg-white px-4 py-3.5 pr-12 text-slate-900 outline-none transition focus:ring-4 ${passwordError
                        ? 'border-red-300 focus:border-red-500 focus:ring-red-500/10'
                        : 'border-slate-300 focus:border-slate-900 focus:ring-slate-900/10'
                        }`}
                    />
                    <button
                      type="button"
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                      onClick={() => setShowPassword((value) => !value)}
                      className="absolute right-1.5 top-1/2 inline-flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-xl text-slate-500 transition hover:bg-slate-100 hover:text-slate-700"
                    >
                      {showPassword ? (
                        <EyeOff size={18} aria-hidden="true" />
                      ) : (
                        <Eye size={18} aria-hidden="true" />
                      )}
                    </button>
                  </div>

                  {!bootstrapped && password && (
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                      <div className="mb-2 flex items-center justify-between">
                        <span className={`text-sm font-medium ${passwordStrength.tone}`}>
                          Password strength: {passwordStrength.label}
                        </span>
                        <span className="text-xs text-slate-500">{password.length} characters</span>
                      </div>
                      <div className="flex gap-1" aria-hidden="true">
                        {[1, 2, 3, 4, 5, 6].map((level) => (
                          <div
                            key={level}
                            className={`h-2 flex-1 rounded-full ${level <= passwordStrength.score ? passwordStrength.bar : 'bg-slate-200'
                              }`}
                          />
                        ))}
                      </div>
                    </div>
                  )}

                  {!bootstrapped && !password && (
                    <p className="text-xs text-slate-500">
                      Use at least 8 characters with upper/lowercase letters, a number, and a symbol.
                    </p>
                  )}

                  {passwordError && (
                    <p id="password-error" role="alert" className="text-xs text-red-600">
                      {passwordError}
                    </p>
                  )}
                </div>

                {bootstrapped && (
                  <div className="flex items-center justify-between gap-4">
                    <label htmlFor="rememberMe" className="flex items-center gap-3 text-sm text-slate-600">
                      <input
                        id="rememberMe"
                        type="checkbox"
                        checked={rememberMe}
                        onChange={(event) => setRememberMe(event.target.checked)}
                        className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-900"
                      />
                      <span>Remember me</span>
                    </label>

                    <button
                      type="button"
                      onClick={() => setShowForgotPassword(true)}
                      className="text-sm font-medium text-slate-600 transition hover:text-slate-900"
                    >
                      Forgot password?
                    </button>
                  </div>
                )}

                {formError && (
                  <div className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
                    <span>{formError}</span>
                  </div>
                )}

                <button
                  type="submit"
                  disabled={loading || submitting}
                  className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-slate-900 px-5 py-3.5 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {submitting && <Loader2 size={16} className="animate-spin" aria-hidden="true" />}
                  {submitting
                    ? 'Processing...'
                    : bootstrapped
                      ? 'Sign in'
                      : 'Create administrator account'}
                </button>
              </form>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}