'use client';

import { ReactNode, useEffect, useState } from 'react';
import { motion, useScroll, useSpring, useTransform } from 'framer-motion';
import SmoothScroll from './SmoothScroll';
import Sidebar from '@/components/Sidebar';

interface DashboardLayoutProps {
  children: ReactNode;
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  const { scrollY } = useScroll();
  
  const headerOpacity = useTransform(scrollY, [0, 80], [0.7, 0.95]);
  const headerBlur = useTransform(scrollY, [0, 80], [8, 20]);
  const headerShadow = useTransform(scrollY, [0, 80], [0, 1]);
  const headerBorder = useTransform(scrollY, [0, 80], [0, 1]);

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
      
      <main className="relative z-10 min-h-screen lg:ml-72 pt-4 pb-12">
        {children}
      </main>

      <style jsx global>{`
        @keyframes shift {
          0%, 100% { transform: translate(0, 0) scale(1); }
          33% { transform: translate(30px, -30px) scale(1.05); }
          66% { transform: translate(-20px, 20px) scale(0.95); }
        }
      `}</style>
    </div>
    </SmoothScroll>
  );
}