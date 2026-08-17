"""Engine evaluation harness for IntegrityDesk versus real external tools.

Scores every IntegrityDesk engine (via ``BatchDetectionService``, the same path
used by production similarity jobs) and the real MOSS / JPlag / Dolos adapters
(via ``ExternalToolRunner``) against the same labeled pair set, then reports a
comparable metric per scorer: ROC-AUC plus precision / recall / F1 at the best
and default thresholds.

This harness intentionally uses the real adapters instead of the seeded
``_simulate_*`` fallbacks used by ``PANBenchmarkRunner`` so the numbers reflect
actual tool behavior. External tools that are not available locally are reported
with an explicit ``available=False`` status rather than fake scores.

Output: ``reports/engine_evaluation/ENGINE_EVAL_<timestamp>.json`` and
``reports/engine_evaluation/ENGINE_EVAL_<timestamp>.md``.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class LabeledPair:
    """One labeled code pair used by the evaluation harness."""

    pair_id: str
    code_a: str
    code_b: str
    label: int
    language: str = "java"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScorerResult:
    """Metrics for a single scorer (one engine or one external tool)."""

    name: str
    kind: str  # integritydesk | external_tool
    available: bool
    error: str = ""
    support: int = 0
    auc_roc: float = 0.0
    best_threshold: float = 0.0
    best_f1: float = 0.0
    best_precision: float = 0.0
    best_recall: float = 0.0
    default_f1: float = 0.0  # at threshold 0.5
    default_precision: float = 0.0
    default_recall: float = 0.0
    scores: List[float] = field(default_factory=list)
    labels: List[int] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, Any]:
        """Convert to a JSON-safe dictionary."""
        payload = asdict(self)
        payload["scores"] = [round(value, 6) for value in self.scores]
        payload["labels"] = list(self.labels)
        return payload


@dataclass
class EngineEvaluationReport:
    """Serializable report for the engine evaluation harness."""

    run_id: str
    timestamp: str
    dataset_name: str
    language: str
    pair_count: int
    positive_pairs: int
    negative_pairs: int
    scorers: List[ScorerResult]
    runtime_seconds: float
    source_files: Optional[list[str]] = None

    def save_json(self, path: Path) -> Path:
        """Write JSON report to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "dataset_name": self.dataset_name,
            "language": self.language,
            "pair_count": self.pair_count,
            "positive_pairs": self.positive_pairs,
            "negative_pairs": self.negative_pairs,
            "runtime_seconds": round(self.runtime_seconds, 4),
            "source_files": self.source_files,
            "scorers": [scorer.to_json_dict() for scorer in self.scorers],
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def save_markdown(self, path: Path) -> Path:
        """Write Markdown report to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        lines: list[str] = [
            "# Engine Evaluation Report",
            "",
            f"- Run: `{self.run_id}`",
            f"- Generated: `{self.timestamp}`",
            f"- Dataset: `{self.dataset_name}`",
            f"- Language: `{self.language}`",
            f"- Pairs: `{self.pair_count}` ({self.positive_pairs} positive, "
            f"{self.negative_pairs} negative)",
            f"- Runtime: `{self.runtime_seconds:.1f}s`",
            "",
            "## Ranking",
            "",
            "| Scorer | Kind | AUC-ROC | F1@best | P@best | R@best | "
            "F1@0.5 | P@0.5 | R@0.5 | Threshold | Support |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]

        ranked = sorted(
            (scorer for scorer in self.scorers if scorer.available),
            key=lambda item: item.auc_roc,
            reverse=True,
        )
        for scorer in ranked:
            lines.append(
                "| "
                f"{scorer.name} | {scorer.kind} | "
                f"{scorer.auc_roc:.4f} | "
                f"{scorer.best_f1:.4f} | "
                f"{scorer.best_precision:.4f} | "
                f"{scorer.best_recall:.4f} | "
                f"{scorer.default_f1:.4f} | "
                f"{scorer.default_precision:.4f} | "
                f"{scorer.default_recall:.4f} | "
                f"{scorer.best_threshold:.2f} | "
                f"{scorer.support} |"
            )

        unavailable = [scorer for scorer in self.scorers if not scorer.available]
        if unavailable:
            lines.extend(
                [
                    "",
                    "## Unavailable Tools",
                    "",
                    "| Scorer | Reason |",
                    "| --- | --- |",
                ]
            )
            for scorer in unavailable:
                lines.append(f"| {scorer.name} | {scorer.error} |")

        lines.extend(
            [
                "",
                "## Notes",
                "",
                (
                    "- ``integritydesk`` scorers use the production "
                    "``BatchDetectionService`` path; each engine contributes its "
                    "raw pre-fusion score."
                ),
                (
                    "- ``moss``, ``jplag``, ``dolos`` use the real local adapters; "
                    "tools that cannot run locally are reported as unavailable."
                ),
                (
                    "- F1@best is the maximum F1 over a 0.02 threshold sweep; "
                    "F1@0.5 uses the standard 0.5 cutoff."
                ),
            ]
        )

        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    @classmethod
    def from_json(cls, path: Path) -> "EngineEvaluationReport":
        """Load a report previously written by ``save_json``."""
        payload = json.loads(path.read_text(encoding="utf-8"))
        scorers = [ScorerResult(**item) for item in payload["scorers"]]
        return cls(
            run_id=payload["run_id"],
            timestamp=payload["timestamp"],
            dataset_name=payload["dataset_name"],
            language=payload.get("language", ""),
            pair_count=int(payload["pair_count"]),
            positive_pairs=int(payload["positive_pairs"]),
            negative_pairs=int(payload["negative_pairs"]),
            scorers=scorers,
            runtime_seconds=float(payload.get("runtime_seconds", 0.0)),
            source_files=payload.get("source_files"),
        )


class EngineEvaluationRunner:
    """Evaluate IntegrityDesk engines and real external tools on a labeled set."""

    SCORER_KIND_EXTERNAL = "external_tool"
    SCORER_KIND_INTEGRITYDESK = "integritydesk"

    EXTERNAL_TOOLS = ("moss", "jplag", "dolos")

    def __init__(
        self,
        output_dir: Path = Path("reports/engine_evaluation"),
        dataset_root: Optional[Path] = None,
        threshold_step: float = 0.02,
        moss_user_id: str = "",
        enabled_tools: Optional[Iterable[str]] = None,
        pair_limit: Optional[int] = None,
    ) -> None:
        """Initialize the evaluation runner.

        Args:
            output_dir: Directory for report artifacts and caches.
            dataset_root: Optional root dir for the IR-Plag dataset.
            threshold_step: Step size for the threshold sweep.
            moss_user_id: Stanford MOSS user id; MOSS is skipped when empty.
            enabled_tools: External tools to attempt; defaults to all.
            pair_limit: Optional cap on the number of labeled pairs scored.
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.dataset_root = dataset_root or self._default_dataset_root()
        self.threshold_step = threshold_step
        self.moss_user_id = moss_user_id
        self.enabled_tools = set(enabled_tools or self.EXTERNAL_TOOLS)
        self.pair_limit = pair_limit

    def run(self) -> EngineEvaluationReport:
        """Execute the harness and write report artifacts."""
        started = time.time()
        pairs = self._load_ir_plag_pairs()
        if self.pair_limit is not None and self.pair_limit < len(pairs):
            pairs = self._balanced_subset(pairs, self.pair_limit)
        submissions = self._submissions_for_pairs(pairs)

        engine_scorers = self._score_integritydesk_engines(submissions, pairs)
        external_scorers = self._score_external_tools(pairs)

        scorers = engine_scorers + external_scorers
        report = EngineEvaluationReport(
            run_id=f"ENGINE_EVAL_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            timestamp=datetime.now().isoformat(timespec="seconds"),
            dataset_name="IR-Plag-Dataset",
            language="java",
            pair_count=len(pairs),
            positive_pairs=sum(pair.label for pair in pairs),
            negative_pairs=sum(1 for pair in pairs if pair.label == 0),
            scorers=scorers,
            runtime_seconds=time.time() - started,
            source_files=[
                str(path) for path in sorted(self.dataset_root.rglob("*.java"))[:5]
            ],
        )

        report.save_json(self.output_dir / f"{report.run_id}.json")
        report.save_markdown(self.output_dir / f"{report.run_id}.md")
        return report

    def _default_dataset_root(self) -> Path:
        """Return the default IR-Plag dataset root."""
        repo_root = Path(__file__).resolve().parents[4]
        return repo_root / "data" / "datasets" / "IR-Plag-Dataset"

    def _load_ir_plag_pairs(self) -> List[LabeledPair]:
        """Load labeled original-vs-plagiarized / original-vs-non-plagiarized pairs."""
        root = self.dataset_root
        if not root.exists():
            raise FileNotFoundError(f"IR-Plag dataset not found at {root}")

        pairs: List[LabeledPair] = []
        for case_dir in sorted(root.glob("case-*")):
            original_files = sorted((case_dir / "original").glob("*.java"))
            if not original_files:
                logger.warning("No original file for %s", case_dir.name)
                continue
            original_code = self._read_code(original_files[0])
            for plag_path in sorted((case_dir / "plagiarized").rglob("*.java")):
                pairs.append(
                    LabeledPair(
                        pair_id=(
                            f"{case_dir.name}:plag:{plag_path.parent.name}:"
                            f"{plag_path.name}"
                        ),
                        code_a=original_code,
                        code_b=self._read_code(plag_path),
                        label=1,
                        metadata={
                            "case": case_dir.name,
                            "role": "plagiarized",
                            "file_b": str(plag_path),
                        },
                    )
                )
            for negative_path in sorted((case_dir / "non-plagiarized").rglob("*.java")):
                pairs.append(
                    LabeledPair(
                        pair_id=(
                            f"{case_dir.name}:non:{negative_path.parent.name}:"
                            f"{negative_path.name}"
                        ),
                        code_a=original_code,
                        code_b=self._read_code(negative_path),
                        label=0,
                        metadata={
                            "case": case_dir.name,
                            "role": "non-plagiarized",
                            "file_b": str(negative_path),
                        },
                    )
                )
        return pairs

    @staticmethod
    def _read_code(path: Path) -> str:
        """Read one source file."""
        return path.read_text(encoding="utf-8", errors="replace")

    def _balanced_subset(
        self, pairs: List[LabeledPair], limit: int
    ) -> List[LabeledPair]:
        """Take a label-balanced subset when limiting the pair count.

        Slices positives and negatives independently so partial runs still
        produce a meaningful AUC, then interleaves them deterministically.
        """
        positives = [pair for pair in pairs if pair.label == 1]
        negatives = [pair for pair in pairs if pair.label == 0]
        if not positives or not negatives:
            return pairs[:limit]

        positive_slice = positives[: (limit // 2) + (limit % 2)]
        negative_slice = negatives[: (limit // 2)]
        selected: List[LabeledPair] = []
        for index in range(max(len(positive_slice), len(negative_slice))):
            if index < len(positive_slice):
                selected.append(positive_slice[index])
            if index < len(negative_slice):
                selected.append(negative_slice[index])
        return selected

    def _submissions_for_pairs(self, pairs: List[LabeledPair]) -> Dict[str, str]:
        """Build a filename-keyed submission map with unique per-pair names."""
        submissions: Dict[str, str] = {}
        for index, pair in enumerate(pairs):
            file_a = f"pair_{index:04d}_a.java"
            file_b = f"pair_{index:04d}_b.java"
            submissions[file_a] = pair.code_a
            submissions[file_b] = pair.code_b
        return submissions

    def _pair_specs(self, pairs: List[LabeledPair]) -> List[Dict[str, Any]]:
        """Build the pair spec list consumed by ``BatchDetectionService``."""
        specs: List[Dict[str, Any]] = []
        for index, pair in enumerate(pairs):
            specs.append(
                {
                    "file_a": f"pair_{index:04d}_a.java",
                    "file_b": f"pair_{index:04d}_b.java",
                    "label": pair.label,
                }
            )
        return specs

    def _score_integritydesk_engines(
        self,
        submissions: Dict[str, str],
        pairs: List[LabeledPair],
    ) -> List[ScorerResult]:
        """Score all IntegrityDesk engines on every pair using the production path."""
        from src.backend.application.services.batch_detection_service import (
            BatchDetectionService,
        )

        try:
            service = BatchDetectionService()
        except Exception as exc:  # pragma: no cover - environment specific
            logger.exception("Failed to initialize BatchDetectionService")
            return [
                self._unavailable_scorer(
                    "integritydesk", f"BatchDetectionService init failed: {exc}"
                )
            ]

        pair_specs = self._pair_specs(pairs)
        results = service.compare_pairs(
            submissions=submissions,
            pairs=pair_specs,
        )

        # ``compare_pairs`` returns results sorted by score descending, so
        # align features to labels via the stable pair filenames instead of
        # relying on result order.
        pair_keys = list(enumerate(pairs))
        result_by_key: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for result in results:
            file_a = getattr(result, "file_a", "")
            file_b = getattr(result, "file_b", "")
            if file_a and file_b:
                result_by_key[
                    EngineEvaluationRunner._normalize_pair(file_a, file_b)
                ] = dict(getattr(result, "features", {}) or {})

        engine_names = ("ast", "fingerprint", "embedding", "ngram", "winnowing")
        feature_rows: Dict[str, List[float]] = {name: [] for name in engine_names}
        feature_rows["logic_flow"] = []
        feature_rows["fused"] = []
        feature_rows["fused_score"] = []
        feature_rows["baseline_adjusted_score"] = []

        labels: List[int] = []
        for index, pair in pair_keys:
            expected_key = EngineEvaluationRunner._normalize_pair(
                f"pair_{index:04d}_a.java",
                f"pair_{index:04d}_b.java",
            )
            feature_row = result_by_key.get(expected_key, {})
            labels.append(pair.label)
            for name in engine_names:
                feature_rows[name].append(float(feature_row.get(name, 0.0)))
            feature_rows["logic_flow"].append(float(feature_row.get("logic_flow", 0.0)))
            feature_rows["fused"].append(float(feature_row.get("raw_score", 0.0)))
            feature_rows["fused_score"].append(
                float(feature_row.get("fused_score", 0.0))
            )
            feature_rows["baseline_adjusted_score"].append(
                float(feature_row.get("baseline_adjusted_score", 0.0))
            )

        scorers: List[ScorerResult] = []
        for name, scores in feature_rows.items():
            scorers.append(
                self._make_scorer(
                    name=name,
                    kind=self.SCORER_KIND_INTEGRITYDESK,
                    scores=scores,
                    labels=labels,
                )
            )
        return scorers

    def _score_external_tools(
        self,
        pairs: List[LabeledPair],
    ) -> List[ScorerResult]:
        """Score the real MOSS / JPlag / Dolos adapters on every pair."""
        from src.backend.benchmark.runners.external_tool_runner import (
            ExternalToolRunner,
        )

        submissions = self._submissions_for_pairs(pairs)
        pair_tuples = [
            (f"pair_{index:04d}_a.java", f"pair_{index:04d}_b.java")
            for index in range(len(pairs))
        ]

        runner = ExternalToolRunner(moss_user_id=self.moss_user_id)
        tool_results = runner.run_selected_tools(
            tool_ids=self.enabled_tools,
            submissions=submissions,
            pairs=pair_tuples,
        )

        labels = [pair.label for pair in pairs]
        scorers: List[ScorerResult] = []

        for tool_id, payload in tool_results.items():
            pair_scores = self._extract_tool_pair_scores(payload, pair_tuples)
            if pair_scores is None:
                error = str(payload.get("error", "tool unavailable"))
                if not error:
                    error = "tool did not produce pair scores"
                scorers.append(self._unavailable_scorer(tool_id, error))
                continue
            scores = [pair_scores.get(pair_key, 0.0) for pair_key in pair_tuples]
            scorers.append(
                self._make_scorer(
                    name=tool_id,
                    kind=self.SCORER_KIND_EXTERNAL,
                    scores=scores,
                    labels=labels,
                )
            )
        return scorers

    @staticmethod
    def _extract_tool_pair_scores(
        payload: Dict[str, Any],
        pair_tuples: List[Tuple[str, str]],
    ) -> Optional[Dict[Tuple[str, str], float]]:
        """Map normalized external-tool output onto the requested pair keys."""
        rows = payload.get("pairs")
        if not isinstance(rows, list) or not rows:
            return None
        by_key: Dict[Tuple[str, str], float] = {}
        for row in rows:
            file_a = row.get("file_a")
            file_b = row.get("file_b")
            if not file_a or not file_b:
                continue
            score = float(row.get("score", 0.0))
            key = EngineEvaluationRunner._normalize_pair(file_a, file_b)
            by_key[key] = max(0.0, min(1.0, score))
        if not by_key:
            return None
        return by_key

    @staticmethod
    def _normalize_pair(file_a: str, file_b: str) -> Tuple[str, str]:
        """Build a stable unordered pair key."""
        return tuple(sorted((file_a, file_b)))  # type: ignore[return-value]

    def _make_scorer(
        self,
        name: str,
        kind: str,
        scores: List[float],
        labels: List[int],
    ) -> ScorerResult:
        """Compute metrics for one scorer from aligned scores and labels."""
        auc = EngineEvaluationRunner.auc_roc(scores, labels)
        best = EngineEvaluationRunner.best_threshold_metrics(
            scores, labels, self.threshold_step
        )
        default = EngineEvaluationRunner.metrics_at_threshold(scores, labels, 0.5)
        return ScorerResult(
            name=name,
            kind=kind,
            available=True,
            support=len(scores),
            auc_roc=round(auc, 6),
            best_threshold=round(best["threshold"], 4),
            best_f1=round(best["f1"], 6),
            best_precision=round(best["precision"], 6),
            best_recall=round(best["recall"], 6),
            default_f1=round(default["f1"], 6),
            default_precision=round(default["precision"], 6),
            default_recall=round(default["recall"], 6),
            scores=[float(value) for value in scores],
            labels=[int(value) for value in labels],
        )

    @staticmethod
    def _unavailable_scorer(name: str, error: str) -> ScorerResult:
        """Build a scorer result for an unavailable tool."""
        return ScorerResult(
            name=name,
            kind=EngineEvaluationRunner.SCORER_KIND_EXTERNAL,
            available=False,
            error=error,
        )

    @staticmethod
    def auc_roc(scores: List[float], labels: List[int]) -> float:
        """Compute ROC-AUC using the Mann-Whitney concordance estimator."""
        positives = [score for score, label in zip(scores, labels) if label == 1]
        negatives = [score for score, label in zip(scores, labels) if label == 0]
        if not positives or not negatives:
            return 0.0

        # AUC = P(score_positive > score_negative) + 0.5 * P(equal)
        concordant = 0
        ties = 0
        for positive_score in positives:
            for negative_score in negatives:
                if positive_score > negative_score:
                    concordant += 1
                elif positive_score == negative_score:
                    ties += 1

        total = len(positives) * len(negatives)
        return max(0.0, min(1.0, (concordant + 0.5 * ties) / total))

    @classmethod
    def best_threshold_metrics(
        cls,
        scores: List[float],
        labels: List[int],
        step: float = 0.02,
    ) -> Dict[str, float]:
        """Sweep thresholds and return the best-F1 operating point."""
        best: Dict[str, float] = {
            "threshold": 0.5,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
        }
        threshold = 0.0
        while threshold <= 1.000001:
            metrics = cls.metrics_at_threshold(scores, labels, threshold)
            if metrics["f1"] > best["f1"]:
                best = {"threshold": threshold, **metrics}
            threshold += max(step, 1e-4)
        return best

    @staticmethod
    def metrics_at_threshold(
        scores: List[float],
        labels: List[int],
        threshold: float,
    ) -> Dict[str, float]:
        """Compute binary metrics for a single threshold."""
        tp = fp = tn = fn = 0
        for score, label in zip(scores, labels):
            predicted = 1 if score >= threshold else 0
            if predicted == 1 and label == 1:
                tp += 1
            elif predicted == 0 and label == 0:
                tn += 1
            elif predicted == 1 and label == 0:
                fp += 1
            else:
                fn += 1
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (
            2.0 * precision * recall / (precision + recall)
            if (precision + recall)
            else 0.0
        )
        return {
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }


def run_engine_evaluation(
    output_dir: Path = Path("reports/engine_evaluation"),
    dataset_root: Optional[Path] = None,
    threshold_step: float = 0.02,
    moss_user_id: str = "",
    enabled_tools: Optional[Iterable[str]] = None,
    pair_limit: Optional[int] = None,
) -> EngineEvaluationReport:
    """Convenience wrapper used by the CLI."""
    runner = EngineEvaluationRunner(
        output_dir=output_dir,
        dataset_root=dataset_root,
        threshold_step=threshold_step,
        moss_user_id=moss_user_id,
        enabled_tools=enabled_tools,
        pair_limit=pair_limit,
    )
    return runner.run()
