'use client';

import { FormEvent, ReactNode, useEffect, useMemo, useState } from 'react';
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
 * messages are never echoed. When the backend returns a correlation / request
 * id header it is appended so support can find the matching log line.
 */
function getErrorMessage(error: unknown, context: 'signin' | 'general' = 'general'): string {
  const { status, reference } = getErrorInfo(error);

  let message: string;
  if (status === undefined) {
    message = 'Something went wrong. Please try again.';
  } else if (status === 429) {
    message = 'Too many attempts. Please wait a moment and try again.';
  } else if (status === 401 && context === 'signin') {
    message = 'Incorrect email or password.';
  } else if (status === 403 && context === 'signin') {
    message = 'This account can’t sign in yet. If you just registered, open the verification link we emailed you.';
  } else if (status >= 500) {
    message = 'Something went wrong on our side. Please try again.';
  } else {
    message = 'We couldn’t complete that request. Please check your details and try again.';
  }

  return reference ? `${message} (Reference: ${reference})` : message;
}

/**
 * Only same-origin, in-app paths are allowed. The query string is kept
 * (``/results?tab=pairs`` used to lose ``?tab=pairs``), and ``/login`` itself
 * is rejected so a signed-in user can't be bounced back onto this page.
 */
function sanitizeNextPath(value: string | null): string {
  if (!value || !value.startsWith('/') || value.startsWith('//') || value.includes('\\')) {
    return '/';
  }

  try {
    const url = new URL(value, window.location.origin);
    if (url.origin !== window.location.origin) {
      return '/';
    }
    if (url.pathname === '/login' || url.pathname.startsWith('/login/')) {
      return '/';
    }
    return `${url.pathname}${url.search}`;
  } catch {
    return '/';
  }
}

const SSO_START_URL = process.env.NEXT_PUBLIC_SSO_START_URL ?? '';

/**
 * Where "Sign in with UTORid" sends the browser (the backend's OIDC start
 * endpoint). Returns null until NEXT_PUBLIC_SSO_START_URL is configured. Only
 * same-origin or HTTPS targets are accepted so a bad value can't send users
 * to a plain-HTTP or odd-scheme address.
 */
function resolveSsoStartUrl(nextPath: string | null): string | null {
  if (!SSO_START_URL) {
    return null;
  }

  try {
    const url = new URL(SSO_START_URL, window.location.origin);
    if (url.origin !== window.location.origin && url.protocol !== 'https:') {
      return null;
    }
    url.searchParams.set('next', nextPath ?? '/');
    return url.toString();
  } catch {
    return null;
  }
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

  // The meter must never call a password "Strong" or "Medium" when the server
  // would reject it (e.g. "Passw0rd!" is 9 characters).
  if (validateNewPassword(password) !== null) {
    score = Math.min(score, 2);
  }

  if (score <= 2) {
    return { score, label: 'Weak', tone: 'text-red-700', bar: 'bg-red-500' };
  }

  if (score <= 4) {
    return { score, label: 'Medium', tone: 'text-amber-700', bar: 'bg-amber-500' };
  }

  return { score, label: 'Strong', tone: 'text-emerald-700', bar: 'bg-emerald-500' };
}

function validateEmail(email: string): string | null {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!email) return null;
  if (!emailRegex.test(email)) return 'Please enter a valid email address.';
  return null;
}

/* -------------------------------------------------------------------------- */
/* Shared styles + small components (defined outside LoginPage on purpose:    */
/* components declared inside would remount on every keystroke)               */
/* -------------------------------------------------------------------------- */

const PRIMARY_BUTTON =
  'theme-button-primary inline-flex w-full items-center justify-center gap-2 rounded-2xl px-5 py-3.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60';
const SECONDARY_BUTTON =
  'inline-flex w-full items-center justify-center gap-2 rounded-2xl border border-slate-300 bg-white px-5 py-3.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60';

function inputClass(invalid: boolean, padRight = ''): string {
  return `w-full rounded-2xl border bg-white px-4 py-3.5 ${padRight} text-slate-900 outline-none transition focus:ring-4 ${invalid
    ? 'border-red-300 focus:border-red-500 focus:ring-red-500/10'
    : 'border-slate-300 focus:border-slate-900 focus:ring-slate-900/10'
    }`;
}

function ErrorBanner({ message }: { message: string }) {
  if (!message) return null;

  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
    >
      <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}

function TextField({
  id,
  label,
  value,
  onChange,
  autoComplete,
  placeholder,
  autoFocus,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete: string;
  placeholder: string;
  autoFocus?: boolean;
}) {
  return (
    <div className="space-y-2">
      <label htmlFor={id} className="block text-sm font-medium text-slate-700">
        {label}
      </label>
      <input
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        autoComplete={autoComplete}
        autoFocus={autoFocus}
        placeholder={placeholder}
        className={inputClass(false)}
      />
    </div>
  );
}

function EmailField({
  id,
  value,
  error,
  onChange,
  onBlur,
  autoComplete = 'email',
  autoFocus,
}: {
  id: string;
  value: string;
  error: string;
  onChange: (value: string) => void;
  onBlur: () => void;
  autoComplete?: string;
  autoFocus?: boolean;
}) {
  const errorId = `${id}-error`;

  return (
    <div className="space-y-2">
      <label htmlFor={id} className="block text-sm font-medium text-slate-700">
        Email address
      </label>
      <div className="relative">
        <input
          id={id}
          name="email"
          type="email"
          inputMode="email"
          autoCapitalize="none"
          spellCheck={false}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onBlur={onBlur}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : undefined}
          autoComplete={autoComplete}
          autoFocus={autoFocus}
          placeholder="name@institution.edu"
          className={inputClass(Boolean(error), 'pr-11')}
        />
        {value && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2" aria-hidden="true">
            {error ? (
              <XCircle size={16} className="text-red-500" />
            ) : validateEmail(value.trim()) === null ? (
              <CheckCircle size={16} className="text-emerald-600" />
            ) : null}
          </div>
        )}
      </div>
      {error && (
        <p id={errorId} role="alert" className="text-xs text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}

function PasswordField({
  id,
  name,
  label = 'Password',
  value,
  error,
  onChange,
  show,
  onToggleShow,
  autoComplete,
  placeholder,
  children,
}: {
  id: string;
  name: string;
  label?: string;
  value: string;
  error: string;
  onChange: (value: string) => void;
  show: boolean;
  onToggleShow: () => void;
  autoComplete: string;
  placeholder: string;
  children?: ReactNode;
}) {
  const errorId = `${id}-error`;
  const [capsLock, setCapsLock] = useState(false);

  return (
    <div className="space-y-2">
      <label htmlFor={id} className="block text-sm font-medium text-slate-700">
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          name={name}
          type={show ? 'text' : 'password'}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : undefined}
          onKeyDown={(event) => setCapsLock(event.getModifierState('CapsLock'))}
          onKeyUp={(event) => setCapsLock(event.getModifierState('CapsLock'))}
          onBlur={() => setCapsLock(false)}
          autoComplete={autoComplete}
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          placeholder={placeholder}
          className={inputClass(Boolean(error), 'pr-12')}
        />
        <button
          type="button"
          aria-label={show ? 'Hide password' : 'Show password'}
          onClick={onToggleShow}
          className="absolute right-1.5 top-1/2 inline-flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-xl text-slate-500 transition hover:bg-slate-100 hover:text-slate-700"
        >
          {show ? <EyeOff size={18} aria-hidden="true" /> : <Eye size={18} aria-hidden="true" />}
        </button>
      </div>

      {capsLock && (
        <p role="status" className="text-xs font-medium text-amber-700">
          Caps Lock is on.
        </p>
      )}

      {children}

      {error && (
        <p id={errorId} role="alert" className="text-xs text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}

function PasswordStrengthMeter({ password }: { password: string }) {
  const strength = useMemo(() => calculatePasswordStrength(password), [password]);

  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <div className="mb-2 flex items-center justify-between">
        <span className={`text-sm font-medium ${strength.tone}`}>Password strength: {strength.label}</span>
        <span className="text-xs text-slate-500">{password.length} characters</span>
      </div>
      <div className="flex gap-1" aria-hidden="true">
        {[1, 2, 3, 4, 5, 6].map((level) => (
          <div
            key={level}
            className={`h-2 flex-1 rounded-full ${level <= strength.score ? strength.bar : 'bg-slate-200'}`}
          />
        ))}
      </div>
    </div>
  );
}

function PasswordHint() {
  return (
    <p className="text-xs text-slate-500">
      Use at least 12 characters with an uppercase letter, a lowercase letter, and a number.
    </p>
  );
}

/* -------------------------------------------------------------------------- */
/* Page                                                                       */
/* -------------------------------------------------------------------------- */

function PasswordRequirements({ password }: { password: string }) {
  const rules = [
    { label: 'At least 12 characters', ok: password.length >= 12 },
    { label: 'An uppercase letter', ok: /[A-Z]/.test(password) },
    { label: 'A lowercase letter', ok: /[a-z]/.test(password) },
    { label: 'A number', ok: /[0-9]/.test(password) },
  ];

  return (
    <ul className="space-y-1 text-xs" aria-label="Password requirements">
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

/** Empty field -> one-line hint; while typing -> strength meter + live checklist. */
function PasswordFeedback({ password }: { password: string }) {
  if (!password) {
    return <PasswordHint />;
  }

  return (
    <>
      <PasswordStrengthMeter password={password} />
      <PasswordRequirements password={password} />
    </>
  );
}

function NoticeBanner({ message }: { message: string }) {
  return (
    <div
      role="status"
      className="mb-5 flex items-start gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700"
    >
      <ShieldCheck size={16} className="mt-0.5 shrink-0 text-slate-500" aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}

// Fixed, benign messages selected by ?reason=. Anything not listed is ignored,
// so a crafted link can't put arbitrary text on the page.
const NOTICES: Record<string, string> = {
  expired: 'Your session expired. Please sign in again.',
  signed_out: 'You have been signed out.',
  password_reset: 'Your password was updated. Sign in with your new password.',
};

type LoginMethod = 'password' | 'register';
type View = 'start' | 'signin' | 'bootstrap' | 'forgot' | 'forgot-sent' | 'register' | 'register-sent';

export default function LoginPage() {
  const router = useRouter();
  const { user, loading, bootstrapped, login, guestLogin, bootstrapAdmin } = useAuth();

  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [tenantName, setTenantName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [forceSignIn, setForceSignIn] = useState(false);

  const [emailError, setEmailError] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [confirmPasswordError, setConfirmPasswordError] = useState('');
  const [formError, setFormError] = useState('');

  const [submitting, setSubmitting] = useState(false);
  const [guestSubmitting, setGuestSubmitting] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const [notice, setNotice] = useState('');

  // ``null`` until the ?next= parameter has been read. The sign-in redirect
  // waits for it, which replaces the old 200ms timer that only existed to
  // stop an already-signed-in user being sent to "/" before ``next`` was parsed.
  const [nextPath, setNextPath] = useState<string | null>(null);

  const [showForgotPassword, setShowForgotPassword] = useState(false);
  const [resetEmailSent, setResetEmailSent] = useState(false);
  // "password" is the sign-in landing (UTORid first, or the email form when
  // showEmailForm is on). "register" opens the self-signup form, which ends in a
  // "check your inbox" card rather than a session — the account stays locked
  // until the emailed link is redeemed.
  const [loginMethod, setLoginMethod] = useState<LoginMethod>('password');
  const [showEmailForm, setShowEmailForm] = useState(false);
  const [redirecting, setRedirecting] = useState(false);
  const [ssoNotice, setSsoNotice] = useState('');
  const [registerEmailSent, setRegisterEmailSent] = useState(false);
  const [resendNotice, setResendNotice] = useState('');

  // Treat "status still loading" as sign-in so returning professors never see
  // the bootstrap form flash before /api/auth/status resolves.
  const showLogin = loading || bootstrapped || forceSignIn;

  const view: View = showForgotPassword
    ? resetEmailSent
      ? 'forgot-sent'
      : 'forgot'
    : showLogin && loginMethod === 'register'
      ? registerEmailSent
        ? 'register-sent'
        : 'register'
      : showLogin
        ? showEmailForm
          ? 'signin'
          : 'start'
        : 'bootstrap';

  const busy = loading || submitting || guestSubmitting || redirecting || cooldown > 0;

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setNextPath(sanitizeNextPath(params.get('next')));

    const reason = params.get('reason');
    setNotice(reason && Object.prototype.hasOwnProperty.call(NOTICES, reason) ? NOTICES[reason] : '');

    // ?method=email opens the email form directly (used after a password reset).
    if (params.get('method') === 'email') {
      setShowEmailForm(true);
    }
  }, []);

  useEffect(() => {
    // Guests are bounced back to the sign-in form rather than away from it:
    // they reached /login to upgrade the demo session into a real account.
    if (loading || !user || user.role === 'guest' || nextPath === null) {
      return;
    }
    router.replace(nextPath);
  }, [loading, user, nextPath, router]);

  // Rate-limit countdown: submit buttons stay locked until it reaches zero.
  useEffect(() => {
    if (cooldown <= 0) {
      return;
    }
    const timer = setTimeout(() => setCooldown((seconds) => seconds - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  // Coming back with the browser's Back button can restore this page with the
  // redirect spinner still on; reset it.
  useEffect(() => {
    const handlePageShow = (event: PageTransitionEvent) => {
      if (event.persisted) {
        setRedirecting(false);
      }
    };
    window.addEventListener('pageshow', handlePageShow);
    return () => window.removeEventListener('pageshow', handlePageShow);
  }, []);

  /* ----------------------------- state helpers ---------------------------- */

  const clearFeedback = () => {
    setFormError('');
    setEmailError('');
    setPasswordError('');
    setConfirmPasswordError('');
    setSsoNotice('');
    setResendNotice('');
    setNotice('');
  };

  // Passwords never carry over between views (e.g. sign-in -> register).
  const clearSecrets = () => {
    setPassword('');
    setConfirmPassword('');
    setShowPassword(false);
  };

  /** Switch view and reset everything transient so nothing stale carries over. */
  const openView = (method: LoginMethod, options: { emailForm?: boolean } = {}) => {
    clearFeedback();
    clearSecrets();
    setShowForgotPassword(false);
    setResetEmailSent(false);
    setRegisterEmailSent(false);
    setShowEmailForm(options.emailForm ?? false);
    setLoginMethod(method);
  };

  const handleBackToPassword = () => openView('password');
  // From the reset flow, "back" returns to the email form the user came from.
  const handleBackToLogin = () => openView('password', { emailForm: true });
  const handleChooseRegister = () => openView('register');

  const handleUseEmail = () => {
    // Keep any ?reason= notice (e.g. "session expired") visible on the email form.
    setFormError('');
    setSsoNotice('');
    setShowEmailForm(true);
  };

  const handleBackToUtorid = () => {
    clearFeedback();
    clearSecrets();
    setShowEmailForm(false);
  };

  const handleShowForgotPassword = () => {
    // Without this, a failed sign-in's error banner followed the user into
    // the reset form.
    clearFeedback();
    clearSecrets();
    setResetEmailSent(false);
    setShowForgotPassword(true);
  };

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

  const handleConfirmPasswordChange = (value: string) => {
    setConfirmPassword(value);
    if (confirmPasswordError) setConfirmPasswordError('');
  };

  /** Shared email checks; returns true when the address is usable. */
  const checkEmail = (trimmedEmail: string, fieldId: string): boolean => {
    if (!trimmedEmail) {
      setEmailError('Email address is required.');
      focusField(fieldId);
      return false;
    }
    const emailValidationError = validateEmail(trimmedEmail);
    if (emailValidationError) {
      setEmailError(emailValidationError);
      focusField(fieldId);
      return false;
    }
    return true;
  };

  /* -------------------------------- handlers ------------------------------ */

  /** Move focus to the first invalid field so keyboard and screen-reader users land on the problem. */
  const focusField = (id: string) => {
    window.requestAnimationFrame(() => document.getElementById(id)?.focus());
  };

  /** On a 429, lock the submit buttons for the server's Retry-After (30s if absent). */
  const applyRateLimit = (error: unknown) => {
    const { status, retryAfter } = getErrorInfo(error);
    if (status === 429) {
      setCooldown(retryAfter ?? 30);
    }
  };

  const cooldownLabel = cooldown > 0 ? `Try again in ${cooldown}s` : null;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submitting || guestSubmitting) return;

    clearFeedback();

    const trimmedEmail = email.trim();
    const trimmedFullName = fullName.trim();
    const trimmedTenantName = tenantName.trim();

    if (!checkEmail(trimmedEmail, 'email')) {
      return;
    }

    if (showLogin) {
      // Don't spend a request (and a rate-limit attempt) on an empty password.
      if (!password) {
        setPasswordError('Password is required.');
        focusField('password');
        return;
      }
    } else {
      if (!trimmedFullName) {
        setFormError('Full name is required.');
        focusField('full-name');
        return;
      }

      if (!trimmedTenantName) {
        setFormError('Workspace name is required.');
        focusField('tenant-name');
        return;
      }

      const validatedPasswordError = validateNewPassword(password);
      if (validatedPasswordError) {
        setPasswordError(validatedPasswordError);
        focusField('password');
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

      router.replace(nextPath ?? '/');
    } catch (authError) {
      setFormError(getErrorMessage(authError, showLogin ? 'signin' : 'general'));
      applyRateLimit(authError);
    } finally {
      setSubmitting(false);
    }
  };

  const handleForgotPasswordSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submitting) return;

    clearFeedback();

    const trimmedEmail = email.trim();
    if (!checkEmail(trimmedEmail, 'forgot-email')) {
      return;
    }

    setSubmitting(true);

    try {
      await apiClient.post('/api/auth/forgot-password', { email: trimmedEmail });
      setResetEmailSent(true);
    } catch (error) {
      // 4xx answers are shown as "sent" so the form never reveals whether an
      // account exists. Network failures, rate limits and server errors are
      // real problems the user can act on, so those are surfaced.
      const { status } = getErrorInfo(error);
      if (status === undefined || status === 429 || status >= 500) {
        setFormError(getErrorMessage(error));
        applyRateLimit(error);
      } else {
        setResetEmailSent(true);
      }
    } finally {
      setSubmitting(false);
    }
  };

  /**
   * Start a guest demo session and land on the checker.
   *
   * ``nextPath`` is set before the session starts so the sign-in redirect
   * (which fires once ``user`` resolves) also goes to ``/upload``: a guest has
   * no dashboard to land on. If it fails, the original ``next`` target is
   * restored (it used to be reset to "/").
   */
  const handleGuestLogin = async () => {
    if (submitting || guestSubmitting) return;

    clearFeedback();
    const previousNextPath = nextPath;
    setGuestSubmitting(true);
    try {
      setNextPath('/upload');
      await guestLogin();
      router.replace('/upload');
    } catch (error) {
      setNextPath(previousNextPath);
      setFormError(getErrorMessage(error));
      applyRateLimit(error);
    } finally {
      setGuestSubmitting(false);
    }
  };

  /**
   * Start UTORid sign-in (Entra ID).
   *
   * A full-page redirect to the backend's sign-in endpoint, which owns the
   * OIDC exchange and the session; this page never handles a password or token
   * for it. ``next`` is passed along, but the backend must validate it again
   * before redirecting after sign-in. Until NEXT_PUBLIC_SSO_START_URL is set,
   * say so plainly instead of pretending the hand-off happened.
   */
  const handleUtorid = () => {
    if (loading || submitting || guestSubmitting || redirecting) return;

    clearFeedback();

    const target = resolveSsoStartUrl(nextPath);
    if (!target) {
      setSsoNotice('UTORid sign-in isn’t connected for this workspace yet. Use your email to sign in for now.');
      return;
    }

    setRedirecting(true);
    window.location.assign(target);
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
    if (submitting) return;

    clearFeedback();

    const trimmedEmail = email.trim();
    const trimmedFullName = fullName.trim();

    if (!checkEmail(trimmedEmail, 'register-email')) {
      return;
    }
    if (!trimmedFullName) {
      setFormError('Full name is required.');
      focusField('register-name');
      return;
    }
    const passwordValidationError = validateNewPassword(password);
    if (passwordValidationError) {
      setPasswordError(passwordValidationError);
      focusField('register-password');
      return;
    }
    if (password !== confirmPassword) {
      setConfirmPasswordError('Passwords do not match.');
      focusField('register-confirm');
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
      applyRateLimit(error);
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
    if (submitting) return;

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
      applyRateLimit(error);
    } finally {
      setSubmitting(false);
    }
  };

  /* --------------------------------- render ------------------------------- */

  const headings: Record<View, string> = {
    start: 'Sign-In',
    signin: 'Sign-In',
    bootstrap: 'Create Administrator Account',
    forgot: 'Reset password',
    'forgot-sent': 'Check your email',
    register: 'Create Account',
    'register-sent': 'Check your email',
  };

  const subtitles: Partial<Record<View, string>> = {
    start: 'Use your UTORid to sign in, or continue with email.',
    forgot: 'Enter your email address and we will send reset instructions.',
    'forgot-sent': 'If the account exists, password reset instructions have been sent.',
    bootstrap: 'Set up the first administrator account for this workspace.',
  };

  const subtitle = subtitles[view];

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

        <main className="flex items-center justify-center bg-white">
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
                {view === 'register' || view === 'register-sent' ? (
                  <UserPlus size={20} aria-hidden="true" />
                ) : (
                  <LockKeyhole size={20} aria-hidden="true" />
                )}
              </div>
              <h2 className="text-2xl font-semibold tracking-tight text-slate-900">{headings[view]}</h2>
              {subtitle && <p className="mt-2 text-sm leading-6 text-slate-600">{subtitle}</p>}
            </div>

            {(view === 'start' || view === 'signin') && notice && <NoticeBanner message={notice} />}

            {view === 'forgot-sent' && (
              <div className="space-y-6">
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
                  <div className="flex items-start gap-3">
                    <CheckCircle size={18} className="mt-0.5 shrink-0 text-emerald-600" aria-hidden="true" />
                    <div>
                      <p className="text-sm font-medium text-slate-900">Reset instructions sent</p>
                      <p className="mt-1 text-sm text-slate-600">
                        If an account exists for <strong>{email.trim()}</strong>, you’ll receive an email shortly.
                      </p>
                    </div>
                  </div>
                </div>

                <button type="button" onClick={handleBackToLogin} className={PRIMARY_BUTTON}>
                  <ArrowLeft size={16} aria-hidden="true" />
                  Return to sign in
                </button>
              </div>
            )}

            {view === 'forgot' && (
              <form className="space-y-5" onSubmit={handleForgotPasswordSubmit} noValidate>
                <EmailField
                  id="forgot-email"
                  value={email}
                  error={emailError}
                  onChange={handleEmailChange}
                  onBlur={handleEmailBlur}
                  autoFocus
                />

                <ErrorBanner message={formError} />

                <button type="submit" disabled={busy} className={PRIMARY_BUTTON}>
                  {submitting ? 'Sending...' : cooldownLabel ?? 'Send reset instructions'}
                </button>

                <button type="button" onClick={handleBackToLogin} className={SECONDARY_BUTTON}>
                  <ArrowLeft size={16} aria-hidden="true" />
                  Back to sign in
                </button>
              </form>
            )}

            {view === 'start' && (
              <div className="space-y-5">
                {ssoNotice && (
                  <div
                    role="status"
                    className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800"
                  >
                    <AlertTriangle size={16} className="mt-0.5 shrink-0 text-amber-600" aria-hidden="true" />
                    <span>{ssoNotice}</span>
                  </div>
                )}

                <ErrorBanner message={formError} />

                <button
                  type="button"
                  onClick={handleUtorid}
                  disabled={loading || submitting || guestSubmitting || redirecting}
                  className={PRIMARY_BUTTON}
                >
                  {redirecting ? (
                    <Loader2 size={16} className="animate-spin" aria-hidden="true" />
                  ) : (
                    <KeyRound size={16} aria-hidden="true" />
                  )}
                  {redirecting ? 'Redirecting…' : 'Sign in with UTORid'}
                </button>

                <button
                  type="button"
                  onClick={handleUseEmail}
                  disabled={redirecting}
                  className="block w-full text-center text-sm font-medium text-slate-600 transition hover:text-slate-900 disabled:opacity-60"
                >
                  Use email instead
                </button>

                <div className="relative py-1" aria-hidden="true">
                  <span className="block w-full border-t border-slate-200" />
                  <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 bg-white px-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                    or
                  </span>
                </div>

                <button type="button" onClick={handleGuestLogin} disabled={busy} className={SECONDARY_BUTTON}>
                  {guestSubmitting ? (
                    <Loader2 size={16} className="animate-spin" aria-hidden="true" />
                  ) : (
                    <Rocket size={16} aria-hidden="true" />
                  )}
                  {guestSubmitting ? 'Starting demo…' : 'Continue as guest'}
                </button>

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
              </div>
            )}

            {view === 'register-sent' && (
              <div className="space-y-6">
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
                  <div className="flex items-start gap-3">
                    <CheckCircle size={18} className="mt-0.5 shrink-0 text-emerald-600" aria-hidden="true" />
                    <div>
                      <p className="text-sm font-medium text-slate-900">Verification email sent</p>
                      <p className="mt-1 text-sm text-slate-600">
                        We sent a verification link to <strong>{email.trim()}</strong>. Open it to activate your
                        account.
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

                <ErrorBanner message={formError} />

                <button
                  type="button"
                  onClick={handleResendVerification}
                  disabled={busy}
                  className={SECONDARY_BUTTON}
                >
                  {submitting && <Loader2 size={16} className="animate-spin" aria-hidden="true" />}
                  Resend verification email
                </button>

                <button type="button" onClick={handleBackToPassword} className={PRIMARY_BUTTON}>
                  <ArrowLeft size={16} aria-hidden="true" />
                  Back to sign in
                </button>
              </div>
            )}

            {view === 'register' && (
              <form className="space-y-5" onSubmit={handleRegisterSubmit} noValidate>
                <TextField
                  id="register-name"
                  label="Full name"
                  value={fullName}
                  onChange={(value) => {
                    setFullName(value);
                    if (formError) setFormError('');
                  }}
                  autoComplete="name"
                  placeholder="Professor Ada Lovelace"
                  autoFocus
                />

                <EmailField
                  id="register-email"
                  value={email}
                  error={emailError}
                  onChange={handleEmailChange}
                  onBlur={handleEmailBlur}
                />

                <PasswordField
                  id="register-password"
                  name="new-password"
                  value={password}
                  error={passwordError}
                  onChange={handlePasswordChange}
                  show={showPassword}
                  onToggleShow={() => setShowPassword((value) => !value)}
                  autoComplete="new-password"
                  placeholder="Create a password"
                >
                  {<PasswordFeedback password={password} />}
                </PasswordField>

                <PasswordField
                  id="register-confirm"
                  name="confirm-password"
                  label="Confirm password"
                  value={confirmPassword}
                  error={confirmPasswordError}
                  onChange={handleConfirmPasswordChange}
                  show={showPassword}
                  onToggleShow={() => setShowPassword((value) => !value)}
                  autoComplete="new-password"
                  placeholder="Repeat the password"
                />

                <ErrorBanner message={formError} />

                <button type="submit" disabled={busy} className={PRIMARY_BUTTON}>
                  {submitting && <Loader2 size={16} className="animate-spin" aria-hidden="true" />}
                  {submitting ? 'Creating account…' : cooldownLabel ?? 'Create account'}
                </button>

                <button type="button" onClick={handleBackToPassword} className={SECONDARY_BUTTON}>
                  <ArrowLeft size={16} aria-hidden="true" />
                  Back to sign in
                </button>
              </form>
            )}

            {(view === 'signin' || view === 'bootstrap') && (
              <form className="space-y-5" onSubmit={handleSubmit} noValidate>
                {view === 'bootstrap' && (
                  <>
                    <TextField
                      id="full-name"
                      label="Full name"
                      value={fullName}
                      onChange={setFullName}
                      autoComplete="name"
                      placeholder="Professor Ada Lovelace"
                    />
                    <TextField
                      id="tenant-name"
                      label="Workspace name"
                      value={tenantName}
                      onChange={setTenantName}
                      autoComplete="organization"
                      placeholder="Computer Science Department"
                    />
                  </>
                )}

                <EmailField
                  id="email"
                  value={email}
                  error={emailError}
                  onChange={handleEmailChange}
                  onBlur={handleEmailBlur}
                  autoComplete={view === 'signin' ? 'username' : 'email'}
                />

                <PasswordField
                  id="password"
                  name="password"
                  value={password}
                  error={passwordError}
                  onChange={handlePasswordChange}
                  show={showPassword}
                  onToggleShow={() => setShowPassword((value) => !value)}
                  autoComplete={view === 'signin' ? 'current-password' : 'new-password'}
                  placeholder="Enter your password"
                >
                  {view === 'bootstrap' && <PasswordFeedback password={password} />}
                </PasswordField>

                {view === 'signin' && (
                  <div className="flex items-center justify-end">
                    <button
                      type="button"
                      onClick={handleShowForgotPassword}
                      className="text-sm font-medium text-slate-600 transition hover:text-slate-900"
                    >
                      Forgot password?
                    </button>
                  </div>
                )}

                <ErrorBanner message={formError} />

                <button type="submit" disabled={busy} className={PRIMARY_BUTTON}>
                  {submitting && <Loader2 size={16} className="animate-spin" aria-hidden="true" />}
                  {submitting
                    ? 'Processing...'
                    : cooldownLabel ?? (view === 'signin' ? 'Sign in' : 'Create administrator account')}
                </button>

                <div className="relative py-1" aria-hidden="true">
                  <span className="block w-full border-t border-slate-200" />
                  <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 bg-white px-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                    or
                  </span>
                </div>

                {view === 'signin' && (
                  <button type="button" onClick={handleBackToUtorid} className={SECONDARY_BUTTON}>
                    <ArrowLeft size={16} aria-hidden="true" />
                    Back to UTORid sign-in
                  </button>
                )}

                <button type="button" onClick={handleGuestLogin} disabled={busy} className={SECONDARY_BUTTON}>
                  {guestSubmitting ? (
                    <Loader2 size={16} className="animate-spin" aria-hidden="true" />
                  ) : (
                    <Rocket size={16} aria-hidden="true" />
                  )}
                  {guestSubmitting ? 'Starting demo…' : 'Continue as guest'}
                </button>

                {view === 'signin' && (
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

                {view === 'bootstrap' && (
                  <button type="button" onClick={() => setForceSignIn(true)} className={SECONDARY_BUTTON}>
                    Already have an account? Sign in
                  </button>
                )}
              </form>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
