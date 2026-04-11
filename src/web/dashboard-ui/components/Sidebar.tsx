// @ts-nocheck
'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  BarChart3,
  Bot,
  BrainCircuit,
  ClipboardCheck,
  FileSearch,
  FlaskConical,
  LayoutDashboard,
  LogOut,
  Menu,
  MoonStar,
  ShieldAlert,
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

  const capabilityPillars = [
    {
      label: 'Plagiarism Check',
      detail: 'Classmates, past work, and source overlap',
      icon: FileSearch,
      tone: 'text-blue-600 bg-blue-50 border-blue-100',
    },
    {
      label: 'AI Detection',
      detail: 'Writing-pattern and code-origin signals',
      icon: Bot,
      tone: 'text-emerald-600 bg-emerald-50 border-emerald-100',
    },
    {
      label: 'Evidence Review',
      detail: 'Matched passages, score context, and notes',
      icon: ClipboardCheck,
      tone: 'text-amber-600 bg-amber-50 border-amber-100',
    },
    {
      label: 'Benchmark Lab',
      detail: 'Validate detectors against real tool runs',
      icon: FlaskConical,
      tone: 'text-violet-600 bg-violet-50 border-violet-100',
    },
  ];

  const navSections = [
    {
      label: 'Review',
      items: [
        {
          href: '/',
          label: 'Case Dashboard',
          description: 'Open flagged work and review outcomes',
          icon: LayoutDashboard,
          badge: 'Workflow',
        },
        {
          href: '/upload',
          label: 'Plagiarism & AI Check',
          description: 'Run assignment review on real submissions',
          icon: Upload,
          badge: 'Core',
        },
      ],
    },
    {
      label: 'Validation',
      items: [
        {
          href: '/benchmark',
          label: 'Benchmark Lab',
          description: 'Compare real detectors on benchmark datasets',
          icon: BarChart3,
          badge: 'Research',
        },
        ...(user?.role === 'admin'
          ? [
            {
              href: '/settings',
              label: 'Preferences',
              description: 'Tune review rules and system behavior',
              icon: Settings,
              badge: 'Admin',
            },
            {
              href: '/admin',
              label: 'User Admin',
              description: 'Manage professor and admin accounts',
              icon: Shield,
              badge: 'Admin',
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

        <nav className="scrollbar-thin flex-1 space-y-8 overflow-y-auto px-4 py-8">
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
                        <span className="flex items-center gap-2">
                          <span className="block truncate text-sm font-medium">{item.label}</span>
                          {item.badge && (
                            <span className={`rounded-full px-2 py-0.5 text-[9px] font-semibold uppercase tracking-[0.16em] ${
                              active
                                ? 'bg-blue-600/10 text-blue-700'
                                : 'bg-[var(--surface)] text-[var(--text-muted)]'
                            }`}>
                              {item.badge}
                            </span>
                          )}
                        </span>
                        <span className="block truncate text-[11px] text-[var(--text-muted)]">{item.description}</span>
                      </span>
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}

          <div className="rounded-[28px] border border-[color:var(--border)] bg-[var(--surface)] p-4 shadow-sm">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                  Integrity Stack
                </div>
                <div className="mt-2 text-sm font-semibold text-[var(--text-primary)]">
                  More than plagiarism and AI flags
                </div>
                <div className="mt-1 text-[11px] leading-5 text-[var(--text-muted)]">
                  A strong professor workflow needs review, evidence, and validation in one place.
                </div>
              </div>
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-600 to-violet-600 text-white shadow-md">
                <BrainCircuit size={17} />
              </div>
            </div>

            <div className="mt-4 space-y-2.5">
              {capabilityPillars.map((pillar) => (
                <div
                  key={pillar.label}
                  className="flex items-start gap-3 rounded-2xl border border-[color:var(--border)] bg-[var(--surface-muted)] px-3 py-3"
                >
                  <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl border ${pillar.tone}`}>
                    <pillar.icon size={16} />
                  </div>
                  <div className="min-w-0">
                    <div className="text-xs font-semibold text-[var(--text-primary)]">{pillar.label}</div>
                    <div className="mt-1 text-[11px] leading-5 text-[var(--text-muted)]">{pillar.detail}</div>
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-4 flex items-start gap-3 rounded-2xl border border-blue-600/10 bg-blue-600/[0.06] px-3 py-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-2xl bg-blue-600/10 text-blue-600">
                <ShieldAlert size={15} />
              </div>
              <div>
                <div className="text-[11px] font-semibold text-[var(--text-primary)]">Decision support, not black-box scoring</div>
                <div className="mt-1 text-[11px] leading-5 text-[var(--text-muted)]">
                  Professors need evidence they can review, explain, and act on fairly.
                </div>
              </div>
            </div>
          </div>
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
