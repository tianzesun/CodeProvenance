"""MVP pipeline wiring for the first five accuracy improvements.

Each feature handed to the ranker is now a real measurement. What was wrong:

- ``fingerprint`` and ``winnowing`` were the same number: the Jaccard of the SET of normalised
  tokens. That set is the vocabulary (keywords, operators, ``ID_0..ID_n``), which any two programs
  largely share, so unrelated submissions scored high. ``fingerprint`` is now the Jaccard of the
  k-gram sets and ``winnowing`` the Jaccard of the winnowed fingerprints, both over
  ``shape_tokens`` (identifier numbering by first appearance is not stable: see normalization).
- ``identifier_rename_score`` was ``min / max`` of the identifier TOKEN counts (about 1.0 for any two
  programs of similar size), so the ranker's "same structure with renamed identifiers" rule was
  nearly always satisfied. It is now the share of ALIGNED identifier positions whose names differ.
- ``ast`` was 1.0 for any two non-Python or unparseable submissions (both sides had no hashes), and
  every submission with the starter code removed was parsed after line surgery that can break
  Python syntax. Starter subtrees are now excluded from the hash multiset, and an AST that cannot
  be computed is left out of the features.
- Two submissions that contain only starter code (or nothing) had empty token sets, which compared as
  1.0, and fail every test identically. With too little student-written code the pair is flagged
  ``insufficient_evidence`` and every evidence feature is 0.
- ``starter_code_overlap`` was passed to the ranker AFTER the starter code had been removed, so the
  ranker discounted (x0.55) a comparison that no longer contained starter code. It is reported in
  ``diagnostics`` instead.
- ``edge_case_behavior_similarity`` duplicated ``runtime_bug_similarity`` (two votes from one
  measurement) and is no longer emitted; ``label`` defaults to None (unlabeled), not 0.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from src.backend.engines.mvp.ast_subtree import ASTSubtreeHasher
from src.backend.engines.mvp.normalization import CodeNormalizer, NormalizedCode
from src.backend.engines.mvp.precision_ranking import PrecisionAt20Ranker, RankedCase
from src.backend.engines.mvp.same_bug import RuntimeOutcome, SameBugDetector
from src.backend.engines.mvp.starter_code import StarterCodeRemover

#: Fewer student-written tokens than this (after starter removal) is no basis for a comparison.
MIN_TOKENS = 30
KGRAM = 5
WINDOW = 4
MAX_ALIGN_TOKENS = 4000
_PYTHON = frozenset({"python", "py", "python3"})


@dataclass(frozen=True)
class MVPAnalysisResult:
    """Pair-level output from the MVP detection pipeline."""

    case_id: str
    features: dict[str, float]
    ranked_case: RankedCase
    label: int | None = None
    category: str = "unknown"
    #: True when there was too little student-written code to compare (features are all 0)
    insufficient_evidence: bool = False
    diagnostics: dict[str, Any] = field(default_factory=dict)


class MVPDetectionPipeline:
    """Run starter removal, normalization, AST hashing, same-bug detection, and ranking."""

    def __init__(
        self,
        starter_sources: Iterable[str] | None = None,
        language: str = "python",
        min_tokens: int = MIN_TOKENS,
    ) -> None:
        starters = list(starter_sources or [])
        self.language = language
        self.min_tokens = min_tokens
        self.normalizer = CodeNormalizer()
        self.starter_remover = StarterCodeRemover(starters, language)
        self.ast_hasher = ASTSubtreeHasher()
        self.same_bug_detector = SameBugDetector()
        self.precision_ranker = PrecisionAt20Ranker()
        self._python = str(language or "python").lower() in _PYTHON
        self._starter_exact: frozenset[str] = frozenset()
        if self._python and starters:
            exact: set[str] = set()
            for source in starters:
                exact |= self.ast_hasher.exact_hashes(source)
            self._starter_exact = frozenset(exact)

    def analyze_pair(
        self,
        case_id: str,
        source_a: str,
        source_b: str,
        *,
        outcomes_a: Iterable[RuntimeOutcome] | None = None,
        outcomes_b: Iterable[RuntimeOutcome] | None = None,
        label: int | None = None,
        category: str = "unknown",
        common_failure_rates: Mapping[str, float] | None = None,
    ) -> MVPAnalysisResult:
        """Analyze one submission pair and return ranker-ready evidence."""
        clean_a = self.starter_remover.remove(source_a)
        clean_b = self.starter_remover.remove(source_b)
        norm_a = self.normalizer.normalize(clean_a.filtered_source, self.language)
        norm_b = self.normalizer.normalize(clean_b.filtered_source, self.language)

        diagnostics: dict[str, Any] = {
            "starter_overlap_a": round(clean_a.starter_overlap, 4),
            "starter_overlap_b": round(clean_b.starter_overlap, 4),
            "tokens_a": len(norm_a.tokens),
            "tokens_b": len(norm_b.tokens),
        }
        features: dict[str, float] = {}
        insufficient = min(len(norm_a.tokens), len(norm_b.tokens)) < self.min_tokens
        if insufficient:
            diagnostics["reason"] = (
                f"fewer than {self.min_tokens} student-written tokens on at least one side "
                "(only starter code, or nearly empty)"
            )
            features = {"fingerprint": 0.0, "winnowing": 0.0, "identifier_rename_score": 0.0}
        else:
            fp_a = set(self.normalizer.kgrams(norm_a.shape_tokens, KGRAM))
            fp_b = set(self.normalizer.kgrams(norm_b.shape_tokens, KGRAM))
            features["fingerprint"] = self._jaccard(fp_a, fp_b)
            features["winnowing"] = self._jaccard(
                self.normalizer.fingerprints(norm_a.shape_tokens, KGRAM, WINDOW),
                self.normalizer.fingerprints(norm_b.shape_tokens, KGRAM, WINDOW),
            )
            features["identifier_rename_score"] = self._rename_score(norm_a, norm_b)

            if self._python:
                comparison = self.ast_hasher.compare(source_a, source_b, exclude_exact=self._starter_exact)
                diagnostics["ast_containment"] = round(comparison.containment, 4)
                if comparison.comparable:
                    features["ast"] = comparison.similarity
                else:
                    diagnostics["ast"] = "unavailable (unparseable, or nothing left after excluding starter code)"
            else:
                diagnostics["ast"] = "not computed (the AST engine handles Python only)"

            # Runtime behaviour is only evidence when there is student code behind it: blank or
            # starter-only submissions fail every test the same way.
            if outcomes_a is not None and outcomes_b is not None:
                finding = self.same_bug_detector.compare(outcomes_a, outcomes_b, common_failure_rates)
                features["runtime_bug_similarity"] = finding.score
                diagnostics["same_bug"] = {
                    "shared_failures": finding.shared_failures,
                    "failing_union": finding.failing_union,
                    "evidence": finding.evidence,
                }

        ranked = self.precision_ranker.rank(
            [{"case_id": case_id, "features": features, "label": label, "category": category}]
        )[0]
        return MVPAnalysisResult(
            case_id=case_id,
            features=features,
            ranked_case=ranked,
            label=label,
            category=category,
            insufficient_evidence=insufficient,
            diagnostics=diagnostics,
        )

    def rank_pairs(self, results: Iterable[MVPAnalysisResult]) -> list[RankedCase]:
        """Rank previously analyzed MVP pair results (labels and categories are carried over)."""
        cases = [
            {"case_id": r.case_id, "features": r.features, "label": r.label, "category": r.category}
            for r in results
        ]
        return self.precision_ranker.rank(cases)

    def precision_at_k(self, results: Iterable[MVPAnalysisResult], k: int = 20) -> float:
        """Precision@K over the labeled results (see ``PrecisionAt20Ranker.precision_at_k``)."""
        cases = [
            {"case_id": r.case_id, "features": r.features, "label": r.label, "category": r.category}
            for r in results
        ]
        return self.precision_ranker.precision_at_k(cases, k)

    @staticmethod
    def _jaccard(left: set, right: set) -> float:
        """Jaccard of two sets; 0.0 when either is empty (nothing to compare)."""
        if not left or not right:
            return 0.0
        return len(left & right) / len(left | right)

    @staticmethod
    def _rename_score(a: NormalizedCode, b: NormalizedCode) -> float:
        """Share of ALIGNED identifier positions whose names differ (0 = none renamed).

        The two shape streams are aligned; at every aligned ``ID`` position the original names are
        compared. Identical code scores 0 (it is a verbatim copy, not a rename). It is only reported
        when at least half of the shorter file aligns: a few matching fragments of unrelated code
        used to give "100% renamed". The score only means something together with a high
        token/AST similarity.
        """
        tokens_a, tokens_b = a.shape_tokens[:MAX_ALIGN_TOKENS], b.shape_tokens[:MAX_ALIGN_TOKENS]
        if not tokens_a or not tokens_b:
            return 0.0
        blocks = [
            block
            for block in SequenceMatcher(None, tokens_a, tokens_b, autojunk=False).get_matching_blocks()
            if block.size >= 3
        ]
        if sum(block.size for block in blocks) < 0.5 * min(len(tokens_a), len(tokens_b)):
            return 0.0
        aligned = renamed = 0
        for block in blocks:
            for offset in range(block.size):
                i, j = block.a + offset, block.b + offset
                if tokens_a[i] == "ID":
                    aligned += 1
                    renamed += a.original_tokens[i] != b.original_tokens[j]
        return renamed / aligned if aligned else 0.0
