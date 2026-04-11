'use client';

import { FormEvent, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertTriangle, LockKeyhole, ShieldCheck, Eye, EyeOff, CheckCircle, XCircle, Loader2, ArrowLeft } from 'lucide-react';
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

function calculatePasswordStrength(password: string): { score: number; label: string; color: string } {
  let score = 0;

  if (password.length >= 8) score += 1;
  if (password.length >= 12) score += 1;
  if (/[a-z]/.test(password)) score += 1;
  if (/[A-Z]/.test(password)) score += 1;
  if (/[0-9]/.test(password)) score += 1;
  if (/[^A-Za-z0-9]/.test(password)) score += 1;

  if (score <= 2) return { score, label: 'Weak', color: 'text-red-500' };
  if (score <= 4) return { score, label: 'Medium', color: 'text-yellow-500' };
  return { score, label: 'Strong', color: 'text-green-500' };
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
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [nextPath, setNextPath] = useState('/');
  const [showForgotPassword, setShowForgotPassword] = useState(false);
  const [resetEmailSent, setResetEmailSent] = useState(false);

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
    setEmailError('');

    const passwordError = validatePasswordInput(password);
    const emailValidationError = validateEmail(email);

    if (emailValidationError) {
      setEmailError(emailValidationError);
      return;
    }

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

  const handleEmailChange = (value: string) => {
    setEmail(value);
    const validationError = validateEmail(value);
    setEmailError(validationError || '');
  };

  const handlePasswordChange = (value: string) => {
    setPassword(value);
    // Clear password error when user starts typing
    if (error && error.includes('Password')) {
      setError('');
    }
  };

  const handleForgotPasswordSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    setEmailError('');

    const emailValidationError = validateEmail(email);
    if (emailValidationError) {
      setEmailError(emailValidationError);
      return;
    }

    setSubmitting(true);

    try {
      const API = ''; // Will use environment variable
      await axios.post(`${API}/api/auth/forgot-password`, { email });
      setResetEmailSent(true);
    } catch (authError) {
      setError(getErrorMessage(authError));
    } finally {
      setSubmitting(false);
    }
  };

  const handleBackToLogin = () => {
    setShowForgotPassword(false);
    setResetEmailSent(false);
    setError('');
    setEmailError('');
  };

  return (
    <div className="min-h-screen bg-slate-950 px-4 py-6 text-slate-100 sm:py-10">
      <div className="mx-auto grid min-h-[calc(100vh-3rem)] max-w-6xl gap-6 sm:min-h-[calc(100vh-5rem)] sm:gap-8 lg:grid-cols-[1.1fr_0.9fr]">
        <section className="relative order-2 overflow-hidden rounded-[24px] border border-white/10 bg-gradient-to-br from-slate-900 via-slate-950 to-blue-950 px-6 py-8 shadow-2xl sm:rounded-[36px] sm:px-8 sm:py-10 lg:order-1">
          {/* Artistic Background */}
          <div className="absolute inset-0">
            {/* Primary gradient */}
            <div className="absolute inset-0 bg-gradient-to-br from-blue-600/20 via-slate-900/50 to-indigo-900/30" />

            {/* Floating orbs */}
            <div className="absolute top-20 left-20 w-64 h-64 bg-blue-400/10 rounded-full blur-3xl animate-pulse" />
            <div className="absolute bottom-20 right-20 w-48 h-48 bg-indigo-400/15 rounded-full blur-2xl animate-pulse" style={{ animationDelay: '1s' }} />
            <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-32 h-32 bg-slate-300/5 rounded-full blur-xl" />

            {/* Subtle pattern overlay */}
            <div className="absolute inset-0 opacity-[0.02] bg-[radial-gradient(circle_at_1px_1px,rgba(255,255,255,0.3)_1px,transparent_0)] bg-[length:24px_24px]" />
          </div>

          <div className="relative flex flex-col items-center justify-center min-h-[500px]">
            {/* Main logo and branding */}
            <div className="text-center space-y-8 mb-12">
              <div className="relative">
                {/* Outer glow ring */}
                <div className="absolute inset-0 rounded-full bg-gradient-to-r from-blue-400/20 to-indigo-400/20 blur-xl scale-150" />
                <div className="relative inline-flex items-center justify-center w-24 h-24 rounded-full bg-gradient-to-br from-blue-600 via-blue-700 to-indigo-800 text-white shadow-2xl">
                  <ShieldCheck size={36} className="drop-shadow-lg" />
                </div>
              </div>

              <div className="space-y-3">
                <h1 className="font-display text-5xl font-bold text-white sm:text-6xl tracking-tight">
                  IntegrityDesk
                </h1>
                <div className="h-px w-32 bg-gradient-to-r from-transparent via-white/30 to-transparent mx-auto" />
                <p className="text-slate-300 text-sm uppercase tracking-[0.4em] font-light">
                  Academic Integrity Platform
                </p>
              </div>
            </div>

            {/* Elegant divider */}
            <div className="w-full max-w-xs mx-auto">
              <div className="flex items-center justify-center space-x-4">
                <div className="h-px flex-1 bg-gradient-to-r from-transparent to-white/20" />
                <div className="w-2 h-2 rounded-full bg-white/30" />
                <div className="h-px flex-1 bg-gradient-to-l from-transparent to-white/20" />
              </div>
            </div>

            {/* Minimal status text */}
            <div className="text-center mt-8">
              <p className="text-white/80 text-lg font-light italic">
                {bootstrapped ? 'Secure Academic Workspace' : 'System Initialization'}
              </p>
            </div>
          </div>
        </section>

        <section className="order-1 flex items-center lg:order-2">
          <div className="w-full rounded-[24px] border border-slate-200/60 bg-white/95 backdrop-blur-xl p-8 shadow-2xl sm:rounded-[32px] sm:p-10">
            {/* Subtle background pattern */}
            <div className="absolute inset-0 opacity-[0.02] bg-[radial-gradient(circle_at_1px_1px,rgba(0,0,0,0.3)_1px,transparent_0)] bg-[length:20px_20px] rounded-[24px] sm:rounded-[32px]" />

            <div className="relative mb-8 text-center">
              <div className="inline-flex items-center justify-center w-14 h-14 rounded-3xl bg-gradient-to-br from-slate-100 to-slate-200 text-slate-600 mb-6 shadow-lg">
                <LockKeyhole size={22} />
              </div>
              <h2 className="text-3xl font-bold text-slate-900 mb-3 tracking-tight">
                {bootstrapped ? 'Welcome Back' : 'Initialize System'}
              </h2>
              <p className="text-slate-600 leading-relaxed text-base">
                {bootstrapped
                  ? 'Enter your credentials to access the dashboard'
                  : 'Set up the first administrator account'}
              </p>
            </div>

            {showForgotPassword ? (
              resetEmailSent ? (
                <div className="space-y-6">
                  <div className="text-center">
                    <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-3xl bg-green-100 text-green-600">
                      <CheckCircle size={24} />
                    </div>
                    <h3 className="mt-4 text-xl font-semibold text-slate-900">Check your email</h3>
                    <p className="mt-2 text-sm text-slate-600">
                      We&apos;ve sent password reset instructions to <strong>{email}</strong>
                    </p>
                  </div>

                  <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
                    <p>
                      If you don&apos;t see the email in your inbox, please check your spam folder.
                      The link will expire in 24 hours.
                    </p>
                  </div>

                  <button
                    onClick={handleBackToLogin}
                    className="inline-flex w-full items-center gap-3 rounded-2xl bg-slate-900 px-6 py-4 text-sm font-semibold text-white transition-all hover:bg-slate-800 hover:shadow-lg"
                  >
                    <ArrowLeft size={16} />
                    Return to Sign In
                  </button>
                </div>
              ) : (
                <form className="space-y-4" onSubmit={handleForgotPasswordSubmit}>
                  <div className="text-center">
                    <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-100 text-blue-600">
                      <LockKeyhole size={20} />
                    </div>
                    <h3 className="mt-4 text-lg font-semibold text-slate-900">Reset your password</h3>
                    <p className="mt-2 text-sm text-slate-600">
                      Enter your email address and we&apos;ll send you a link to reset your password.
                    </p>
                  </div>

                  <div>
                    <label className="mb-1.5 block text-sm font-medium text-slate-700">Email</label>
                    <div className="relative">
                      <input
                        type="email"
                        value={email}
                        onChange={(event) => handleEmailChange(event.target.value)}
                        className={`w-full rounded-2xl border px-4 py-3 text-slate-900 placeholder:text-slate-400 outline-none transition focus:ring-2 ${
                          emailError
                            ? 'border-red-300 focus:border-red-500 focus:ring-red-500/20'
                            : 'border-slate-200 focus:border-blue-500 focus:ring-blue-500/20'
                        }`}
                        placeholder="name@university.edu"
                      />
                      {email && (
                        <div className="absolute right-3 top-1/2 -translate-y-1/2">
                          {emailError ? (
                            <XCircle size={16} className="text-red-500" />
                          ) : (
                            <CheckCircle size={16} className="text-green-500" />
                          )}
                        </div>
                      )}
                    </div>
                    {emailError && (
                      <p className="mt-1 text-xs text-red-600">{emailError}</p>
                    )}
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
                    className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {submitting && <Loader2 size={16} className="animate-spin" />}
                    {submitting ? 'Sending...' : 'Send Reset Link'}
                  </button>

                  <button
                    type="button"
                    onClick={handleBackToLogin}
                    className="inline-flex w-full items-center gap-3 rounded-2xl border border-slate-200 bg-white px-6 py-4 text-sm font-semibold text-slate-700 transition-all hover:bg-slate-50 hover:shadow-md"
                  >
                    <ArrowLeft size={16} />
                    Return to Sign In
                  </button>
                </form>
              )
            ) : (
            <form className="relative space-y-6" onSubmit={handleSubmit}>
              {!bootstrapped && (
                <>
                  <div className="space-y-2">
                    <label className="block text-sm font-semibold text-slate-800 tracking-wide">Full Name</label>
                    <input
                      value={fullName}
                      onChange={(event) => setFullName(event.target.value)}
                      className="w-full rounded-2xl border-2 border-slate-200 px-5 py-4 text-slate-900 placeholder:text-slate-400 outline-none transition-all duration-300 focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10 hover:border-slate-300"
                      placeholder="Professor Ada Lovelace"
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="block text-sm font-semibold text-slate-800 tracking-wide">Workspace Name</label>
                    <input
                      value={tenantName}
                      onChange={(event) => setTenantName(event.target.value)}
                      className="w-full rounded-2xl border-2 border-slate-200 px-5 py-4 text-slate-900 placeholder:text-slate-400 outline-none transition-all duration-300 focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10 hover:border-slate-300"
                      placeholder="Computer Science Department"
                    />
                  </div>
                </>
              )}

              <div className="space-y-2">
                <label className="block text-sm font-semibold text-slate-800 tracking-wide">Email Address</label>
                <div className="relative group">
                  <input
                    type="email"
                    value={email}
                    onChange={(event) => handleEmailChange(event.target.value)}
                    className={`w-full rounded-2xl border-2 px-5 py-4 text-slate-900 placeholder:text-slate-400 outline-none transition-all duration-300 focus:ring-4 hover:border-slate-300 ${
                      emailError
                        ? 'border-red-300 focus:border-red-500 focus:ring-red-500/10'
                        : 'border-slate-200 focus:border-blue-500 focus:ring-blue-500/10'
                    }`}
                    placeholder="name@university.edu"
                  />
                  {email && (
                    <div className="absolute right-4 top-1/2 -translate-y-1/2 transition-opacity duration-200">
                      {emailError ? (
                        <XCircle size={18} className="text-red-500" />
                      ) : (
                        <CheckCircle size={18} className="text-green-500" />
                      )}
                    </div>
                  )}
                </div>
                {emailError && (
                  <p className="mt-2 text-xs text-red-600 font-medium">{emailError}</p>
                )}
              </div>

              <div className="space-y-2">
                <label className="block text-sm font-semibold text-slate-800 tracking-wide">Password</label>
                <div className="relative group">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(event) => handlePasswordChange(event.target.value)}
                    className={`w-full rounded-2xl border-2 px-5 py-4 pr-14 text-slate-900 placeholder:text-slate-400 outline-none transition-all duration-300 focus:ring-4 hover:border-slate-300 ${
                      error && error.includes('Password')
                        ? 'border-red-300 focus:border-red-500 focus:ring-red-500/10'
                        : 'border-slate-200 focus:border-blue-500 focus:ring-blue-500/10'
                    }`}
                    placeholder="Enter your password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors duration-200"
                  >
                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
                {password && (
                  <div className="mt-3 p-3 rounded-xl bg-slate-50 border border-slate-200/50">
                    <div className="flex items-center justify-between mb-2">
                      <div className={`text-sm font-semibold ${calculatePasswordStrength(password).color}`}>
                        {calculatePasswordStrength(password).label}
                      </div>
                      <div className="text-xs text-slate-500 font-medium">
                        {password.length}/8 characters
                      </div>
                    </div>
                    <div className="flex gap-1">
                      {[1, 2, 3, 4, 5, 6].map((level) => (
                        <div
                          key={level}
                          className={`h-2 flex-1 rounded-full transition-all duration-300 ${
                            level <= calculatePasswordStrength(password).score
                              ? calculatePasswordStrength(password).color.replace('text-', 'bg-')
                              : 'bg-slate-200'
                          }`}
                        />
                      ))}
                    </div>
                  </div>
                )}
                {!password && (
                  <p className="mt-2 text-xs text-slate-500 italic">
                    Minimum 8 characters with mixed case, numbers, and symbols
                  </p>
                )}
                </div>

              {bootstrapped && (
                <div className="flex items-center justify-center gap-3 py-2">
                  <input
                    type="checkbox"
                    id="rememberMe"
                    checked={rememberMe}
                    onChange={(event) => setRememberMe(event.target.checked)}
                    className="h-4 w-4 rounded border-2 border-slate-300 text-blue-600 focus:ring-blue-500 focus:ring-offset-0 transition-colors"
                  />
                  <label htmlFor="rememberMe" className="text-sm text-slate-600 font-medium cursor-pointer">
                    Remember me for 30 days
                  </label>
                </div>
              )}

              {error && (
                <div className="flex items-start gap-3 rounded-2xl border-2 border-red-200 bg-red-50/80 backdrop-blur-sm px-5 py-4 text-sm text-red-700 shadow-sm">
                  <AlertTriangle size={18} className="mt-0.5 shrink-0" />
                  <span className="font-medium">{error}</span>
                </div>
              )}

              <button
                type="submit"
                disabled={loading || submitting}
                className="relative inline-flex w-full items-center justify-center gap-3 rounded-2xl bg-gradient-to-r from-slate-900 to-slate-800 px-8 py-5 text-base font-semibold text-white transition-all duration-300 hover:from-slate-800 hover:to-slate-700 hover:shadow-xl hover:scale-[1.02] disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:scale-100 overflow-hidden group"
              >
                <div className="absolute inset-0 bg-gradient-to-r from-blue-600/0 to-indigo-600/0 group-hover:from-blue-600/10 group-hover:to-indigo-600/10 transition-all duration-300" />
                {submitting && <Loader2 size={18} className="animate-spin relative z-10" />}
                <span className="relative z-10">
                  {submitting ? 'Processing...' : bootstrapped ? 'Access Dashboard' : 'Initialize System'}
                </span>
              </button>

                {bootstrapped && (
                  <div className="text-center pt-2">
                    <button
                      type="button"
                      onClick={() => setShowForgotPassword(true)}
                      className="text-sm text-slate-500 hover:text-slate-700 transition-colors duration-200 font-medium hover:underline decoration-2 underline-offset-4"
                    >
                      Forgot your password?
                    </button>
                  </div>
                )}
              </form>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
