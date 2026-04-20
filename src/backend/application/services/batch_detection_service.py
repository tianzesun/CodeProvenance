"""Batch Detection Service - Process entire folders of student submissions.

Phase 1 features:
- File ingestion (read folder of student submissions)
- All-pairs comparison engine  
- Similarity matrix with ranked suspicious pairs
- Basic report (which pairs scored above threshold)
"""

import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
from dataclasses import dataclass, field
import json

logger = logging.getLogger(__name__)


@dataclass
class ComparisonResult:
    file_a: str
    file_b: str
    score: float
    risk_level: str
    features: Dict[str, float] = field(default_factory=dict)
    contributions: Dict[str, float] = field(default_factory=dict)


def _risk_level(score: float) -> str:
    if score >= 0.9:
        return "CRITICAL"
    elif score >= 0.75:
        return "HIGH"
    elif score >= 0.5:
        return "MEDIUM"
    return "LOW"


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

                if fused.final_score >= self.threshold * 0.5:  # Store even low scores
                    pair_result = ComparisonResult(
                        file_a=fa,
                        file_b=fb,
                        score=fused.final_score,
                        risk_level=_risk_level(fused.final_score),
                        features={
                            k: v
                            for k, v in {
                                "ast": features.ast,
                                "fingerprint": features.fingerprint,
                                "embedding": features.embedding,
                                "ngram": features.ngram,
                                "winnowing": features.winnowing,
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
        results = []
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
            results.append(
                ComparisonResult(
                    file_a=fa,
                    file_b=fb,
                    score=fused.final_score,
                    risk_level=_risk_level(fused.final_score),
                    features={
                        k: v
                        for k, v in {
                            "ast": features.ast,
                            "fingerprint": features.fingerprint,
                            "embedding": features.embedding,
                            "ngram": features.ngram,
                            "winnowing": features.winnowing,
                        }.items()
                        if v is not None
                    },
                    contributions=dict(fused.contributions),
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
                    "score": round(r.score, 3),
                    "risk": r.risk_level,
                    "features": {k: round(v, 3) for k, v in r.features.items()},
                }
                for r in suspicious
            ],
            "all_results": [
                {"file_a": r.file_a, "file_b": r.file_b, "score": round(r.score, 3)}
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
