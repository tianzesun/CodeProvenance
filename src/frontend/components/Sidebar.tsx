'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  AlertTriangle,
  BarChart3,
  BookOpen,
  Bot,
  ChevronLeft,
  ChevronRight,
  Database,
  FileText,
  GitCompare,
  History,
  LayoutDashboard,
  LogOut,
  Menu,
  MoonStar,
  PlusCircle,
  Scale,
  ScrollText,
  Settings,
  Shield,
  ShieldCheck,
  SunMedium,
  X,
  type LucideIcon,
} from 'lucide-react';

/** Roles a nav item can be visible to. Mirrors ``AuthRole`` in AuthProvider. */
export type NavRole = 'admin' | 'professor' | 'guest';

export interface NavItem {
  /** Route to link to. */
  href: string;
  /** Single label used for every role — divergence between roles is avoided. */
  label: string;
  icon: LucideIcon;
  /**
   * Additional path prefixes that should also mark this item active.
   * Needed for nested routes (e.g. /ai-detector/accuracy under /ai-detector).
   */
  activeOn?: string[];
  /** Roles allowed to see and reach this item. */
  roles: NavRole[];
  /**
   * Marks items that are core to the daily loop. Used to decide what stays
   * visible when the rail is collapsed to icons on short viewports.
   */
  primary?: boolean;
}

export interface NavGroup {
  /** Section heading. Hidden entirely when the group has no visible items. */
  title: string;
  items: NavItem[];
}

/**
 * Single source of truth for the sidebar and for route access.
 *
 * Grouping is by workflow stage rather than by owning team, so the rail reads
 * as "what am I doing" instead of "which squad built it":
 *
 *   - Teaching / Academic   — run a check, review its output
 *   - Insights              — understand outcomes over time
 *   - Engine & Validation   — prove the detector behaves
 *   - Administration       — manage the workspace
 *
 * `roles` is an explicit allowlist rather than nested role ternaries, so adding
 * a role (TA, department head) is a one-token change per item instead of
 * restructuring every group.
 */
export const NAV_GROUPS: NavGroup[] = [
  {
    // Dashboard sits outside the groups: it is the universal landing page, not
    // a workflow stage, and it should read as a distinct "home" affordance.
    title: 'Overview',
    items: [
      {
        href: '/',
        label: 'Dashboard',
        icon: LayoutDashboard,
        // "/" is a prefix of every path, so active state is handled explicitly
        // in the render (exact match only) rather than by prefix matching.
        roles: ['professor', 'admin'],
        primary: true,
      },
    ],
  },
  {
    title: 'Teaching',
    items: [
      {
        href: '/upload',
        label: 'Plagiarism Checker',
        icon: PlusCircle,
        // The guest demo session lands here and never leaves the check flow.
        roles: ['professor', 'admin', 'guest'],
        primary: true,
      },
      {
        href: '/history',
        label: 'Check History',
        icon: History,
        roles: ['professor', 'admin'],
        primary: true,
      },
      {
        href: '/ai-detector',
        label: 'AI Code Review',
        icon: Bot,
        // /ai-detector/accuracy is a separate nav item, so it must not light
        // up the parent entry.
        activeOn: ['/ai-detector'],
        roles: ['professor', 'admin', 'guest'],
        primary: true,
      },
      {
        href: '/cases',
        label: 'My Cases',
        icon: Scale,
        roles: ['professor', 'admin'],
        primary: true,
      },
      {
        href: '/courses',
        label: 'Courses & Assignments',
        icon: BookOpen,
        // Professor workspace: course CRUD itself is admin-only and lives in
        // Administration → Users & courses, so admins are kept out of this
        // item entirely (DashboardLayout redirects them to /admin).
        roles: ['professor'],
        primary: true,
      },
    ],
  },
  {
    title: 'Insights',
    items: [
      {
        href: '/analytics',
        label: 'Analytics',
        icon: BarChart3,
        roles: ['admin'],
        primary: true,
      },
      {
        href: '/reports',
        label: 'Reports',
        icon: ScrollText,
        roles: ['admin'],
      },
      {
        href: '/assignments',
        label: 'Assignments',
        icon: FileText,
        roles: ['admin'],
      },
      {
        href: '/error-analysis',
        label: 'Error Analysis',
        icon: AlertTriangle,
        roles: ['admin'],
      },
    ],
  },
  {
    title: 'Engine & Validation',
    items: [
      {
        href: '/benchmark',
        label: 'Benchmark',
        icon: ShieldCheck,
        roles: ['admin'],
      },
      {
        href: '/compare-tools',
        label: 'Compare Tools',
        icon: GitCompare,
        roles: ['admin'],
      },
      {
        href: '/tools/fpr-validation',
        label: 'FPR Validation',
        icon: Scale,
        roles: ['admin'],
      },
      {
        href: '/ai-detector/accuracy',
        label: 'AI Accuracy',
        icon: Bot,
        roles: ['admin'],
      },
      {
        href: '/datasets',
        label: 'Datasets',
        icon: Database,
        roles: ['admin'],
      },
    ],
  },
  {
    title: 'Administration',
    items: [
      {
        href: '/admin',
        label: 'Users',
        icon: Shield,
        roles: ['admin'],
      },
      {
        href: '/settings',
        label: 'Settings',
        icon: Settings,
        // The settings page renders with requiredRole="admin" (tenant and
        // engine configuration), so showing it to professors would only ever
        // bounce them back to the dashboard.
        roles: ['admin'],
      },
    ],
  },
];

/**
 * Flat list of every route a role may reach, longest prefix first.
 *
 * ``DashboardLayout`` uses this to gate navigation instead of maintaining a
 * separate hand-written allowlist that drifts out of sync with the sidebar.
 *
 * A guest demo session is the one role whose routes are not simply "everything
 * in ``NAV_GROUPS``": it drops ``/`` (the dashboard is a workspace summary a
 * demo has no workspace behind) and adds ``/results`` (reached by drilling in
 * from a completed check, never from the rail). Every other adjustment stays
 * expressed through ``roles`` on the nav items themselves.
 */
export function routesForRole(role: NavRole | undefined): string[] {
  if (!role) return [];

  const isGuest = role === 'guest';
  return [
    ...(isGuest ? [] : ['/']),
    ...(isGuest ? ['/results'] : []),
    ...NAV_GROUPS.flatMap((group) =>
      group.items
        .filter((item) => item.roles.includes(role))
        .map((item) => item.href),
    ),
  ].sort((a, b) => b.length - a.length);
}

/** True when ``path`` is reachable by ``role``. */
export function canRoleAccessPath(role: NavRole | undefined, path: string | null): boolean {
  if (!role || !path) return false;
  return routesForRole(role).some(
    (route) => path === route || (route !== '/' && path.startsWith(`${route}/`)),
  );
}


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

  useEffect(() => {
    document.documentElement.setAttribute('data-sidebar-collapsed', String(collapsed));
    document.documentElement.style.setProperty('--sidebar-width', collapsed ? '80px' : '288px');
  }, [collapsed]);

  // Nav is derived from the shared config rather than rebuilt with nested role
  // ternaries, so visibility and route access stay in sync by construction.
  const role = (user?.role ?? undefined) as NavRole | undefined;
  const navGroups = NAV_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((item) => role && item.roles.includes(role)),
  })).filter((group) => group.items.length > 0);

  // Sidebar footer descriptor: a guest session is labelled for what it is so
  // nobody mistakes a demo run for a saved workspace.
  const roleLabel =
    user?.role === 'admin'
      ? 'Administrator'
      : user?.role === 'guest'
        ? 'Guest demo · not saved'
        : 'Professor';

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

        {/* min-h-0 lets the flex child actually shrink below its content height
            so overflow-y-auto engages; without it a tall nav list pushes the
            whole aside past the viewport instead of scrolling internally.
            overscroll-behavior keeps the wheel from chaining to the page. */}
        <nav
          className={`scrollbar-thin min-h-0 flex-1 overflow-y-auto overscroll-contain py-8 transition-all duration-300 ${collapsed ? 'px-2' : 'px-4'}`}
          tabIndex={0}
          aria-label="Main navigation"
        >
          <div className={`space-y-6 ${collapsed ? 'flex flex-col items-center' : ''}`}>
            {navGroups.map((group) => (
              <div key={group.title} className="space-y-2">
                {!collapsed && (
                  <div className="px-3">
                    <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-[var(--text-muted)]">{group.title}</span>
                  </div>
                )}
                {group.items.map((item) => {
                  // "/" is a prefix of every path, so the Dashboard entry
                  // matches exactly while other entries match on segment prefix.
                  const active = item.activeOn
                    ? item.activeOn.some(
                        (path) =>
                          path === pathname ||
                          (path !== '/' && pathname?.startsWith(`${path}/`)),
                      )
                    : item.href === pathname ||
                      pathname?.startsWith(`${item.href}/`);

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
            ))}
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
                      {roleLabel}{user?.tenant_name ? ` · ${user.tenant_name}` : ''}
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
