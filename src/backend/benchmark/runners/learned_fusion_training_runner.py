"""Train the production learned-fusion scoring model on combined datasets.

Fits a logistic classifier over the seven production similarity features
(ast, fingerprint, embedding, ngram, winnowing, logic_flow, coverage) on the
combined IR-Plag + conplag labeled pairs, evaluates it with honest
leave-one-case/problem-out cross-validation, and writes the version-1 JSON
artifact consumed by :class:`LearnedFusionScorer` in ``BatchDetectionService``.

The rule-based production score is measured on the same pairs as the
baseline, so the report shows the uplift the learned model provides before
the artifact replaces the rule-based path.
"""

from __future__ import annotations

import csv
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.backend.benchmark.runners.engine_evaluation_runner import LabeledPair
from src.backend.engines.scoring.learned_fusion import (
    ARTIFACT_NAME,
    ARTIFACT_VERSION,
    DEFAULT_FEATURE_NAMES,
    MODELS_DIR,
)

logger = logging.getLogger(__name__)

SUPPORTED_DATASETS: Tuple[str, ...] = ("IR-Plag-Dataset", "conplag")
MODEL_DESCRIPTION = "LogisticRegression(class_weight=balanced)"


@dataclass
class LearnedFusionReport:
    """Serializable report for the learned fusion training workflow."""

    generated_at: str
    train_datasets: List[str]
    pair_count: int
    positive_pairs: int
    negative_pairs: int
    feature_names: List[str]
    production_fused_auc: float
    production_fused_f1_best: float
    production_fused_threshold: float
    logo_auc: float
    logo_f1_best: float
    logo_threshold: float
    logo_fold_count: int
    coefficient_weights: Dict[str, float]
    intercept: float
    artifact_path: str
    logo_per_dataset: Dict[str, float] = field(default_factory=dict)
    logo_notes: str = "leave-one-case/problem-out across IR-Plag + conplag"
    runtime_seconds: float = 0.0

    def to_json_dict(self) -> Dict[str, Any]:
        """Convert to a JSON-safe dictionary."""
        return asdict(self)

    def save_json(self, path: Path) -> Path:
        """Write JSON report to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_json_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def save_markdown(self, path: Path) -> Path:
        """Write Markdown report to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        lines: List[str] = [
            "# Learned Fusion Training Report",
            "",
            f"- Generated: `{self.generated_at}`",
            f"- Train datasets: `{', '.join(self.train_datasets)}`",
            (
                f"- Pairs: `{self.pair_count}` "
                f"({self.positive_pairs} positive, {self.negative_pairs} negative)"
            ),
            f"- Features: `{', '.join(self.feature_names)}`",
            "",
            "## Honest Cross-Validation (LOGO)",
            "",
            "| Scorer | AUC-ROC | Best F1 | Threshold |",
            "| --- | ---: | ---: | ---: |",
            (
                f"| Production fused (rule) | {self.production_fused_auc:.4f} | "
                f"{self.production_fused_f1_best:.4f} | "
                f"{self.production_fused_threshold:.2f} |"
            ),
            (
                f"| Learned fusion (LOGO) | {self.logo_auc:.4f} | "
                f"{self.logo_f1_best:.4f} | {self.logo_threshold:.2f} |"
            ),
            "",
            f"- LOGO folds: `{self.logo_fold_count}`",
            f"- Notes: {self.logo_notes}",
        ]
        if self.logo_per_dataset:
            lines.extend(
                [
                    "",
                    "### Per-Dataset LOGO AUC",
                    "",
                    "| Dataset | AUC-ROC |",
                    "| --- | ---: |",
                ]
            )
            for dataset_name in sorted(self.logo_per_dataset):
                lines.append(
                    f"| {dataset_name} | "
                    f"{self.logo_per_dataset[dataset_name]:.4f} |"
                )
        lines.extend(
            [
                "",
                "## Learned Coefficients",
                "",
                "| Feature | Weight |",
                "| --- | ---: |",
            ]
        )
        for feature_name in self.feature_names:
            lines.append(
                f"| {feature_name} | "
                f"{self.coefficient_weights.get(feature_name, 0.0):.4f} |"
            )
        lines.extend(
            [
                f"| _intercept_ | {self.intercept:.4f} |",
                "",
                f"- Artifact: `{self.artifact_path}`",
                "",
                (
                    "Removing the artifact reverts production scoring to the "
                    "rule-based path."
                ),
            ]
        )
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path


class LearnedFusionTrainingRunner:
    """Train the learned fusion scorer on combined labeled datasets."""

    def __init__(
        self,
        output_dir: Path,
        dataset_roots: Optional[List[Path]] = None,
        threshold_step: float = 0.02,
        seed: int = 42,
    ) -> None:
        """Initialize the training runner.

        Args:
            output_dir: Directory for JSON/Markdown training reports.
            dataset_roots: Roots to search for labeled datasets; defaults to
                ``data/datasets`` and ``data/bigger_datasets``.
            threshold_step: Step size for the best-F1 threshold sweep.
            seed: Random seed for the logistic classifier.
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.dataset_roots = dataset_roots or self._default_dataset_roots()
        self.threshold_step = threshold_step
        self.seed = seed
        self.feature_names: List[str] = list(DEFAULT_FEATURE_NAMES)

    def run(
        self,
        enabled_datasets: Optional[List[str]] = None,
        artifact_path: Optional[Path] = None,
    ) -> LearnedFusionReport:
        """Execute the training workflow and write the model artifact.

        Args:
            enabled_datasets: Datasets to train on; defaults to all supported.
            artifact_path: Where to write the JSON artifact; defaults to the
                production models directory consumed at scoring time.

        Returns:
            The populated training report.

        Raises:
            FileNotFoundError: When no requested dataset is present locally.
        """
        started = time.time()
        datasets = list(enabled_datasets or SUPPORTED_DATASETS)
        unsupported = [name for name in datasets if name not in SUPPORTED_DATASETS]
        if unsupported:
            raise ValueError(f"Unsupported training datasets: {', '.join(unsupported)}")

        pairs = self._load_pairs(datasets)
        if not pairs:
            raise FileNotFoundError(
                "No labeled pairs found; checked roots: "
                + ", ".join(str(root) for root in self.dataset_roots)
            )

        rows = self._extract_feature_rows(pairs)
        labels = [pair.label for pair in pairs]
        groups = [self._group_key(pair) for pair in pairs]

        production_scores = [row["raw_score"] for row in rows]
        production_auc = self._auc(production_scores, labels)
        production_best = self._best_threshold(production_scores, labels)

        oof_by_index, fold_count = self._logo_cross_validate(rows, labels, groups)
        oof_indices = sorted(oof_by_index)
        logo_scores = [oof_by_index[index] for index in oof_indices]
        logo_labels = [labels[index] for index in oof_indices]
        logo_auc = self._auc(logo_scores, logo_labels)
        logo_best = self._best_threshold(logo_scores, logo_labels)
        logo_per_dataset = self._logo_auc_per_dataset(oof_by_index, labels, pairs)

        coefficient_weights, intercept = self._fit_final_model(rows, labels)

        target_path = (
            Path(artifact_path) if artifact_path else MODELS_DIR / ARTIFACT_NAME
        )
        self._write_artifact(
            target_path,
            datasets,
            pairs,
            coefficient_weights,
            intercept,
            production_auc,
            logo_auc,
            logo_best,
        )

        report = LearnedFusionReport(
            generated_at=datetime.now().isoformat(timespec="seconds"),
            train_datasets=datasets,
            pair_count=len(pairs),
            positive_pairs=sum(labels),
            negative_pairs=sum(1 for label in labels if label == 0),
            feature_names=list(self.feature_names),
            production_fused_auc=round(production_auc, 4),
            production_fused_f1_best=round(production_best["f1"], 4),
            production_fused_threshold=round(production_best["threshold"], 4),
            logo_auc=round(logo_auc, 4),
            logo_f1_best=round(logo_best["f1"], 4),
            logo_threshold=round(logo_best["threshold"], 4),
            logo_fold_count=fold_count,
            coefficient_weights=coefficient_weights,
            intercept=intercept,
            artifact_path=str(target_path),
            logo_per_dataset={
                name: round(value, 4) for name, value in logo_per_dataset.items()
            },
            runtime_seconds=round(time.time() - started, 2),
        )

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report.save_json(self.output_dir / f"learned_fusion_report_{stamp}.json")
        report.save_markdown(self.output_dir / f"learned_fusion_report_{stamp}.md")
        return report

    # ------------------------------------------------------------------
    # Dataset loading
    # ------------------------------------------------------------------

    @staticmethod
    def _default_dataset_roots() -> List[Path]:
        """Return the default dataset search roots."""
        repo_root = Path(__file__).resolve().parents[4]
        return [
            repo_root / "data" / "datasets",
            repo_root / "data" / "bigger_datasets",
        ]

    def _find_dataset_dir(self, dataset_name: str) -> Path:
        """Locate one dataset directory across the configured roots."""
        for root in self.dataset_roots:
            candidate = root / dataset_name
            if candidate.exists():
                return candidate
        raise FileNotFoundError(
            f"Dataset {dataset_name} not found under: "
            + ", ".join(str(root) for root in self.dataset_roots)
        )

    def _load_pairs(self, dataset_names: List[str]) -> List[LabeledPair]:
        """Load labeled pairs from every requested dataset."""
        all_pairs: List[LabeledPair] = []
        for dataset_name in dataset_names:
            if dataset_name == "IR-Plag-Dataset":
                pairs = self._load_ir_plag_pairs()
            elif dataset_name == "conplag":
                pairs = self._load_conplag_pairs()
            else:  # pragma: no cover - guarded by run()
                raise ValueError(f"Unsupported training dataset: {dataset_name}")
            logger.info(
                "Loaded %s pairs for %s (%s positive)",
                len(pairs),
                dataset_name,
                sum(pair.label for pair in pairs),
            )
            all_pairs.extend(pairs)
        return all_pairs

    def _load_ir_plag_pairs(self) -> List[LabeledPair]:
        """Load every IR-Plag case as original-vs-other labeled pairs."""
        root = self._find_dataset_dir("IR-Plag-Dataset")
        pairs: List[LabeledPair] = []
        for case_dir in sorted(root.glob("case-*")):
            original_files = sorted((case_dir / "original").glob("*.java"))
            if not original_files:
                logger.warning("No original file for %s", case_dir.name)
                continue
            original_code = self._read_code(original_files[0])
            for role, sub_dir, label in (
                ("plag", "plagiarized", 1),
                ("non", "non-plagiarized", 0),
            ):
                for other_path in sorted((case_dir / sub_dir).rglob("*.java")):
                    pairs.append(
                        LabeledPair(
                            pair_id=(
                                f"{case_dir.name}:{role}:"
                                f"{other_path.parent.name}:{other_path.name}"
                            ),
                            code_a=original_code,
                            code_b=self._read_code(other_path),
                            label=label,
                            metadata={
                                "dataset": "IR-Plag-Dataset",
                                "case": case_dir.name,
                                "role": role,
                            },
                        )
                    )
        return pairs

    def _load_conplag_pairs(self) -> List[LabeledPair]:
        """Load ConPlag pairs from the train and test pair lists."""
        root = self._find_dataset_dir("conplag")
        pair_ids: List[str] = []
        for split_file in ("train_pairs.csv", "test_pairs.csv"):
            split_path = root / "versions" / split_file
            if not split_path.exists():
                logger.warning("Missing ConPlag split file %s", split_path)
                continue
            with split_path.open("r", encoding="utf-8") as handle:
                pair_ids.extend(
                    row[0].strip()
                    for row in csv.reader(handle)
                    if row and row[0].strip()
                )

        label_lookup: Dict[str, Dict[str, str]] = {}
        labels_path = root / "versions" / "labels.csv"
        with labels_path.open("r", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                label_lookup[f"{row['sub1']}_{row['sub2']}"] = row
                label_lookup[f"{row['sub2']}_{row['sub1']}"] = row

        pairs: List[LabeledPair] = []
        version_dir = root / "versions" / "version_1"
        for pair_id in pair_ids:
            pair_dir = version_dir / pair_id
            code_files = sorted(pair_dir.glob("*.java"))
            if len(code_files) != 2:
                logger.warning("Skipping malformed ConPlag pair %s", pair_id)
                continue
            label_row = label_lookup.get(pair_id)
            if label_row is None:
                logger.warning("Missing label for ConPlag pair %s", pair_id)
                continue
            pairs.append(
                LabeledPair(
                    pair_id=pair_id,
                    code_a=self._read_code(code_files[0]),
                    code_b=self._read_code(code_files[1]),
                    label=int(label_row["verdict"]),
                    metadata={
                        "dataset": "conplag",
                        "problem": label_row["problem"],
                    },
                )
            )
        return pairs

    @staticmethod
    def _read_code(path: Path) -> str:
        """Read one source file."""
        return path.read_text(encoding="utf-8", errors="replace")

    @staticmethod
    def _group_key(pair: LabeledPair) -> str:
        """Return the LOGO fold key: IR-Plag case or ConPlag problem."""
        metadata = pair.metadata or {}
        return str(metadata.get("case") or metadata.get("problem") or pair.pair_id)

    # ------------------------------------------------------------------
    # Feature extraction and training
    # ------------------------------------------------------------------

    def _extract_feature_rows(self, pairs: List[LabeledPair]) -> List[Dict[str, float]]:
        """Score every pair through the production path and collect features.

        The currently deployed learned artifact is neutralized so features and
        the rule-based baseline are measured without the outgoing model's
        influence on the primary score.
        """
        from src.backend.application.services.batch_detection_service import (
            BatchDetectionService,
        )

        service = BatchDetectionService()
        service.learned_scorer = None

        submissions: Dict[str, str] = {}
        specs: List[Dict[str, Any]] = []
        for index, pair in enumerate(pairs):
            file_a = f"pair_{index:04d}_a.java"
            file_b = f"pair_{index:04d}_b.java"
            submissions[file_a] = pair.code_a
            submissions[file_b] = pair.code_b
            specs.append({"file_a": file_a, "file_b": file_b, "label": pair.label})

        started = time.time()
        results = service.compare_pairs(submissions=submissions, pairs=specs)
        result_by_key: Dict[Tuple[str, str], Dict[str, float]] = {}
        for result in results:
            result_by_key[self._normalize_pair(result.file_a, result.file_b)] = dict(
                result.features or {}
            )

        rows: List[Dict[str, float]] = []
        for index in range(len(pairs)):
            expected_key = self._normalize_pair(
                f"pair_{index:04d}_a.java",
                f"pair_{index:04d}_b.java",
            )
            feature_row = result_by_key.get(expected_key, {})
            row = {
                name: float(feature_row.get(name, 0.0) or 0.0)
                for name in self.feature_names
            }
            row["raw_score"] = float(feature_row.get("raw_score", 0.0) or 0.0)
            rows.append(row)
            if (index + 1) % 25 == 0 or index + 1 == len(pairs):
                logger.info(
                    "Extracted %s/%s pair feature rows in %.1fs",
                    index + 1,
                    len(pairs),
                    time.time() - started,
                )
        return rows

    def _fit_final_model(
        self, rows: List[Dict[str, float]], labels: List[int]
    ) -> Tuple[Dict[str, float], float]:
        """Fit the production logistic model on all pairs."""
        classifier = self._fit_logistic(rows, labels)
        coefficient_weights = {
            name: float(weight)
            for name, weight in zip(self.feature_names, classifier.coef_[0])
        }
        return coefficient_weights, float(classifier.intercept_[0])

    def _fit_logistic(self, rows: List[Dict[str, float]], labels: List[int]) -> Any:
        """Fit a balanced logistic classifier over the feature rows."""
        try:
            from sklearn.linear_model import LogisticRegression
        except ImportError as exc:  # pragma: no cover - environment specific
            raise RuntimeError(
                "scikit-learn is required for learned fusion training"
            ) from exc

        matrix = [[row[name] for name in self.feature_names] for row in rows]
        classifier = LogisticRegression(
            class_weight="balanced", max_iter=1000, random_state=self.seed
        )
        classifier.fit(matrix, labels)
        return classifier

    def _logo_cross_validate(
        self,
        rows: List[Dict[str, float]],
        labels: List[int],
        groups: List[str],
    ) -> Tuple[Dict[int, float], int]:
        """Run leave-one-group-out cross-validation.

        Returns the out-of-fold probability for each scored pair keyed by its
        pair index, and the number of folds that could be trained. Folds whose
        training split lacks a class are skipped with a warning.
        """
        unique_groups = sorted(set(groups))
        held_out_indices = {
            group: [index for index, value in enumerate(groups) if value == group]
            for group in unique_groups
        }

        oof_by_index: Dict[int, float] = {}
        fold_count = 0
        for group in unique_groups:
            held_out = set(held_out_indices[group])
            train_rows = [
                row for index, row in enumerate(rows) if index not in held_out
            ]
            train_labels = [
                label for index, label in enumerate(labels) if index not in held_out
            ]
            if len(set(train_labels)) < 2:
                logger.warning(
                    "Skipping LOGO fold %s: training split has one class", group
                )
                continue
            classifier = self._fit_logistic(train_rows, train_labels)
            matrix = [
                [rows[index][name] for name in self.feature_names]
                for index in held_out_indices[group]
            ]
            probabilities = classifier.predict_proba(matrix)[:, 1]
            for index, probability in zip(held_out_indices[group], probabilities):
                oof_by_index[index] = float(probability)
            fold_count += 1
            logger.info(
                "LOGO fold %s done (%s/%s)", group, fold_count, len(unique_groups)
            )
        return oof_by_index, fold_count

    def _logo_auc_per_dataset(
        self,
        oof_by_index: Dict[int, float],
        labels: List[int],
        pairs: List[LabeledPair],
    ) -> Dict[str, float]:
        """Compute per-dataset LOGO AUC over the aligned out-of-fold scores."""
        per_dataset_scores: Dict[str, List[float]] = {}
        per_dataset_labels: Dict[str, List[int]] = {}
        for index, score in oof_by_index.items():
            dataset_name = str((pairs[index].metadata or {}).get("dataset", "unknown"))
            per_dataset_scores.setdefault(dataset_name, []).append(score)
            per_dataset_labels.setdefault(dataset_name, []).append(labels[index])
        return {
            name: self._auc(per_dataset_scores[name], per_dataset_labels[name])
            for name in per_dataset_scores
            if len(set(per_dataset_labels[name])) == 2
        }

    def _write_artifact(
        self,
        path: Path,
        datasets: List[str],
        pairs: List[LabeledPair],
        coefficient_weights: Dict[str, float],
        intercept: float,
        production_auc: float,
        logo_auc: float,
        logo_best: Dict[str, float],
    ) -> None:
        """Write the version-1 JSON artifact consumed at scoring time."""
        labels = [pair.label for pair in pairs]
        payload = {
            "version": ARTIFACT_VERSION,
            "feature_names": list(self.feature_names),
            "coefficients": [
                float(coefficient_weights.get(name, 0.0)) for name in self.feature_names
            ],
            "intercept": float(intercept),
            "metadata": {
                "trained_at": datetime.now().isoformat(timespec="seconds"),
                "datasets": list(datasets),
                "pair_count": len(pairs),
                "positive_pairs": sum(labels),
                "negative_pairs": sum(1 for label in labels if label == 0),
                "logo_auc_roc": round(logo_auc, 4),
                "production_fused_auc_roc": round(production_auc, 4),
                "model": MODEL_DESCRIPTION,
                "logo_best_f1": round(logo_best["f1"], 4),
                "logo_best_threshold": round(logo_best["threshold"], 4),
                "logo_notes": ("leave-one-case/problem-out across IR-Plag + conplag"),
                "feature_count": len(self.feature_names),
            },
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info("Wrote learned fusion artifact to %s", path)

    # ------------------------------------------------------------------
    # Metric helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_pair(file_a: str, file_b: str) -> Tuple[str, str]:
        """Build a stable unordered pair key."""
        return tuple(sorted((file_a, file_b)))  # type: ignore[return-value]

    @staticmethod
    def _auc(scores: List[float], labels: List[int]) -> float:
        """Compute ROC-AUC using the Mann-Whitney concordance estimator."""
        positives = [score for score, label in zip(scores, labels) if label == 1]
        negatives = [score for score, label in zip(scores, labels) if label == 0]
        if not positives or not negatives:
            return 0.0

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

    def _best_threshold(
        self, scores: List[float], labels: List[int]
    ) -> Dict[str, float]:
        """Sweep thresholds and return the best-F1 operating point."""
        best: Dict[str, float] = {
            "threshold": 0.5,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
        }
        step_count = max(1, int(round(1.0 / max(self.threshold_step, 1e-4))))
        for step_index in range(step_count + 1):
            threshold = step_index * self.threshold_step
            metrics = self._metrics_at_threshold(scores, labels, threshold)
            if metrics["f1"] > best["f1"]:
                best = {"threshold": threshold, **metrics}
        return best

    @staticmethod
    def _metrics_at_threshold(
        scores: List[float], labels: List[int], threshold: float
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


def run_learned_fusion_training(
    output_dir: Path,
    artifact_path: Optional[Path] = None,
    threshold_step: float = 0.02,
    seed: int = 42,
    enabled_datasets: Optional[List[str]] = None,
) -> LearnedFusionReport:
    """Convenience wrapper used by the CLI."""
    runner = LearnedFusionTrainingRunner(
        output_dir=output_dir,
        threshold_step=threshold_step,
        seed=seed,
    )
    return runner.run(enabled_datasets=enabled_datasets, artifact_path=artifact_path)
