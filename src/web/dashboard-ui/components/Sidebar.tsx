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
  const [loggingOut, setLoggingOut] = useState(false);
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
    if (loggingOut) return; // Prevent multiple logout attempts

    setLoggingOut(true);
    try {
      await logout();
      router.replace('/login');
    } catch (error) {
      console.error('Logout failed:', error);
      // Still redirect to login even if logout fails
      router.replace('/login');
    } finally {
      setLoggingOut(false);
    }
  };

  return (
    <>
      <button
        className="theme-card-strong fixed left-4 top-6 z-50 rounded-2xl p-3 text-[var(--text-primary)] shadow-lg backdrop-blur-xl transition-all hover:scale-105 lg:hidden"
        onClick={() => setMobileOpen((open) => !open)}
        aria-label={mobileOpen ? 'Close menu' : 'Open menu'}
      >
        {mobileOpen ? <X size={20} /> : <Menu size={20} />}
      </button>

      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r border-[color:var(--border)] bg-[var(--surface-strong)] backdrop-blur-2xl shadow-2xl transition-all duration-300 ease-out lg:translate-x-0 ${
            mobileOpen ? 'translate-x-0' : '-translate-x-full'
          }`}
      >
        <div className="theme-section-line border-b border-[color:var(--border)] px-6 py-8">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-600 text-white shadow-lg">
                <Shield size={20} />
              </div>
              <div>
                <div className="font-display text-lg font-semibold text-[var(--text-primary)]">IntegrityDesk</div>
                <div className="text-[10px] uppercase tracking-[0.2em] text-[var(--text-muted)]">Assignment Review</div>
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

        <nav className="scrollbar-thin flex-1 space-y-10 overflow-y-auto px-4 py-8">
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

        <div className="border-t border-[color:var(--border)] p-6">
          <div className="rounded-2xl border border-[color:var(--border)] bg-[var(--surface-muted)] px-4 py-4 shadow-sm">
            <div className="flex items-center gap-4">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-600 text-sm font-semibold text-white shadow-md">
                {user?.full_name?.charAt(0)?.toUpperCase() || 'U'}
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-semibold text-[var(--text-primary)]">{user?.full_name || 'Workspace'}</div>
                <div className="text-xs text-[var(--text-muted)]">
                  {user?.role === 'admin' ? 'Administrator' : 'Professor'}{user?.tenant_name ? ` · ${user.tenant_name}` : ''}
                </div>
              </div>
              <button
                type="button"
                onClick={handleLogout}
                disabled={loggingOut}
                className="inline-flex h-8 w-8 items-center justify-center rounded-xl text-[var(--text-muted)] transition hover:bg-[var(--surface)] hover:text-[var(--text-primary)] disabled:opacity-50 disabled:cursor-not-allowed"
                title={loggingOut ? "Logging out..." : "Log out"}
              >
                <LogOut size={14} className={loggingOut ? "animate-spin" : ""} />
              </button>
            </div>
          </div>
        </div>
      </aside>

      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-slate-950/50 backdrop-blur-md lg:hidden animate-in fade-in duration-300"
          onClick={() => setMobileOpen(false)}
        />
      )}
    </>
  );
}
