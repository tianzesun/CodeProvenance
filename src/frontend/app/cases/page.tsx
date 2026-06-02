'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import DashboardLayout from '@/components/DashboardLayout';
import { Card, CardHeader, PageHeader, RiskBadge, StatusBadge } from '@/components/saas/SaaSPrimitives';
import { assignmentCases } from '@/lib/mockIntegrityData';
import {
  ArrowUpRight,
  ChevronDown,
  ClipboardList,
  Filter,
  Search,
  X,
} from 'lucide-react';

// ─── Types ─────────────────────────────────────────────────────────────────────

type CaseStatus = 'pending' | 'in-review' | 'cleared' | 'escalated' | string;
type RiskLevel = 'high' | 'medium' | 'low' | string;

interface CaseItem {
  id: string;
  status: CaseStatus;
  course: string;
  assignment: string;
  students: string;
  reason: string;
  risk: RiskLevel;
  reviewer: string;
}

type StatusFilter = 'all' | CaseStatus;
type RiskFilter = 'all' | RiskLevel;

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Normalise raw data — mock data may not be perfectly typed */
function toCaseItem(raw: unknown): CaseItem {
  const r = raw as Record<string, unknown>;
  return {
    id: String(r.id ?? ''),
    status: String(r.status ?? 'pending'),
    course: String(r.course ?? ''),
    assignment: String(r.assignment ?? ''),
    students: String(r.students ?? ''),
    reason: String(r.reason ?? ''),
    risk: String(r.risk ?? 'low'),
    reviewer: String(r.reviewer ?? '—'),
  };
}

const RISK_ORDER: Record<string, number> = { high: 0, medium: 1, low: 2 };

function riskSort(a: CaseItem, b: CaseItem): number {
  return (RISK_ORDER[a.risk] ?? 3) - (RISK_ORDER[b.risk] ?? 3);
}

// ─── Filter pill ───────────────────────────────────────────────────────────────

function FilterSelect({
  value,
  onChange,
  options,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { label: string; value: string }[];
  placeholder: string;
}) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-10 appearance-none rounded-xl border border-slate-200 bg-white pl-3 pr-8 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white"
      >
        <option value="all">{placeholder}</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
      <ChevronDown
        size={13}
        className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400"
      />
    </div>
  );
}

// ─── Risk badge fallback (in case SaaSPrimitives doesn't cover all values) ────

function RiskPill({ value }: { value: string }) {
  const styles: Record<string, string> = {
    high: 'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400',
    medium: 'bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400',
    low: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-400',
  };
  const dots: Record<string, string> = {
    high: 'bg-red-500', medium: 'bg-amber-500', low: 'bg-emerald-500',
  };
  const key = value.toLowerCase();
  const cls = styles[key] ?? 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400';
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${cls}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${dots[key] ?? 'bg-slate-400'}`} />
      {value.charAt(0).toUpperCase() + value.slice(1)}
    </span>
  );
}

// ─── Mobile case card ──────────────────────────────────────────────────────────

function CaseMobileCard({ item }: { item: CaseItem }) {
  return (
    <article className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-950">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-slate-900 dark:text-white">
            {item.students}
          </div>
          <div className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{item.reason}</div>
        </div>
        <RiskPill value={item.risk} />
      </div>

      <div className="mt-3 grid grid-cols-2 gap-3 rounded-2xl bg-slate-50 p-3 dark:bg-slate-900">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
            Course
          </div>
          <div className="mt-1 text-sm font-medium text-slate-800 dark:text-slate-200">
            {item.course}
          </div>
          <div className="text-xs text-slate-500 dark:text-slate-400">{item.assignment}</div>
        </div>
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
            Status
          </div>
          <div className="mt-1">
            <StatusBadge status={item.status} />
          </div>
        </div>
        <div className="col-span-2">
          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
            Reviewer
          </div>
          <div className="mt-1 text-sm text-slate-700 dark:text-slate-300">
            {item.reviewer}
          </div>
        </div>
      </div>

      <Link
        href={`/cases/${item.id}`}
        className="mt-3 flex h-10 w-full items-center justify-center gap-2 rounded-2xl border border-slate-200 text-sm font-semibold text-slate-700 transition hover:bg-slate-100 dark:border-slate-800 dark:text-slate-300 dark:hover:bg-slate-900"
      >
        Open case
        <ArrowUpRight size={14} />
      </Link>
    </article>
  );
}

// ─── Empty state ───────────────────────────────────────────────────────────────

function EmptyState({ hasFilters, onClear }: { hasFilters: boolean; onClear: () => void }) {
  return (
    <div className="px-5 py-16 text-center">
      <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-3xl bg-slate-100 dark:bg-slate-900">
        <ClipboardList size={22} className="text-slate-400 dark:text-slate-600" />
      </div>
      <h3 className="mt-4 text-base font-semibold text-slate-900 dark:text-white">
        {hasFilters ? 'No matching cases' : 'No cases yet'}
      </h3>
      <p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-slate-500 dark:text-slate-400">
        {hasFilters
          ? 'Try adjusting your search or filters to find what you are looking for.'
          : 'Cases flagged for review will appear here once submissions are processed.'}
      </p>
      {hasFilters && (
        <button
          type="button"
          onClick={onClear}
          className="mt-5 inline-flex h-10 items-center gap-2 rounded-2xl border border-slate-200 px-4 text-sm font-medium text-slate-700 transition hover:bg-slate-100 dark:border-slate-800 dark:text-slate-300 dark:hover:bg-slate-900"
        >
          <X size={14} />
          Clear filters
        </button>
      )}
    </div>
  );
}

// ─── Page ──────────────────────────────────────────────────────────────────────

export default function CasesQueuePage() {
  const cases = useMemo<CaseItem[]>(
    () => (assignmentCases as unknown[]).map(toCaseItem).sort(riskSort),
    []
  );

  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [riskFilter, setRiskFilter] = useState<RiskFilter>('all');

  // Derive unique filter options from data
  const statusOptions = useMemo(() => {
    const unique = [...new Set(cases.map((c) => c.status))];
    return unique.map((s) => ({ value: s, label: s.charAt(0).toUpperCase() + s.slice(1).replace('-', ' ') }));
  }, [cases]);

  const riskOptions = useMemo(() => {
    const order = ['high', 'medium', 'low'];
    const unique = [...new Set(cases.map((c) => c.risk.toLowerCase()))];
    return unique
      .sort((a, b) => order.indexOf(a) - order.indexOf(b))
      .map((r) => ({ value: r, label: r.charAt(0).toUpperCase() + r.slice(1) }));
  }, [cases]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return cases.filter((c) => {
      if (statusFilter !== 'all' && c.status !== statusFilter) return false;
      if (riskFilter !== 'all' && c.risk.toLowerCase() !== riskFilter) return false;
      if (q) {
        const haystack = `${c.course} ${c.assignment} ${c.students} ${c.reason} ${c.reviewer}`.toLowerCase();
        if (!haystack.includes(q)) return false;
      }
      return true;
    });
  }, [cases, query, statusFilter, riskFilter]);

  const hasFilters = query !== '' || statusFilter !== 'all' || riskFilter !== 'all';

  const clearFilters = () => {
    setQuery('');
    setStatusFilter('all');
    setRiskFilter('all');
  };

  return (
    <DashboardLayout>
      <div className="max-w-none px-4 py-6 sm:px-6 lg:px-8 lg:py-8 space-y-6">

        {/* ── Header ──────────────────────────────────────────────────────────── */}
        <PageHeader
          eyebrow="Cases"
          title="Academic integrity review queue"
          description="Assign, review, dismiss, and export cases — without digging through raw tool output."
          action={null}
          eyebrowStyle="badge"
        />

        {/* ── Queue card ──────────────────────────────────────────────────────── */}
        <section className="overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-950">

          {/* Toolbar */}
          <div className="flex flex-col gap-3 border-b border-slate-200 px-5 py-4 dark:border-slate-800 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Queue</h2>
              <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
                {filtered.length === cases.length
                  ? `${cases.length} case${cases.length !== 1 ? 's' : ''}, sorted by risk`
                  : `${filtered.length} of ${cases.length} cases`}
              </p>
            </div>

            <div className="flex flex-wrap gap-2">
              {/* Search */}
              <div className="relative">
                <Search
                  size={15}
                  className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                />
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search cases, students…"
                  className="h-10 w-56 rounded-xl border border-slate-200 bg-white pl-9 pr-4 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white dark:placeholder:text-slate-500"
                />
                {query && (
                  <button
                    type="button"
                    onClick={() => setQuery('')}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                  >
                    <X size={13} />
                  </button>
                )}
              </div>

              {/* Status filter */}
              <FilterSelect
                value={statusFilter}
                onChange={(v) => setStatusFilter(v as StatusFilter)}
                options={statusOptions}
                placeholder="All statuses"
              />

              {/* Risk filter */}
              <FilterSelect
                value={riskFilter}
                onChange={(v) => setRiskFilter(v as RiskFilter)}
                options={riskOptions}
                placeholder="All risk levels"
              />

              {/* Clear */}
              {hasFilters && (
                <button
                  type="button"
                  onClick={clearFilters}
                  className="inline-flex h-10 items-center gap-1.5 rounded-xl border border-slate-200 px-3 text-sm text-slate-600 transition hover:bg-slate-100 dark:border-slate-800 dark:text-slate-400 dark:hover:bg-slate-900"
                >
                  <X size={13} />
                  Clear
                </button>
              )}
            </div>
          </div>

          {/* Desktop table */}
          {filtered.length === 0 ? (
            <EmptyState hasFilters={hasFilters} onClear={clearFilters} />
          ) : (
            <>
              <div className="hidden overflow-x-auto md:block">
                <table className="w-full min-w-[860px] text-left">
                  <thead className="bg-slate-50 dark:bg-slate-900/80">
                    <tr>
                      {['Status', 'Course & assignment', 'Students & reason', 'Risk', 'Reviewer', ''].map((h) => (
                        <th
                          key={h}
                          className="px-5 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400"
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                    {filtered.map((item) => (
                      <tr
                        key={item.id}
                        className="transition-colors hover:bg-slate-50 dark:hover:bg-slate-900/50"
                      >
                        <td className="px-5 py-4">
                          <StatusBadge status={item.status} />
                        </td>

                        <td className="px-5 py-4">
                          <div className="text-sm font-semibold text-slate-900 dark:text-white">
                            {item.course}
                          </div>
                          <div className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                            {item.assignment}
                          </div>
                        </td>

                        <td className="px-5 py-4">
                          <div className="text-sm font-medium text-slate-900 dark:text-white">
                            {item.students}
                          </div>
                          <div className="mt-0.5 max-w-[240px] truncate text-xs text-slate-500 dark:text-slate-400">
                            {item.reason}
                          </div>
                        </td>

                        <td className="px-5 py-4">
                          <RiskPill value={item.risk} />
                        </td>

                        <td className="px-5 py-4 text-sm text-slate-600 dark:text-slate-400">
                          {item.reviewer}
                        </td>

                        <td className="px-5 py-4 text-right">
                          <Link
                            href={`/cases/${item.id}`}
                            className="inline-flex h-8 items-center gap-1.5 rounded-xl border border-slate-200 px-3 text-xs font-semibold text-slate-700 transition hover:bg-slate-100 dark:border-slate-800 dark:text-slate-300 dark:hover:bg-slate-900"
                          >
                            Open
                            <ArrowUpRight size={12} />
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Mobile cards */}
              <div className="grid gap-3 p-4 md:hidden">
                {filtered.map((item) => (
                  <CaseMobileCard key={item.id} item={item} />
                ))}
              </div>
            </>
          )}

          {/* Table footer */}
          {filtered.length > 0 && (
            <div className="border-t border-slate-200 px-5 py-3 dark:border-slate-800">
              <p className="text-xs text-slate-400 dark:text-slate-600">
                Showing {filtered.length} of {cases.length} cases · Sorted by risk level
              </p>
            </div>
          )}
        </section>

      </div>
    </DashboardLayout>
  );
}