// @ts-nocheck
'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  BarChart3,
  LayoutDashboard,
  LogOut,
  Menu,
  MoonStar,
  Settings,
  Shield,
  SunMedium,
  Upload,
  X,
} from 'lucide-react';

import { useAuth } from '@/components/AuthProvider';
import { useTheme } from '@/components/ThemeProvider';

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);
  const { theme, toggleTheme } = useTheme();
  const { user, logout } = useAuth();

  const navSections = [
    {
      label: 'Start',
      items: [
        {
          href: '/',
          label: 'Home',
          description: 'Start a check or open results',
          icon: LayoutDashboard,
        },
        {
          href: '/upload',
          label: 'Check Assignment',
          description: 'Upload files or a ZIP archive',
          icon: Upload,
        },
      ],
    },
    {
      label: 'Tools',
      items: [
        {
          href: '/benchmark',
          label: 'Benchmark Lab',
          description: 'Advanced multi-engine comparison',
          icon: BarChart3,
        },
        ...(user?.role === 'admin'
          ? [
              {
                href: '/settings',
                label: 'Preferences',
                description: 'System-wide model and workflow settings',
                icon: Settings,
              },
              {
                href: '/admin',
                label: 'User Admin',
                description: 'Manage professor and admin accounts',
                icon: Shield,
              },
            ]
          : []),
      ],
    },
  ];

  const handleLogout = async () => {
    await logout();
    router.replace('/login');
  };

  return (
    <>
      <button
        className="theme-card-strong fixed left-4 top-4 z-50 rounded-2xl p-2.5 text-[var(--text-primary)] lg:hidden"
        onClick={() => setMobileOpen((open) => !open)}
      >
        {mobileOpen ? <X size={18} /> : <Menu size={18} />}
      </button>

      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r border-[color:var(--border)] bg-[var(--surface-strong)] backdrop-blur-2xl transition-transform duration-300 lg:translate-x-0 ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="theme-section-line border-b border-[color:var(--border)] px-6 py-6">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-600 text-white shadow-sm">
                <Shield size={18} />
              </div>
              <div>
                <div className="font-display text-base font-semibold text-[var(--text-primary)]">IntegrityDesk</div>
                <div className="text-[11px] uppercase tracking-[0.2em] text-[var(--text-muted)]">Assignment Review</div>
              </div>
            </div>

            <button
              onClick={toggleTheme}
              className="theme-button-secondary inline-flex h-10 w-10 items-center justify-center rounded-2xl transition"
              aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
              title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
            >
              {theme === 'dark' ? <SunMedium size={17} /> : <MoonStar size={17} />}
            </button>
          </div>

        </div>

        <nav className="scrollbar-thin flex-1 space-y-8 overflow-y-auto px-4 py-6">
          {navSections.map((section) => (
            <div key={section.label}>
              <div className="mb-3 px-3 text-[10px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                {section.label}
              </div>
              <div className="space-y-2">
                {section.items.map((item) => {
                  const active = pathname === item.href;

                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={() => setMobileOpen(false)}
                      className={`group flex items-center gap-3 rounded-2xl border px-3 py-3 transition ${
                        active
                          ? 'border-blue-600/20 bg-blue-600/[0.08] text-[var(--text-primary)]'
                          : 'border-transparent text-[var(--text-secondary)] hover:border-[color:var(--border)] hover:bg-[var(--surface-muted)]'
                      }`}
                    >
                      <span
                        className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border ${
                          active
                            ? 'border-blue-600/20 bg-blue-600/10 text-blue-600'
                            : 'border-[color:var(--border)] bg-[var(--surface)] text-[var(--text-muted)]'
                        }`}
                      >
                        <item.icon size={17} />
                      </span>

                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium">{item.label}</span>
                        <span className="block truncate text-[11px] text-[var(--text-muted)]">{item.description}</span>
                      </span>
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        <div className="border-t border-[color:var(--border)] p-4">
          <div className="rounded-2xl border border-[color:var(--border)] bg-[var(--surface-muted)] px-3 py-3">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-600 text-[11px] font-semibold text-white">
                P
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium text-[var(--text-primary)]">{user?.full_name || 'Workspace'}</div>
                <div className="text-[11px] text-[var(--text-muted)]">
                  {user?.role === 'admin' ? 'Administrator' : 'Professor'}{user?.tenant_name ? ` · ${user.tenant_name}` : ''}
                </div>
              </div>
              <button
                type="button"
                onClick={handleLogout}
                className="inline-flex h-8 w-8 items-center justify-center rounded-xl text-[var(--text-muted)] transition hover:bg-[var(--surface)] hover:text-[var(--text-primary)]"
                title="Log out"
              >
                <LogOut size={14} />
              </button>
            </div>
          </div>
        </div>
      </aside>

      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-slate-950/35 backdrop-blur-sm lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}
    </>
  );
}
