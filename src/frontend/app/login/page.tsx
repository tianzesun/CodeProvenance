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
  Rocket,
  KeyRound,
  UserPlus,
} from 'lucide-react';
import { apiClient } from '@/lib/apiClient';
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

function sanitizeNextPath(value: string | null): string {
  if (!value || !value.startsWith('/') || value.startsWith('//')) {
    return '/';
  }

  const target = value.split('#')[0];
  try {
    const url = new URL(target, window.location.origin);
    return url.origin === window.location.origin ? url.pathname : '/';
  } catch {
    return '/';
  }
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

/**
 * Mirror of the server's password policy (``validate_password_strength``)
 * wherever a password is set - bootstrap-admin, self-registration, reset:
 * 12+ characters with upper- and lowercase letters and a number. Checking
 * here keeps the failure next to the field instead of arriving as a server
 * error after submit.
 */
function validateNewPassword(password: string): string | null {
  if (password.length < 12) return 'Password must be at least 12 characters long.';
  if (!/[A-Z]/.test(password)) return 'Password must contain at least one uppercase letter.';
  if (!/[a-z]/.test(password)) return 'Password must contain at least one lowercase letter.';
  if (!/[0-9]/.test(password)) return 'Password must contain at least one number.';
  return null;
}

function validateEmail(email: string): string | null {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!email) return null;
  if (!emailRegex.test(email)) return 'Please enter a valid email address.';
  return null;
}

export default function LoginPage() {
  const router = useRouter();
  const { user, loading, bootstrapped, login, guestLogin, bootstrapAdmin } = useAuth();

  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [tenantName, setTenantName] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [forceSignIn, setForceSignIn] = useState(false);

  const [emailError, setEmailError] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [formError, setFormError] = useState('');

  const [submitting, setSubmitting] = useState(false);
  const [guestSubmitting, setGuestSubmitting] = useState(false);
  const [nextPath, setNextPath] = useState('/');
  const [showForgotPassword, setShowForgotPassword] = useState(false);
  const [resetEmailSent, setResetEmailSent] = useState(false);
  // Sign-in method chosen on this page. SSO is UI-only for now: picking it
  // swaps the password form for an email prompt, and no session is issued
  // until an identity provider is connected. "register" opens the
  // self-signup form, which ends in a "check your inbox" card rather than a
  // session — the account stays locked until the emailed link is redeemed.
  const [loginMethod, setLoginMethod] = useState<'password' | 'sso' | 'register'>('password');
  const [ssoNotice, setSsoNotice] = useState('');
  const [registerEmailSent, setRegisterEmailSent] = useState(false);
  const [confirmPassword, setConfirmPassword] = useState('');
  const [confirmPasswordError, setConfirmPasswordError] = useState('');
  const [resendNotice, setResendNotice] = useState('');

  // Treat "status still loading" as sign-in so returning professors never see
  // the bootstrap form flash before /api/auth/status resolves.
  const showLogin = loading || bootstrapped || forceSignIn;

  const passwordStrength = useMemo(
    () => calculatePasswordStrength(password),
    [password]
  );

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setNextPath(sanitizeNextPath(params.get('next')));
  }, []);

  useEffect(() => {
    // Add a small delay to prevent immediate redirects during authentication resolution
    const timer = setTimeout(() => {
      // Guests are bounced back to the sign-in form rather than away from it:
      // they reached /login to upgrade the demo session into a real account.
      if (!loading && user && user.role !== 'guest') {
        router.replace(nextPath);
      }
    }, 200); // 200ms delay

    return () => clearTimeout(timer);
  }, [loading, user, nextPath, router]);

  const handleEmailChange = (value: string) => {
    setEmail(value);
    // A brand-new error waits for blur or submit so the field never turns
    // red mid-word; once it is red, keep revalidating so fixing the address
    // clears it as the user types.
    if (emailError) setEmailError(validateEmail(value.trim()) || '');
  };

  const handleEmailBlur = () => {
    setEmailError(validateEmail(email.trim()) || '');
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

    if (!trimmedEmail) {
      setEmailError('Email address is required.');
      return;
    }

    const emailValidationError = validateEmail(trimmedEmail);
    if (emailValidationError) {
      setEmailError(emailValidationError);
      return;
    }

    if (!showLogin) {
      if (!trimmedFullName) {
        setFormError('Full name is required.');
        return;
      }

      if (!trimmedTenantName) {
        setFormError('Workspace name is required.');
        return;
      }

      const validatedPasswordError = validateNewPassword(password);
      if (validatedPasswordError) {
        setPasswordError(validatedPasswordError);
        return;
      }
    }

    setSubmitting(true);

    try {
      if (showLogin) {
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
    if (!trimmedEmail) {
      setEmailError('Email address is required.');
      return;
    }

    const emailValidationError = validateEmail(trimmedEmail);

    if (emailValidationError) {
      setEmailError(emailValidationError);
      return;
    }

    setSubmitting(true);

    try {
      await apiClient.post('/api/auth/forgot-password', { email: trimmedEmail });
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

  /**
   * Start a guest demo session and land on the checker.
   *
   * ``nextPath`` is set before the session starts so the sign-in redirect
   * (which fires once ``user`` resolves) also goes to ``/upload``: a guest has
   * no dashboard to land on.
   */
  const handleGuestLogin = async () => {
    setFormError('');
    setGuestSubmitting(true);
    try {
      setNextPath('/upload');
      await guestLogin();
      router.replace('/upload');
    } catch (error) {
      setNextPath('/');
      setFormError(getErrorMessage(error));
    } finally {
      setGuestSubmitting(false);
    }
  };

  /**
   * Collect the email for a single-sign-on attempt.
   *
   * SSO is UI-only for now: this is where a real flow would hand the address
   * to ``POST /api/auth/sso/start``, resolve the domain's identity provider
   * and redirect the browser to it. Until one is connected, say so plainly
   * instead of pretending the hand-off happened.
   */
  const handleSsoSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    setFormError('');
    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      setEmailError('Email address is required.');
      return;
    }
    const emailValidationError = validateEmail(trimmedEmail);
    if (emailValidationError) {
      setEmailError(emailValidationError);
      return;
    }

    setSsoNotice(
      'Single sign-on isn’t configured for this workspace yet — no identity provider is connected. Use your email and password to sign in for now.'
    );
  };

  /** Leave the SSO/register prompts and restore the password form. */
  const handleBackToPassword = () => {
    setLoginMethod('password');
    setSsoNotice('');
    setRegisterEmailSent(false);
    setResendNotice('');
    setFormError('');
    setEmailError('');
    setPasswordError('');
    setConfirmPasswordError('');
    setPassword('');
    setConfirmPassword('');
  };

  /** Swap the password form's email prompt for the SSO one. */
  const handleChooseSso = () => {
    setLoginMethod('sso');
    setSsoNotice('');
    setEmailError('');
  };

  /** Open the self-registration form. */
  const handleChooseRegister = () => {
    setLoginMethod('register');
    setRegisterEmailSent(false);
    setResendNotice('');
    setFormError('');
    setEmailError('');
    setPasswordError('');
    setConfirmPasswordError('');
  };

  /**
   * Submit a self-signup.
   *
   * Success never signs the user in: the server creates an inactive
   * professor account in its own workspace and emails a verification link,
   * so the form switches to the "check your inbox" card.
   */
  const handleRegisterSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    setFormError('');
    setEmailError('');
    setPasswordError('');
    setConfirmPasswordError('');

    const trimmedEmail = email.trim();
    const trimmedFullName = fullName.trim();

    if (!trimmedEmail) {
      setEmailError('Email address is required.');
      return;
    }
    const emailValidationError = validateEmail(trimmedEmail);
    if (emailValidationError) {
      setEmailError(emailValidationError);
      return;
    }
    if (!trimmedFullName) {
      setFormError('Full name is required.');
      return;
    }
    const passwordValidationError = validateNewPassword(password);
    if (passwordValidationError) {
      setPasswordError(passwordValidationError);
      return;
    }
    if (password !== confirmPassword) {
      setConfirmPasswordError('Passwords do not match.');
      return;
    }

    setSubmitting(true);
    try {
      await apiClient.post('/api/auth/register', {
        email: trimmedEmail,
        full_name: trimmedFullName,
        password,
      });
      setRegisterEmailSent(true);
      setResendNotice('');
    } catch (error) {
      setFormError(getErrorMessage(error));
    } finally {
      setSubmitting(false);
    }
  };

  /**
   * Ask the server to mail the verification link again.
   *
   * Re-registering with the same details is the resend path: the server
   * rotates the token and answers the same generic message, so the button
   * works whether or not the first email ever arrived.
   */
  const handleResendVerification = async () => {
    setFormError('');
    setResendNotice('');
    setSubmitting(true);
    try {
      await apiClient.post('/api/auth/register', {
        email: email.trim(),
        full_name: fullName.trim(),
        password,
      });
      setResendNotice('Verification email sent again.');
    } catch (error) {
      setFormError(getErrorMessage(error));
    } finally {
      setSubmitting(false);
    }
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
                                    {!showLogin
                    ? 'Initialize Institutional Workspace'
                    : loginMethod === 'register'
                      ? 'Create Your Account'
                      : 'Academic Workspace Sign-In'}
                </h2>
                <p className="mt-4 text-base leading-7 text-slate-300">
                                    {!showLogin
                    ? 'Create the first administrator account and configure the workspace for your institution.'
                    : loginMethod === 'register'
                      ? 'Set up your workspace in minutes and start checking submissions for academic integrity.'
                      : 'Access academic integrity tools, review assignments, and manage courses from your secure workspace.'}
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
                {loginMethod === 'register' && showLogin ? (
                  <UserPlus size={20} aria-hidden="true" />
                ) : loginMethod === 'sso' && showLogin ? (
                  <KeyRound size={20} aria-hidden="true" />
                ) : (
                  <LockKeyhole size={20} aria-hidden="true" />
                )}
              </div>
<h2 className="text-2xl font-semibold tracking-tight text-slate-900">
                {showForgotPassword
                  ? resetEmailSent
                    ? 'Check your email'
                    : 'Reset password'
                  : showLogin
                    ? loginMethod === 'sso'
                      ? 'Sign in with SSO'
                      : loginMethod === 'register'
                        ? registerEmailSent
                          ? 'Check your email'
                          : 'Create Account'
                        : 'Sign-In'
                    : 'Create Administrator Account'}
              </h2>
{(showForgotPassword || !showLogin) && (
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  {showForgotPassword
                    ? resetEmailSent
                      ? 'If the account exists, password reset instructions have been sent.'
                      : 'Enter your email address and we will send reset instructions.'
                    : 'Set up the first administrator account for this workspace.'}
                </p>
              )}
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
                    className="theme-button-primary inline-flex w-full items-center justify-center gap-2 rounded-2xl px-5 py-3.5 text-sm font-semibold transition"
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
                        onChange={(event) => handleEmailChange(event.target.value)} onBlur={handleEmailBlur}
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
                          ) : validateEmail(email.trim()) === null ? (
                            <CheckCircle size={16} className="text-emerald-600" />
                          ) : null}
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
                  className="theme-button-primary inline-flex w-full items-center justify-center gap-2 rounded-2xl px-5 py-3.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {submitting ? 'Sending...' : 'Send reset instructions'}
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
            ) : loginMethod === 'sso' && showLogin ? (
              <form className="space-y-5" onSubmit={handleSsoSubmit} noValidate>
                <div className="space-y-2">
                  <label htmlFor="sso-email" className="block text-sm font-medium text-slate-700">
                    Email address
                  </label>
                  <div className="relative">
                    <input
                      id="sso-email"
                      type="email"
                      value={email}
                      onChange={(event) => handleEmailChange(event.target.value)} onBlur={handleEmailBlur}
                      aria-invalid={emailError ? true : undefined}
                      aria-describedby={emailError ? 'sso-email-error' : undefined}
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
                        ) : validateEmail(email.trim()) === null ? (
                          <CheckCircle size={16} className="text-emerald-600" />
                        ) : null}
                      </div>
                    )}
                  </div>
                  {emailError && (
                    <p id="sso-email-error" role="alert" className="text-xs text-red-600">
                      {emailError}
                    </p>
                  )}
                </div>

                {ssoNotice && (
                  <div
                    role="status"
                    className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800"
                  >
                    <AlertTriangle size={16} className="mt-0.5 shrink-0 text-amber-600" aria-hidden="true" />
                    <span>{ssoNotice}</span>
                  </div>
                )}

                <button
                  type="submit"
                  disabled={loading || submitting}
                  className="theme-button-primary inline-flex w-full items-center justify-center gap-2 rounded-2xl px-5 py-3.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {submitting && <Loader2 size={16} className="animate-spin" aria-hidden="true" />}
                  Continue with SSO
                </button>

                <button
                  type="button"
                  onClick={handleBackToPassword}
                  className="inline-flex w-full items-center justify-center gap-2 rounded-2xl border border-slate-300 bg-white px-5 py-3.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
                >
                  <ArrowLeft size={16} aria-hidden="true" />
                  Back to sign in
                </button>
              </form>
            ) : loginMethod === 'register' && showLogin ? (
              registerEmailSent ? (
                <div className="space-y-6">
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
                    <div className="flex items-start gap-3">
                      <CheckCircle size={18} className="mt-0.5 shrink-0 text-emerald-600" aria-hidden="true" />
                      <div>
                        <p className="text-sm font-medium text-slate-900">
                          Verification email sent
                        </p>
                        <p className="mt-1 text-sm text-slate-600">
                          We sent a verification link to <strong>{email.trim()}</strong>. Open it
                          to activate your account.
                        </p>
                      </div>
                    </div>
                  </div>

                  {resendNotice && (
                    <div
                      role="status"
                      className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800"
                    >
                      {resendNotice}
                    </div>
                  )}

                  {formError && (
                    <div className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                      <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
                      <span>{formError}</span>
                    </div>
                  )}

                  <button
                    type="button"
                    onClick={handleResendVerification}
                    disabled={loading || submitting}
                    className="inline-flex w-full items-center justify-center gap-2 rounded-2xl border border-slate-300 bg-white px-5 py-3.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {submitting && <Loader2 size={16} className="animate-spin" aria-hidden="true" />}
                    Resend verification email
                  </button>

                  <button
                    type="button"
                    onClick={handleBackToPassword}
                    className="theme-button-primary inline-flex w-full items-center justify-center gap-2 rounded-2xl px-5 py-3.5 text-sm font-semibold transition"
                  >
                    <ArrowLeft size={16} aria-hidden="true" />
                    Back to sign in
                  </button>
                </div>
              ) : (
                <form className="space-y-5" onSubmit={handleRegisterSubmit} noValidate>
                  <div className="space-y-2">
                    <label htmlFor="register-name" className="block text-sm font-medium text-slate-700">
                      Full name
                    </label>
                    <input
                      id="register-name"
                      value={fullName}
                      onChange={(event) => {
                        setFullName(event.target.value);
                        if (formError) setFormError('');
                      }}
                      autoComplete="name"
                      placeholder="Professor Ada Lovelace"
                      className="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3.5 text-slate-900 outline-none transition focus:border-slate-900 focus:ring-4 focus:ring-slate-900/10"
                    />
                  </div>

                  <div className="space-y-2">
                    <label htmlFor="register-email" className="block text-sm font-medium text-slate-700">
                      Email address
                    </label>
                    <div className="relative">
                      <input
                        id="register-email"
                        type="email"
                        value={email}
                        onChange={(event) => handleEmailChange(event.target.value)} onBlur={handleEmailBlur}
                        aria-invalid={emailError ? true : undefined}
                        aria-describedby={emailError ? 'register-email-error' : undefined}
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
                          ) : validateEmail(email.trim()) === null ? (
                            <CheckCircle size={16} className="text-emerald-600" />
                          ) : null}
                        </div>
                      )}
                    </div>
                    {emailError && (
                      <p id="register-email-error" role="alert" className="text-xs text-red-600">
                        {emailError}
                      </p>
                    )}
                  </div>

                  <div className="space-y-2">
                    <label htmlFor="register-password" className="block text-sm font-medium text-slate-700">
                      Password
                    </label>
                    <div className="relative">
                      <input
                        id="register-password"
                        type={showPassword ? 'text' : 'password'}
                        value={password}
                        onChange={(event) => handlePasswordChange(event.target.value)}
                        aria-invalid={passwordError ? true : undefined}
                        aria-describedby={passwordError ? 'register-password-error' : undefined}
                        autoComplete="new-password"
                        placeholder="Create a password"
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

                    {password && (
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

                    {!password && (
                      <p className="text-xs text-slate-500">
                        Use at least 12 characters with an uppercase letter, a lowercase letter, and a number.
                      </p>
                    )}

                    {passwordError && (
                      <p id="register-password-error" role="alert" className="text-xs text-red-600">
                        {passwordError}
                      </p>
                    )}
                  </div>

                  <div className="space-y-2">
                    <label htmlFor="register-confirm" className="block text-sm font-medium text-slate-700">
                      Confirm password
                    </label>
                    <div className="relative">
                      <input
                        id="register-confirm"
                        type={showPassword ? 'text' : 'password'}
                        value={confirmPassword}
                        onChange={(event) => {
                          setConfirmPassword(event.target.value);
                          if (confirmPasswordError) setConfirmPasswordError('');
                        }}
                        aria-invalid={confirmPasswordError ? true : undefined}
                        aria-describedby={confirmPasswordError ? 'register-confirm-error' : undefined}
                        autoComplete="new-password"
                        placeholder="Repeat the password"
                        className={`w-full rounded-2xl border bg-white px-4 py-3.5 pr-12 text-slate-900 outline-none transition focus:ring-4 ${confirmPasswordError
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
                    {confirmPasswordError && (
                      <p id="register-confirm-error" role="alert" className="text-xs text-red-600">
                        {confirmPasswordError}
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
                    className="theme-button-primary inline-flex w-full items-center justify-center gap-2 rounded-2xl px-5 py-3.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {submitting && <Loader2 size={16} className="animate-spin" aria-hidden="true" />}
                    {submitting ? 'Creating account…' : 'Create account'}
                  </button>

                  <button
                    type="button"
                    onClick={handleBackToPassword}
                    className="inline-flex w-full items-center justify-center gap-2 rounded-2xl border border-slate-300 bg-white px-5 py-3.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
                  >
                    <ArrowLeft size={16} aria-hidden="true" />
                    Back to sign in
                  </button>
                </form>
              )
            ) : (
              <form className="space-y-5" onSubmit={handleSubmit} noValidate>
                                {!showLogin && (
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
                      onChange={(event) => handleEmailChange(event.target.value)} onBlur={handleEmailBlur}
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
                        ) : validateEmail(email.trim()) === null ? (
                          <CheckCircle size={16} className="text-emerald-600" />
                        ) : null}
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
                      autoComplete={showLogin ? 'current-password' : 'new-password'}
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

                  {!showLogin && password && (
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

                                    {!showLogin && !password && (
                    <p className="text-xs text-slate-500">
                      Use at least 12 characters with an uppercase letter, a lowercase letter, and a number.
                    </p>
                  )}

                  {passwordError && (
                    <p id="password-error" role="alert" className="text-xs text-red-600">
                      {passwordError}
                    </p>
                  )}
                </div>

                                {showLogin && (
                  <div className="flex items-center justify-end">
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
                  className="theme-button-primary inline-flex w-full items-center justify-center gap-2 rounded-2xl px-5 py-3.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {submitting && <Loader2 size={16} className="animate-spin" aria-hidden="true" />}
                  {submitting
                    ? 'Processing...'
                    : showLogin
                      ? 'Sign in'
                      : 'Create administrator account'}
                </button>

                <div className="relative py-1" aria-hidden="true">
                  <span className="block w-full border-t border-slate-200" />
                  <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 bg-white px-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                    or
                  </span>
                </div>

                {showLogin && (
                  <button
                    type="button"
                    onClick={handleChooseSso}
                    className="inline-flex w-full items-center justify-center gap-2 rounded-2xl border border-slate-300 bg-white px-5 py-3.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
                  >
                    <KeyRound size={16} aria-hidden="true" />
                    Continue with SSO
                  </button>
                )}

                <button
                  type="button"
                  onClick={handleGuestLogin}
                  disabled={loading || guestSubmitting}
                  className="inline-flex w-full items-center justify-center gap-2 rounded-2xl border border-slate-300 bg-white px-5 py-3.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {guestSubmitting ? (
                    <Loader2 size={16} className="animate-spin" aria-hidden="true" />
                  ) : (
                    <Rocket size={16} aria-hidden="true" />
                  )}
                  {guestSubmitting ? 'Starting demo…' : 'Continue as guest'}
                </button>

                {showLogin && (
                  <p className="text-center text-sm text-slate-500">
                    Don’t have an account?{' '}
                    <button
                      type="button"
                      onClick={handleChooseRegister}
                      className="font-semibold text-slate-900 underline-offset-4 transition hover:underline"
                    >
                      Create one
                    </button>
                  </p>
                )}

                {!showLogin && (
                  <button
                    type="button"
                    onClick={() => setForceSignIn(true)}
                    className="inline-flex w-full items-center justify-center gap-2 rounded-2xl border border-slate-300 bg-white px-5 py-3.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
                  >
                    Already have an account? Sign in
                  </button>
                )}
               </form>
             )}
           </div>
         </section>
      </div>
    </div>
  );
}