// @ts-nocheck
'use client';

import Link from 'next/link';
import { motion } from 'framer-motion';
import { ArrowRight } from 'lucide-react';

export const fadeUp = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.35, ease: 'easeOut' },
};

export function PageShell({ children }) {
  return <div className="mx-auto max-w-7xl space-y-6 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">{children}</div>;
}

export function PageHeader({ eyebrow, title, description, action }) {
  return (
    <motion.section
      {...fadeUp}
      className="rounded-xl border border-slate-200 bg-white px-5 py-5 shadow-sm"
    >
      <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
        <div className="max-w-3xl">
          {eyebrow && <div className="text-sm font-medium text-slate-500">{eyebrow}</div>}
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">{title}</h1>
          {description && <p className="mt-3 text-sm leading-6 text-slate-600">{description}</p>}
        </div>
        {action}
      </div>
    </motion.section>
  );
}

export function Card({ children, className = '' }) {
  return (
    <motion.section
      {...fadeUp}
      className={`rounded-xl border border-slate-200 bg-white shadow-sm ${className}`}
    >
      {children}
    </motion.section>
  );
}

export function CardHeader({ title, description, action }) {
  return (
    <div className="flex flex-col gap-3 border-b border-slate-200 px-5 py-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
        {description && <p className="mt-1 text-sm text-slate-500">{description}</p>}
      </div>
      {action}
    </div>
  );
}

export function StatCard({ label, value, detail, icon: Icon, tone = 'slate' }) {
  const tones = {
    blue: 'bg-blue-50 text-blue-700',
    red: 'bg-red-50 text-red-700',
    green: 'bg-emerald-50 text-emerald-700',
    slate: 'bg-slate-50 text-slate-700',
  };

  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-sm font-medium text-slate-500">{label}</div>
          <div className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">{value}</div>
          {detail && <div className="mt-2 text-sm text-slate-500">{detail}</div>}
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

export function ButtonLink({ href, children, variant = 'primary', icon: Icon }) {
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

export function ActionButton({ children, variant = 'primary', icon: Icon, onClick }) {
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

export function RiskBadge({ value, label }) {
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

export function StatusBadge({ status }) {
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

export function EmptyState({ title, description, href, action }) {
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
