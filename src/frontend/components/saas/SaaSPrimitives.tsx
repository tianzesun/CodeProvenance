'use client';

import Link from 'next/link';
import { motion } from 'framer-motion';
import { ArrowRight } from 'lucide-react';

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: React.ReactNode;
  eyebrowStyle?: 'default' | 'badge';
}

interface CardProps {
  children: React.ReactNode;
  className?: string;
}

interface CardHeaderProps {
  title: string;
  description?: string;
  action?: React.ReactNode;
}

interface StatCardProps {
  label: string;
  value: string;
  detail?: string;
  icon?: React.ElementType;
  tone?: 'slate' | 'blue' | 'red' | 'green' | 'amber';
}

interface ButtonLinkProps {
  href: string;
  children: React.ReactNode;
  variant?: 'primary' | 'secondary';
  icon?: React.ElementType;
}

interface ActionButtonProps {
  children: React.ReactNode;
  variant?: 'primary' | 'secondary';
  icon?: React.ElementType;
  onClick?: () => void;
}

interface RiskBadgeProps {
  value: number | string;
  label?: string;
}

interface StatusBadgeProps {
  status: string;
}

interface EmptyStateProps {
  title: string;
  description: string;
  href?: string;
  action?: string;
}

export const fadeUp = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.35, ease: 'easeOut' },
};

export function PageShell({ children }: { children: React.ReactNode }) {
  return <div className="mx-auto max-w-7xl space-y-6 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">{children}</div>;
}

export function PageHeader({ eyebrow, title, description, action, eyebrowStyle = 'default' }: PageHeaderProps) {
  return (
    <motion.section
      {...(fadeUp as any)}
      className="rounded-xl border border-slate-200 bg-white px-5 py-5 shadow-sm dark:border-slate-800 dark:bg-slate-950"
    >
      <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
        <div className="max-w-3xl">
          {eyebrow && eyebrowStyle === 'badge' ? (
            <div className="inline-flex items-center gap-2 rounded-full border border-blue-600/10 bg-blue-600/[0.06] px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.2em] text-blue-600 dark:border-blue-400/20 dark:bg-blue-400/10 dark:text-blue-400">
              {eyebrow}
            </div>
          ) : eyebrow ? (
            <div className="text-sm font-medium text-slate-500 dark:text-slate-400">{eyebrow}</div>
          ) : null}
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950 dark:text-white">{title}</h1>
          {description && (
            <p className="mt-3 text-sm leading-6 text-slate-600 dark:text-slate-300">
              {description}
            </p>
          )}
        </div>
        {action}
      </div>
    </motion.section>
  );
}

export function Card({ children, className = '' }: CardProps) {
  return (
    <motion.section
      {...(fadeUp as any)}
      className={`rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950 ${className}`}
    >
      {children}
    </motion.section>
  );
}

export function CardHeader({ title, description, action }: CardHeaderProps) {
  return (
    <div className="flex flex-col gap-3 border-b border-slate-200 px-5 py-4 sm:flex-row sm:items-end sm:justify-between dark:border-slate-800">
      <div>
        <h2 className="text-lg font-semibold text-slate-950 dark:text-white">{title}</h2>
        {description && (
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{description}</p>
        )}
      </div>
      {action}
    </div>
  );
}

export function StatCard({ label, value, detail, icon: Icon, tone = 'slate' }: StatCardProps) {
  const tones = {
    blue: 'bg-blue-50 text-blue-700 dark:bg-blue-950/30 dark:text-blue-400',
    red: 'bg-red-50 text-red-700 dark:bg-red-950/30 dark:text-red-400',
    green: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-400',
    amber: 'bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-300',
    slate: 'bg-slate-50 text-slate-700 dark:bg-slate-900/50 dark:text-slate-400',
  };

  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-sm font-medium text-slate-500 dark:text-slate-400">{label}</div>
          <div className="mt-2 text-3xl font-semibold tracking-tight text-slate-950 dark:text-white">
            {value}
          </div>
          {detail && (
            <div className="mt-2 text-sm text-slate-500 dark:text-slate-400">{detail}</div>
          )}
        </div>
        {Icon && (
          <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${tones[tone]}`}>
            <Icon size={18} />
          </div>
        )}
      </div>
    </Card>
  );
}

export function ButtonLink({ href, children, variant = 'primary', icon: Icon }: { href: string; children: React.ReactNode; variant?: string; icon?: React.ComponentType<{ size: number }> }) {
  const className = variant === 'primary'
    ? 'bg-blue-600 text-white hover:bg-blue-700'
    : 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-50';

  return (
    <Link
      href={href}
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold transition ${className}`}
    >
      {Icon && <Icon size={16} />}
      {children}
    </Link>
  );
}

export function ActionButton({ children, variant = 'primary', icon: Icon, onClick }: { children: React.ReactNode; variant?: string; icon?: React.ComponentType<{ size: number }>; onClick?: () => void }) {
  const className = variant === 'primary'
    ? 'bg-blue-600 text-white hover:bg-blue-700'
    : 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-50';

  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold transition ${className}`}
    >
      {Icon && <Icon size={16} />}
      {children}
    </button>
  );
}

export function RiskBadge({ value, label }: RiskBadgeProps) {
  const score = Number(value) || 0;
  const tone = score >= 90
    ? 'bg-red-50 text-red-700 ring-red-100'
    : score >= 70
      ? 'bg-amber-50 text-amber-700 ring-amber-100'
      : 'bg-emerald-50 text-emerald-700 ring-emerald-100';

  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${tone}`}>
      {label || `${score}%`}
    </span>
  );
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const normalized = String(status || '').toLowerCase();
  const tone = normalized.includes('review')
    ? 'bg-emerald-50 text-emerald-700 ring-emerald-100'
    : normalized.includes('mark')
      ? 'bg-blue-50 text-blue-700 ring-blue-100'
      : normalized.includes('new')
        ? 'bg-red-50 text-red-700 ring-red-100'
        : 'bg-slate-50 text-slate-700 ring-slate-100';

  return <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${tone}`}>{status}</span>;
}

export function EmptyState({ title, description, href, action }: EmptyStateProps) {
  return (
    <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-5 py-10 text-center">
      <div className="text-base font-semibold text-slate-950">{title}</div>
      <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500">{description}</p>
      {href && (
        <Link href={href} className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-blue-600">
          {action || 'Open'}
          <ArrowRight size={15} />
        </Link>
      )}
    </div>
  );
}
