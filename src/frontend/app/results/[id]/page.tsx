// @ts-nocheck — TODO: add proper types (tracked in types/api.ts)

'use client';

import DashboardLayout from '@/components/DashboardLayout';
import { useAuth } from '@/components/AuthProvider';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { apiClient } from '@/lib/apiClient';

interface WebAnalysisSubmission {
  name: string;
  match_count?: number;
}
import { ButtonLink, Card, Modal } from '@/components/saas/SaaSPrimitives';
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  FileDown,
  Filter,
  Globe,
  Search,
  TreePine,
  GitBranch,
  BookOpen,
  Calendar,
} from 'lucide-react';

// Dispositions available in the Pair Detail Inspector status dropdown.
// Values match the backend pair review statuses.
const REFERENCE_HEADERS = ['x-correlation-id', 'x-request-id'];

/** Generic, status-keyed text; a correlation id is appended when the backend sends one. */
function describeActionError(error, fallback) {
  const status = typeof error?.response?.status === 'number' ? error.response.status : undefined;
  const headers = error?.response?.headers || {};
  const reference = REFERENCE_HEADERS.map((name) => headers[name]).find((v) => typeof v === 'string' && v);

  let message = fallback;
  if (status === 401) message = 'Your session has expired. Please sign in again.';
  else if (status === 403) message = 'You don’t have permission to do that.';
  else if (status === 404) message = 'This analysis could not be found.';
  else if (status === 409) message = 'This analysis was changed elsewhere. Reload the page and try again.';
  else if (status === 429) message = 'Too many requests. Please wait a moment and try again.';

  return reference ? `${message} (Reference: ${reference})` : message;
}

const STATUS_OPTIONS = [
  { value: 'unreviewed', label: 'Unreviewed' },
  { value: 'needs_review', label: 'Needs review' },
  { value: 'confirmed', label: 'Confirmed' },
  { value: 'dismissed', label: 'Dismissed' },
  { value: 'escalated', label: 'Escalated' },
];

function formatPercent(value) {
  const num = Number(value) || 0;
  return `${Math.round(num * 100)}`;
}

function getAssignmentTitle(job) {
  return (
    (typeof job?.assignment_name === 'string' && job.assignment_name.trim()) ||
    (typeof job?.course_name === 'string' && job.course_name.trim()) ||
    'Analysis Results'
  );
}

function formatRunDate(iso) {
  if (!iso) {
    return 'unknown date';
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return 'unknown date';
  }
  return `${date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })} · ${date.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}`;
}

function getThreshold(job) {
  const threshold = Number(job?.threshold);
  return Number.isFinite(threshold) ? threshold : 0.75;
}

function sortResultsByScore(results) {
  return [...results].sort((a, b) => (Number(b.score) || 0) - (Number(a.score) || 0));
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

// mapVerdictToLabel returns labels with spaces ("REVIEW REQUIRED") while these lookups used underscored keys,
// so no badge ever matched and every verdict was grey. The key is normalised first.
function verdictKey(verdict) {
  return String(verdict || '').trim().replace(/\s+/g, '_').toUpperCase();
}

function getVerdictStyle(verdict) {
  const styles = {
    CLEAN: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    REVIEW_REQUIRED: 'bg-blue-100 text-blue-700 border-blue-200',
    STRONG_SIMILARITY_OBSERVED: 'bg-red-100 text-red-700 border-red-200',
  };
  return styles[verdictKey(verdict)] || 'bg-slate-100 text-slate-600 border-slate-200';
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

// Evidence chips come from the blocks the analysis actually isolated. They used to be guessed from the
// *names* of the feature scores, and when nothing matched the page invented "identical blocks, renamed
// variables, uncommon logic match" for the pair.
function getEvidenceTypes(result) {
  const blocks = Array.isArray(result?.matching_blocks) ? result.matching_blocks : [];
  const counts = { identical: 0, renamed: 0, logic: 0 };
  blocks.forEach((block) => {
    counts[cloneCategory(block)] += 1;
  });
  const labels = { identical: 'identical', renamed: 'renamed-variable', logic: 'uncommon-logic' };
  return Object.entries(counts)
    .filter(([, n]) => n > 0)
    .map(([category, n]) => `${n} ${labels[category]} block${n === 1 ? '' : 's'}`);
}

// When a submission's source isn't in the response this returns '', and the panel says so. It used to return
// made-up sample code (`solve_tree`) labelled with the student's file name, which read as their submission.
function getSubmissionCode(submissions, name) {
  const code = submissions?.[name];
  return typeof code === 'string' ? code : '';
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
    return `The snippet matches line-for-line between the two files (${pct}%). Exact matches are the strongest form of textual similarity, although shared starter code or a common idiom can also match exactly.`;
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

// Accepts "12-18" or a single line "12". A single-line block used to be ignored (its end was NaN).
function parseRange(value) {
  if (value === null || value === undefined) return null;
  const parts = String(value).split('-').map((p) => Number(p.trim()));
  const start = parts[0];
  const end = parts.length > 1 ? parts[1] : parts[0];
  if (!Number.isInteger(start) || !Number.isInteger(end) || start < 1 || end < start) return null;
  return [start, Math.min(end, start + 5000)];
}

function highlightedLines(code, matchingBlocks, isLeft = true) {
  // Returns a Map of line number -> category ('identical' | 'renamed' | 'logic').
  // Categories map to clone types: Type 1 = identical, Type 2 = renamed
  // identifiers/literals, Type 3/4 = modified or semantically similar logic.
  const lineCategories = new Map();
  if (!Array.isArray(matchingBlocks)) {
    return lineCategories;
  }
  for (const block of matchingBlocks) {
    const range = parseRange(block?.[isLeft ? 'lines_a' : 'lines_b']);
    if (!range) continue;
    const category = cloneCategory(block);
    for (let i = range[0]; i <= range[1]; i++) {
      // Keep the strongest category for each line
      const existing = lineCategories.get(i);
      if (!existing || CATEGORY_PRIORITY[category] > CATEGORY_PRIORITY[existing]) {
        lineCategories.set(i, category);
      }
    }
  }
  return lineCategories;
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
  const params = useParams();
  const id = Array.isArray(params?.id) ? params.id[0] : params?.id;
  const encId = encodeURIComponent(id || '');
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  // A guest demo session can read this run but never record a verdict on it:
  // the review PATCH is rejected server-side, so the controls stay read-only
  // here rather than showing an optimistic status that was never saved.
  const isGuest = user?.role === 'guest';
  const leftRef = useRef(null);
  const rightRef = useRef(null);
  const syncingRef = useRef(false);

  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  // The open pair is tracked by its key. It was an index into `reviewResults` (only pairs above the job
  // threshold), so opening a pair below that threshold showed whichever pair was open before.
  const [activeKey, setActiveKey] = useState('');
  const [saving, setSaving] = useState(false);
  const [reviewError, setReviewError] = useState('');
  const [savedFlash, setSavedFlash] = useState(false);
  const [pendingConfirm, setPendingConfirm] = useState(null); // { row, status }
  const [blocksExpanded, setBlocksExpanded] = useState(false);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const flashTimerRef = useRef(null);
  const hasUser = Boolean(user);

  // New triage state for ranked table UX
  const [searchTerm, setSearchTerm] = useState('');
  const [minSimilarity, setMinSimilarity] = useState(0.5);
  const [statusFilter, setStatusFilter] = useState('all'); // all | unreviewed | needs_review | dismissed
  const [sortMode, setSortMode] = useState('unreviewed'); // unreviewed | similarity | evidence | verdict
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [pairStatuses, setPairStatuses] = useState({}); // key `${a}::${b}` -> status string
  const [reportsOpen, setReportsOpen] = useState(false); // Reports dropdown in inspector header
  const [detailTab, setDetailTab] = useState('signals'); // signals | blocks | code

  useEffect(() => () => {
    if (flashTimerRef.current) clearTimeout(flashTimerRef.current);
  }, []);

  // Keyed on whether there is a user, not the user object: an auth refresh used to re-run this and
  // replace any status changes with the server copy.
  useEffect(() => {
    if (authLoading) {
      return;
    }
    const loginUrl = `/login?next=${encodeURIComponent(`/results/${id || ''}`)}`;
    if (!hasUser) {
      router.replace(loginUrl);
      return;
    }
    if (!id) {
      setError('This page needs an analysis id.');
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    setLoading(true);
    setError(null);

    apiClient.get(`/api/jobs/${encodeURIComponent(id)}`, { signal: controller.signal })
      .then((res) => {
        setJob(res.data);
        setError(null);
        setLoading(false);
        // Seed local pair statuses from the per-pair review persisted in the DB. A job-level status is
        // not copied onto every pair here (see legacyJobStatus below).
        const pairs = Array.isArray(res.data?.results) ? res.data.results : [];
        const seeded = {};
        pairs.forEach((r) => {
          const k = pairKey(r);
          if (k && r.review_status) {
            seeded[k] = r.review_status;
          }
        });
        setPairStatuses(seeded);
      })
      .catch((err) => {
        if (controller.signal.aborted) {
          return;
        }
        const status = err?.response?.status;
        // Only 401 means "sign in". A 403 used to bounce a signed-in user to the login page.
        if (status === 401) {
          router.replace(loginUrl);
          return;
        }
        setError(
          status === 403
            ? 'You don’t have access to this analysis.'
            : status === 404
              ? 'Assignment not found.'
              : describeActionError(err, 'Failed to load assignment.'),
        );
        setLoading(false);
      });

    return () => controller.abort();
  }, [authLoading, hasUser, id, router, loadAttempt]);

  const updateReview = async (payload) => {
    const res = await apiClient.patch(`/api/job/${encId}/review`, payload);
    setJob(res.data);
  };

  // Saves one pair's status. The new value is shown immediately and rolled back, with a visible error,
  // if the save fails. Before, a failure was an unhandled rejection and the screen kept showing a status
  // that had never been recorded.
  const updatePairStatus = async (row, newStatus) => {
    const key = pairKey(row);
    if (!key || saving || isGuest) {
      return;
    }
    const previous = pairStatuses[key];
    setSaving(true);
    setReviewError('');
    setSavedFlash(false);
    setPairStatuses((prev) => ({ ...prev, [key]: newStatus }));

    try {
      // review_status is the job-level status the backend still expects ("backward compat"). Note it
      // overwrites the whole job's status with this pair's, so the backend should treat it as legacy.
      await updateReview({
        review_status: newStatus,
        pair_reviews: { [key]: { status: newStatus } },
      });
      setSavedFlash(true);
      if (flashTimerRef.current) clearTimeout(flashTimerRef.current);
      flashTimerRef.current = setTimeout(() => setSavedFlash(false), 3000);
    } catch (err) {
      setPairStatuses((prev) => {
        const next = { ...prev };
        if (previous === undefined) delete next[key];
        else next[key] = previous;
        return next;
      });
      setReviewError(describeActionError(err, 'Couldn’t save the review status. The change was not recorded.'));
    } finally {
      setSaving(false);
    }
  };

  // A "Confirmed" pair is a formal finding, so it asks first. Other statuses save straight away.
  const requestStatusChange = (row, newStatus) => {
    if (!row || newStatus === (row._status || 'unreviewed')) {
      return;
    }
    if (newStatus === 'confirmed') {
      setPendingConfirm({ row, status: newStatus });
      return;
    }
    updatePairStatus(row, newStatus);
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
  // A job-level status applies to pairs only for older runs that carry no per-pair review at all. Otherwise
  // reviewing one pair (which also writes the job-level status) made every other pair look reviewed after a reload.
  const legacyJobStatus = results.some((r) => 'review_status' in r) ? null : job?.review_status || null;
  const statusOf = (r) => pairStatuses[pairKey(r)] || r.review_status || legacyJobStatus || 'unreviewed';

  // === New ranked + filterable table data (client-side, no new API) ===
  const tableData = useMemo(() => {
    const base = results;
    let rows = base.map((r, idx) => {
      const sc = Number(r.score) || 0;
      const feats = r.features || {};
      const strong = Object.values(feats).filter((v) => Number(v) >= 0.5).length;
      const k = pairKey(r);
      const st = pairStatuses[k] || r.review_status || legacyJobStatus || 'unreviewed';
      // Use verdict from API if available, otherwise derive from score
      const rawVerdict = r.verdict || (sc >= 0.75 ? (sc >= 0.9 ? 'TRUE' : 'PROBABLE') : sc >= 0.5 ? 'REVIEW' : 'CLEAN');
      const verdict = mapVerdictToLabel(rawVerdict);
      return {
        ...r,
        _rank: idx + 1,
        _score: sc,
        _confidence: typeof r.confidence === 'number' ? Math.max(0, Math.min(1, r.confidence)) : null,
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
        const aOrder = verdictOrder[verdictKey(a.verdict)] ?? 1;
        const bOrder = verdictOrder[verdictKey(b.verdict)] ?? 1;
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
  }, [results, searchTerm, minSimilarity, statusFilter, sortMode, pairStatuses, legacyJobStatus]);

  // Active result for the detail view (falls back to the first row of the filtered table)
  const activeResult = useMemo(
    () => tableData.find((r) => r._key === activeKey) || tableData[0] || null,
    [tableData, activeKey],
  );

  const submissions = job?.submissions && typeof job.submissions === 'object' ? job.submissions : {};
  // Use code_a/code_b from the result if available, otherwise the submission text. If neither exists the
  // panel says the source isn't available.
  const leftCode = (typeof activeResult?.code_a === 'string' && activeResult.code_a) || getSubmissionCode(submissions, activeResult?.file_a);
  const rightCode = (typeof activeResult?.code_b === 'string' && activeResult.code_b) || getSubmissionCode(submissions, activeResult?.file_b);
  const leftHighlights = highlightedLines(leftCode, activeResult?.matching_blocks, true);
  const rightHighlights = highlightedLines(rightCode, activeResult?.matching_blocks, false);
  const score = Number(activeResult?.score) || Number(activeResult?._score) || 0;
  const safeScore = Number.isFinite(score) ? score : 0;
  // This is the similarity score. It was labelled "Confidence", which it isn't; real confidence is
  // shown separately when the analysis returns one.
  const similarityDisplay = Math.round(safeScore * 100);
  const hasConfidence = typeof activeResult?._confidence === 'number';
  const confidencePct = hasConfidence ? Math.round(activeResult._confidence * 100) : 0;
  const evidenceTypes = getEvidenceTypes(activeResult);
  const evidenceSignals = buildEvidenceSignals(activeResult).filter((s) => s.fired);

  // External / Public source matches for this specific pair (for side-by-side integration)
  const externalA = job?.web_analysis?.submissions?.find((s: WebAnalysisSubmission) => s.name === activeResult?.file_a);
  const externalB = job?.web_analysis?.submissions?.find((s: WebAnalysisSubmission) => s.name === activeResult?.file_b);
  const hasExternalMatches = (externalA?.match_count || 0) > 0 || (externalB?.match_count || 0) > 0;

  const openDrawerFor = (row) => {
    setReportsOpen(false);
    setDetailTab('signals');
    setBlocksExpanded(false);
    setActiveKey(row._key);
    setDrawerOpen(true);
    window.scrollTo({ top: 0 });
  };

  const closeDrawer = () => setDrawerOpen(false);

  // Navigate to adjacent pair within the current filtered tableData
  const navigatePair = useCallback((direction: 1 | -1) => {
    if (tableData.length === 0) return;
    setReportsOpen(false);
    const currentKey = pairKey(activeResult);
    const currentTableIdx = tableData.findIndex((r) => r._key === currentKey);
    const nextTableIdx = currentTableIdx + direction;
    if (nextTableIdx < 0 || nextTableIdx >= tableData.length) return;
    setBlocksExpanded(false);
    setActiveKey(tableData[nextTableIdx]._key);
  }, [activeResult, tableData]);

  const currentTableIndex = useMemo(() => {
    const key = pairKey(activeResult);
    return tableData.findIndex((r) => r._key === key);
  }, [activeResult, tableData]);

  // Current disposition of the pair shown in the inspector
  const activeStatus = activeResult?._status || 'unreviewed';

  // Review progress for the workspace header
  const reviewedCount = results.filter((r) => statusOf(r) !== 'unreviewed').length;
  const reviewPct = results.length ? Math.round((reviewedCount / results.length) * 100) : 0;
  const highRiskCount = results.filter(
    (r) => (Number(r.score) || 0) >= 0.75 && statusOf(r) !== 'dismissed',
  ).length;

  // Keyboard navigation: J/K or ArrowLeft/ArrowRight when drawer is open
  useEffect(() => {
    if (!drawerOpen) return;
    const handler = (e: KeyboardEvent) => {
      // Leave browser and OS shortcuts alone (Cmd/Ctrl+K used to be swallowed as "previous pair").
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      // Don't intercept when typing in inputs/textareas
      const target = e.target as HTMLElement;
      const tag = target?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target?.isContentEditable) return;
      if (pendingConfirm) return;
      if (e.key === 'Escape') {
        // Close the Reports menu first, then the pair.
        if (reportsOpen) setReportsOpen(false);
        else closeDrawer();
      } else if (e.key === 'ArrowRight' || e.key === 'j' || e.key === 'J') {
        e.preventDefault();
        navigatePair(1);
      } else if (e.key === 'ArrowLeft' || e.key === 'k' || e.key === 'K') {
        e.preventDefault();
        navigatePair(-1);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [drawerOpen, navigatePair, reportsOpen, pendingConfirm]);

  if (loading) {
    return (
      <DashboardLayout>
        <div role="status" className="flex min-h-[60vh] flex-col items-center justify-center p-8">
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
          <div role="alert" className="max-w-md rounded-lg border border-[color:var(--border)] bg-white p-6 text-center shadow-sm">
            <div className="text-lg font-semibold text-[var(--text-primary)]">{error || 'Assignment not found'}</div>
            <div className="mt-5 flex items-center justify-center gap-3">
              <button
                type="button"
                onClick={() => setLoadAttempt((n) => n + 1)}
                className="inline-flex rounded-md border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              >
                Try again
              </button>
              <Link href="/" className="inline-flex rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white">
                Back to Dashboard
              </Link>
            </div>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="theme-page-container space-y-6">

        {/* ── Header ──────────────────────────────────────────────────────────── */}
        <Card className="overflow-hidden">
          {/* Row 1: identity (left) + page-level action (right) */}
          <div className="flex flex-col gap-4 px-5 py-5 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <div className="inline-flex items-center gap-2 rounded-full border border-blue-600/10 bg-blue-600/[0.06] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-blue-600 dark:border-blue-400/20 dark:bg-blue-400/10 dark:text-blue-400">
                Review Workspace
              </div>
              <h1 className="mt-2.5 truncate text-2xl font-semibold tracking-tight text-slate-950 dark:text-white">
                {getAssignmentTitle(job)}
              </h1>
              <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-500 dark:text-slate-400">
                <span className="inline-flex items-center gap-1.5" title="Course">
                  <BookOpen size={14} /> {job?.course_name || 'No course linked'}
                </span>
                <span className="inline-flex items-center gap-1.5" title="Analysis run time">
                  <Calendar size={14} /> Analyzed {formatRunDate(job?.created_at)}
                </span>
              </div>
            </div>

            {/* Page-level navigation CTA — top-right, aligned with identity.
                Omitted for the guest demo: /dossier is outside the demo's
                route set, so the link would only bounce back to the checker. */}
            {!isGuest && (
              <div className="shrink-0 sm:pt-1">
                <ButtonLink href={`/dossier/${encId}`} variant="secondary">
                  Evidence Dossier &amp; Viva Questions
                </ButtonLink>
              </div>
            )}
          </div>

          {/* Row 2: metrics strip */}
          <div className="flex flex-wrap items-center gap-x-6 gap-y-3 border-t border-slate-200 bg-slate-50/60 px-5 py-3.5 dark:border-slate-800 dark:bg-slate-900/40">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-white px-3 py-1 text-sm font-medium text-slate-700 ring-1 ring-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-700">
                {job?.file_count || Object.keys(submissions).length || 0} submissions
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-white px-3 py-1 text-sm font-medium text-slate-700 ring-1 ring-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-700">
                {results.length} pair{results.length === 1 ? '' : 's'}
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-red-100 px-3 py-1 text-sm font-medium text-red-700 dark:bg-red-900/30 dark:text-red-400">
                {highRiskCount} high-risk
              </span>
            </div>

            {/* Review progress */}
            <div className="ml-auto w-full max-w-xs">
              <div className="flex items-center justify-between text-xs font-medium text-slate-500 dark:text-slate-400">
                <span>Review progress</span>
                <span className="font-mono">{reviewedCount}/{results.length} · {reviewPct}%</span>
              </div>
              <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-slate-200/70 dark:bg-slate-800">
                <div
                  className={`h-full rounded-full transition-all duration-300 ${reviewPct === 100 ? 'bg-emerald-500' : 'bg-blue-600'}`}
                  style={{ width: `${reviewPct}%` }}
                />
              </div>
            </div>
          </div>
        </Card>

        {reviewError && (
          <div role="alert" className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            <AlertCircle size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
            <span className="flex-1">{reviewError}</span>
            <button type="button" onClick={() => setReviewError('')} className="shrink-0 font-semibold underline underline-offset-2">Dismiss</button>
          </div>
        )}

        {/* ── Filters bar ──────────────────────────────────────────────────────── */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Sort (most important action after seeing summary) */}
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Sort by</span>
            <select
              value={sortMode}
              aria-label="Sort pairs by"
              onChange={(e) => setSortMode(e.target.value)}
              className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white"
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
                aria-label="Minimum similarity"
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
              aria-label="Filter by status"
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white"
            >
              <option value="all">All statuses</option>
              <option value="unreviewed">Unreviewed</option>
              <option value="needs_review">Needs review</option>
              <option value="confirmed">Confirmed</option>
              <option value="dismissed">Dismissed</option>
              <option value="escalated">Escalated</option>
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
              aria-label="Search files"
              className="w-full rounded-lg border border-slate-200 bg-white py-1.5 pl-8 pr-3 text-sm outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 dark:border-slate-800 dark:bg-slate-900 dark:text-white dark:placeholder:text-slate-500"
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
        {!(drawerOpen && activeResult) && (
          <Card className="overflow-hidden">
            <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3 dark:border-slate-800">
              <h2 className="text-sm font-semibold text-slate-950 dark:text-white">Suspicious Pairs — Ranked</h2>
              <div className="text-xs text-slate-500 dark:text-slate-400">
                {tableData.length} of {results.length} pairs shown
                {tableData.length > 0 && (
                  <span className="ml-2 text-slate-400 dark:text-slate-600">· click to open · J/K to navigate</span>
                )}
              </div>
            </div>

            {tableData.length === 0 ? (
              <div className="p-8 text-center text-sm text-slate-500 dark:text-slate-400">
                No pairs match the current filters. Try lowering the similarity threshold or clearing the search.
              </div>
            ) : (
              <div className="max-h-[520px] overflow-auto">
                <table className="w-full min-w-[860px] table-fixed border-collapse text-sm">
                  <caption className="sr-only">Pairs ranked by similarity</caption>
                  <thead className="sticky top-0 z-10 bg-slate-50 text-left text-xs font-semibold uppercase tracking-wider text-slate-600 dark:bg-slate-900/50 dark:text-slate-400">
                    <tr>
                      <th scope="col" className="w-12 px-4 py-3">#</th>
                      <th scope="col" className="w-[23%] px-4 py-3">Submission A</th>
                      <th scope="col" className="w-[23%] px-4 py-3">Submission B</th>
                      <th scope="col" className="w-20 px-4 py-3">Score</th>
                      <th scope="col" className="w-28 px-4 py-3">Verdict</th>
                      <th scope="col" className="w-28 px-4 py-3">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                    {tableData.map((row) => {
                      const isActive = row._key === activeKey;
                      const status = row._status || 'unreviewed';
                      const statusTone =
                        status === 'dismissed'
                          ? 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400'
                          : status === 'confirmed'
                            ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                            : status === 'escalated'
                              ? 'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400'
                              : status === 'needs_review'
                                ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
                                : 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400';

                      return (
                        <tr
                          key={row._key}
                          onClick={() => openDrawerFor(row)}
                          tabIndex={0}
                          onKeyDown={(e) => {
                            // The row was click-only. Enter/Space on the row itself (not on its status select) opens it.
                            if (e.target === e.currentTarget && (e.key === 'Enter' || e.key === ' ')) {
                              e.preventDefault();
                              openDrawerFor(row);
                            }
                          }}
                          className={`cursor-pointer transition hover:bg-slate-50 dark:hover:bg-slate-900/50 ${isActive ? 'bg-blue-50/60 dark:bg-blue-900/20' : ''}`}
                        >
                          <td className="px-4 py-3 font-mono text-xs text-slate-500 dark:text-slate-400">{row._denseRank}</td>
                          <td className="truncate px-4 py-3 font-medium text-slate-950 dark:text-white" title={row.file_a}>{row.file_a}</td>
                          <td className="truncate px-4 py-3 font-medium text-slate-950 dark:text-white" title={row.file_b}>{row.file_b}</td>
                          <td className="px-4 py-3">
                            <span className={`font-mono text-sm font-semibold ${row._score >= 0.75 ? 'text-red-600 dark:text-red-400' : row._score >= 0.45 ? 'text-amber-600 dark:text-amber-400' : 'text-slate-600 dark:text-slate-400'}`}>
                              {Math.round((row._score || 0) * 100)}%
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <VerdictBadge verdict={row.verdict} />
                          </td>
                          <td className="px-4 py-3">
                            <select
                              value={status}
                              aria-label={`Status for ${row.file_a} versus ${row.file_b}`}
                              disabled={saving || isGuest}
                              title={
                                isGuest
                                  ? 'Guest demo sessions cannot record verdicts.'
                                  : undefined
                              }
                              onClick={(e) => e.stopPropagation()}
                              onChange={(e) => requestStatusChange(row, e.target.value)}
                              className={`cursor-pointer rounded-full border-0 px-2.5 py-0.5 text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-blue-200 disabled:opacity-50 ${statusTone}`}
                            >
                              {STATUS_OPTIONS.map((opt) => (
                                <option key={opt.value} value={opt.value} className="bg-white text-slate-800 dark:bg-slate-900 dark:text-slate-200">
                                  {opt.label}
                                </option>
                              ))}
                            </select>
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
              {/* Row 1: identity + navigation */}
              <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-200 px-5 py-4 dark:border-slate-800">
                <div className="min-w-0">
                  <button
                    type="button"
                    onClick={closeDrawer}
                    className="text-xs font-semibold text-blue-600 hover:underline dark:text-blue-400"
                  >
                    ← All pairs
                  </button>

                  {/* Filename pair: two large titles + elegant "VS" divider */}
                  <div className="mt-2.5 flex flex-wrap items-baseline gap-x-3 gap-y-1">
                    <h2 className="truncate text-xl font-semibold tracking-tight text-slate-950 dark:text-white">
                      {activeResult.file_a}
                    </h2>
                    <span className="inline-flex shrink-0 items-center rounded-md border border-slate-200 bg-slate-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.15em] text-slate-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400">
                      vs
                    </span>
                    <h2 className="truncate text-xl font-semibold tracking-tight text-slate-950 dark:text-white">
                      {activeResult.file_b}
                    </h2>
                  </div>

                  {/* Verdict + confidence as labeled mini-metrics */}
                  <div className="mt-3.5 flex flex-wrap items-center gap-x-6 gap-y-2">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-400 dark:text-slate-500">
                        Verdict
                      </span>
                      <VerdictBadge verdict={activeResult.verdict} />
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-400 dark:text-slate-500">
                        Similarity
                      </span>
                      <span className="font-mono text-sm font-semibold text-slate-700 dark:text-slate-200">
                        {similarityDisplay}%
                      </span>
                      <div className="h-1 w-16 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                        <div
                          className={`h-full rounded-full ${similarityDisplay >= 75
                              ? 'bg-red-500'
                              : similarityDisplay >= 45
                                ? 'bg-amber-500'
                                : 'bg-emerald-500'
                            }`}
                          style={{ width: `${Math.max(similarityDisplay, 4)}%` }}
                        />
                      </div>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {/* Reports dropdown — consolidates all report / export links */}
                  <div className="relative">
                    <button
                      type="button"
                      onClick={() => setReportsOpen((v) => !v)}
                      aria-haspopup="menu"
                      aria-expanded={reportsOpen}
                      className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800/50"
                    >
                      <FileDown size={14} /> Reports
                      <ChevronDown size={14} className={`transition ${reportsOpen ? 'rotate-180' : ''}`} />
                    </button>
                    {reportsOpen && (
                      <>
                        <div className="fixed inset-0 z-20" onClick={() => setReportsOpen(false)} />
                        <div className="absolute right-0 z-30 mt-2 w-56 overflow-hidden rounded-xl border border-slate-200 bg-white py-1 shadow-lg dark:border-slate-800 dark:bg-slate-900">
                          {[
                            { label: 'HTML Report', href: `/report/${encId}/download` },
                            { label: 'PDF Report', href: `/report/${encId}/download-pdf` },
                            { label: 'Committee Report', href: `/report/${encId}/committee` },
                            { label: 'JSON Data', href: `/report/${encId}/download-json` },
                            { label: 'CSV Data', href: `/report/${encId}/download-csv` },
                            { label: 'Integrity Report', href: `/api/reports/integrity-assessment/${encId}?format=html`, accent: true },
                            { label: 'Integrity PDF', href: `/api/reports/integrity-assessment/${encId}?format=pdf`, accent: true },
                          ].map((item) => (
                            <a
                              key={item.label}
                              href={item.href}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={() => setReportsOpen(false)}
                              className={`block px-4 py-2 text-sm hover:bg-slate-50 dark:hover:bg-slate-800 ${item.accent
                                  ? 'text-blue-700 dark:text-blue-300'
                                  : 'text-slate-700 dark:text-slate-300'
                                }`}
                            >
                              {item.label}
                            </a>
                          ))}
                        </div>
                      </>
                    )}
                  </div>
                  {/* Prev / Next navigation */}
                  <div className="flex items-center gap-1 rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
                    <button
                      type="button"
                      onClick={() => navigatePair(-1)}
                      disabled={currentTableIndex <= 0}
                      title="Previous pair (K / ←)"
                      className="rounded-l-xl px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-30 dark:text-slate-400 dark:hover:bg-slate-800"
                    >
                      ‹ Prev
                    </button>
                    <span className="select-none border-x border-slate-200 px-2 py-2 text-xs text-slate-400 dark:border-slate-700">
                      {currentTableIndex >= 0 ? currentTableIndex + 1 : '–'} / {tableData.length}
                    </span>
                    <button
                      type="button"
                      onClick={() => navigatePair(1)}
                      disabled={currentTableIndex >= tableData.length - 1}
                      title="Next pair (J / →)"
                      className="rounded-r-xl px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-30 dark:text-slate-400 dark:hover:bg-slate-800"
                    >
                      Next ›
                    </button>
                  </div>
                </div>
              </div>

              {/* Review decision for this pair. The status could only be changed from the list, which is
                  hidden while a pair is open, even though the footer said changes save immediately. */}
              <div className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-slate-200 px-5 py-3 dark:border-slate-800">
                <label className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-500 dark:text-slate-400">
                  Review status
                  <select
                    value={activeStatus}
                    disabled={saving || isGuest}
                    title={isGuest ? 'Guest demo sessions cannot record verdicts.' : undefined}
                    onChange={(e) => requestStatusChange(activeResult, e.target.value)}
                    className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium normal-case tracking-normal text-slate-800 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
                  >
                    {STATUS_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                </label>
                {hasConfidence && (
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-400 dark:text-slate-500">Confidence</span>
                    <span className="font-mono text-sm font-semibold text-slate-700 dark:text-slate-200">{confidencePct}%</span>
                  </div>
                )}
                {saving && <span role="status" className="text-xs text-slate-500">Saving…</span>}
                {savedFlash && !saving && (
                  <span role="status" className="inline-flex items-center gap-1 text-xs font-medium text-emerald-600 dark:text-emerald-400">
                    <CheckCircle2 size={13} aria-hidden="true" /> Saved
                  </span>
                )}
              </div>

              {/* Row 2: section tabs */}
              <div className="flex gap-1 overflow-x-auto border-b border-slate-200 px-3 dark:border-slate-800">
                {[
                  { id: 'signals', label: 'Evidence Signals', count: evidenceSignals.length },
                  { id: 'blocks', label: 'Evidence Blocks', count: activeResult?.matching_blocks?.length || 0 },
                  { id: 'code', label: 'Side-by-side', count: null },
                ].map((tab) => {
                  const isActive = detailTab === tab.id;
                  return (
                    <button
                      key={tab.id}
                      type="button"
                      aria-pressed={detailTab === tab.id}
                      onClick={() => setDetailTab(tab.id)}
                      className={`flex items-center gap-1.5 border-b-2 px-3 py-2.5 text-sm font-medium transition ${isActive
                          ? 'border-blue-600 text-blue-700 dark:border-blue-400 dark:text-blue-300'
                          : 'border-transparent text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200'
                        }`}
                    >
                      {tab.label}
                      {tab.count !== null && (
                        <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-semibold ${isActive
                            ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300'
                            : 'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400'
                          }`}>
                          {tab.count}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </Card>

            {detailTab === 'signals' && (
              <div>
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

                {/* Public-source matches for either file (this data was computed but never displayed). Similar
                    code in two submissions can come from a shared public source rather than from each other. */}
                {(externalA || externalB) && (
                  <div className="mt-4">
                    <Card className="overflow-hidden">
                      <div className="flex items-start gap-2 px-5 py-4">
                        <Globe size={16} className="mt-0.5 shrink-0 text-blue-600 dark:text-blue-400" aria-hidden="true" />
                        <div>
                          <div className="text-sm font-semibold text-slate-950 dark:text-white">Public source matches</div>
                          <p className="mt-1 text-xs leading-5 text-slate-600 dark:text-slate-400">
                            {hasExternalMatches
                              ? `${activeResult.file_a}: ${externalA?.match_count || 0} · ${activeResult.file_b}: ${externalB?.match_count || 0} match${(externalA?.match_count || 0) + (externalB?.match_count || 0) === 1 ? '' : 'es'} found on public sources. Check them before attributing the similarity between these two submissions to each other.`
                              : 'No public-source matches were found for either file.'}
                          </p>
                        </div>
                      </div>
                    </Card>
                  </div>
                )}

                {/* Evidence chips — simplified signal summary */}
                {evidenceTypes.length > 0 && (
                  <Card className="mt-4 overflow-hidden">
                    <div className="px-5 py-4">
                      <div className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                        Matched block types
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
              </div>
            )}

            {/* Evidence Blocks - matching code blocks between submissions */}
            {detailTab === 'blocks' && (
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
                  {(activeResult?.matching_blocks || []).slice(0, blocksExpanded ? 200 : 5).map((block, idx) => (
                    <BlockDetail key={idx} block={block} codeA={leftCode} codeB={rightCode} />
                  ))}
                  {(activeResult?.matching_blocks?.length || 0) > 5 && (
                    <button
                      type="button"
                      onClick={() => setBlocksExpanded((v) => !v)}
                      className="text-xs font-semibold text-blue-600 hover:underline dark:text-blue-400"
                    >
                      {blocksExpanded
                        ? 'Show fewer blocks'
                        : `Show ${activeResult.matching_blocks.length - 5} more block${activeResult.matching_blocks.length - 5 === 1 ? '' : 's'}`}
                    </button>
                  )}
                  {(activeResult?.matching_blocks?.length || 0) === 0 && (
                    <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900/40 dark:text-slate-400">
                      No matching code blocks were isolated for this pair. The side-by-side view still shows full-source highlights.
                    </div>
                  )}
                </div>
              </Card>
            )}

            {detailTab === 'code' && (
              <>
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
              </>
            )}

            <div className="text-center text-[11px] text-slate-500 dark:text-slate-400">
              Changes update the pair status immediately. Use the tabs above to inspect signals, blocks, and source.
            </div>
          </div>
        ) : null}

        <Modal
          open={pendingConfirm !== null}
          title="Mark this pair as confirmed?"
          description="Confirmed records a finding for this pair in the review history."
          onClose={() => { if (!saving) setPendingConfirm(null); }}
          footer={(
            <>
              <button
                type="button"
                onClick={() => setPendingConfirm(null)}
                disabled={saving}
                className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={saving}
                onClick={async () => {
                  if (!pendingConfirm) return;
                  const { row, status } = pendingConfirm;
                  await updatePairStatus(row, status);
                  setPendingConfirm(null);
                }}
                className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-60"
              >
                {saving ? 'Saving…' : 'Confirm pair'}
              </button>
            </>
          )}
        >
          {pendingConfirm && (
            <p className="text-sm leading-6 text-slate-600 dark:text-slate-300">
              <strong className="font-semibold">{pendingConfirm.row.file_a}</strong> and{' '}
              <strong className="font-semibold">{pendingConfirm.row.file_b}</strong>. Similarity is a reason to look closer,
              not a finding on its own: confirm only after you have reviewed the code and any public-source matches.
            </p>
          )}
        </Modal>
      </div>
    </DashboardLayout>
  );
}

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
  // sees the matched region verbatim, not just a line range.
  const lines = String(code || '').split('\n');
  const range = parseRange(rangeKey);
  return range ? lines.slice(range[0] - 1, range[1]) : [];
}

function BlockDetail({ block, codeA, codeB }) {
  const cat = cloneCategory(block);
  const style = BLOCK_STYLES[cat] || BLOCK_STYLES.logic;
  const sliceA = sliceCodeLines(codeA, block.lines_a);
  const sliceB = sliceCodeLines(codeB, block.lines_b);
  const startA = parseRange(block.lines_a)?.[0] || 0;
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
          { title: 'File B', lines: sliceB, base: parseRange(block.lines_b)?.[0] || 0, paneClass },
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
        role="region"
        tabIndex={0}
        aria-label={`${title} source code`}
        className="max-h-[560px] overflow-auto bg-slate-950 text-sm leading-6 text-slate-100"
      >
        {!String(code || '').trim() ? (
          <div className="px-4 py-6 text-sm text-slate-400">
            Source code isn’t available for this submission, so nothing can be shown or highlighted.
          </div>
        ) : (
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
        )}
      </div>
    </div>
  );
};
