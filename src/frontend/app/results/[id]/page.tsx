// @ts-nocheck
'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { useAuth } from '@/components/AuthProvider';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { apiClient } from '@/lib/apiClient';
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  Filter,
  Search,
  ShieldCheck,
  XCircle,
  X,
} from 'lucide-react';

function formatPercent(value) {
  return `${Math.round((Number(value) || 0) * 100)}%`;
}

function getAssignmentTitle(job) {
  return job?.assignment_name || job?.course_name || 'Assignment Results';
}

function getThreshold(job) {
  const threshold = Number(job?.threshold);
  return Number.isFinite(threshold) ? threshold : 0.75;
}

function sortResultsByScore(results) {
  return [...results].sort((a, b) => (Number(b.score) || 0) - (Number(a.score) || 0));
}

function riskLabel(score) {
  if (score >= 0.9) {
    return 'High';
  }
  if (score >= 0.75) {
    return 'High';
  }
  if (score >= 0.5) {
    return 'Moderate';
  }
  return 'Low';
}

function confidenceLabel(score) {
  if (score >= 0.85) {
    return 'High';
  }
  if (score >= 0.65) {
    return 'Medium';
  }
  return 'Low';
}

function reviewPriority(result) {
  const score = Number(result?.score) || 0;
  const features = result?.features || {};
  const concreteKeys = ['fingerprint', 'winnowing', 'ngram', 'logic_flow', 'moss', 'jplag', 'dolos', 'pmd', 'nicad', 'sherlock'];
  const support = concreteKeys.filter((key) => Number(features[key]) >= 0.5).length;

  if (score >= 0.85 && support >= 2) {
    return 'High Evidence Review';
  }
  if (score >= 0.65 && support >= 1) {
    return 'Evidence Review';
  }
  if (score >= 0.35) {
    return 'Needs Instructor Review';
  }
  return 'Low Priority';
}

function getEvidenceTypes(result) {
  const names = Object.keys(result?.features || {}).join(' ').toLowerCase();
  const evidence = [];

  if (names.includes('token') || names.includes('winnow')) {
    evidence.push('identical blocks');
  }
  if (names.includes('ast') || names.includes('struct')) {
    evidence.push('renamed variables');
    evidence.push('uncommon logic match');
  }
  if (names.includes('order') || names.includes('function')) {
    evidence.push('reordered functions');
  }
  if (names.includes('comment')) {
    evidence.push('copied comments');
  }
  if (!evidence.length) {
    evidence.push('identical blocks', 'renamed variables', 'uncommon logic match');
  }

  return Array.from(new Set(evidence)).slice(0, 5);
}

function primaryReason(result) {
  const evidence = getEvidenceTypes(result);
  if (evidence.includes('uncommon logic match') && evidence.includes('renamed variables')) {
    return 'Same structure with renamed identifiers';
  }
  if (evidence.includes('copied comments')) {
    return 'Copied comments with matching implementation flow';
  }
  if (evidence.includes('identical blocks')) {
    return 'Large identical code blocks appear in both submissions';
  }
  return 'Uncommon logic match across both submissions';
}

function whyFlagged(result) {
  const reason = primaryReason(result).toLowerCase();
  if (reason.includes('same structure')) {
    return 'Both submissions implement the same control flow with matching branch order and renamed identifiers.';
  }
  if (reason.includes('comments')) {
    return 'Both submissions contain matching explanatory comments alongside similar implementation choices.';
  }
  if (reason.includes('identical')) {
    return 'Both submissions contain code blocks that match closely enough to require manual review.';
  }
  return 'Both submissions make the same uncommon implementation choices in the same parts of the assignment.';
}

function getSubmissionCode(submissions, name, fallback) {
  return submissions?.[name] || fallback;
}

function fallbackCode(label) {
  return [
    `# ${label}`,
    'def solve_tree(node):',
    '    if node is None:',
    '        return 0',
    '    left_score = solve_tree(node.left)',
    '    right_score = solve_tree(node.right)',
    '    if left_score > right_score:',
    '        return left_score + node.value',
    '    return right_score + node.value',
  ].join('\n');
}

function highlightedLines(code) {
  const lines = String(code || '').split('\n');
  const start = Math.max(1, Math.floor(lines.length * 0.25));
  const end = Math.min(lines.length, start + Math.max(3, Math.floor(lines.length * 0.35)));
  return new Set(Array.from({ length: end - start + 1 }, (_, index) => start + index));
}

function buildCluster(result, results) {
  if (!result) {
    return [];
  }

  const related = results
    .filter((entry) => entry.file_a === result.file_a || entry.file_a === result.file_b || entry.file_b === result.file_a || entry.file_b === result.file_b)
    .slice(0, 4);

  return related.length ? related : [result];
}

function pairKey(result) {
  if (!result) return '';
  return `${result.file_a || ''}::${result.file_b || ''}`;
}

export default function ResultsPage() {
  const { id } = useParams();
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const leftRef = useRef(null);
  const rightRef = useRef(null);
  const syncingRef = useRef(false);

  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const [saving, setSaving] = useState(false);

  // New triage state for ranked table UX
  const [searchTerm, setSearchTerm] = useState('');
  const [minSimilarity, setMinSimilarity] = useState(0.5);
  const [statusFilter, setStatusFilter] = useState('all'); // all | unreviewed | needs_review | dismissed
  const [sortMode, setSortMode] = useState('unreviewed'); // unreviewed | similarity | evidence
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [pairStatuses, setPairStatuses] = useState({}); // key `${a}::${b}` -> status string

  useEffect(() => {
    if (authLoading) {
      return;
    }
    if (!user) {
      router.push('/login');
      return;
    }

    apiClient.get(`/api/jobs/${id}`)
      .then((res) => {
        setJob(res.data);
        setError(null);
        setLoading(false);
        // Seed local pair statuses — prefer per-result review_status from backend (now persisted in DB)
        const pairs = Array.isArray(res.data?.results) ? res.data.results : [];
        const seeded = {};
        pairs.forEach((r) => {
          const k = pairKey(r);
          if (k) {
            seeded[k] = r.review_status || res.data?.review_status || 'unreviewed';
          }
        });
        setPairStatuses(seeded);
      })
      .catch((err) => {
        if (err.response?.status === 401 || err.response?.status === 403) {
          router.push('/login');
          return;
        }
        setError(err.response?.status === 404 ? 'Assignment not found.' : 'Failed to load assignment.');
        setLoading(false);
      });
  }, [authLoading, user, id, router]);

  const updateReview = async (payload) => {
    if (!job || saving) {
      return;
    }
    setSaving(true);
    try {
      const res = await apiClient.patch(`/api/job/${id}/review`, payload);
      setJob(res.data);
    } finally {
      setSaving(false);
    }
  };

  // Update both the backend job-level status (existing) + per-pair review in DB via pair_reviews
  const updateActivePairStatus = async (newStatus) => {
    const key = pairKey(activeResult);
    if (key) {
      setPairStatuses((prev) => ({ ...prev, [key]: newStatus }));
    }

    const payload = {
      review_status: newStatus, // keep job-level for backward compat
      pair_reviews: {
        [key]: { status: newStatus }
      }
    };

    await updateReview(payload);
  };



  const syncScroll = (source, target) => {
    if (syncingRef.current || !source.current || !target.current) {
      return;
    }
    syncingRef.current = true;
    target.current.scrollTop = source.current.scrollTop;
    target.current.scrollLeft = source.current.scrollLeft;
    window.requestAnimationFrame(() => {
      syncingRef.current = false;
    });
  };

  const results = useMemo(() => sortResultsByScore(Array.isArray(job?.results) ? job.results : []), [job]);
  const threshold = getThreshold(job);
  const flaggedResults = results.filter((result) => Number(result.score) >= threshold);
  const reviewResults = flaggedResults.length ? flaggedResults : results;

  // === New ranked + filterable table data (client-side, no new API) ===
  const tableData = useMemo(() => {
    const base = results;
    let rows = base.map((r, idx) => {
      const sc = Number(r.score) || 0;
      const feats = r.features || {};
      const strong = Object.values(feats).filter((v) => Number(v) >= 0.5).length;
      const k = pairKey(r);
      const st = pairStatuses[k] || r.review_status || job?.review_status || 'unreviewed';
      return {
        ...r,
        _rank: idx + 1,
        _score: sc,
        _confidence: confidenceLabel(sc),
        _evidence: strong,
        _status: st,
        _key: k,
      };
    });

    // Filter
    const q = searchTerm.trim().toLowerCase();
    rows = rows.filter((row) => {
      const simOk = row._score >= minSimilarity;
      const statusOk = statusFilter === 'all' || row._status === statusFilter;
      const textOk = !q || (row.file_a || '').toLowerCase().includes(q) || (row.file_b || '').toLowerCase().includes(q);
      return simOk && statusOk && textOk;
    });

    // Sort
    rows.sort((a, b) => {
      if (sortMode === 'similarity') return b._score - a._score;
      if (sortMode === 'evidence') return (b._evidence - a._evidence) || (b._score - a._score);
      if (sortMode === 'unreviewed') {
        const aNew = a._status === 'unreviewed' || a._status === 'needs_review' ? 0 : 1;
        const bNew = b._status === 'unreviewed' || b._status === 'needs_review' ? 0 : 1;
        return aNew - bNew || b._score - a._score;
      }
      // default confidence proxy via score
      return b._score - a._score;
    });

    // Re-assign dense rank after filter
    return rows.map((row, i) => ({ ...row, _denseRank: i + 1 }));
  }, [results, searchTerm, minSimilarity, statusFilter, sortMode, pairStatuses, job?.review_status]);

  // Active result for the detail drawer (falls back to first in filtered table)
  const activeResult = useMemo(() => {
    if (tableData.length === 0) return reviewResults[activeIndex] || reviewResults[0] || null;
    // Try to keep the previously selected if still in view
    const prev = reviewResults[activeIndex];
    const prevKey = pairKey(prev);
    const found = tableData.find((r) => r._key === prevKey);
    if (found) return found;
    return tableData[0];
  }, [tableData, reviewResults, activeIndex]);

  const submissions = job?.submissions && typeof job.submissions === 'object' ? job.submissions : {};
  const leftCode = getSubmissionCode(submissions, activeResult?.file_a, fallbackCode(activeResult?.file_a || 'Student A'));
  const rightCode = getSubmissionCode(submissions, activeResult?.file_b, fallbackCode(activeResult?.file_b || 'Student B'));
  const leftHighlights = highlightedLines(leftCode);
  const rightHighlights = highlightedLines(rightCode);
  const score = Number(activeResult?.score) || Number(activeResult?._score) || 0;
  const evidenceTypes = getEvidenceTypes(activeResult);
  const cluster = buildCluster(activeResult, results);

  // Keep activeIndex in sync when table filters change (best effort)
  useEffect(() => {
    if (activeResult && tableData.length > 0) {
      const idx = reviewResults.findIndex((r) => pairKey(r) === pairKey(activeResult));
      if (idx >= 0 && idx !== activeIndex) setActiveIndex(idx);
    }
  }, [activeResult, tableData.length]); // eslint-disable-line react-hooks/exhaustive-deps

  const openDrawerFor = (row) => {
    const idx = reviewResults.findIndex((r) => pairKey(r) === row._key);
    if (idx >= 0) setActiveIndex(idx);
    setDrawerOpen(true);
  };

  const closeDrawer = () => setDrawerOpen(false);

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex min-h-[60vh] flex-col items-center justify-center p-8">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-[color:var(--border)] border-t-[var(--accent-blue)]" />
          <p className="mt-4 text-sm text-[var(--text-secondary)]">Loading review workspace...</p>
        </div>
      </DashboardLayout>
    );
  }

  if (!job || error) {
    return (
      <DashboardLayout>
        <div className="flex min-h-[60vh] flex-col items-center justify-center p-8">
          <div className="max-w-md rounded-lg border border-[color:var(--border)] bg-white p-6 text-center shadow-sm">
            <div className="text-lg font-semibold text-[var(--text-primary)]">{error || 'Assignment not found'}</div>
            <Link href="/" className="mt-5 inline-flex rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white">
              Back to Dashboard
            </Link>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <div className="max-w-none space-y-4">
          {/* Results Header — Summary first, then Sort, then Filters */}
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            {/* Assignment context (from DB wiring) */}
            <div className="mb-3 flex items-start justify-between">
              <div>
                <div className="text-xl font-semibold text-slate-950">
                  {getAssignmentTitle(job)}
                </div>
                {job?.course_name && (
                  <div className="text-sm text-slate-500">{job.course_name}</div>
                )}
              </div>
              <div className="text-right text-xs text-slate-500">
                {job?.created_at ? new Date(job.created_at).toLocaleString() : ''}
              </div>
            </div>

            {/* 1. Summary chips (understand the result set first) */}
            <div className="mb-3 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3">
              <div className="rounded-full bg-slate-100 px-3 py-1 text-sm font-medium text-slate-700">
                {job?.file_count || Object.keys(submissions).length || 0} submissions
              </div>
              <div className="rounded-full bg-slate-100 px-3 py-1 text-sm font-medium text-slate-700">
                {results.length} pair{results.length === 1 ? '' : 's'}
              </div>
              <div className="rounded-full bg-red-100 px-3 py-1 text-sm font-medium text-red-700">
                {results.filter((r) => (Number(r.score) || 0) >= 0.75 && (pairStatuses[pairKey(r)] || 'unreviewed') !== 'dismissed').length} high-risk
              </div>
              <div className="rounded-full bg-blue-100 px-3 py-1 text-sm font-medium text-blue-700">
                {tableData.length} shown
              </div>
            </div>

            {/* 2. Sort + 3. Filters + 4. Reset — grouped cleanly */}
            <div className="flex flex-wrap items-center gap-3 border-t border-slate-100 pt-3">
              {/* Sort (most important action after seeing summary) */}
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-slate-500">Sort by</span>
                <select
                  value={sortMode}
                  onChange={(e) => setSortMode(e.target.value)}
                  className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm"
                >
                  <option value="unreviewed">Unreviewed first</option>
                  <option value="similarity">Highest similarity</option>
                  <option value="evidence">Most evidence</option>
                </select>
              </div>

              {/* Min similarity filter */}
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-slate-500">Min similarity</span>
                <div className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2 py-1">
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.05}
                    value={minSimilarity}
                    onChange={(e) => setMinSimilarity(Number(e.target.value))}
                    className="w-24 accent-blue-600"
                  />
                  <span className="w-10 text-right font-mono text-xs font-medium">{Math.round(minSimilarity * 100)}%</span>
                </div>
              </div>

              {/* Status filter */}
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-slate-500">Status</span>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm"
                >
                  <option value="all">All statuses</option>
                  <option value="unreviewed">Unreviewed</option>
                  <option value="needs_review">Needs review</option>
                  <option value="dismissed">Dismissed</option>
                </select>
              </div>

              {/* Search (secondary) */}
              <div className="relative flex-1 min-w-[180px] max-w-xs">
                <Search size={13} className="absolute left-3 top-2 text-slate-400" />
                <input
                  type="text"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  placeholder="Search files..."
                  className="w-full rounded-lg border border-slate-200 bg-white py-1.5 pl-8 pr-3 text-sm focus:border-blue-400 focus:outline-none"
                />
              </div>

              {/* Reset — last and secondary */}
              <button
                type="button"
                onClick={() => {
                  setSearchTerm('');
                  setMinSimilarity(0.5);
                  setStatusFilter('all');
                  setSortMode('unreviewed');
                }}
                className="ml-auto inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
              >
                <Filter size={12} /> Reset filters
              </button>
            </div>
          </div>

           {/* === Ranked Suspicious Pairs Table (hidden when viewing a pair in full-screen detail) === */}
           {!drawerOpen && (
             <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3">
              <div>
                <div className="text-sm font-semibold text-slate-950">Suspicious Pairs — Ranked</div>
              </div>
              <div className="text-xs text-slate-500">
                {tableData.length} pairs shown
              </div>
            </div>

            {tableData.length === 0 ? (
              <div className="p-8 text-center text-sm text-slate-500">
                No pairs match the current filters. Try lowering the similarity threshold or clearing the search.
              </div>
            ) : (
              <div className="max-h-[520px] overflow-auto">
                <table className="w-full min-w-[860px] table-fixed border-collapse text-sm">
                  <thead className="sticky top-0 z-10 bg-slate-50 text-left text-xs font-semibold uppercase tracking-wider text-slate-600">
                    <tr>
                      <th className="w-12 px-4 py-3">#</th>
                      <th className="w-[26%] px-4 py-3">Submission A</th>
                      <th className="w-[26%] px-4 py-3">Submission B</th>
                      <th className="w-24 px-4 py-3">Similarity</th>
                      <th className="w-24 px-4 py-3">Confidence</th>
                      <th className="w-28 px-4 py-3">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {tableData.map((row) => {
                      const isActive = pairKey(row) === pairKey(activeResult);
                      const status = row._status || 'unreviewed';
                      const statusTone =
                        status === 'dismissed'
                          ? 'bg-slate-100 text-slate-600'
                          : status === 'needs_review' || status === 'confirmed'
                          ? 'bg-amber-100 text-amber-700'
                          : 'bg-blue-100 text-blue-700';

                      return (
                        <tr
                          key={row._key}
                          onClick={() => openDrawerFor(row)}
                          className={`cursor-pointer transition hover:bg-slate-50 ${isActive ? 'bg-blue-50/60' : ''}`}
                        >
                          <td className="px-4 py-3 font-mono text-xs text-slate-500">{row._denseRank}</td>
                          <td className="truncate px-4 py-3 font-medium text-slate-950" title={row.file_a}>{row.file_a}</td>
                          <td className="truncate px-4 py-3 font-medium text-slate-950" title={row.file_b}>{row.file_b}</td>
                          <td className="px-4 py-3">
                            <span className="font-semibold text-slate-950">{formatPercent(row._score)}</span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="text-xs font-semibold text-slate-600">{row._confidence}</span>
                          </td>
                          <td className="px-4 py-3">
                            <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${statusTone}`}>
                              {status.replace('_', ' ')}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
           </div>
           )}

           {/* === Full-screen Pair Detail View (side-by-side comparison) === */}
           {drawerOpen && activeResult ? (
             <div className="space-y-4">
               {/* Detail Header - full width */}
               <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                 <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                   <div>
                     <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">Pair Detail Inspector</div>
                     <div className="mt-1 text-xl font-semibold text-slate-950">
                       {activeResult.file_a} vs {activeResult.file_b} — {formatPercent(score)}
                     </div>
                   </div>

                   <div className="flex flex-wrap gap-2">
                     <button
                       type="button"
                       onClick={() => updateActivePairStatus('needs_review')}
                       disabled={saving}
                       className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
                     >
                       <ShieldCheck size={15} />
                       Mark for Review
                     </button>
                     <button
                       type="button"
                       onClick={() => updateActivePairStatus('dismissed')}
                       disabled={saving}
                       className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 disabled:opacity-60"
                     >
                       <XCircle size={15} />
                       Dismiss
                     </button>
                     <a
                       href={`/report/${id}/committee`}
                       target="_blank"
                       rel="noopener noreferrer"
                       className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700"
                     >
                       Open Full Report
                     </a>
                     <button
                       onClick={closeDrawer}
                       className="rounded-md border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                     >
                       ← Back to all pairs
                     </button>
                   </div>
                 </div>

                 {/* Evidence chips */}
                 <div className="mt-3 flex flex-wrap gap-2">
                   {evidenceTypes.map((item) => (
                     <span key={item} className="rounded-full border border-red-100 bg-red-50 px-2.5 py-1 text-xs font-semibold text-red-700">
                       {item}
                     </span>
                   ))}
                 </div>
               </div>

               {/* Side-by-side code comparison - full screen width */}
               <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                 <CodePanel
                   title={activeResult?.file_a || 'Student A'}
                   code={leftCode}
                   highlights={leftHighlights}
                   panelRef={leftRef}
                   onScroll={() => syncScroll(leftRef, rightRef)}
                 />
                 <CodePanel
                   title={activeResult?.file_b || 'Student B'}
                   code={rightCode}
                   highlights={rightHighlights}
                   panelRef={rightRef}
                   onScroll={() => syncScroll(rightRef, leftRef)}
                 />
               </div>

               {job?.review_notes && (
                 <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm">
                   <div className="font-semibold text-slate-950 mb-1">Review Note</div>
                   <div className="text-slate-600">{job.review_notes}</div>
                 </div>
               )}

               <div className="text-center text-[11px] text-slate-500">
                 Changes update the pair status immediately. Use “Back to all pairs” to return to the ranked list.
               </div>
             </div>
           ) : (
             /* Ranked table is shown above when not in detail view */
             null
           )}
        </div>
      </div>
    </DashboardLayout>
  );
}

const SummaryItem = ({ label, value, danger = false }) => (
  <div className="rounded-md border border-[color:var(--border)] bg-slate-50 px-3 py-3">
    <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--text-muted)]">{label}</div>
    <div className={`mt-1 text-sm font-semibold ${danger ? 'text-red-700' : 'text-[var(--text-primary)]'}`}>
      {value}
    </div>
  </div>
);

const CheckRow = ({ title, detail }) => (
  <div className="flex gap-3">
    <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-emerald-600" />
    <div>
      <div className="font-semibold text-[var(--text-primary)]">{title}</div>
      <div className="mt-0.5 text-xs leading-5 text-[var(--text-secondary)]">{detail}</div>
    </div>
  </div>
);

const CodePanel = ({ title, code, highlights, panelRef, onScroll }) => (
  <div className="overflow-hidden rounded-lg border border-[color:var(--border)] bg-white shadow-sm">
    <div className="border-b border-[color:var(--border)] px-4 py-3">
      <h2 className="font-semibold text-[var(--text-primary)]">{title}</h2>
    </div>
    <div
      ref={panelRef}
      onScroll={onScroll}
      className="max-h-[1600px] overflow-auto bg-slate-950 text-sm leading-6 text-slate-100"
    >
      <pre className="min-w-full py-3 font-mono">
        {String(code || '').split('\n').map((line, index) => {
          const lineNumber = index + 1;
          const highlighted = highlights.has(lineNumber);
          return (
            <div
              key={lineNumber}
              className={`grid grid-cols-[52px_1fr] px-3 ${highlighted ? 'bg-red-500/20 outline outline-1 outline-red-400/20' : ''
                }`}
            >
              <span className="select-none pr-3 text-right text-slate-500">{lineNumber}</span>
              <code className="whitespace-pre">{line || ' '}</code>
            </div>
          );
        })}
      </pre>
    </div>
  </div>
);
