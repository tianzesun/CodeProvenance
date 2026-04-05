'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  Upload,
  BarChart3,
  FileText,
  Settings,
  Shield,
  ChevronDown,
  Menu,
  X,
  LogOut,
  Bell,
} from 'lucide-react';

const navSections = [
  {
    label: 'Analysis',
    items: [
      { href: '/', label: 'Dashboard', icon: LayoutDashboard },
      { href: '/upload', label: 'New Analysis', icon: Upload },
      { href: '/benchmark', label: 'Multi-Tool Compare', icon: BarChart3 },
    ],
  },
  {
    label: 'Management',
    items: [
      { href: '/reports', label: 'Reports', icon: FileText },
      { href: '/settings', label: 'Settings', icon: Settings },
    ],
  },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <>
      <button
        className="lg:hidden fixed top-4 left-4 z-50 p-2 rounded-lg bg-slate-900 text-white shadow-lg"
        onClick={() => setMobileOpen(!mobileOpen)}
      >
        {mobileOpen ? <X size={18} /> : <Menu size={18} />}
      </button>

      <aside
        className={`fixed inset-y-0 left-0 z-40 w-64 bg-slate-950 text-white flex flex-col transition-transform duration-300 lg:translate-x-0 ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Brand */}
        <div className="px-5 py-5 border-b border-white/[0.06]">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
              <Shield size={16} className="text-white" />
            </div>
            <div>
              <div className="font-bold text-sm tracking-tight">IntegrityDesk</div>
              <div className="text-[10px] text-white/30 uppercase tracking-[0.15em] font-medium">Enterprise</div>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-4 px-3 space-y-6 overflow-y-auto">
          {navSections.map((section) => (
            <div key={section.label}>
              <div className="px-3 mb-2 text-[10px] font-bold text-white/25 uppercase tracking-[0.15em]">
                {section.label}
              </div>
              <div className="space-y-0.5">
                {section.items.map((item) => {
                  const active = pathname === item.href;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={() => setMobileOpen(false)}
                      className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 ${
                        active
                          ? 'bg-white/[0.08] text-white shadow-sm'
                          : 'text-white/50 hover:bg-white/[0.04] hover:text-white/80'
                      }`}
                    >
                      <item.icon size={17} className={`shrink-0 transition-colors ${active ? 'text-blue-400' : 'text-white/40'}`} />
                      {item.label}
                      {active && <div className="ml-auto w-1 h-1 rounded-full bg-blue-400" />}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        {/* User */}
        <div className="p-3 border-t border-white/[0.06]">
          <div className="flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-white/[0.04] transition-colors cursor-pointer group">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center text-[11px] font-bold shadow-sm">
              P
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium truncate">Professor</div>
              <div className="text-[11px] text-white/30">Faculty Account</div>
            </div>
            <LogOut size={14} className="text-white/20 group-hover:text-white/50 transition-colors" />
          </div>
        </div>
      </aside>

      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-30 lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}
    </>
  );
}
