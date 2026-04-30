'use client';

import { ReactNode, useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import SmoothScroll from './SmoothScroll';
import { useAuth } from '@/components/AuthProvider';
import Sidebar from '@/components/Sidebar';
import { SunMedium, MoonStar } from 'lucide-react';

interface DashboardLayoutProps {
  children: ReactNode;
  requiredRole?: 'admin' | 'professor';
}

export default function DashboardLayout({ children, requiredRole }: DashboardLayoutProps) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, loading, bootstrapped } = useAuth();

  useEffect(() => {
    if (loading) {
      return;
    }

    if (!bootstrapped || !user) {
      router.replace(`/login?next=${encodeURIComponent(pathname || '/')}`);
      return;
    }

    if (requiredRole === 'admin' && user.role !== 'admin') {
      router.replace('/');
    }
  }, [bootstrapped, loading, pathname, requiredRole, router, user]);

  if (loading || !bootstrapped || !user || (requiredRole === 'admin' && user.role !== 'admin')) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <div className="rounded-3xl border border-slate-200 bg-white px-6 py-5 text-sm text-slate-500 shadow-sm">
          Loading workspace...
        </div>
      </div>
    );
  }

   return (
     <SmoothScroll>
       <div className="min-h-screen bg-slate-50 relative overflow-hidden theme-shell">
       {/* Background Effects */}
       <div className="fixed inset-0 pointer-events-none overflow-hidden">
         <div className="absolute top-0 left-1/4 w-[800px] h-[800px] bg-blue-200/20 rounded-full blur-3xl animate-[shift_25s_ease-in-out_infinite]" />
         <div className="absolute bottom-0 right-1/4 w-[600px] h-[600px] bg-brand-100/30 rounded-full blur-3xl animate-[shift_25s_ease-in-out_infinite_reverse]" />
         <div className="absolute inset-0 opacity-[0.03] bg-[url('/grain.svg')] repeat" />
       </div>

       <Sidebar />
       
       <main className="relative z-10 min-h-screen lg:ml-72 pt-6 pb-16 lg:pt-8 lg:pb-20 flex flex-col">
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
       onClick={() => {
         const event = new CustomEvent('toggleTheme');
         window.dispatchEvent(event);
       }}
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
