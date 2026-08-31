// @ts-nocheck — TODO: add proper types (tracked in types/api.ts)

'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { useAuth } from '@/components/AuthProvider';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { apiClient } from '@/lib/apiClient';
import { ButtonLink, PageHeader, ActionButton, Card } from '@/components/saas/SaaSPrimitives';
import {
  AlertTriangle,
  CheckCircle2,
  FileText,
  Filter,
  Search,
  ShieldCheck,
  X,
  TreePine,
  GitBranch,
} from 'lucide-react';

function formatPercent(value) {
  const num = Number(value) || 0;
  return `${Math.round(num * 100)}`;
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

function mapVerdictToLabel(verdict) {
  // Map old verdict labels to new ones
  const labels = {
    CLEAN: 'CLEAN',
    REVIEW_REQUIRED: 'REVIEW REQUIRED',
    STRONG_SIMILARITY_OBSERVED: 'STRONG SIMILARITY OBSERVED',
    TRUE: 'STRONG SIMILARITY OBSERVED',
    PROBABLE: 'REVIEW REQUIRED',
    REVIEW: 'REVIEW REQUIRED',
    FLAG: 'REVIEW REQUIRED',
  };
  return labels[verdict] || 'REVIEW REQUIRED';
}

function getVerdictStyle(verdict) {
  const styles = {
    CLEAN: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    REVIEW_REQUIRED: 'bg-blue-100 text-blue-700 border-blue-200',
    STRONG_SIMILARITY_OBSERVED: 'bg-red-100 text-red-700 border-red-200',
  };
  return styles[verdict] || 'bg-slate-100 text-slate-600 border-slate-200';
}

function VerdictBadge({ verdict }) {
  if (!verdict) {
    return null;
  }
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-semibold ${getVerdictStyle(verdict)}`}>
      {verdict}
    </span>
  );
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

function cloneCategory(block) {
  // Map backend clone_type to a display category for color highlighting.
  const type = block?.clone_type;
  if (type === 'Type 1') return 'identical';
  if (type === 'Type 2') return 'renamed';
  if (type === 'Type 3' || type === 'Type 4') return 'logic';
  // Fallback when clone_type is missing (legacy data): infer from similarity.
  const similarity = typeof block?.similarity === 'number' ? block.similarity : 0.75;
  if (similarity >= 0.9) return 'identical';
  if (similarity >= 0.7) return 'renamed';
  return 'logic';
}

function cloneCategoryLabel(block) {
  const labels = {
    identical: 'identical block',
    renamed: 'renamed variables',
    logic: 'uncommon logic match',
  };
  return labels[cloneCategory(block)];
}

function cloneReason(block) {
  // Plain-language basis for a matching block, mirroring the code-matching
  // engine's clone-type classification (Type 1..4).
  const type = block?.clone_type;
  const pct = Math.round((block.similarity || 0.75) * 100);
  if (type === 'Type 1') {
    return `The snippet matches byte-for-byte (line-for-line) between the two files. Exact copies score ${pct}% — this is the strongest evidence of copying.`;
  }
  if (type === 'Type 2') {
    return `The snippet has identical structure and literal values, but identifier names were changed. Renaming still scores ${pct}% because the underlying tokens match after normalizing names.`;
  }
  if (type === 'Type 3') {
    return `The snippet is a near match with some statements added, removed, or reordered. At ${pct}% it still indicates a likely common origin.`;
  }
  return `The snippet achieves the same behavior through different syntax. At ${pct}% it suggests shared intent rather than shared code.`;
}

const CATEGORY_PRIORITY = { identical: 3, renamed: 2, logic: 1 };

function highlightedLines(code, matchingBlocks, isLeft = true) {
  // Returns a Map of line number -> category ('identical' | 'renamed' | 'logic')
  // If matching_blocks provided, parse line ranges from backend data.
  // Categories map to clone types: Type 1 = identical, Type 2 = renamed
  // identifiers/literals, Type 3/4 = modified or semantically similar logic.
  if (matchingBlocks && Array.isArray(matchingBlocks) && matchingBlocks.length > 0) {
    const lineCategories = new Map();
    for (const block of matchingBlocks) {
      // Use lines_a for left panel, lines_b for right panel
      const rangeKey = isLeft ? 'lines_a' : 'lines_b';
      const range = block[rangeKey];
      const category = cloneCategory(block);
      if (range) {
        const [start, end] = range.split('-').map(Number);
        if (!isNaN(start) && !isNaN(end)) {
          for (let i = start; i <= end; i++) {
            // Keep the strongest category for each line
            const existing = lineCategories.get(i);
            if (!existing || CATEGORY_PRIORITY[category] > CATEGORY_PRIORITY[existing]) {
              lineCategories.set(i, category);
            }
          }
        }
      }
    }
    return lineCategories;
  }
  // Fallback: no matching blocks data available
  return new Map();
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

const ENGINE_META = {
  ast: {
    name: 'Structure (AST)',
    what: 'How similarly the code is organized at the syntax level.',
    why: 'Same structure even when names or details differ.',
  },
  fingerprint: {
    name: 'Token fingerprint',
    what: 'Overlap in the raw token (identifier/keyword) sequence.',
    why: 'The token streams line up almost exactly.',
  },
  embedding: {
    name: 'Semantic meaning',
    what: 'Model-based comparison of what both files mean.',
    why: 'Both files express the same behavior and intent.',
  },
  ngram: {
    name: 'Token n-gram match',
    what: 'Shared consecutive token runs (typical n-gram overlap).',
    why: 'Long identical token runs appear in both files.',
  },
  winnowing: {
    name: 'Chunk hash match',
    what: 'Rabin-fingerprint / winnowing chunk overlap.',
    why: 'Near-identical code chunks are detected by hashing.',
  },
  logic_flow: {
    name: 'Logic flow',
    what: 'Order and shape of the control flow graph.',
    why: 'Both files follow the same path through branches and loops.',
  },
};

function normalizeKeyword(key) {
  return String(key || '')
    .toLowerCase()
    .replace(/[^a-z0-9]/g, '');
}

function engineMetaFor(key) {
  const norm = normalizeKeyword(key);
  for (const k of Object.keys(ENGINE_META)) {
    if (normalizeKeyword(k) === norm) return ENGINE_META[k];
  }
  // Fuzzy match so legacy keys like "ast_similarity" still resolve.
  for (const k of Object.keys(ENGINE_META)) {
    if (norm.includes(normalizeKeyword(k)) || normalizeKeyword(k).includes(norm)) {
      return ENGINE_META[k];
    }
  }
  return {
    name: key,
    what: 'Similarity signal from this analysis engine.',
    why: 'This signal draws comparisons across the two files.',
  };
}

function buildEvidenceSignals(result) {
  // Derive professor-readable evidence from the real backend feature keys
  // plus the fusion_debug breakdown (which engine fired past the threshold).
  // Returns an ordered list of { key, name, what, why, score, fired, source }.
  const features = result?.features || {};
  const debug = result?.fusion_debug || {};
  const threshold = typeof debug.threshold === 'number' ? debug.threshold : 0.5;
  const firedSet = new Set((debug.engines_fired || []).map(normalizeKeyword));

  const signals = [];
  for (const [key, raw] of Object.entries(features)) {
    const score = Number(raw) || 0;
    if (score <= 0) continue;
    const meta = engineMetaFor(key);
    const fired = debug.engines_fired ? firedSet.has(normalizeKeyword(key)) : score >= threshold;
    signals.push({
      key,
      name: meta.name,
      what: meta.what,
      why: meta.why,
      score,
      fired,
    });
  }

  // If fusion_debug carries active_evidence with engines the feature map
  // omits, backfill them so no fired engine is hidden.
  for (const entry of debug.active_evidence || []) {
    const key = String(entry.engine);
    if (signals.some((s) => s.key === key)) continue;
    const score = Number(entry.score) || 0;
    if (score <= 0) continue;
    const meta = engineMetaFor(key);
    signals.push({
      key,
      name: meta.name,
      what: meta.what,
      why: meta.why,
      score,
      fired: Boolean(entry.fired),
    });
  }

  return signals
    .sort((a, b) => b.score - a.score)
    .slice(0, 6);
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
  const [sortMode, setSortMode] = useState('unreviewed'); // unreviewed | similarity | evidence | verdict
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
      // Use verdict from API if available, otherwise derive from score
      const rawVerdict = r.verdict || (sc >= 0.75 ? (sc >= 0.9 ? 'TRUE' : 'PROBABLE') : sc >= 0.5 ? 'REVIEW' : 'CLEAN');
      const verdict = mapVerdictToLabel(rawVerdict);
      // Use confidence from API if available, otherwise derive from score
      const conf = typeof r.confidence === 'number' ? r.confidence : confidenceLabel(sc);
      return {
        ...r,
        _rank: idx + 1,
        _score: sc,
        _confidence: conf,
        _evidence: strong,
        _status: st,
        _key: k,
        verdict: verdict,
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
      if (sortMode === 'verdict') {
        const verdictOrder = { 'STRONG_SIMILARITY_OBSERVED': 0, 'REVIEW_REQUIRED': 1, 'CLEAN': 2 };
        const aOrder = verdictOrder[a.verdict] ?? 1;
        const bOrder = verdictOrder[b.verdict] ?? 1;
        return aOrder - bOrder || b._score - a._score;
      }
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
  // Use code_a/code_b from result if available, otherwise fall back to submissions
  const leftCode = activeResult?.code_a || getSubmissionCode(submissions, activeResult?.file_a, fallbackCode(activeResult?.file_a || 'Student A'));
  const rightCode = activeResult?.code_b || getSubmissionCode(submissions, activeResult?.file_b, fallbackCode(activeResult?.file_b || 'Student B'));
  const leftHighlights = highlightedLines(leftCode, activeResult?.matching_blocks, true);
  const rightHighlights = highlightedLines(rightCode, activeResult?.matching_blocks, false);
  const score = Number(activeResult?.score) || Number(activeResult?._score) || 0;
  const safeScore = isNaN(score) ? 0 : score;
  const confidenceDisplay = Math.round(safeScore * 100);
  const evidenceTypes = getEvidenceTypes(activeResult);
  const cluster = buildCluster(activeResult, results);
  const evidenceSignals = buildEvidenceSignals(activeResult).filter((s) => s.fired);

  // External / Public source matches for this specific pair (for side-by-side integration)
  const externalA = job?.web_analysis?.submissions?.find((s: any) => s.name === activeResult?.file_a);
  const externalB = job?.web_analysis?.submissions?.find((s: any) => s.name === activeResult?.file_b);
  const hasExternalMatches = (externalA?.match_count || 0) > 0 || (externalB?.match_count || 0) > 0;

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
      <div className="px-4 py-6 sm:px-6 lg:px-8 lg:py-8 space-y-6">

        {/* ── Header ──────────────────────────────────────────────────────────── */}
        <div className="flex flex-wrap items-start justify-between gap-3">
          <PageHeader
            eyebrow="Review workspace"
            title={getAssignmentTitle(job)}
            description={job?.course_name ? `${job.course_name} · ${job?.created_at ? new Date(job.created_at).toLocaleString() : ''}` : ''}
            eyebrowStyle="badge"
          />
          <ButtonLink
            href={`/dossier/${id}`}
            variant="secondary"
          >
            Evidence Dossier & Viva Questions
          </ButtonLink>
        </div>

        {/* ── Summary chips ────────────────────────────────────────────────────── */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-3 py-1 text-sm font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-300">
            {job?.file_count || Object.keys(submissions).length || 0} submissions
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-3 py-1 text-sm font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-300">
            {results.length} pair{results.length === 1 ? '' : 's'}
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-red-100 px-3 py-1 text-sm font-medium text-red-700 dark:bg-red-900/30 dark:text-red-400">
            {results.filter((r) => (Number(r.score) || 0) >= 0.75 && (pairStatuses[pairKey(r)] || 'unreviewed') !== 'dismissed').length} high-risk
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-100 px-3 py-1 text-sm font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
            {tableData.length} shown
          </span>
        </div>

        {/* ── Filters bar ──────────────────────────────────────────────────────── */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Sort (most important action after seeing summary) */}
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Sort by</span>
            <select
              value={sortMode}
              onChange={(e) => setSortMode(e.target.value)}
              className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm dark:border-slate-800 dark:bg-slate-900 dark:text-white"
            >
              <option value="unreviewed">Unreviewed first</option>
              <option value="similarity">Highest similarity</option>
              <option value="evidence">Most evidence</option>
              <option value="verdict">By verdict priority</option>
            </select>
          </div>

          {/* Min similarity filter */}
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Min similarity</span>
            <div className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2 py-1 dark:border-slate-800 dark:bg-slate-900">
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
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Status</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm dark:border-slate-800 dark:bg-slate-900 dark:text-white"
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
              className="w-full rounded-lg border border-slate-200 bg-white py-1.5 pl-8 pr-3 text-sm focus:border-blue-400 focus:outline-none dark:border-slate-800 dark:bg-slate-900 dark:text-white dark:placeholder:text-slate-500"
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
            className="ml-auto inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50 dark:border-slate-800 dark:text-slate-400 dark:hover:bg-slate-900"
          >
<Filter size={12} /> Reset filters
          </button>
        </div>

        {/* ── Ranked Suspicious Pairs Table ──────────────────────────────────── */}
        {!drawerOpen && (
          <Card className="overflow-hidden">
            <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3 dark:border-slate-800">
              <h2 className="text-sm font-semibold text-slate-950 dark:text-white">Suspicious Pairs — Ranked</h2>
              <div className="text-xs text-slate-500 dark:text-slate-400">
                {tableData.length} pairs shown
              </div>
            </div>

            {tableData.length === 0 ? (
              <div className="p-8 text-center text-sm text-slate-500 dark:text-slate-400">
                No pairs match the current filters. Try lowering the similarity threshold or clearing the search.
              </div>
            ) : (
              <div className="max-h-[520px] overflow-auto">
                <table className="w-full min-w-[860px] table-fixed border-collapse text-sm">
                  <thead className="sticky top-0 z-10 bg-slate-50 text-left text-xs font-semibold uppercase tracking-wider text-slate-600 dark:bg-slate-900/50 dark:text-slate-400">
                    <tr>
                      <th className="w-12 px-4 py-3">#</th>
                      <th className="w-[26%] px-4 py-3">Submission A</th>
                      <th className="w-[26%] px-4 py-3">Submission B</th>
                      <th className="w-32 px-4 py-3">Verdict</th>
                      <th className="w-28 px-4 py-3">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                    {tableData.map((row) => {
                      const isActive = pairKey(row) === pairKey(activeResult);
                      const status = row._status || 'unreviewed';
                      const statusTone =
                        status === 'dismissed'
                          ? 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400'
                          : status === 'needs_review' || status === 'confirmed'
                            ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
                            : 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400';

                      return (
                        <tr
                          key={row._key}
                          onClick={() => openDrawerFor(row)}
                          className={`cursor-pointer transition hover:bg-slate-50 dark:hover:bg-slate-900/50 ${isActive ? 'bg-blue-50/60 dark:bg-blue-900/20' : ''}`}
                        >
                          <td className="px-4 py-3 font-mono text-xs text-slate-500 dark:text-slate-400">{row._denseRank}</td>
                          <td className="truncate px-4 py-3 font-medium text-slate-950 dark:text-white" title={row.file_a}>{row.file_a}</td>
                          <td className="truncate px-4 py-3 font-medium text-slate-950 dark:text-white" title={row.file_b}>{row.file_b}</td>
                          <td className="px-4 py-3">
                            <VerdictBadge verdict={row.verdict} />
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
          </Card>
        )}

        {/* ── Full-screen Pair Detail View ────────────────────────────────────── */}
        {drawerOpen && activeResult ? (
          <div className="space-y-4">
            <Card className="overflow-hidden">
              <div className="flex flex-col gap-4 px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Pair Detail Inspector</div>
                  <div className="mt-1 text-xl font-semibold text-slate-950 dark:text-white">
                    {activeResult.file_a} vs {activeResult.file_b}
                  </div>
                  <div className="mt-1 flex items-center gap-2">
                    <VerdictBadge verdict={activeResult.verdict} />
                    <span className="text-sm text-slate-500 dark:text-slate-400">{confidenceDisplay}% confidence</span>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <ActionButton
                    variant="primary"
                    icon={ShieldCheck}
                    onClick={() => updateActivePairStatus('needs_review')}
                    disabled={saving}
                  >
                    Mark for Review
                  </ActionButton>
                  <ActionButton
                    variant="secondary"
                    icon={X}
                    onClick={() => updateActivePairStatus('dismissed')}
                    disabled={saving}
                  >
                    Dismiss
                  </ActionButton>
                  <a
                    href={`/report/${id}/committee`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800/50"
                  >
                    Committee Report
                  </a>
                  <a
                    href={`/report/${id}/download`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800/50"
                  >
                    HTML Report
                  </a>
                  <a
                    href={`/report/${id}/download-json`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800/50"
                  >
                    JSON Data
                  </a>
                  <a
                    href={`/report/${id}/download-pdf`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800/50"
                  >
                    PDF Report
                  </a>
                  <a
                    href={`/api/reports/integrity-assessment/${id}?format=html`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center justify-center gap-2 rounded-xl border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-semibold text-blue-700 transition hover:bg-blue-100 dark:border-blue-800 dark:bg-blue-900/30 dark:text-blue-300 dark:hover:bg-blue-900/50"
                  >
                    <FileText size={14} /> Integrity Report
                  </a>
                  <a
                    href={`/api/reports/integrity-assessment/${id}?format=pdf`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center justify-center gap-2 rounded-xl border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-semibold text-blue-700 transition hover:bg-blue-100 dark:border-blue-800 dark:bg-blue-900/30 dark:text-blue-300 dark:hover:bg-blue-900/50"
                  >
                    <FileText size={14} /> Integrity PDF
                  </a>
                  <a
                    href={`/report/${id}/download-csv`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800/50"
                  >
                    CSV Data
                  </a>
                  <button
                    onClick={closeDrawer}
                    className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-800 dark:text-slate-300 dark:hover:bg-slate-900"
                  >
                    ← Back to all pairs
                  </button>
                </div>
              </div>
            </Card>

            {/* Evidence Summary - why this pair was flagged */}
            <Card className="overflow-hidden">
              <div className="flex items-center gap-2 border-b border-slate-200 bg-slate-50/60 px-5 py-4 dark:border-slate-800 dark:bg-slate-900/40">
                <TreePine size={16} className="text-blue-600 dark:text-blue-400" />
                <div>
                  <div className="text-sm font-semibold text-slate-950 dark:text-white">Why this pair was flagged</div>
                  <div className="text-xs text-slate-500 dark:text-slate-400">
                    The signals below are the independent checks that support this verdict. A check is
                    marked as contributing when its score crosses the alert threshold.
                  </div>
                </div>
              </div>
              <div className="px-5 py-4">
                {evidenceSignals.length > 0 ? (
                  <div className="space-y-3">
                    {evidenceSignals.map((signal) => (
                      <div
                        key={signal.key}
                        className={`rounded-lg border p-3 ${signal.fired ? 'border-blue-200 bg-blue-50/70 dark:border-blue-800/40 dark:bg-blue-950/30' : 'border-slate-200 bg-slate-50/60 dark:border-slate-800 dark:bg-slate-900/40'}`}
                      >
                        <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-sm font-semibold text-slate-950 dark:text-white">{signal.name}</span>
                            {signal.fired ? (
                              <span className="rounded-full bg-blue-600 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white">
                                Contributing
                              </span>
                            ) : (
                              <span className="rounded-full bg-slate-200 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                                Supporting
                              </span>
                            )}
                            <span className="font-mono text-sm font-semibold text-slate-700 dark:text-slate-300">
                              {Math.round(signal.score * 100)}%
                            </span>
                          </div>
                        </div>
                        <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
                          <div
                            className={`h-full rounded-full ${signal.fired ? 'bg-blue-600 dark:bg-blue-500' : 'bg-slate-400 dark:bg-slate-600'}`}
                            style={{ width: `${Math.min(100, Math.max(0, Math.round(signal.score * 100)))}%` }}
                          />
                        </div>
                        <p className="mt-2 text-xs leading-5 text-slate-600 dark:text-slate-400">
                          {signal.what}{' '}
                          <span className="font-medium text-slate-700 dark:text-slate-300">{signal.why}</span>
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900/40 dark:text-slate-400">
                    No individual engine signal was above zero for this pair. Review the highlighted
                    blocks and verdict context below for guidance.
                  </div>
                )}
              </div>
            </Card>

            {/* Evidence Blocks - matching code blocks between submissions */}
            {activeResult?.matching_blocks && activeResult.matching_blocks.length > 0 && (
              <Card className="overflow-hidden">
                <div className="flex items-center gap-2 border-b border-slate-200 bg-slate-50/60 px-5 py-4 dark:border-slate-800 dark:bg-slate-900/40">
                  <GitBranch size={16} className="text-purple-600 dark:text-purple-400" />
                  <div>
                    <div className="text-sm font-semibold text-slate-950 dark:text-white">Evidence Blocks</div>
                    <div className="text-xs text-slate-500 dark:text-slate-400">
                      Matching code regions highlighted in the panels below.
                    </div>
                  </div>
                </div>
                <div className="space-y-3 px-5 py-4">
                  {activeResult.matching_blocks.slice(0, 5).map((block, idx) => (
                    <BlockDetail key={idx} block={block} codeA={leftCode} codeB={rightCode} />
                  ))}
                  {activeResult.matching_blocks.length > 5 && (
                    <div className="text-xs text-slate-500 dark:text-slate-400">
                      +{activeResult.matching_blocks.length - 5} more blocks
                    </div>
                  )}
                </div>
              </Card>
            )}

            {/* Evidence chips (simplified view) */}
            {evidenceTypes.length > 0 && (
              <Card className="overflow-hidden">
                <div className="px-5 py-4">
                  <div className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Evidence Signals
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {evidenceTypes.map((item) => (
                      <span key={item} className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-semibold text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
                        {item}
                      </span>
                    ))}
                  </div>
                </div>
              </Card>
            )}

            {/* Similarity Legend */}
            <Card className="overflow-hidden">
              <div className="px-5 py-3">
                <div className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  Highlight Legend
                </div>
                <div className="flex flex-wrap gap-x-6 gap-y-2 text-xs text-slate-600 dark:text-slate-400">
                  <span className="flex items-center gap-2">
                    <span className="w-4 h-3 rounded-sm bg-red-500/60 border border-red-400"></span>
                    Identical (exact copy)
                  </span>
                  <span className="flex items-center gap-2">
                    <span className="w-4 h-3 rounded-sm bg-amber-500/50 border border-amber-400"></span>
                    Renamed (renamed identifiers/literals)
                  </span>
                  <span className="flex items-center gap-2">
                    <span className="w-4 h-3 rounded-sm bg-blue-500/50 border border-blue-400"></span>
                    Logic (modified or semantically similar)
                  </span>
                </div>
              </div>
            </Card>

            {/* Side-by-side code comparison */}
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <CodePanel
                title={activeResult?.file_a || 'Student A'}
                code={leftCode}
                highlights={leftHighlights}
                panelRef={leftRef}
                isLeft={true}
                onScroll={() => syncScroll(leftRef, rightRef)}
              />
              <CodePanel
                title={activeResult?.file_b || 'Student B'}
                code={rightCode}
                highlights={rightHighlights}
                panelRef={rightRef}
                isLeft={false}
                onScroll={() => syncScroll(rightRef, leftRef)}
              />
            </div>

            {job?.review_notes && (
              <Card>
                <div className="font-semibold text-slate-950 dark:text-white mb-1">Review Note</div>
                <div className="text-sm text-slate-600 dark:text-slate-400">{job.review_notes}</div>
              </Card>
            )}

            <div className="text-center text-[11px] text-slate-500 dark:text-slate-400">
              Changes update the pair status immediately. Use "Back to all pairs" to return to the ranked list.
            </div>
          </div>
        ) : null}
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

const BLOCK_STYLES = {
  identical: {
    border: 'border-red-200 dark:border-red-800/40',
    chip: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
    label: 'identical block',
  },
  renamed: {
    border: 'border-amber-200 dark:border-amber-800/40',
    chip: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
    label: 'renamed variables',
  },
  logic: {
    border: 'border-blue-200 dark:border-blue-800/40',
    chip: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
    label: 'uncommon logic match',
  },
};

function sliceCodeLines(code, rangeKey) {
  // Extract the exact source lines a matching block spans so the professor
  // sees the copied region verbatim, not just a line range.
  const lines = String(code || '').split('\n');
  const [start, end] = String(rangeKey || '').split('-').map(Number);
  if (!isNaN(start) && !isNaN(end)) {
    return lines.slice(start - 1, end);
  }
  return [];
}

function BlockDetail({ block, codeA, codeB }) {
  const cat = cloneCategory(block);
  const style = BLOCK_STYLES[cat] || BLOCK_STYLES.logic;
  const sliceA = sliceCodeLines(codeA, block.lines_a);
  const sliceB = sliceCodeLines(codeB, block.lines_b);
  const startA = Number(String(block.lines_a || '0').split('-')[0]) || 0;
  const paneClass = PANEL_COLORS[cat] || PANEL_COLORS.logic;

  return (
    <div className={`rounded-lg border p-3 ${style.border}`}>
      <div className="flex flex-wrap items-center gap-2 text-xs font-medium mb-2">
        <span className="text-slate-500 dark:text-slate-400">Block</span>
        <span className={`rounded px-2 py-0.5 ${style.chip}`}>{style.label}</span>
        <span className={`rounded px-2 py-0.5 ${style.chip}`}>
          {Math.round((block.similarity || 0.75) * 100)}% match
        </span>
        <span className="text-slate-500 dark:text-slate-400">
          File A lines {block.lines_a || 'N/A'} · File B lines {block.lines_b || 'N/A'}
        </span>
      </div>
      <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
        {[
          { title: 'File A', lines: sliceA, base: startA, paneClass },
          { title: 'File B', lines: sliceB, base: Number(String(block.lines_b || '0').split('-')[0]) || 0, paneClass },
        ].map(({ title, lines, base, paneClass }) => (
          <div key={title} className="overflow-hidden rounded-md bg-slate-950">
            <div className="border-b border-slate-800 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
              {title}
            </div>
            <pre className="max-h-40 overflow-auto p-2 font-mono text-xs leading-5 text-slate-100">
              {lines.length > 0 ? lines.map((line, i) => (
                <div key={i} className={`px-1 ${paneClass}`}>
                  <span className="mr-2 select-none text-white/60">{base + i}</span>
                  {line || ' '}
                </div>
              )) : (<div className="text-slate-500">No source available</div>)}
            </pre>
          </div>
        ))}
      </div>
      <p className="mt-2 text-xs leading-5 text-slate-600 dark:text-slate-400">{cloneReason(block)}</p>
    </div>
  );
}

const PANEL_COLORS = {
  identical: 'bg-red-500/60 text-red-50',
  renamed: 'bg-amber-500/50 text-amber-50',
  logic: 'bg-blue-500/50 text-blue-50',
};

const CATEGORY_SWATCH = {
  identical: 'bg-red-500/60 border-red-400',
  renamed: 'bg-amber-500/50 border-amber-400',
  logic: 'bg-blue-500/50 border-blue-400',
};

const CodePanel = ({ title, code, highlights, panelRef, onScroll, isLeft }) => {
  // One shared palette across both files so a matching pair is instantly
  // recognizable: identical (exact copy) -> red, renamed (renamed
  // identifiers/literals) -> amber, logic (modified/semantically similar)
  // -> blue. The panels are still distinguishable by their tinted headers.
  const getHighlightClass = (category) => PANEL_COLORS[category] || PANEL_COLORS.logic;

  return (
    <div className="overflow-hidden rounded-lg border border-[color:var(--border)] bg-white shadow-sm">
      <div className={`border-b px-4 py-3 ${isLeft ? 'border-red-200/70 bg-red-50/50 dark:border-red-900/40 dark:bg-red-950/20' : 'border-blue-200/70 bg-blue-50/50 dark:border-blue-900/40 dark:bg-blue-950/20'}`}>
        <h2 className={`font-semibold ${isLeft ? 'text-red-800 dark:text-red-300' : 'text-blue-800 dark:text-blue-300'}`}>{title}</h2>
        {highlights && highlights.size > 0 && (
          <div className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400">
            {highlights.size} highlighted line{highlights.size === 1 ? '' : 's'}
          </div>
        )}
      </div>
      <div
        ref={panelRef}
        onScroll={onScroll}
        className="max-h-[560px] overflow-auto bg-slate-950 text-sm leading-6 text-slate-100"
      >
        <pre className="min-w-full py-3 font-mono">
          {String(code || '').split('\n').map((line, index) => {
            const lineNumber = index + 1;
            const category = highlights.get(lineNumber);
            const isMatched = Boolean(category);
            // Color coding (per panel palette): identical / renamed /
            // uncommon logic match
            const highlightClass = isMatched
              ? `${getHighlightClass(category)}`
              : '';
            return (
              <div
                key={lineNumber}
                className={`grid grid-cols-[52px_1fr] px-3 ${highlightClass}`}
              >
                <span className={`select-none pr-3 text-right ${isMatched ? 'text-white/70' : 'text-slate-500'}`}>{lineNumber}</span>
                <code className="whitespace-pre">{line || ' '}</code>
              </div>
            );
          })}
        </pre>
      </div>
    </div>
  );
};