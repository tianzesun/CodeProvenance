'use client';

import { ReactNode, useEffect, useRef } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import SmoothScroll from './SmoothScroll';
import { useAuth } from '@/components/AuthProvider';
import { useTheme } from '@/components/ThemeProvider';
import Sidebar from '@/components/Sidebar';
import SkeletonLoader from '@/components/SkeletonLoader';
import { SunMedium, MoonStar } from 'lucide-react';

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
          router.replace('/');
        }
      }

      // Reset redirect key when authentication is successful
      lastRedirectRef.current = null;
    }, 100); // 100ms delay

    return () => clearTimeout(timer);
  }, [bootstrapped, loading, pathname, requiredRole, requireAuth, router, user]);

  // Show loading only if auth is required
  if (requireAuth && (loading || !bootstrapped || !user || (requiredRole === 'admin' && user.role !== 'admin'))) {
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
