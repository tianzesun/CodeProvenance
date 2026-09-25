'use client';

import Link from 'next/link';
import { motion, type Transition } from 'framer-motion';
import { AlertCircle, ArrowRight, ChevronLeft, ChevronRight, Loader2, X } from 'lucide-react';

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

interface DataTableProps {
  children: React.ReactNode;
  className?: string;
}

interface PaginationProps {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  label?: string;
}

interface ModalProps {
  open: boolean;
  title: string;
  description?: string;
  onClose: () => void;
  children: React.ReactNode;
  footer?: React.ReactNode;
}

interface FilterChipProps {
  active: boolean;
  label: string;
  count?: number;
  onClick: () => void;
  tone?: 'neutral' | 'warning' | 'negative';
}

export function FilterChip({ active, label, count, onClick, tone = 'neutral' }: FilterChipProps) {
  const activeTone = tone === 'negative'
    ? 'border-red-200 bg-red-50 text-red-700'
    : tone === 'warning'
      ? 'border-amber-200 bg-amber-50 text-amber-700'
      : 'border-slate-900 bg-slate-900 text-white';
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`inline-flex items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-xs font-semibold transition ${active
        ? activeTone
        : 'border-[color:var(--border)] bg-[var(--surface-strong)] text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]'
      }`}
    >
      {label}
      {count !== undefined && (
        <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-bold ${active ? 'bg-white/20' : 'bg-[var(--surface-muted)]'
        }`}
        >
          {count}
        </span>
      )}
    </button>
  );
}


export function DataTable({ children, className = '' }: DataTableProps) {
  return (
    <div className={`theme-card-strong overflow-hidden rounded-[24px] shadow-sm ${className}`}>
      <div className="scrollbar-thin overflow-x-auto">{children}</div>
    </div>
  );
}

export function TableHeader({ children }: { children: React.ReactNode }) {
  return <thead className="theme-table-header">{children}</thead>;
}

export function TableBody({ children }: { children: React.ReactNode }) {
  return <tbody className="divide-y divide-[color:var(--border)]">{children}</tbody>;
}

export function TableRow({ children, className = '', onClick }: { children: React.ReactNode; className?: string; onClick?: () => void }) {
  return (
    <tr
      onClick={onClick}
      className={`theme-table-row ${onClick ? 'cursor-pointer' : ''} ${className}`}
    >
      {children}
    </tr>
  );
}

export function TableCell({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <td className={`px-5 py-4 text-sm text-[var(--text-secondary)] ${className}`}>{children}</td>;
}

export function TableHead({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <th className={`px-5 py-3 text-left ${className}`}>{children}</th>;
}

export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="theme-card-muted flex items-center justify-center gap-2 rounded-[24px] px-5 py-16 text-sm text-[var(--text-muted)]">
      <Loader2 size={16} className="animate-spin" />
      {label}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex items-start gap-3 rounded-[20px] border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300">
      <AlertCircle size={16} className="mt-0.5 shrink-0" />
      <div className="flex-1">
        <span>{message}</span>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="ml-3 font-semibold underline underline-offset-2"
          >
            Retry
          </button>
        )}
      </div>
    </div>
  );
}

export function Pagination({ page, totalPages, onPageChange, label = 'rows' }: PaginationProps) {
  const safePage = Math.min(Math.max(1, page), Math.max(1, totalPages));
  return (
    <div className="flex flex-col gap-3 border-t border-[color:var(--border)] px-5 py-3 sm:flex-row sm:items-center sm:justify-between">
      <span className="text-xs text-[var(--text-muted)]">
        Page {safePage} of {Math.max(1, totalPages)} {label}
      </span>
      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={() => onPageChange(Math.max(1, safePage - 1))}
          disabled={safePage <= 1}
          aria-label="Previous page"
          className="theme-icon-button"
        >
          <ChevronLeft size={15} />
        </button>
        <button
          type="button"
          onClick={() => onPageChange(Math.min(Math.max(1, totalPages), safePage + 1))}
          disabled={safePage >= totalPages}
          aria-label="Next page"
          className="theme-icon-button"
        >
          <ChevronRight size={15} />
        </button>
      </div>
    </div>
  );
}

export function Modal({ open, title, description, onClose, children, footer }: ModalProps) {
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onClick={onClose}
    >
      <div
        className="theme-card-strong w-full max-w-lg rounded-[24px] p-6 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="theme-section-title text-lg">{title}</h2>
            {description && (
              <p className="mt-1 text-sm text-[var(--text-muted)]">{description}</p>
            )}
          </div>
          <button type="button" onClick={onClose} aria-label="Close dialog" className="theme-icon-button">
            <X size={15} />
          </button>
        </div>
        <div className="mt-5">{children}</div>
        {footer && <div className="mt-6 flex justify-end gap-2">{footer}</div>}
      </div>
    </div>
  );
}


export const fadeUp = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.35, ease: 'easeOut' },
} as const;

export function PageShell({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <div className={`theme-page-container space-y-6 ${className}`}>{children}</div>;
}

export function PageHeader({ eyebrow, title, description, action, eyebrowStyle = 'default' }: PageHeaderProps) {
  return (
    <motion.section
      {...fadeUp}
      className="theme-card-strong rounded-[28px] px-6 py-6 lg:px-8"
    >
      <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
        <div className="max-w-3xl">
          {eyebrow && eyebrowStyle === 'badge' ? (
            <div className="inline-flex items-center gap-2 rounded-full border border-blue-600/10 bg-blue-600/[0.06] px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.2em] text-blue-600 dark:border-blue-400/20 dark:bg-blue-400/10 dark:text-blue-400">
              {eyebrow}
            </div>
          ) : eyebrow ? (
            <div className="text-sm font-medium text-[var(--text-muted)]">{eyebrow}</div>
          ) : null}
          <h1 className="mt-2 font-display text-3xl font-semibold tracking-tight text-[var(--text-primary)]">{title}</h1>
          {description && (
            <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">
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
      {...fadeUp}
      className={`theme-card-strong rounded-[24px] shadow-sm ${className}`}
    >
      {children}
    </motion.section>
  );
}

export function CardHeader({ title, description, action }: CardHeaderProps) {
  return (
    <div className="flex flex-col gap-3 border-b border-slate-200 px-5 py-4 sm:flex-row sm:items-end sm:justify-between dark:border-slate-800">
      <div>
        <h2 className="theme-section-title text-lg">{title}</h2>
        {description && (
          <p className="mt-1 text-sm text-[var(--text-muted)]">{description}</p>
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
    ? 'theme-button-primary px-5 py-2.5 text-sm font-semibold transition'
    : 'theme-button-secondary px-5 py-2.5 text-sm font-semibold transition';

  return (
    <Link
      href={href}
      className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition ${className}`}
    >
      {Icon && <Icon size={16} />}
      {children}
    </Link>
  );
}

export function ActionButton({ children, variant = 'primary', icon: Icon, onClick }: { children: React.ReactNode; variant?: string; icon?: React.ComponentType<{ size: number }>; onClick?: () => void }) {
  const className = variant === 'primary'
    ? 'theme-button-primary px-5 py-2.5 text-sm font-semibold transition'
    : 'theme-button-secondary px-5 py-2.5 text-sm font-semibold transition';

  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition ${className}`}
    >
      {Icon && <Icon size={16} />}
      {children}
    </button>
  );
}

export function RiskBadge({ value, label }: RiskBadgeProps) {
  const score = Number(value) || 0;
  const tone = score >= 90
    ? 'theme-badge-negative'
    : score >= 70
      ? 'theme-badge-warning'
      : 'theme-badge-positive';

  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${tone}`}>
      {label || `${score}%`}
    </span>
  );
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const normalized = String(status || '').toLowerCase();
  const tone = normalized.includes('review')
    ? 'theme-badge-positive'
    : normalized.includes('mark')
      ? 'theme-badge-neutral'
      : normalized.includes('new')
        ? 'theme-badge-negative'
        : 'theme-badge-neutral';

  return <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${tone}`}>{status}</span>;
}

export function EmptyState({ title, description, href, action }: EmptyStateProps) {
  return (
    <div className="theme-card-muted rounded-[20px] px-5 py-10 text-center">
      <div className="theme-section-title text-base">{title}</div>
      <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[var(--text-muted)]">{description}</p>
      {href && (
        <Link href={href} className="theme-link mt-5 inline-flex items-center gap-2 text-sm font-semibold">
          {action || 'Open'}
          <ArrowRight size={15} />
        </Link>
      )}
    </div>
  );
}
