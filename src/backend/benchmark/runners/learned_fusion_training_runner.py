"""Train the production learned-fusion scoring model on combined datasets.

Fits a logistic classifier over the seven production similarity features
(ast, fingerprint, embedding, ngram, winnowing, logic_flow, coverage) on the
combined labelled pairs, evaluates it with grouped cross-validation that never
puts the same code on both sides of a split, and writes the version-1 JSON
artifact consumed by :class:`LearnedFusionScorer` in ``BatchDetectionService``.

The rule-based production score is measured on the same pairs as the baseline,
so the report shows the uplift the learned model provides before the artifact
replaces the rule-based path.

Datasets differ in what a label means, and the difference matters:

* ``IR-Plag-Dataset``, ``conplag`` and ``kaggle_student_code`` describe pairs of
  *same-assignment* submissions. Their negatives are the hard, product-relevant
  ones: two independent solutions of the same problem.
* ``poolc_600k_python`` labels every pair of accepted solutions to the same
  competitive-programming problem as ``similar`` and every cross-problem pair as
  ``different``. Its positives add Python and short-file diversity, but its
  negatives are trivial; ``poolc_negative_ratio`` (default 0) decides how many
  of them are admitted at all.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import random
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.backend.benchmark.runners.engine_evaluation_runner import LabeledPair
from src.backend.engines.scoring.learned_fusion import (
    ARTIFACT_NAME,
    ARTIFACT_VERSION,
    DEFAULT_FEATURE_NAMES,
    MODELS_DIR,
)

logger = logging.getLogger(__name__)

SUPPORTED_DATASETS: Tuple[str, ...] = (
    "IR-Plag-Dataset",
    "conplag",
    "kaggle_student_code",
    "poolc_600k_python",
)
MODEL_DESCRIPTION = "LogisticRegression(class_weight=balanced)"

#: PoolC holds ~600k pairs; extraction costs seconds per pair, so an unbounded
#: PoolC run is never useful. Used when the operator gives no explicit cap.
DEFAULT_POOLC_MAX_PAIRS = 20_000

#: Bump when the extracted feature values change meaning; it invalidates caches.
FEATURE_CACHE_VERSION = 1

#: File extension per corpus language, so the file-type classifier and the
#: language-specific engines see the right language.
LANGUAGE_EXTENSIONS: Dict[str, str] = {
    "java": ".java",
    "python": ".py",
    "py": ".py",
    "c": ".c",
    "cpp": ".cpp",
    "c++": ".cpp",
    "javascript": ".js",
    "js": ".js",
}


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
    cv_mode: str
    cv_auc: float
    cv_f1_best: float
    cv_threshold: float
    cv_fold_count: int
    coefficient_weights: Dict[str, float]
    intercept: float
    artifact_path: str
    per_dataset_auc: Dict[str, float] = field(default_factory=dict)
    per_dataset_production_auc: Dict[str, float] = field(default_factory=dict)
    pairs_per_dataset: Dict[str, int] = field(default_factory=dict)
    cv_notes: str = ""
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
            f"## Cross-Validation ({self.cv_mode})",
            "",
            "| Scorer | AUC-ROC | Best F1 | Threshold |",
            "| --- | ---: | ---: | ---: |",
            (
                f"| Production fused (rule) | {self.production_fused_auc:.4f} | "
                f"{self.production_fused_f1_best:.4f} | "
                f"{self.production_fused_threshold:.2f} |"
            ),
            (
                f"| Learned fusion (out-of-fold) | {self.cv_auc:.4f} | "
                f"{self.cv_f1_best:.4f} | {self.cv_threshold:.2f} |"
            ),
            "",
            f"- Folds that could be trained: `{self.cv_fold_count}`",
            f"- Notes: {self.cv_notes}",
        ]
        if self.per_dataset_auc or self.pairs_per_dataset:
            lines.extend(
                [
                    "",
                    "### Per-Dataset Breakdown",
                    "",
                    "| Dataset | Pairs | Rule AUC | Out-of-fold AUC |",
                    "| --- | ---: | ---: | ---: |",
                ]
            )
            dataset_names = sorted(
                set(self.per_dataset_auc) | set(self.pairs_per_dataset)
            )
            for dataset_name in dataset_names:
                rule_auc = self.per_dataset_production_auc.get(dataset_name)
                cv_auc = self.per_dataset_auc.get(dataset_name)
                rule_text = "-" if rule_auc is None else f"{rule_auc:.4f}"
                cv_text = "-" if cv_auc is None else f"{cv_auc:.4f}"
                lines.append(
                    f"| {dataset_name} | {self.pairs_per_dataset.get(dataset_name, 0)} "
                    f"| {rule_text} | {cv_text} |"
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
        max_pairs_per_dataset: Optional[int] = None,
        cv_folds: int = 0,
        poolc_negative_ratio: float = 0.0,
        cache_path: Optional[Path] = None,
        dataset_weighting: str = "proportional",
    ) -> None:
        """Initialize the training runner.

        Args:
            output_dir: Directory for JSON/Markdown training reports.
            dataset_roots: Roots to search for labeled datasets; defaults to
                ``data/datasets`` and ``data/bigger_datasets``.
            threshold_step: Step size for the best-F1 threshold sweep.
            seed: Random seed for the logistic classifier, the sampling and the
                fold assignment.
            max_pairs_per_dataset: Optional per-dataset cap. PoolC alone holds
                ~600k pairs, so a cap keeps a run's feature extraction bounded;
                sampling stays balanced between classes when both are present.
            cv_folds: Number of grouped folds for cross-validation. ``0`` keeps
                the original leave-one-group-out scheme; any value >= 2 uses a
                grouped k-fold, which is the only affordable option once a
                corpus contributes hundreds of groups.
            poolc_negative_ratio: Admit at most ``ratio * positives`` PoolC
                cross-problem pairs (its negatives are different problems, not
                independent solutions of the same one). ``0`` uses positives
                only.
            cache_path: Optional JSONL feature cache. Extraction is the
                expensive step (the embedding feature dominates), so a cache
                lets a long run resume and lets alternative training mixes be
                scored without re-extracting.
            dataset_weighting: ``"proportional"`` lets every pair count once, so
                a large corpus dominates the fit. ``"equal"`` gives each corpus
                the same total weight, which keeps the small, product-realistic
                corpora relevant when PoolC is in the mix.
        """
        if dataset_weighting not in {"proportional", "equal"}:
            raise ValueError(
                "dataset_weighting must be 'proportional' or 'equal', got "
                f"{dataset_weighting!r}"
            )
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.dataset_roots = dataset_roots or self._default_dataset_roots()
        self.threshold_step = threshold_step
        self.seed = seed
        self.max_pairs_per_dataset = max_pairs_per_dataset
        self.cv_folds = cv_folds
        self.poolc_negative_ratio = poolc_negative_ratio
        self.cache_path = Path(cache_path) if cache_path else None
        self.dataset_weighting = dataset_weighting
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
        sample_weights = self._sample_weights(pairs)

        production_scores = [row["raw_score"] for row in rows]
        production_auc = self._auc(production_scores, labels)
        production_best = self._best_threshold(production_scores, labels)

        if self.cv_folds and self.cv_folds >= 2:
            oof_by_index, fold_count = self._group_kfold_cross_validate(
                rows, labels, groups, self.cv_folds, sample_weights
            )
            cv_mode = f"grouped {self.cv_folds}-fold"
        else:
            oof_by_index, fold_count = self._logo_cross_validate(
                rows, labels, groups, sample_weights
            )
            cv_mode = "leave-one-group-out"

        oof_indices = sorted(oof_by_index)
        cv_scores = [oof_by_index[index] for index in oof_indices]
        cv_labels = [labels[index] for index in oof_indices]
        cv_auc = self._auc(cv_scores, cv_labels)
        cv_best = self._best_threshold(cv_scores, cv_labels)
        per_dataset_auc = self._auc_per_dataset(oof_by_index, labels, pairs)
        per_dataset_production_auc = self._auc_per_dataset(
            {index: score for index, score in enumerate(production_scores)},
            labels,
            pairs,
        )
        pairs_per_dataset = self._count_per_dataset(pairs)

        coefficient_weights, intercept = self._fit_final_model(
            rows, labels, sample_weights
        )

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
            cv_auc,
            cv_best,
            cv_mode=cv_mode,
            pairs_per_dataset=pairs_per_dataset,
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
            cv_mode=cv_mode,
            cv_auc=round(cv_auc, 4),
            cv_f1_best=round(cv_best["f1"], 4),
            cv_threshold=round(cv_best["threshold"], 4),
            cv_fold_count=fold_count,
            coefficient_weights=coefficient_weights,
            intercept=intercept,
            artifact_path=str(target_path),
            per_dataset_auc={
                name: round(value, 4) for name, value in per_dataset_auc.items()
            },
            per_dataset_production_auc={
                name: round(value, 4)
                for name, value in per_dataset_production_auc.items()
            },
            pairs_per_dataset=pairs_per_dataset,
            cv_notes=self._cv_notes(cv_mode, datasets),
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
            elif dataset_name == "kaggle_student_code":
                pairs = self._load_kaggle_pairs()
            elif dataset_name == "poolc_600k_python":
                pairs = self._load_poolc_pairs()
            else:  # pragma: no cover - guarded by run()
                raise ValueError(f"Unsupported training dataset: {dataset_name}")
            pairs = self._limit_pairs(pairs)
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

    def _load_kaggle_pairs(self) -> List[LabeledPair]:
        """Load the labelled same-classroom student pairs.

        These are Python submissions from one class, so every pair is two
        solutions of the same assignment: the negatives are the hard
        false-positive case the product actually faces.
        """
        root = self._find_dataset_dir("kaggle_student_code")
        csv_path = root / "cheating_dataset.csv"
        if not csv_path.exists():
            raise FileNotFoundError(f"Missing Kaggle pair list: {csv_path}")
        pairs: List[LabeledPair] = []
        with csv_path.open("r", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                file_a = (row.get("File_1") or "").strip()
                file_b = (row.get("File_2") or "").strip()
                path_a, path_b = root / file_a, root / file_b
                if (
                    not file_a
                    or not file_b
                    or not path_a.exists()
                    or not path_b.exists()
                ):
                    logger.warning(
                        "Skipping Kaggle pair with missing files: %s / %s",
                        file_a,
                        file_b,
                    )
                    continue
                pairs.append(
                    LabeledPair(
                        pair_id=f"{file_a}::{file_b}",
                        code_a=self._read_code(path_a),
                        code_b=self._read_code(path_b),
                        label=int(row.get("Label") or 0),
                        language="python",
                        metadata={
                            "dataset": "kaggle_student_code",
                            "group": "classroom",
                        },
                    )
                )
        return pairs

    def _load_poolc_pairs(self) -> List[LabeledPair]:
        """Load a balanced PoolC sample of Python competitive-programming pairs.

        PoolC marks every pair of solutions to the same problem ``similar`` and
        every cross-problem pair ``different``. Only the positives describe the
        clone shape the product scores; the negatives are admitted up to
        ``poolc_negative_ratio`` because they are far easier than a pair of
        independent submissions of the same assignment.
        """
        root = self._find_dataset_dir("poolc_600k_python")
        shards = sorted((root / "data").glob("*.parquet"))
        if not shards:
            raise FileNotFoundError(f"No PoolC parquet shards under {root / 'data'}")

        import pyarrow.parquet as pq

        cap = self.max_pairs_per_dataset
        if cap is None:
            cap = DEFAULT_POOLC_MAX_PAIRS
            logger.info(
                "No --max-pairs given; capping PoolC at %s pairs",
                DEFAULT_POOLC_MAX_PAIRS,
            )
        positive_cap = max(1, cap // 2)
        negative_cap = int(positive_cap * max(0.0, self.poolc_negative_ratio))

        rng = random.Random(self.seed)
        pairs: List[LabeledPair] = []
        positives_taken = 0
        negatives_taken = 0

        for shard in shards:
            meta_rows = pq.read_table(
                shard, columns=["similar", "code1_group", "code2_group"]
            ).to_pylist()
            positive_rows = [
                index for index, row in enumerate(meta_rows) if row["similar"]
            ]
            negative_rows = [
                index for index, row in enumerate(meta_rows) if not row["similar"]
            ]
            wanted_positive = min(len(positive_rows), positive_cap - positives_taken)
            wanted_negative = min(len(negative_rows), negative_cap - negatives_taken)
            chosen = sorted(
                rng.sample(positive_rows, max(0, wanted_positive))
                + rng.sample(negative_rows, max(0, wanted_negative))
            )
            if not chosen:
                continue
            code_rows = (
                pq.read_table(shard, columns=["code1", "code2"])
                .take(chosen)
                .to_pylist()
            )
            for position, row_index in enumerate(chosen):
                meta = meta_rows[row_index]
                label = 1 if meta["similar"] else 0
                pairs.append(
                    LabeledPair(
                        pair_id=f"{shard.stem}:{row_index}",
                        code_a=str(code_rows[position].get("code1") or ""),
                        code_b=str(code_rows[position].get("code2") or ""),
                        label=label,
                        language="python",
                        metadata={
                            "dataset": "poolc_600k_python",
                            "group": self._poolc_group_key(meta),
                        },
                    )
                )
                if label:
                    positives_taken += 1
                else:
                    negatives_taken += 1
            if positives_taken >= positive_cap and negatives_taken >= negative_cap:
                break
        return pairs

    def _limit_pairs(self, pairs: List[LabeledPair]) -> List[LabeledPair]:
        """Cap one dataset at ``max_pairs_per_dataset`` pairs, keeping both classes.

        PoolC is capped inside its own loader because its class mix is
        controlled by ``poolc_negative_ratio`` instead.
        """
        cap = self.max_pairs_per_dataset
        if not cap or len(pairs) <= cap:
            return pairs
        positives = [pair for pair in pairs if pair.label == 1]
        negatives = [pair for pair in pairs if pair.label == 0]
        if not positives or not negatives:
            return pairs[:cap]
        rng = random.Random(self.seed)
        chosen_positives = rng.sample(positives, min(len(positives), max(1, cap // 2)))
        remaining = max(0, cap - len(chosen_positives))
        chosen_negatives = rng.sample(negatives, min(len(negatives), remaining))
        chosen = chosen_positives + chosen_negatives
        return sorted(chosen, key=lambda pair: pair.pair_id)

    @staticmethod
    def _read_code(path: Path) -> str:
        """Read one source file."""
        return path.read_text(encoding="utf-8", errors="replace")

    @staticmethod
    def _poolc_group_key(meta: Dict[str, Any]) -> str:
        """PoolC group as an unordered endpoint-group pair (``small-large``).

        PoolC positives sit inside one group and negatives across two, so the
        unordered endpoint pair keeps related rows in the same CV fold.
        """
        first = int(meta.get("code1_group") or 0)
        second = int(meta.get("code2_group") or 0)
        return f"{min(first, second)}-{max(first, second)}"

    @staticmethod
    def _group_key(pair: LabeledPair) -> str:
        """Return the CV fold key, namespaced by dataset.

        The dataset prefix matters as soon as more than one corpus is loaded: a
        PoolC group ``12`` and a ConPlag problem ``12`` are unrelated and must
        not share a fold.
        """
        metadata = pair.metadata or {}
        dataset = str(metadata.get("dataset", "unknown"))
        group = (
            metadata.get("group")
            or metadata.get("case")
            or metadata.get("problem")
            or pair.pair_id
        )
        return f"{dataset}::{group}"

    # ------------------------------------------------------------------
    # Feature extraction and training
    # ------------------------------------------------------------------

    def _extract_feature_rows(self, pairs: List[LabeledPair]) -> List[Dict[str, float]]:
        """Score every pair through the production path and collect features.

        The currently deployed learned artifact is neutralized so features and
        the rule-based baseline are measured without the outgoing model's
        influence on the primary score. Extracted rows are cached when
        ``cache_path`` is set: extraction is the expensive step, so a cache
        lets a long run resume and lets alternative training mixes be measured
        for the price of a logistic fit.
        """
        from src.backend.application.services.batch_detection_service import (
            BatchDetectionService,
        )

        cached = self._load_feature_cache()
        rows: List[Optional[Dict[str, float]]] = [None] * len(pairs)
        missing: List[int] = []
        for index, pair in enumerate(pairs):
            cache_key = self._cache_key(pair)
            if cache_key in cached:
                rows[index] = cached[cache_key]
            else:
                missing.append(index)
        logger.info(
            "Feature cache: %s/%s rows reused, %s to extract",
            len(pairs) - len(missing),
            len(pairs),
            len(missing),
        )

        if missing:
            service = BatchDetectionService()
            service.learned_scorer = None

            submissions: Dict[str, str] = {}
            specs: List[Dict[str, Any]] = []
            file_names: Dict[int, Tuple[str, str]] = {}
            for index in missing:
                pair = pairs[index]
                extension = self._extension_for(pair.language)
                file_a = f"pair_{index:05d}_a{extension}"
                file_b = f"pair_{index:05d}_b{extension}"
                submissions[file_a] = pair.code_a
                submissions[file_b] = pair.code_b
                specs.append({"file_a": file_a, "file_b": file_b, "label": pair.label})
                file_names[index] = (file_a, file_b)

            started = time.time()
            results = service.compare_pairs(submissions=submissions, pairs=specs)
            result_by_key: Dict[Tuple[str, str], Dict[str, float]] = {}
            for result in results:
                result_by_key[self._normalize_pair(result.file_a, result.file_b)] = (
                    dict(result.features or {})
                )

            extracted: List[Tuple[str, Dict[str, float]]] = []
            for completed, index in enumerate(missing, start=1):
                feature_row = result_by_key.get(
                    self._normalize_pair(*file_names[index]), {}
                )
                row = {
                    name: float(feature_row.get(name, 0.0) or 0.0)
                    for name in self.feature_names
                }
                row["raw_score"] = float(feature_row.get("raw_score", 0.0) or 0.0)
                rows[index] = row
                extracted.append((self._cache_key(pairs[index]), row))
                if completed % 25 == 0 or completed == len(missing):
                    logger.info(
                        "Extracted %s/%s pair feature rows in %.1fs",
                        completed,
                        len(missing),
                        time.time() - started,
                    )
            self._append_feature_cache(extracted)

        final_rows: List[Dict[str, float]] = []
        for index, row in enumerate(rows):
            if row is None:  # pragma: no cover - defensive
                raise RuntimeError(
                    f"Missing feature row for pair {pairs[index].pair_id}"
                )
            final_rows.append(row)
        return final_rows

    def _load_feature_cache(self) -> Dict[str, Dict[str, float]]:
        """Read the JSONL feature cache, if one is configured."""
        if not self.cache_path or not self.cache_path.exists():
            return {}
        cache: Dict[str, Dict[str, float]] = {}
        with self.cache_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("Skipping a corrupt feature cache line")
                    continue
                key = entry.get("key")
                row = entry.get("row")
                if key and isinstance(row, dict):
                    cache[str(key)] = {
                        str(name): float(value) for name, value in row.items()
                    }
        return cache

    def _append_feature_cache(
        self, entries: Sequence[Tuple[str, Dict[str, float]]]
    ) -> None:
        """Append freshly extracted rows to the JSONL feature cache."""
        if not self.cache_path or not entries:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with self.cache_path.open("a", encoding="utf-8") as handle:
            for key, row in entries:
                handle.write(
                    json.dumps({"key": key, "row": row}, ensure_ascii=False) + "\n"
                )

    @staticmethod
    def _cache_key(pair: LabeledPair) -> str:
        """Stable key for one pair's feature row.

        The code itself is hashed, so editing a corpus file invalidates its
        entry instead of silently training on stale features.
        """
        digest = hashlib.sha1()
        metadata = pair.metadata or {}
        for chunk in (
            str(FEATURE_CACHE_VERSION),
            str(metadata.get("dataset", "")),
            pair.pair_id,
            pair.code_a,
            pair.code_b,
        ):
            digest.update(chunk.encode("utf-8", errors="replace"))
            digest.update(b"|")
        return digest.hexdigest()

    @staticmethod
    def _extension_for(language: str) -> str:
        """File extension for a corpus language, defaulting to a neutral one."""
        return LANGUAGE_EXTENSIONS.get((language or "").strip().lower(), ".txt")

    def _fit_final_model(
        self,
        rows: List[Dict[str, float]],
        labels: List[int],
        sample_weights: Optional[List[float]] = None,
    ) -> Tuple[Dict[str, float], float]:
        """Fit the production logistic model on all pairs."""
        classifier = self._fit_logistic(rows, labels, sample_weights)
        coefficient_weights = {
            name: float(weight)
            for name, weight in zip(self.feature_names, classifier.coef_[0])
        }
        return coefficient_weights, float(classifier.intercept_[0])

    def _fit_logistic(
        self,
        rows: List[Dict[str, float]],
        labels: List[int],
        sample_weights: Optional[List[float]] = None,
    ) -> Any:
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
        classifier.fit(matrix, labels, sample_weight=sample_weights)
        return classifier

    def _logo_cross_validate(
        self,
        rows: List[Dict[str, float]],
        labels: List[int],
        groups: List[str],
        sample_weights: Optional[List[float]] = None,
    ) -> Tuple[Dict[int, float], int]:
        """Run leave-one-group-out cross-validation.

        Returns the out-of-fold probability for each scored pair keyed by its
        pair index, and the number of folds that could be trained.
        """
        held_out_sets = {
            group: [index for index, value in enumerate(groups) if value == group]
            for group in sorted(set(groups))
        }
        return self._score_held_out_sets(
            rows, labels, held_out_sets, "LOGO fold", sample_weights
        )

    def _group_kfold_cross_validate(
        self,
        rows: List[Dict[str, float]],
        labels: List[int],
        groups: List[str],
        folds: int,
        sample_weights: Optional[List[float]] = None,
    ) -> Tuple[Dict[int, float], int]:
        """Run grouped k-fold cross-validation.

        Every pair of one group lands in the same fold, so no code is scored by
        a model that already saw it. The assignment is seeded and therefore
        reproducible. With hundreds of groups (PoolC), k-fold is the only
        affordable protocol; leave-one-group-out would fit hundreds of models.
        """
        if folds < 2:
            raise ValueError("Grouped k-fold requires at least two folds")
        unique_groups = sorted(set(groups))
        shuffled = list(unique_groups)
        random.Random(self.seed).shuffle(shuffled)
        fold_of = {group: index % folds for index, group in enumerate(shuffled)}

        held_out_sets: Dict[str, List[int]] = {}
        for index, group in enumerate(groups):
            held_out_sets.setdefault(f"fold-{fold_of[group]}", []).append(index)
        return self._score_held_out_sets(
            rows, labels, held_out_sets, "Fold", sample_weights
        )

    def _score_held_out_sets(
        self,
        rows: List[Dict[str, float]],
        labels: List[int],
        held_out_sets: Dict[str, List[int]],
        fold_label: str,
        sample_weights: Optional[List[float]] = None,
    ) -> Tuple[Dict[int, float], int]:
        """Fit one model per held-out index set and collect out-of-fold scores.

        Folds whose training split lacks a class are skipped with a warning, so
        the returned mapping may cover fewer pairs than were passed in.
        """
        oof_by_index: Dict[int, float] = {}
        fold_count = 0
        total = len(held_out_sets)
        for name in sorted(held_out_sets):
            held_out = set(held_out_sets[name])
            if not held_out:
                continue
            train_rows = [
                row for index, row in enumerate(rows) if index not in held_out
            ]
            train_labels = [
                label for index, label in enumerate(labels) if index not in held_out
            ]
            if len(set(train_labels)) < 2:
                logger.warning(
                    "Skipping %s %s: training split has one class", fold_label, name
                )
                continue
            train_weights = (
                None
                if sample_weights is None
                else [
                    weight
                    for index, weight in enumerate(sample_weights)
                    if index not in held_out
                ]
            )
            classifier = self._fit_logistic(train_rows, train_labels, train_weights)
            held_out_indices = sorted(held_out)
            matrix = [
                [rows[index][feature] for feature in self.feature_names]
                for index in held_out_indices
            ]
            probabilities = classifier.predict_proba(matrix)[:, 1]
            for index, probability in zip(held_out_indices, probabilities):
                oof_by_index[index] = float(probability)
            fold_count += 1
            logger.info("%s %s done (%s/%s)", fold_label, name, fold_count, total)
        return oof_by_index, fold_count

    def _auc_per_dataset(
        self,
        scores_by_index: Dict[int, float],
        labels: List[int],
        pairs: List[LabeledPair],
    ) -> Dict[str, float]:
        """Compute per-dataset AUC over any aligned index→score mapping."""
        per_dataset_scores: Dict[str, List[float]] = {}
        per_dataset_labels: Dict[str, List[int]] = {}
        for index, score in scores_by_index.items():
            dataset_name = str((pairs[index].metadata or {}).get("dataset", "unknown"))
            per_dataset_scores.setdefault(dataset_name, []).append(score)
            per_dataset_labels.setdefault(dataset_name, []).append(labels[index])
        return {
            name: self._auc(per_dataset_scores[name], per_dataset_labels[name])
            for name in per_dataset_scores
            if len(set(per_dataset_labels[name])) == 2
        }

    @staticmethod
    def _count_per_dataset(pairs: List[LabeledPair]) -> Dict[str, int]:
        """Count loaded pairs per dataset."""
        counts: Dict[str, int] = {}
        for pair in pairs:
            name = str((pair.metadata or {}).get("dataset", "unknown"))
            counts[name] = counts.get(name, 0) + 1
        return dict(sorted(counts.items()))

    def _sample_weights(self, pairs: List[LabeledPair]) -> Optional[List[float]]:
        """Per-pair fit weights, or ``None`` when every pair counts once.

        ``dataset_weighting="equal"`` gives each corpus the same total weight, so
        a 20000-pair PoolC sample cannot drown the 293-pair classroom corpus
        whose distribution the product actually faces. Weights are normalised to
        mean 1 so the regularisation strength does not silently change.
        """
        if self.dataset_weighting != "equal" or not pairs:
            return None
        counts = self._count_per_dataset(pairs)
        raw = [
            1.0 / counts[str((pair.metadata or {}).get("dataset", "unknown"))]
            for pair in pairs
        ]
        mean = sum(raw) / len(raw)
        if mean <= 0:
            return None
        return [value / mean for value in raw]

    def _cv_notes(self, cv_mode: str, datasets: List[str]) -> str:
        """Describe the evaluation protocol in one line."""
        notes = f"{cv_mode}; a fold never splits one group across train and test."
        if "poolc_600k_python" in datasets and self.poolc_negative_ratio <= 0:
            notes += (
                " PoolC cross-problem negatives excluded: they are different"
                " problems, not independent solutions of the same assignment."
            )
        return notes

    def _write_artifact(
        self,
        path: Path,
        datasets: List[str],
        pairs: List[LabeledPair],
        coefficient_weights: Dict[str, float],
        intercept: float,
        production_auc: float,
        cv_auc: float,
        cv_best: Dict[str, float],
        cv_mode: str,
        pairs_per_dataset: Dict[str, int],
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
                "pairs_per_dataset": dict(pairs_per_dataset),
                "pair_count": len(pairs),
                "positive_pairs": sum(labels),
                "negative_pairs": sum(1 for label in labels if label == 0),
                "cv_auc_roc": round(cv_auc, 4),
                "cv_mode": cv_mode,
                "production_fused_auc_roc": round(production_auc, 4),
                "model": MODEL_DESCRIPTION,
                "cv_best_f1": round(cv_best["f1"], 4),
                "cv_best_threshold": round(cv_best["threshold"], 4),
                "cv_notes": self._cv_notes(cv_mode, datasets),
                "dataset_weighting": self.dataset_weighting,
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
    max_pairs_per_dataset: Optional[int] = None,
    cv_folds: int = 0,
    poolc_negative_ratio: float = 0.0,
    cache_path: Optional[Path] = None,
    dataset_weighting: str = "proportional",
) -> LearnedFusionReport:
    """Convenience wrapper used by the CLI."""
    runner = LearnedFusionTrainingRunner(
        output_dir=output_dir,
        threshold_step=threshold_step,
        seed=seed,
        max_pairs_per_dataset=max_pairs_per_dataset,
        cv_folds=cv_folds,
        poolc_negative_ratio=poolc_negative_ratio,
        cache_path=cache_path,
        dataset_weighting=dataset_weighting,
    )
    return runner.run(enabled_datasets=enabled_datasets, artifact_path=artifact_path)
