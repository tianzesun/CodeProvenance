"""MVP pipeline wiring for the first five accuracy improvements."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from src.backend.engines.mvp.ast_subtree import ASTSubtreeHasher
from src.backend.engines.mvp.normalization import CodeNormalizer
from src.backend.engines.mvp.precision_ranking import PrecisionAt20Ranker, RankedCase
from src.backend.engines.mvp.same_bug import RuntimeOutcome, SameBugDetector
from src.backend.engines.mvp.starter_code import StarterCodeRemover


@dataclass(frozen=True)
class MVPAnalysisResult:
    """Pair-level output from the MVP detection pipeline."""

    case_id: str
    features: Dict[str, float]
    ranked_case: RankedCase


class MVPDetectionPipeline:
    """Run starter removal, normalization, AST hashing, same-bug detection, and ranking."""

    def __init__(
        self,
        starter_sources: Optional[Iterable[str]] = None,
        language: str = "python",
    ) -> None:
        self.language = language
        self.normalizer = CodeNormalizer()
        self.starter_remover = StarterCodeRemover(starter_sources or [], language)
        self.ast_hasher = ASTSubtreeHasher()
        self.same_bug_detector = SameBugDetector()
        self.precision_ranker = PrecisionAt20Ranker()

    def analyze_pair(
        self,
        case_id: str,
        source_a: str,
        source_b: str,
        *,
        outcomes_a: Optional[Iterable[RuntimeOutcome]] = None,
        outcomes_b: Optional[Iterable[RuntimeOutcome]] = None,
        label: int = 0,
        category: str = "unknown",
    ) -> MVPAnalysisResult:
        """Analyze one submission pair and return ranker-ready evidence."""
        clean_a = self.starter_remover.remove(source_a)
        clean_b = self.starter_remover.remove(source_b)
        normalized_a = self.normalizer.normalize(clean_a.filtered_source, self.language)
        normalized_b = self.normalizer.normalize(clean_b.filtered_source, self.language)

        token_similarity = self._token_jaccard(normalized_a.tokens, normalized_b.tokens)
        ast_similarity = self.ast_hasher.similarity(
            clean_a.filtered_source, clean_b.filtered_source
        )
        same_bug_score = 0.0
        if outcomes_a is not None and outcomes_b is not None:
            same_bug_score = self.same_bug_detector.compare(
                outcomes_a, outcomes_b
            ).score

        features = {
            "fingerprint": token_similarity,
            "winnowing": token_similarity,
            "ast": ast_similarity,
            "runtime_bug_similarity": same_bug_score,
            "edge_case_behavior_similarity": same_bug_score,
            "identifier_rename_score": min(
                normalized_a.identifier_count,
                normalized_b.identifier_count,
            )
            / max(normalized_a.identifier_count, normalized_b.identifier_count, 1),
            "starter_code_overlap": min(
                clean_a.starter_overlap, clean_b.starter_overlap
            ),
        }
        ranked = self.precision_ranker.rank(
            [
                {
                    "case_id": case_id,
                    "features": features,
                    "label": label,
                    "category": category,
                }
            ]
        )[0]
        return MVPAnalysisResult(case_id=case_id, features=features, ranked_case=ranked)

    def rank_pairs(self, results: Iterable[MVPAnalysisResult]) -> List[RankedCase]:
        """Rank previously analyzed MVP pair results."""
        cases = [
            {
                "case_id": result.case_id,
                "features": result.features,
            }
            for result in results
        ]
        return self.precision_ranker.rank(cases)

    def _token_jaccard(self, left: List[str], right: List[str]) -> float:
        """Compute a simple normalized-token Jaccard score."""
        left_set = set(left)
        right_set = set(right)
        if not left_set and not right_set:
            return 1.0
        if not left_set or not right_set:
            return 0.0
        return len(left_set & right_set) / len(left_set | right_set)
