// @ts-nocheck
'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  BarChart3,
  BookOpen,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  FileText,
  LayoutDashboard,
  LogOut,
  Menu,
  MoonStar,
  SearchCheck,
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
  const [collapsed, setCollapsed] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const { theme, toggleTheme } = useTheme();
  const { user, logout } = useAuth();

  const navItems = [
    {
      href: '/',
      label: 'Dashboard',
      icon: LayoutDashboard,
      activeOn: ['/'],
    },
    {
      href: '/assignments',
      label: 'Assignments',
      icon: Upload,
      activeOn: ['/assignments'],
    },
    {
      href: '/cases',
      label: 'Cases',
      icon: SearchCheck,
      activeOn: ['/cases', '/results'],
    },
    {
      href: '/reports',
      label: 'Reports',
      icon: FileText,
      activeOn: ['/reports'],
    },
    {
      href: '/analytics',
      label: 'Analytics',
      icon: BarChart3,
      activeOn: ['/analytics'],
    },
    {
      href: '/settings',
      label: 'Settings',
      icon: Settings,
      activeOn: ['/settings'],
    },
    ...(user?.role === 'admin'
      ? [
        {
          href: '/benchmark',
          label: 'Benchmark',
          icon: ClipboardList,
        },
        {
          href: '/datasets',
          label: 'Datasets',
          icon: ClipboardList,
        },
        {
          href: '/admin',
          label: 'Users',
          icon: Shield,
        },
      ]
      : []),
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
        className={`fixed inset-y-0 left-0 z-40 flex flex-col border-r border-[color:var(--border)] bg-[var(--surface-strong)] backdrop-blur-2xl shadow-2xl transition-all duration-300 ease-out lg:translate-x-0 ${collapsed ? 'w-20' : 'w-72'
          } ${mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}`}
      >
        <div className={`theme-section-line border-b border-[color:var(--border)] transition-all duration-300 ${collapsed ? 'px-2 py-6' : 'px-6 py-8'}`}>
          <div className="flex items-start justify-between gap-4">
            <div className={`flex items-center ${collapsed ? 'justify-center' : 'gap-4'}`}>
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-600 text-white shadow-lg">
                <Shield size={20} />
              </div>
              {!collapsed && (
                <div>
                  <div className="font-display text-lg font-semibold text-[var(--text-primary)]">IntegrityDesk</div>
                  <div className="text-[10px] uppercase tracking-[0.2em] text-[var(--text-muted)]">Assignment Review</div>
                </div>
              )}
            </div>

            <button
              onClick={() => setCollapsed(!collapsed)}
              className="theme-button-secondary inline-flex h-10 w-10 items-center justify-center rounded-2xl transition"
              aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              {collapsed ? <ChevronRight size={17} /> : <ChevronLeft size={17} />}
            </button>
          </div>

        </div>

        <nav className={`scrollbar-thin flex-1 overflow-y-auto py-8 transition-all duration-300 ${collapsed ? 'px-2' : 'px-4'}`}>
          <div className={`space-y-2 ${collapsed ? 'flex flex-col items-center' : ''}`}>
            {navItems.map((item) => {
              const active = item.activeOn?.some((path) => path === pathname || (path !== '/' && pathname?.startsWith(path)));

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileOpen(false)}
                  className={`group flex items-center gap-3 rounded-2xl border px-3 py-3 transition ${active
                    ? 'border-blue-600/20 bg-blue-600/[0.08] text-[var(--text-primary)]'
                    : 'border-transparent text-[var(--text-secondary)] hover:border-[color:var(--border)] hover:bg-[var(--surface-muted)]'
                    }`}
                >
                  <span
                    className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border ${active
                      ? 'border-blue-600/20 bg-blue-600/10 text-blue-600'
                      : 'border-[color:var(--border)] bg-[var(--surface)] text-[var(--text-muted)]'
                      }`}
                  >
                    <item.icon size={17} />
                  </span>

                  {!collapsed && (
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium">{item.label}</span>
                    </span>
                  )}
                </Link>
              );
            })}
          </div>
        </nav>

        <div className={`border-t border-[color:var(--border)] transition-all duration-300 ${collapsed ? 'p-3' : 'p-6'}`}>
          <div className="rounded-2xl border border-[color:var(--border)] bg-[var(--surface-muted)] px-4 py-4 shadow-sm">
            <div className={`flex items-center ${collapsed ? 'justify-center' : 'gap-4'}`}>
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-600 text-sm font-semibold text-white shadow-md">
                {user?.full_name?.charAt(0)?.toUpperCase() || 'U'}
              </div>
              {!collapsed && (
                <>
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
                </>
              )}
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
