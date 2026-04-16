'use client';

import { ReactNode, useEffect } from 'react';
import { AlertTriangle, Loader2, ShieldAlert } from 'lucide-react';
import { usePathname, useRouter } from 'next/navigation';

import { AuthRole, useAuth } from '@/components/AuthProvider';

interface AdminGuardProps {
  children: ReactNode;
  requiredRole?: AuthRole;
}

function GuardShell() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-white">
      <div className="flex min-h-screen">
        <aside className="hidden w-72 border-r border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950 lg:block">
          <div className="p-6">
            <div className="h-8 w-32 animate-pulse rounded-xl bg-slate-200 dark:bg-slate-800" />
            <div className="mt-8 space-y-3">
              {Array.from({ length: 6 }).map((_, index) => (
                <div
                  key={index}
                  className="h-11 animate-pulse rounded-2xl bg-slate-200 dark:bg-slate-800"
                />
              ))}
            </div>
          </div>
        </aside>

        <div className="flex min-h-screen flex-1 flex-col">
          <header className="border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950">
            <div className="flex h-16 items-center justify-between px-4 lg:px-6">
              <div className="h-6 w-40 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
              <div className="h-10 w-10 animate-pulse rounded-full bg-slate-200 dark:bg-slate-800" />
            </div>
          </header>

          <main className="flex flex-1 items-center justify-center px-6 py-10">
            <div className="flex max-w-md flex-col items-center text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-3xl bg-slate-200 text-slate-500 dark:bg-slate-800 dark:text-slate-300">
                <Loader2 size={22} className="animate-spin" />
              </div>
              <h2 className="mt-4 text-lg font-semibold">Checking your session</h2>
              <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
                We’re verifying your account and permissions.
              </p>
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}

function AccessDenied() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center px-6 py-12">
      <div className="max-w-md rounded-[28px] border border-amber-200 bg-white p-8 text-center shadow-sm dark:border-amber-500/20 dark:bg-slate-950">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300">
          <ShieldAlert size={22} />
        </div>
        <h2 className="mt-4 text-xl font-semibold text-slate-900 dark:text-white">
          Access denied
        </h2>
        <p className="mt-2 text-sm leading-6 text-slate-500 dark:text-slate-400">
          Your account is signed in, but it does not have permission to view this area.
        </p>
      </div>
    </div>
  );
}

export default function AdminGuard({
  children,
  requiredRole = 'admin',
}: AdminGuardProps) {
  const { user, status, bootstrapped } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!bootstrapped || status === 'loading') return;

    if (!user) {
      const next = pathname ? `?next=${encodeURIComponent(pathname)}` : '';
      router.replace(`/login${next}`);
    }
  }, [bootstrapped, status, user, pathname, router]);

  if (!bootstrapped || status === 'loading') {
    return <GuardShell />;
  }

  if (!user) {
    return <GuardShell />;
  }

  if (requiredRole && user.role !== requiredRole) {
    return <AccessDenied />;
  }

  return <>{children}</>;
}
