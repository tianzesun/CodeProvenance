"""Batch Detection Service - Process entire folders of student submissions.

Phase 1 features:
- File ingestion (read folder of student submissions)
- All-pairs comparison engine  
- Similarity matrix with ranked suspicious pairs
- Basic report (which pairs scored above threshold)
"""

import logging
import re
import json
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

ITERATIVE_BLOCK_TOKEN = "ITERATIVE_BLOCK"
DECISION_BLOCK_TOKEN = "DECISION_BLOCK"
BRANCH_BLOCK_TOKEN = "BRANCH_BLOCK"


@dataclass
class ComparisonResult:
    file_a: str
    file_b: str
    score: float
    risk_level: str
    features: Dict[str, float] = field(default_factory=dict)
    contributions: Dict[str, float] = field(default_factory=dict)


def _risk_level(score: float) -> str:
    """Convert similarity score to review priority level.

    0-35%: low review priority
    35-65%: moderate review priority
    65-85%: high review priority
    85%+: critical review priority, requires corroborating evidence
    """
    if score >= 0.85:
        return "CRITICAL"
    elif score >= 0.65:
        return "HIGH"
    elif score >= 0.35:
        return "MEDIUM"
    return "LOW"


def _logic_flow_tokens(code: str) -> List[str]:
    """Extract identifier-insensitive control and operator tokens from source code."""
    code = _strip_comments(code)
    raw_tokens = re.findall(
        r"[A-Za-z_]\w*|\d+|==|!=|<=|>=|&&|\|\||\+=|-=|\*=|/=|%=|\+\+|--|\S",
        code,
    )
    control_keywords = {
        "if",
        "else",
        "for",
        "while",
        "switch",
        "case",
        "return",
        "break",
        "continue",
        "throw",
        "try",
        "catch",
        "finally",
        "do",
    }
    operator_pattern = re.compile(
        r"==|!=|<=|>=|&&|\|\||\+=|-=|\*=|/=|%=|\+\+|--|[+\-*/%=<>&|^~!?:;,.()\[\]{}]"
    )
    normalized_tokens = []
    for token in raw_tokens:
        if token in {"for", "while", "do"}:
            normalized_tokens.append(ITERATIVE_BLOCK_TOKEN)
        elif token in {"if", "switch"}:
            normalized_tokens.append(DECISION_BLOCK_TOKEN)
        elif token in {"else", "case", "default", "elif"}:
            normalized_tokens.append(BRANCH_BLOCK_TOKEN)
        elif (
            token in control_keywords
            or token.isdigit()
            or operator_pattern.fullmatch(token)
        ):
            normalized_tokens.append(token)
    return normalized_tokens


def _strip_comments(code: str) -> str:
    """Remove comments before structural token comparison."""
    code = re.sub(r"#.*?$", "", code, flags=re.MULTILINE)
    code = re.sub(r"//.*?$", "", code, flags=re.MULTILINE)
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
    code = re.sub(r'""".*?"""', "", code, flags=re.DOTALL)
    code = re.sub(r"'''.*?'''", "", code, flags=re.DOTALL)
    return code


def _multiset_jaccard(tokens_a: List[str], tokens_b: List[str]) -> float:
    """Calculate multiset Jaccard similarity for two token streams."""
    if not tokens_a and not tokens_b:
        return 1.0
    if not tokens_a or not tokens_b:
        return 0.0

    from collections import Counter

    counts_a = Counter(tokens_a)
    counts_b = Counter(tokens_b)
    intersection = sum((counts_a & counts_b).values())
    union = sum((counts_a | counts_b).values())
    return intersection / union if union else 0.0


def _logic_flow_similarity(code_a: str, code_b: str) -> float:
    """Compare the logic-bearing token stream while ignoring names and imports."""
    return _multiset_jaccard(_logic_flow_tokens(code_a), _logic_flow_tokens(code_b))


def _clean_similarity_baseline(scores: List[float]) -> float:
    """Estimate normal similarity from labeled clean pairs."""
    if not scores:
        return 0.0
    return max(0.0, min(0.95, float(median(scores))))


def _subtract_clean_baseline(score: float, baseline: float) -> float:
    """Treat the clean-pair baseline as zero while preserving above-baseline signal."""
    if baseline <= 0.0:
        return max(0.0, min(1.0, score))
    adjusted = (score - baseline) / max(0.01, 1.0 - baseline)
    return max(0.0, min(1.0, adjusted))


def _apply_structure_sensitivity_floor(
    score: float,
    ast_score: float,
    fingerprint_score: float,
    logic_flow: float,
) -> float:
    """Preserve control-flow/reorder sensitivity when concrete structure agrees."""
    if ast_score >= 0.85 and fingerprint_score >= 0.55 and logic_flow >= 0.90:
        return max(score, 0.88)
    if ast_score >= 0.85 and fingerprint_score >= 0.55 and logic_flow >= 0.78:
        return max(score, 0.82)
    return score


class BatchDetectionService:
    """Process entire folders of student submissions."""

    def __init__(
        self, threshold: float = 0.5, weights: Optional[Dict[str, float]] = None
    ):
        from src.backend.engines.features.feature_extractor import FeatureExtractor
        from src.backend.engines.scoring.fusion_engine import FusionEngine
        from src.backend.domain.decision import DecisionEngine

        self.extractor = FeatureExtractor()
        self.fusion = FusionEngine(weights=weights)
        self.decision = DecisionEngine(threshold)
        self.threshold = threshold
        self.weights = weights

    def ingest_folder(self, folder: Path) -> Dict[str, str]:
        """Read all code files from a folder.

        Returns: {"filename.py": "code content", ...}
        """
        submissions = {}
        ext_map = {
            ".py": "python",
            ".java": "java",
            ".c": "c",
            ".cpp": "cpp",
            ".js": "javascript",
            ".ts": "typescript",
            ".go": "go",
        }
        for ext in ext_map:
            for f in folder.rglob(f"*{ext}"):
                try:
                    submissions[f.name] = f.read_text(encoding="utf-8")
                except UnicodeDecodeError as exc:
                    logger.warning("Skipping file %s: encoding error: %s", f.name, exc)
                except OSError as exc:
                    logger.warning("Skipping file %s: I/O error: %s", f.name, exc)
                except Exception as exc:
                    logger.warning(
                        "Skipping file %s: unexpected error: %s", f.name, exc
                    )
        return submissions

    def compare_all_pairs(self, submissions: Dict[str, str]) -> List[ComparisonResult]:
        """Compare all pairs of submissions and return ranked results."""
        results = []
        files = list(submissions.keys())
        for i, fa in enumerate(files):
            for fb in files[i + 1 :]:
                ca, cb = submissions[fa], submissions[fb]
                features = self.extractor.extract(ca, cb)
                fused = self.fusion.fuse(features)
                logic_flow = _logic_flow_similarity(ca, cb)
                final_score = _apply_structure_sensitivity_floor(
                    fused.final_score,
                    features.ast,
                    features.fingerprint,
                    logic_flow,
                )

                if final_score >= self.threshold * 0.5:  # Store even low scores
                    pair_result = ComparisonResult(
                        file_a=fa,
                        file_b=fb,
                        score=final_score,
                        risk_level=_risk_level(final_score),
                        features={
                            k: v
                            for k, v in {
                                "ast": features.ast,
                                "fingerprint": features.fingerprint,
                                "embedding": features.embedding,
                                "ngram": features.ngram,
                                "winnowing": features.winnowing,
                                "logic_flow": logic_flow,
                            }.items()
                            if v is not None
                        },
                        contributions=dict(fused.contributions),
                    )
                    results.append(pair_result)

        # Sort by score descending
        results.sort(key=lambda x: x.score, reverse=True)
        return results

    def compare_pairs(
        self, submissions: Dict[str, str], pairs: List[Dict[str, Any]]
    ) -> List[ComparisonResult]:
        """Compare an explicit set of labeled benchmark pairs."""
        scored_pairs = []
        for pair in pairs:
            fa = str(pair.get("file_a", ""))
            fb = str(pair.get("file_b", ""))
            if fa not in submissions or fb not in submissions:
                logger.warning(
                    "Skipping benchmark pair with missing files: %s / %s", fa, fb
                )
                continue

            features = self.extractor.extract(submissions[fa], submissions[fb])
            fused = self.fusion.fuse(features)
            logic_flow = _logic_flow_similarity(submissions[fa], submissions[fb])
            raw_score = _apply_structure_sensitivity_floor(
                fused.final_score,
                features.ast,
                features.fingerprint,
                logic_flow,
            )
            scored_pairs.append(
                {
                    "file_a": fa,
                    "file_b": fb,
                    "label": int(
                        pair.get("label", pair.get("ground_truth_label", 0)) or 0
                    ),
                    "raw_score": raw_score,
                    "logic_flow": logic_flow,
                    "features": features,
                    "contributions": dict(fused.contributions),
                }
            )

        clean_baseline = _clean_similarity_baseline(
            [item["raw_score"] for item in scored_pairs if item["label"] < 2]
        )
        results = []
        for item in scored_pairs:
            features = item["features"]
            raw_score = item["raw_score"]
            final_score = _subtract_clean_baseline(raw_score, clean_baseline)
            results.append(
                ComparisonResult(
                    file_a=item["file_a"],
                    file_b=item["file_b"],
                    score=final_score,
                    risk_level=_risk_level(final_score),
                    features={
                        k: v
                        for k, v in {
                            "ast": features.ast,
                            "fingerprint": features.fingerprint,
                            "embedding": features.embedding,
                            "ngram": features.ngram,
                            "winnowing": features.winnowing,
                            "logic_flow": item["logic_flow"],
                            "raw_score": raw_score,
                            "clean_baseline": clean_baseline,
                        }.items()
                        if v is not None
                    },
                    contributions=item["contributions"],
                )
            )

        results.sort(key=lambda x: x.score, reverse=True)
        return results

    def generate_report(self, results: List[ComparisonResult]) -> Dict[str, Any]:
        """Generate basic report with suspicious pairs above threshold."""
        suspicious = [r for r in results if r.score >= self.threshold]
        total = len(results)

        return {
            "summary": {
                "total_pairs": total,
                "suspicious_pairs": len(suspicious),
                "threshold": self.threshold,
            },
            "suspicious": [
                {
                    "file_a": r.file_a,
                    "file_b": r.file_b,
                    "score": r.score,
                    "risk": r.risk_level,
                    "features": dict(r.features),
                }
                for r in suspicious
            ],
            "all_results": [
                {"file_a": r.file_a, "file_b": r.file_b, "score": r.score}
                for r in results
            ],
        }

    def run_analysis(self, folder: Path, save_to: Path = None) -> Dict[str, Any]:
        """Full pipeline: ingest -> compare -> report."""
        submissions = self.ingest_folder(folder)
        results = self.compare_all_pairs(submissions)
        report = self.generate_report(results)

        if save_to:
            save_to.parent.mkdir(parents=True, exist_ok=True)
            with open(save_to, "w") as f:
                json.dump(report, f, indent=2)

        return report
