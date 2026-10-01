'use client';

import { ReactNode, useEffect, useRef } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import SmoothScroll from './SmoothScroll';
import { useAuth } from '@/components/AuthProvider';
import { useTheme } from '@/components/ThemeProvider';
import Sidebar, { canRoleAccessPath, type NavRole } from '@/components/Sidebar';
import SkeletonLoader from '@/components/SkeletonLoader';
import { Info, SunMedium, MoonStar } from 'lucide-react';

// Routes deliberately closed to admins. Course maintenance lives in
// Administration → Users & courses, so an admin arriving at the Teaching
// "Courses & Assignments" page (bookmark, stale link) is sent to their own
// workspace instead of managing courses from two places.
const ADMIN_EXCLUDED_PATHS = ['/courses'];

/**
 * Persistent reminder that the current session is a demo.
 *
 * Rendered above every page a guest reaches so nobody mistakes an unsaved run
 * for a stored one, with the upgrade path to a real account one click away.
 */
function GuestSessionBanner() {
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-amber-300/70 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-100">
      <span className="flex items-start gap-2">
        <Info size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
        <span>
          <strong className="font-semibold">Guest demo.</strong> You can run a full check, but
          nothing is saved — results and decisions disappear when the session ends.
        </span>
      </span>
      <Link
        href="/login"
        className="inline-flex shrink-0 items-center gap-1.5 rounded-xl border border-amber-400/70 bg-white/70 px-3 py-1.5 text-xs font-semibold transition hover:bg-white dark:border-amber-500/40 dark:bg-transparent dark:hover:bg-amber-500/20"
      >
        Sign in to save results
      </Link>
    </div>
  );
}

interface DashboardLayoutProps {
  children: ReactNode;
  requiredRole?: 'admin' | 'professor';
  requireAuth?: boolean; // New prop to make authentication optional
}

export default function DashboardLayout({ children, requiredRole, requireAuth = true }: DashboardLayoutProps) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, loading, bootstrapped } = useAuth();
  const { toggleTheme } = useTheme();

  // Prevent redirect loops by tracking last redirect
  const lastRedirectRef = useRef<string | null>(null);

  // Routes visible to the professor role. Professors focus on plagiarism
  // checks (single + whole-class), AI-generated code review, and reviewing
  // flagged cases.
  //
  // Access is derived from the shared nav config in Sidebar.tsx so the route
  // gate and the sidebar cannot drift apart. Detail views that are reached by
  // drilling in (rather than from the rail) stay reachable under their owning
  // section.
  const DETAIL_ROUTE_PREFIXES = ['/results', '/dossier'];

  const isProfessorRouteAllowed = (path: string | null): boolean => {
    if (!path) return false;
    if (canRoleAccessPath('professor' as NavRole, path)) return true;
    return DETAIL_ROUTE_PREFIXES.some((prefix) => path.startsWith(`${prefix}/`));
  };

  // Guests are demo sessions: they may run a check and read its results, and
  // nothing else. Derived from the same nav config as the rail, so the visible
  // links and the gate cannot drift apart.
  const isGuestRouteAllowed = (path: string | null): boolean =>
    Boolean(path) && canRoleAccessPath('guest', path);

  const guestBlocked = Boolean(
    user && user.role === 'guest' && !isGuestRouteAllowed(pathname),
  );

  const professorBlocked = Boolean(
    user && user.role !== 'admin' && user.role !== 'guest' && !isProfessorRouteAllowed(pathname),
  );

  const adminBlocked = Boolean(
    user && user.role === 'admin' && ADMIN_EXCLUDED_PATHS.includes(pathname),
  );

  useEffect(() => {
    if (loading) {
      return;
    }

    // If authentication is not required, skip the auth check
    if (!requireAuth) {
      return;
    }

    // Add a small delay to prevent rapid redirect loops
    const timer = setTimeout(() => {
      const redirectKey = `${pathname}-${bootstrapped}-${!!user}-${requiredRole}`;

      if (!bootstrapped || !user) {
        if (lastRedirectRef.current !== redirectKey) {
          lastRedirectRef.current = redirectKey;
          router.replace(`/login?next=${encodeURIComponent(pathname || '/')}`);
        }
        return;
      }

      if (requiredRole === 'admin' && user.role !== 'admin') {
        if (lastRedirectRef.current !== redirectKey) {
          lastRedirectRef.current = redirectKey;
          router.replace(user.role === 'guest' ? '/upload' : '/');
        }
        return;
      }

      // Admins maintain courses in Administration → Users & courses; bounce
      // them off the professor's Teaching page before it flashes content.
      if (user.role === 'admin' && ADMIN_EXCLUDED_PATHS.includes(pathname)) {
        if (lastRedirectRef.current !== redirectKey) {
          lastRedirectRef.current = redirectKey;
          router.replace('/admin');
        }
        return;
      }

      // Guests stay inside the demo: any other route (dashboard, history,
      // courses, admin) goes back to the checker. Checked before the
      // professor rule because a guest's allowed set is a strict subset.
      if (user.role === 'guest' && !isGuestRouteAllowed(pathname)) {
        if (lastRedirectRef.current !== redirectKey) {
          lastRedirectRef.current = redirectKey;
          router.replace('/upload');
        }
        return;
      }

      // Professors are limited to the academic workflow (plagiarism check +
      // AI review + courses/assignments). Redirect them away from Engine/R&D
      // and Manage pages if they navigate there directly.
      if (user.role !== 'admin' && user.role !== 'guest' && !isProfessorRouteAllowed(pathname)) {
        if (lastRedirectRef.current !== redirectKey) {
          lastRedirectRef.current = redirectKey;
          router.replace('/');
        }
      }

      // Reset redirect key when authentication is successful
      lastRedirectRef.current = null;
    }, 100); // 100ms delay

    return () => clearTimeout(timer);
  }, [bootstrapped, loading, pathname, requiredRole, requireAuth, router, user]);

  // Show loading only if auth is required
  if (requireAuth && (loading || !bootstrapped || !user || professorBlocked || adminBlocked || guestBlocked || (requiredRole === 'admin' && user.role !== 'admin'))) {
    return (
      <div className="theme-shell min-h-screen bg-[var(--background)]">
        <SkeletonLoader variant="page" />
      </div>
    );
  }

  return (
    <SmoothScroll>
      <div className="min-h-screen bg-slate-50 relative overflow-hidden theme-shell">
        {/* Skip link for keyboard users */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded-xl focus:bg-blue-600 focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-white"
        >
          Skip to main content
        </a>

        {/* Background Effects */}
        <div className="fixed inset-0 pointer-events-none overflow-hidden" aria-hidden="true">
          <div className="absolute top-0 left-1/4 w-[800px] h-[800px] bg-blue-200/20 rounded-full blur-3xl animate-[shift_25s_ease-in-out_infinite]" />
          <div className="absolute bottom-0 right-1/4 w-[600px] h-[600px] bg-brand-100/30 rounded-full blur-3xl animate-[shift_25s_ease-in-out_infinite_reverse]" />
          <div className="absolute inset-0 opacity-[0.03] bg-[url('/grain.svg')] repeat" />
        </div>

        <Sidebar />

        <main id="main-content" className="dashboard-main relative z-10 min-h-screen pt-6 pb-16 lg:pt-8 lg:pb-20 flex min-w-0 flex-col transition-all duration-300 ease-out">
          <div className="flex-grow">
            {user?.role === 'guest' && <GuestSessionBanner />}
            {children}
          </div>
        </main>

        <style jsx global>{`
         @keyframes shift {
           0%, 100% { transform: translate(0, 0) scale(1); }
           33% { transform: translate(30px, -30px) scale(1.05); }
           66% { transform: translate(-20px, 20px) scale(0.95); }
         }
       `}</style>
        {/* Floating theme toggle button */}
        <button
          onClick={toggleTheme}
          className="fixed bottom-6 right-6 z-50 inline-flex h-12 w-12 items-center justify-center rounded-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-xl hover:scale-105 transition-all"
          aria-label="Toggle theme"
          title="Toggle dark/light mode"
        >
          <SunMedium size={20} className="dark:hidden text-slate-700" />
          <MoonStar size={20} className="hidden dark:block text-slate-200" />
        </button>

      </div>
    </SmoothScroll>
  );
}
