'use client';

import Sidebar from '@/components/Sidebar';

export default function DashboardLayout({ children }) {
  return (
    <div className="theme-shell">
      <Sidebar />
      <main className="relative z-10 min-h-screen lg:ml-72">
        {children}
      </main>
    </div>
  );
}
