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
  TreePine,
  GitBranch,
  BookOpen,
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

function highlightedLines(code, matchingBlocks, isLeft = true) {
  // Returns a Map of line number -> similarity score for colored highlighting
  // If matching_blocks provided, parse line ranges from backend data
  if (matchingBlocks && Array.isArray(matchingBlocks) && matchingBlocks.length > 0) {
    const lineScores = new Map();
    for (const block of matchingBlocks) {
      // Use lines_a for left panel, lines_b for right panel
      const rangeKey = isLeft ? 'lines_a' : 'lines_b';
      const range = block[rangeKey];
      // Use block's similarity if available, otherwise default to 0.75 (medium-high)
      const similarity = typeof block.similarity === 'number' ? block.similarity : 0.75;
      if (range) {
        const [start, end] = range.split('-').map(Number);
        if (!isNaN(start) && !isNaN(end)) {
          for (let i = start; i <= end; i++) {
            // Keep highest similarity score for each line
            if (!lineScores.has(i) || lineScores.get(i) < similarity) {
              lineScores.set(i, similarity);
            }
          }
        }
      }
    }
    return lineScores;
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

function buildEvidenceTree(result) {
  // Build evidence tree from features/scores
  const features = result?.features || {};
  const score = Number(result?.score) || 0;
  
  const evidenceTree = {
    root: {
      name: 'Similarity Analysis',
      score: Math.round(score * 100),
      status: score >= 0.75 ? 'strong' : score >= 0.5 ? 'moderate' : 'weak',
    },
    children: []
  };
  
  // Structural evidence (AST, control flow)
  const structuralScore = features?.ast_similarity || features?.control_flow_similarity || 0;
  if (structuralScore > 0) {
    evidenceTree.children.push({
      name: 'Structural Evidence',
      type: 'branch',
      score: Math.round(structuralScore * 100),
      status: structuralScore >= 0.7 ? 'strong' : structuralScore >= 0.4 ? 'moderate' : 'weak',
      children: [
        {
          name: 'AST Structure',
          type: 'leaf',
          score: Math.round(structuralScore * 100),
          description: 'Code organization patterns show alignment'
        },
        {
          name: 'Control Flow',
          type: 'leaf',
          score: Math.round(structuralScore * 100),
          description: 'Program execution patterns show alignment'
        }
      ]
    });
  }
  
  // Lexical evidence (token, fingerprint)
  const lexicalScore = features?.fingerprint || features?.token_similarity || features?.winnowing || 0;
  if (lexicalScore > 0) {
    evidenceTree.children.push({
      name: 'Lexical Evidence',
      type: 'branch',
      score: Math.round(lexicalScore * 100),
      status: lexicalScore >= 0.7 ? 'strong' : lexicalScore >= 0.4 ? 'moderate' : 'weak',
      children: [
        {
          name: 'Token Sequence',
          type: 'leaf',
          score: Math.round(lexicalScore * 100),
          description: 'Code sequences show overlapping patterns'
        }
      ]
    });
  }
  
  // Semantic evidence
  const semanticScore = features?.embedding_similarity || 0;
  if (semanticScore > 0) {
    evidenceTree.children.push({
      name: 'Semantic Evidence',
      type: 'branch',
      score: Math.round(semanticScore * 100),
      status: semanticScore >= 0.7 ? 'strong' : semanticScore >= 0.4 ? 'moderate' : 'weak',
      children: [
        {
          name: 'Embedding Similarity',
          type: 'leaf',
          score: Math.round(semanticScore * 100),
          description: 'Conceptual alignment between submissions'
        }
      ]
    });
  }
  
  // Divergence evidence (differences)
  const divergenceScore = features?.divergence_score || 0;
  if (divergenceScore > 0) {
    evidenceTree.children.push({
      name: 'Divergence Analysis',
      type: 'branch',
      score: Math.round((1 - divergenceScore) * 100),
      status: divergenceScore >= 0.7 ? 'strong' : divergenceScore >= 0.4 ? 'moderate' : 'weak',
      children: [
        {
          name: 'Structural Differences',
          type: 'leaf',
          score: Math.round((1 - divergenceScore) * 100),
          description: 'Implementation differences reduce similarity concerns'
        }
      ]
    });
  }
  
  return evidenceTree;
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
  const evidenceTree = buildEvidenceTree(activeResult);

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
                  <option value="verdict">By verdict priority</option>
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
                      <th className="w-32 px-4 py-3">Verdict</th>
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
                         {activeResult.file_a} vs {activeResult.file_b}
                       </div>
                       <div className="mt-1 flex items-center gap-2">
                         <VerdictBadge verdict={activeResult.verdict} />
                         <span className="text-sm text-slate-500">{confidenceDisplay}% confidence</span>
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

                  {/* Evidence Tree */}
                  <div className="mt-4 rounded-lg border border-slate-200 bg-white p-4">
                    <div className="flex items-center gap-2 mb-3 text-sm font-semibold text-slate-950">
                      <TreePine size={16} className="text-blue-600" />
                      Evidence Tree
                    </div>
                    <EvidenceTreeNode node={evidenceTree} />
                  </div>

                  {/* Evidence Blocks - matching code blocks between submissions */}
                  {activeResult?.matching_blocks && activeResult.matching_blocks.length > 0 && (
                    <div className="mt-4 rounded-lg border border-slate-200 bg-white p-4">
                      <div className="flex items-center gap-2 mb-3 text-sm font-semibold text-slate-950">
                        <GitBranch size={16} className="text-purple-600" />
                        Evidence Blocks
                      </div>
                      <div className="space-y-3">
                        {activeResult.matching_blocks.slice(0, 5).map((block, idx) => (
                          <div key={idx} className="rounded-lg border border-purple-100 bg-purple-50 p-3">
                            <div className="flex items-center gap-2 text-xs font-medium text-purple-700 mb-2">
                              <span>Block {idx + 1}</span>
                              <span className="px-2 py-0.5 bg-purple-100 rounded">
                                {Math.round((block.similarity || 0.75) * 100)}% match
                              </span>
                            </div>
                            <div className="grid grid-cols-1 gap-2 text-xs">
                              <div>
                                <span className="text-slate-500">File A lines:</span>
                                <span className="ml-1 font-mono text-slate-700">{block.lines_a || 'N/A'}</span>
                              </div>
                              <div>
                                <span className="text-slate-500">File B lines:</span>
                                <span className="ml-1 font-mono text-slate-700">{block.lines_b || 'N/A'}</span>
                              </div>
                            </div>
                          </div>
                        ))}
                        {activeResult.matching_blocks.length > 5 && (
                          <div className="text-xs text-slate-500">
                            +{activeResult.matching_blocks.length - 5} more blocks
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Evidence chips (simplified view) */}
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

                {/* Similarity Legend */}
                <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-xs">
                  <span className="flex items-center gap-2">
                    <span className="w-4 h-3 rounded-sm bg-red-500/30 border border-red-400/50"></span>
                    High similarity (75%+)
                  </span>
                  <span className="flex items-center gap-2">
                    <span className="w-4 h-3 rounded-sm bg-amber-500/25 border border-amber-400/40"></span>
                    Moderate similarity (50-74%)
                  </span>
                  <span className="flex items-center gap-2">
                    <span className="w-4 h-3 rounded-sm bg-emerald-500/20 border border-emerald-400/30"></span>
                    Low similarity (30-49%)
                  </span>
                </div>

               {job?.review_notes && (
                 <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm">
                   <div className="font-semibold text-slate-950 mb-1">Review Note</div>
                   <div className="text-slate-600">{job.review_notes}</div>
                 </div>
               )}

               <div className="text-center text-[11px] text-slate-500">
                 Changes update the pair status immediately. Use "Back to all pairs" to return to the ranked list.
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

function EvidenceTreeNode({ node, depth = 0 }) {
  const statusColors = {
    strong: 'text-red-600 bg-red-50 border-red-100',
    moderate: 'text-amber-600 bg-amber-50 border-amber-200',
    weak: 'text-emerald-600 bg-emerald-50 border-emerald-100',
  };
  const statusColor = statusColors[node.status] || 'text-slate-600 bg-slate-50';
  
  return (
    <div className={`relative ${depth > 0 ? 'ml-4 pl-4 before:absolute before:left-2 before:top-0 before:bottom-0 before:border-slate-200' : ''}`}>
      <div className={`rounded-lg border p-3 mb-2 ${statusColor}`}>
        <div className="flex items-center gap-2">
          {node.type === 'branch' && (
            <GitBranch size={14} className="shrink-0" />
          )}
          {node.type === 'leaf' && (
            <BookOpen size={14} className="shrink-0" />
          )}
          <div className="flex-1">
            <div className="font-semibold text-sm">{node.name}</div>
            {node.description && (
              <div className="text-xs text-slate-500 mt-1">{node.description}</div>
            )}
            {node.score !== undefined && (
              <div className="flex items-center gap-2 mt-1 text-xs">
                <span className="font-medium">{node.score}%</span>
                <span className="text-slate-400">similarity</span>
              </div>
            )}
          </div>
        </div>
      </div>
      {node.children && node.children.length > 0 && (
        <div className="space-y-2">
          {node.children.map((child, idx) => (
            <EvidenceTreeNode 
              key={idx} 
              node={child} 
              depth={depth + 1} 
            />
          ))}
        </div>
      )}
    </div>
  );
}

const CodePanel = ({ title, code, highlights, panelRef, onScroll, isLeft }) => {
  // Get highlight color based on similarity score
  const getHighlightClass = (score) => {
    if (score >= 0.75) return 'bg-red-500/30 outline-red-400/50'; // High similarity - red
    if (score >= 0.5) return 'bg-amber-500/25 outline-amber-400/40'; // Medium - amber
    return 'bg-emerald-500/20 outline-emerald-400/30'; // Low - emerald
  };

  return (
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
            const similarity = highlights.get(lineNumber) || 0;
            const isMatched = similarity > 0;
            // Color coding: Red = highly similar, Amber = moderately similar, Emerald = low similarity
            const highlightClass = isMatched 
              ? `${getHighlightClass(similarity)} outline outline-1`
              : '';
            return (
              <div
                key={lineNumber}
                className={`grid grid-cols-[52px_1fr] px-3 ${highlightClass}`}
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
};