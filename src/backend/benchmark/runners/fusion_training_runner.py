"""Supervised fusion training workflow for plagiarism detection.

This runner prepares a production-oriented workflow for training and evaluating
fusion models across multiple local datasets. It is designed so larger datasets
can be dropped into the repository later without changing the workflow shape.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import pickle
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

from src.backend.benchmark.runners.fusion_optimization_runner import (
    PAIR_FEATURE_NAMES,
    PRIOR_SIGNAL_ALIASES,
    SEED_FORMULA_RAW_WEIGHTS,
    SIGNAL_NAMES,
    STRONG_SIGNAL_NAMES,
    ExperimentResult,
    PairRecord,
    PairSignalExtractor,
    ThresholdMetrics,
    ValidationPair,
    ValidationSubmission,
)


LOGGER = logging.getLogger(__name__)


DATASET_ALIASES: dict[str, str] = {
    "ir-plag": "IR-Plag-Dataset",
    "ir_plag": "IR-Plag-Dataset",
    "conplag": "conplag",
    "conplag-classroom-java": "conplag_classroom_java",
    "conplag_classroom_java": "conplag_classroom_java",
    "codexglue_clone": "codexglue_clone",
    "codexglue-clone": "codexglue_clone",
    "poj104": "poj104",
}


@dataclass
class TrainingCodePair:
    """Canonical labeled code pair used by the training workflow."""

    pair_id: str
    dataset_name: str
    split: str
    language: str
    code_a: str
    code_b: str
    label: int
    problem_id: str = ""
    code_a_path: Optional[str] = None
    code_b_path: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TrainingWorkflowReport:
    """Serializable report for supervised fusion training."""

    generated_at_unix: int
    train_datasets: list[str]
    eval_datasets: list[str]
    train_pair_count: int
    eval_pair_count: int
    signals: list[str]
    pair_features: list[str]
    optional_capabilities: dict[str, bool]
    experiments: list[ExperimentResult]
    best_experiment_name: str
    best_model_name: str
    best_model_path: str
    runtime_seconds: float

    def to_json_dict(self) -> dict[str, Any]:
        """Convert to a JSON-safe dictionary."""
        payload = asdict(self)
        payload["experiments"] = [
            {
                **asdict(experiment),
                "best_metrics": asdict(experiment.best_metrics),
            }
            for experiment in self.experiments
        ]
        return payload

    def save_json(self, path: Path) -> Path:
        """Write JSON report to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_json_dict(), indent=2), encoding="utf-8")
        return path

    def save_markdown(self, path: Path) -> Path:
        """Write Markdown report to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        ranked = sorted(
            self.experiments,
            key=lambda item: item.best_metrics.f1_score,
            reverse=True,
        )
        lines: list[str] = [
            "# Supervised Fusion Training Report",
            "",
            f"- Train datasets: `{', '.join(self.train_datasets)}`",
            f"- Eval datasets: `{', '.join(self.eval_datasets)}`",
            f"- Train pairs: `{self.train_pair_count}`",
            f"- Eval pairs: `{self.eval_pair_count}`",
            f"- Best overall result: `{self.best_experiment_name}`",
            f"- Best model: `{self.best_model_name}`",
            f"- Model artifact: `{self.best_model_path}`",
            "",
            "## Ranking",
            "",
            "| Experiment | Method | F1 | Precision | Recall | Threshold |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
        for item in ranked:
            lines.append(
                "| "
                f"{item.name} | {item.method} | "
                f"{item.best_metrics.f1_score:.4f} | "
                f"{item.best_metrics.precision:.4f} | "
                f"{item.best_metrics.recall:.4f} | "
                f"{item.best_threshold:.2f} |"
            )

        lines.extend(
            [
                "",
                "## Capability Flags",
                "",
                "| Capability | Available |",
                "| --- | --- |",
            ]
        )
        for capability, available in self.optional_capabilities.items():
            lines.append(f"| {capability} | {'yes' if available else 'no'} |")

        for item in ranked:
            lines.extend(
                [
                    "",
                    f"## {item.name}",
                    "",
                    f"- Method: `{item.method}`",
                    f"- Best threshold: `{item.best_threshold:.2f}`",
                    f"- Best F1: `{item.best_metrics.f1_score:.4f}`",
                ]
            )
            if item.notes:
                lines.append(f"- Notes: {'; '.join(item.notes)}")

        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path


class SupervisedFusionTrainingRunner:
    """Train and evaluate supervised fusion models on local datasets."""

    def __init__(
        self,
        output_dir: Path,
        train_datasets: Iterable[str],
        eval_datasets: Iterable[str],
        dataset_roots: Optional[list[Path]] = None,
        train_pair_limit: Optional[int] = None,
        eval_pair_limit: Optional[int] = None,
        threshold_step: float = 0.02,
        optuna_trials: int = 40,
        seed: int = 42,
    ) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.train_datasets = [
            self._normalize_dataset_name(name) for name in train_datasets
        ]
        self.eval_datasets = [
            self._normalize_dataset_name(name) for name in eval_datasets
        ]
        self.dataset_roots = dataset_roots or self._default_dataset_roots()
        self.train_pair_limit = train_pair_limit
        self.eval_pair_limit = eval_pair_limit
        self.threshold_step = threshold_step
        self.optuna_trials = optuna_trials
        self.seed = seed
        self.extractor = PairSignalExtractor(
            self.output_dir / "cache" / "pair_signals.json"
        )

    def run(self) -> TrainingWorkflowReport:
        """Execute the training workflow."""
        started = time.time()
        train_pairs = self._load_pairs(
            self.train_datasets, "train", self.train_pair_limit
        )
        eval_pairs = self._load_pairs(self.eval_datasets, "eval", self.eval_pair_limit)

        train_records = self._build_records(train_pairs, "train")
        eval_records = self._build_records(eval_pairs, "eval")
        self.extractor.flush()

        self._export_matrix(self.output_dir / "train_matrix.csv", train_records)
        self._export_matrix(self.output_dir / "eval_matrix.csv", eval_records)

        experiments: list[ExperimentResult] = []
        experiments.append(self._evaluate_equal_baseline(eval_records))
        experiments.append(self._evaluate_seeded_baseline(eval_records))
        experiments.append(self._evaluate_seeded_pooling(eval_records))

        optional_capabilities = {
            "optuna": self._module_available("optuna"),
            "sklearn": self._module_available("sklearn"),
        }

        model_results, model_artifact = self._train_models(train_records, eval_records)
        experiments.extend(model_results)

        best_experiment = max(experiments, key=lambda item: item.best_metrics.f1_score)
        best_model_experiment = max(
            model_results,
            key=lambda item: item.best_metrics.f1_score,
        )

        report = TrainingWorkflowReport(
            generated_at_unix=int(time.time()),
            train_datasets=self.train_datasets,
            eval_datasets=self.eval_datasets,
            train_pair_count=len(train_records),
            eval_pair_count=len(eval_records),
            signals=list(SIGNAL_NAMES),
            pair_features=list(PAIR_FEATURE_NAMES),
            optional_capabilities=optional_capabilities,
            experiments=experiments,
            best_experiment_name=best_experiment.name,
            best_model_name=best_model_experiment.name,
            best_model_path=str(model_artifact),
            runtime_seconds=time.time() - started,
        )
        return report

    def _build_records(
        self,
        pairs: list[TrainingCodePair],
        role: str,
    ) -> list[PairRecord]:
        """Convert labeled pairs into feature records with progress logging."""
        records: list[PairRecord] = []
        started = time.time()
        total = len(pairs)
        for index, pair in enumerate(pairs, start=1):
            records.append(self._pair_to_record(pair))
            if index == total or index % 25 == 0:
                LOGGER.info(
                    "Extracted %s/%s %s records in %.1fs",
                    index,
                    total,
                    role,
                    time.time() - started,
                )
        return records

    def _load_pairs(
        self,
        dataset_names: list[str],
        role: str,
        pair_limit: Optional[int],
    ) -> list[TrainingCodePair]:
        """Load pairs from all requested datasets."""
        all_pairs: list[TrainingCodePair] = []
        for dataset_name in dataset_names:
            pairs = self._load_dataset_pairs(dataset_name, role)
            if pair_limit is not None:
                remaining = pair_limit - len(all_pairs)
                if remaining <= 0:
                    break
                pairs = pairs[:remaining]
            LOGGER.info("Loaded %s %s pairs for %s", len(pairs), role, dataset_name)
            all_pairs.extend(pairs)
        return all_pairs

    def _load_dataset_pairs(
        self, dataset_name: str, role: str
    ) -> list[TrainingCodePair]:
        """Load one dataset in train or eval mode."""
        if dataset_name == "IR-Plag-Dataset":
            return self._load_ir_plag_pairs(role)
        if dataset_name == "conplag":
            return self._load_conplag_pairs(role)
        if dataset_name == "conplag_classroom_java":
            return self._load_conplag_classroom_pairs(role)
        if dataset_name == "codexglue_clone":
            split = "train" if role == "train" else "validation"
            return self._load_huggingface_pairs(dataset_name, split)
        if dataset_name == "poj104":
            split = "train" if role == "train" else "test"
            return self._load_huggingface_pairs(dataset_name, split)
        raise ValueError(f"Unsupported training dataset: {dataset_name}")

    def _load_ir_plag_pairs(self, role: str) -> list[TrainingCodePair]:
        """Load IR-Plag dataset pairs with deterministic split."""
        root_dir = self._find_dataset_dir("IR-Plag-Dataset")
        pairs: list[TrainingCodePair] = []
        for case_dir in sorted(root_dir.glob("case-*")):
            original_files = sorted((case_dir / "original").glob("*.java"))
            if not original_files:
                continue
            original_path = original_files[0]
            original_code = self._read_code(original_path)

            for plag_path in sorted((case_dir / "plagiarized").rglob("*.java")):
                pair = TrainingCodePair(
                    pair_id=f"{case_dir.name}:plag:{plag_path.parent.name}:{plag_path.name}",
                    dataset_name="IR-Plag-Dataset",
                    split=self._hashed_split(
                        f"{case_dir.name}:{plag_path.parent.name}:{plag_path.name}"
                    ),
                    language="java",
                    code_a=original_code,
                    code_b=self._read_code(plag_path),
                    label=1,
                    problem_id=case_dir.name,
                    code_a_path=str(original_path),
                    code_b_path=str(plag_path),
                    metadata={"case": case_dir.name, "variant": plag_path.parent.name},
                )
                if pair.split == role:
                    pairs.append(pair)

            for negative_path in sorted((case_dir / "non-plagiarized").rglob("*.java")):
                pair = TrainingCodePair(
                    pair_id=f"{case_dir.name}:non:{negative_path.parent.name}:{negative_path.name}",
                    dataset_name="IR-Plag-Dataset",
                    split=self._hashed_split(
                        f"{case_dir.name}:non:{negative_path.parent.name}:{negative_path.name}"
                    ),
                    language="java",
                    code_a=original_code,
                    code_b=self._read_code(negative_path),
                    label=0,
                    problem_id=case_dir.name,
                    code_a_path=str(original_path),
                    code_b_path=str(negative_path),
                    metadata={
                        "case": case_dir.name,
                        "variant": negative_path.parent.name,
                    },
                )
                if pair.split == role:
                    pairs.append(pair)
        return pairs

    def _load_conplag_pairs(self, role: str) -> list[TrainingCodePair]:
        """Load the ConPlag pair dataset."""
        root_dir = self._find_dataset_dir("conplag")
        split_file = "train_pairs.csv" if role == "train" else "test_pairs.csv"
        pair_ids = [
            row[0].strip()
            for row in self._read_csv_rows(root_dir / "versions" / split_file)
            if row and row[0].strip()
        ]

        label_lookup: dict[str, dict[str, str]] = {}
        with (root_dir / "versions" / "labels.csv").open(
            "r", encoding="utf-8"
        ) as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                pair_key = f"{row['sub1']}_{row['sub2']}"
                reverse_key = f"{row['sub2']}_{row['sub1']}"
                label_lookup[pair_key] = row
                label_lookup[reverse_key] = row

        pairs: list[TrainingCodePair] = []
        version_dir = root_dir / "versions" / "version_1"
        for pair_id in pair_ids:
            pair_dir = version_dir / pair_id
            code_files = sorted(pair_dir.glob("*.java"))
            if len(code_files) != 2:
                LOGGER.warning("Skipping malformed ConPlag pair %s", pair_id)
                continue
            label_row = label_lookup.get(pair_id)
            if label_row is None:
                LOGGER.warning("Missing label for ConPlag pair %s", pair_id)
                continue
            pairs.append(
                TrainingCodePair(
                    pair_id=pair_id,
                    dataset_name="conplag",
                    split=role,
                    language="java",
                    code_a=self._read_code(code_files[0]),
                    code_b=self._read_code(code_files[1]),
                    label=int(label_row["verdict"]),
                    problem_id=label_row["problem"],
                    code_a_path=str(code_files[0]),
                    code_b_path=str(code_files[1]),
                    metadata={"problem": label_row["problem"], "version": "version_1"},
                )
            )
        return pairs

    def _load_conplag_classroom_pairs(self, role: str) -> list[TrainingCodePair]:
        """Load the classroom-style ConPlag dataset."""
        root_dir = self._find_dataset_dir("conplag_classroom_java")
        labels_path = root_dir / "labels.csv"
        pairs: list[TrainingCodePair] = []
        with labels_path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                split_name = row.get("split", "").strip().lower()
                normalized_split = "train" if split_name == "train" else "eval"
                if normalized_split != role:
                    continue
                assignment_id = row["assignment_id"]
                path_a = (
                    root_dir
                    / "assignments"
                    / assignment_id
                    / "submissions"
                    / row["file_a"]
                )
                path_b = (
                    root_dir
                    / "assignments"
                    / assignment_id
                    / "submissions"
                    / row["file_b"]
                )
                if not path_a.exists() or not path_b.exists():
                    LOGGER.warning(
                        "Skipping missing classroom files %s %s",
                        path_a,
                        path_b,
                    )
                    continue
                pairs.append(
                    TrainingCodePair(
                        pair_id=f"{assignment_id}:{row['file_a']}:{row['file_b']}",
                        dataset_name="conplag_classroom_java",
                        split=role,
                        language="java",
                        code_a=self._read_code(path_a),
                        code_b=self._read_code(path_b),
                        label=1 if row["label"].strip().lower() == "plagiarized" else 0,
                        problem_id=assignment_id,
                        code_a_path=str(path_a),
                        code_b_path=str(path_b),
                        metadata={"assignment_id": assignment_id},
                    )
                )
        return pairs

    def _load_huggingface_pairs(
        self, dataset_name: str, split: str
    ) -> list[TrainingCodePair]:
        """Load a local HuggingFace dataset from disk."""
        dataset_dir = self._find_dataset_dir(dataset_name)
        huggingface_dir = dataset_dir / "huggingface"
        if not huggingface_dir.exists():
            huggingface_dir = dataset_dir
        try:
            from datasets import load_from_disk
        except ImportError as exc:
            raise ImportError(
                "datasets package is required for local HuggingFace datasets"
            ) from exc

        dataset = load_from_disk(str(huggingface_dir))
        split_data = dataset[split]

        pairs: list[TrainingCodePair] = []
        for index, item in enumerate(split_data):
            if dataset_name == "codexglue_clone":
                pairs.append(
                    TrainingCodePair(
                        pair_id=f"codexglue_clone:{split}:{index}",
                        dataset_name="codexglue_clone",
                        split="train" if split == "train" else "eval",
                        language="java",
                        code_a=item.get("func1", ""),
                        code_b=item.get("func2", ""),
                        label=int(item.get("label", 0)),
                        problem_id=str(item.get("id", "")),
                        metadata={
                            "id1": item.get("id1", ""),
                            "id2": item.get("id2", ""),
                            "hf_split": split,
                        },
                    )
                )
            elif dataset_name == "poj104":
                pairs.append(
                    TrainingCodePair(
                        pair_id=f"poj104:{split}:{index}",
                        dataset_name="poj104",
                        split="train" if split == "train" else "eval",
                        language="java",
                        code_a=item.get("func1", ""),
                        code_b=item.get("func2", ""),
                        label=int(item.get("label", 0)),
                        problem_id=str(item.get("id", "")),
                        metadata={
                            "id1": item.get("id1", ""),
                            "id2": item.get("id2", ""),
                            "hf_split": split,
                        },
                    )
                )
        return pairs

    def _pair_to_record(self, pair: TrainingCodePair) -> PairRecord:
        """Convert one training pair into extracted signals."""
        left = ValidationSubmission(
            submission_id=f"{pair.dataset_name}_a",
            problem_id=pair.problem_id or pair.dataset_name,
            verdict=pair.split,
            language=pair.language,
            code_path=pair.code_a_path or "",
            dsc_path=None,
            cpg_path=None,
            code=pair.code_a,
        )
        right = ValidationSubmission(
            submission_id=f"{pair.dataset_name}_b",
            problem_id=pair.problem_id or pair.dataset_name,
            verdict=pair.split,
            language=pair.language,
            code_path=pair.code_b_path or "",
            dsc_path=None,
            cpg_path=None,
            code=pair.code_b,
        )
        validation_pair = ValidationPair(
            pair_id=pair.pair_id,
            left=left,
            right=right,
            label=pair.label,
            dataset_name=pair.dataset_name,
        )
        return self.extractor.extract(validation_pair)

    def _train_models(
        self,
        train_records: list[PairRecord],
        eval_records: list[PairRecord],
    ) -> tuple[list[ExperimentResult], Path]:
        """Train supervised models and return ranked results."""
        if not self._module_available("sklearn"):
            artifact_path = self.output_dir / "best_model.pkl"
            artifact_path.write_bytes(b"")
            return [
                ExperimentResult(
                    name="Random Forest Meta Learner",
                    method="random_forest",
                    weights={},
                    best_threshold=0.0,
                    best_metrics=ThresholdMetrics(
                        threshold=0.0,
                        precision=0.0,
                        recall=0.0,
                        f1_score=0.0,
                        true_positives=0,
                        false_positives=0,
                        true_negatives=0,
                        false_negatives=0,
                    ),
                    notes=["scikit-learn unavailable"],
                )
            ], artifact_path

        from sklearn.ensemble import (
            ExtraTreesClassifier,
            HistGradientBoostingClassifier,
            RandomForestClassifier,
        )
        from sklearn.linear_model import LogisticRegression

        train_x = [self._meta_features(record) for record in train_records]
        train_y = [record.label for record in train_records]
        eval_x = [self._meta_features(record) for record in eval_records]
        eval_y = [record.label for record in eval_records]

        candidate_models: list[tuple[str, str, Any, list[str]]] = [
            (
                "Random Forest Meta Learner",
                "random_forest",
                RandomForestClassifier(
                    n_estimators=400,
                    random_state=self.seed,
                    n_jobs=1,
                    class_weight="balanced_subsample",
                ),
                ["n_estimators=400"],
            ),
            (
                "Extra Trees Meta Learner",
                "extra_trees",
                ExtraTreesClassifier(
                    n_estimators=500,
                    random_state=self.seed,
                    n_jobs=1,
                    class_weight="balanced_subsample",
                ),
                ["n_estimators=500"],
            ),
            (
                "HistGradientBoosting Meta Learner",
                "hist_gradient_boosting",
                HistGradientBoostingClassifier(
                    random_state=self.seed,
                    max_iter=250,
                    learning_rate=0.05,
                ),
                ["max_iter=250", "learning_rate=0.05"],
            ),
            (
                "Logistic Meta Learner",
                "logistic_regression",
                LogisticRegression(
                    random_state=self.seed,
                    max_iter=2000,
                    class_weight="balanced",
                ),
                ["max_iter=2000"],
            ),
        ]

        if self.optuna_trials > 0 and self._module_available("optuna"):
            tuned_model, tuned_notes = self._tune_random_forest(train_x, train_y)
            candidate_models.insert(
                1,
                (
                    "Tuned Random Forest Meta Learner",
                    "random_forest_optuna",
                    tuned_model,
                    tuned_notes,
                ),
            )

        experiments: list[ExperimentResult] = []
        best_payload: dict[str, Any] = {}
        best_f1 = -1.0

        for name, method, model, notes in candidate_models:
            LOGGER.info("Training %s on %s records", name, len(train_records))
            model.fit(train_x, train_y)
            probabilities = model.predict_proba(eval_x)
            scores = [max(0.0, min(1.0, float(row[1]))) for row in probabilities]
            best_threshold, best_metrics, curve = self._find_best_threshold(
                scores, eval_y
            )
            LOGGER.info(
                "Finished %s with eval F1 %.4f at threshold %.2f",
                name,
                best_metrics.f1_score,
                best_threshold,
            )
            experiment = ExperimentResult(
                name=name,
                method=method,
                weights={},
                best_threshold=best_threshold,
                best_metrics=best_metrics,
                score_preview=[round(score, 4) for score in scores[:10]],
                precision_recall_curve=curve,
                notes=notes,
            )
            experiments.append(experiment)
            if best_metrics.f1_score > best_f1:
                best_f1 = best_metrics.f1_score
                best_payload = {
                    "model": model,
                    "threshold": best_threshold,
                    "method": method,
                    "feature_names": list(SIGNAL_NAMES) + list(PAIR_FEATURE_NAMES),
                    "train_datasets": self.train_datasets,
                    "eval_datasets": self.eval_datasets,
                }

        artifact_path = self.output_dir / "best_model.pkl"
        with artifact_path.open("wb") as handle:
            pickle.dump(best_payload, handle)
        return experiments, artifact_path

    def _tune_random_forest(
        self,
        train_x: list[list[float]],
        train_y: list[int],
    ) -> tuple[Any, list[str]]:
        """Tune a Random Forest with Optuna."""
        import optuna
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import cross_val_score

        def objective(trial: optuna.Trial) -> float:
            model = RandomForestClassifier(
                n_estimators=trial.suggest_int("n_estimators", 200, 800, step=100),
                max_depth=trial.suggest_int("max_depth", 4, 20),
                min_samples_split=trial.suggest_int("min_samples_split", 2, 12),
                min_samples_leaf=trial.suggest_int("min_samples_leaf", 1, 6),
                max_features=trial.suggest_categorical(
                    "max_features", ["sqrt", "log2", None]
                ),
                class_weight="balanced_subsample",
                n_jobs=1,
                random_state=self.seed,
            )
            scores = cross_val_score(
                model,
                train_x,
                train_y,
                cv=3,
                scoring="f1",
                n_jobs=1,
            )
            return float(sum(scores) / len(scores))

        study = optuna.create_study(direction="maximize")
        study.optimize(objective, n_trials=self.optuna_trials, show_progress_bar=False)
        best_params = study.best_params
        model = RandomForestClassifier(
            **best_params,
            class_weight="balanced_subsample",
            n_jobs=1,
            random_state=self.seed,
        )
        notes = ["optimizer=optuna", f"best_cv_f1={study.best_value:.4f}"]
        return model, notes

    def _evaluate_equal_baseline(
        self, eval_records: list[PairRecord]
    ) -> ExperimentResult:
        """Evaluate equal-weight baseline."""
        weights = self._equal_weights()
        return self._evaluate_weighted_strategy(
            name="Equal Weight Baseline",
            method="weighted_average",
            eval_records=eval_records,
            weights=weights,
            pool_mix=0.0,
            notes=[],
        )

    def _evaluate_seeded_baseline(
        self, eval_records: list[PairRecord]
    ) -> ExperimentResult:
        """Evaluate seeded weighted baseline."""
        return self._evaluate_weighted_strategy(
            name="Seeded Prior Fusion",
            method="seeded_weighted_average",
            eval_records=eval_records,
            weights=self._seed_formula_weights(),
            pool_mix=0.0,
            notes=[
                "seed_formula=0.4*AST + 0.25*Winnowing + 0.2*Inbanding + 4*0.1 other engines",
                self._alias_note(),
            ],
        )

    def _evaluate_seeded_pooling(
        self, eval_records: list[PairRecord]
    ) -> ExperimentResult:
        """Evaluate seeded fusion with strong pooling."""
        return self._evaluate_weighted_strategy(
            name="Seeded Prior + Strong Pooling",
            method="strong_pool_then_weighted_average",
            eval_records=eval_records,
            weights=self._seed_formula_weights(),
            pool_mix=0.35,
            notes=[
                "strong_pool_mix=0.35",
                f"strong_signals={','.join(STRONG_SIGNAL_NAMES)}",
                self._alias_note(),
            ],
        )

    def _evaluate_weighted_strategy(
        self,
        name: str,
        method: str,
        eval_records: list[PairRecord],
        weights: dict[str, float],
        pool_mix: float,
        notes: list[str],
    ) -> ExperimentResult:
        """Evaluate a weighted strategy on evaluation records."""
        scores = [
            self._weighted_score(record, weights, pool_mix) for record in eval_records
        ]
        labels = [record.label for record in eval_records]
        best_threshold, best_metrics, curve = self._find_best_threshold(scores, labels)
        return ExperimentResult(
            name=name,
            method=method,
            weights=weights,
            best_threshold=best_threshold,
            best_metrics=best_metrics,
            score_preview=[round(score, 4) for score in scores[:10]],
            precision_recall_curve=curve,
            notes=notes,
        )

    def _find_best_threshold(
        self,
        scores: list[float],
        labels: list[int],
    ) -> tuple[float, ThresholdMetrics, list[dict[str, float]]]:
        """Sweep thresholds and return the best F1 point."""
        best_threshold = 0.5
        best_metrics = self._metrics_at_threshold(scores, labels, best_threshold)
        curve: list[dict[str, float]] = []
        threshold = 0.0
        while threshold <= 1.000001:
            metrics = self._metrics_at_threshold(scores, labels, threshold)
            curve.append(
                {
                    "threshold": round(threshold, 4),
                    "precision": metrics.precision,
                    "recall": metrics.recall,
                    "f1_score": metrics.f1_score,
                }
            )
            if metrics.f1_score > best_metrics.f1_score:
                best_threshold = threshold
                best_metrics = metrics
            threshold += self.threshold_step
        return best_threshold, best_metrics, curve

    @staticmethod
    def _metrics_at_threshold(
        scores: list[float],
        labels: list[int],
        threshold: float,
    ) -> ThresholdMetrics:
        """Compute binary metrics for one threshold."""
        tp = fp = tn = fn = 0
        for score, label in zip(scores, labels):
            prediction = 1 if score >= threshold else 0
            if prediction == 1 and label == 1:
                tp += 1
            elif prediction == 1 and label == 0:
                fp += 1
            elif prediction == 0 and label == 0:
                tn += 1
            else:
                fn += 1
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1_score = (
            2.0 * precision * recall / (precision + recall)
            if (precision + recall)
            else 0.0
        )
        return ThresholdMetrics(
            threshold=threshold,
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            true_positives=tp,
            false_positives=fp,
            true_negatives=tn,
            false_negatives=fn,
        )

    @staticmethod
    def _meta_features(record: PairRecord) -> list[float]:
        """Create meta-model feature vector."""
        return [
            *(record.signals[name] for name in SIGNAL_NAMES),
            *(record.pair_features[name] for name in PAIR_FEATURE_NAMES),
        ]

    @staticmethod
    def _module_available(module_name: str) -> bool:
        """Check optional module availability."""
        try:
            __import__(module_name)
            return True
        except Exception:
            return False

    @staticmethod
    def _default_dataset_roots() -> list[Path]:
        """Return default dataset root directories."""
        repo_root = Path(__file__).resolve().parents[4]
        return [
            repo_root / "data" / "datasets",
            repo_root / "data" / "bigger_datasets",
        ]

    @staticmethod
    def _normalize_dataset_name(dataset_name: str) -> str:
        """Normalize dataset aliases to local directory names."""
        return DATASET_ALIASES.get(dataset_name, dataset_name)

    def _find_dataset_dir(self, dataset_name: str) -> Path:
        """Resolve a dataset directory across known roots."""
        for root in self.dataset_roots:
            candidate = root / dataset_name
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"Dataset directory not found for {dataset_name}")

    @staticmethod
    def _hashed_split(key: str) -> str:
        """Deterministic split based on stable hash."""
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        bucket = int(digest[:8], 16) % 10
        return "train" if bucket < 8 else "eval"

    @staticmethod
    def _read_code(path: Path) -> str:
        """Read source code from disk."""
        return path.read_text(encoding="utf-8", errors="ignore")

    @staticmethod
    def _read_csv_rows(path: Path) -> list[list[str]]:
        """Read a simple CSV file into rows."""
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.reader(handle))

    @staticmethod
    def _equal_weights() -> dict[str, float]:
        """Return equal weights over the seven signals."""
        weight = 1.0 / len(SIGNAL_NAMES)
        return {name: weight for name in SIGNAL_NAMES}

    @staticmethod
    def _normalize_weights(weights: dict[str, float]) -> dict[str, float]:
        """Normalize weights to sum to one."""
        total = sum(max(value, 0.0) for value in weights.values())
        if total <= 0.0:
            return SupervisedFusionTrainingRunner._equal_weights()
        return {
            signal_name: max(weights.get(signal_name, 0.0), 0.0) / total
            for signal_name in SIGNAL_NAMES
        }

    def _seed_formula_weights(self) -> dict[str, float]:
        """Map the seeded formula onto local signals."""
        return self._normalize_weights(
            {
                PRIOR_SIGNAL_ALIASES[name]: value
                for name, value in SEED_FORMULA_RAW_WEIGHTS.items()
            }
        )

    @staticmethod
    def _alias_note() -> str:
        """Explain local signal aliases."""
        return (
            "signal_aliases="
            "ast_sim->cpg_node_type,"
            "winnowing_sim->token_sequence,"
            "inbanding_sim->char_ngram"
        )

    @staticmethod
    def _weighted_score(
        record: PairRecord,
        weights: dict[str, float],
        pool_mix: float,
    ) -> float:
        """Compute weighted score with optional strong-signal pooling."""
        weighted_average = sum(
            weights[signal_name] * record.signals.get(signal_name, 0.0)
            for signal_name in SIGNAL_NAMES
        )
        pool_mix = max(0.0, min(1.0, pool_mix))
        if pool_mix <= 0.0:
            return weighted_average
        strong_score = max(
            record.signals.get(signal_name, 0.0) for signal_name in STRONG_SIGNAL_NAMES
        )
        return (1.0 - pool_mix) * weighted_average + pool_mix * strong_score

    @staticmethod
    def _export_matrix(path: Path, records: list[PairRecord]) -> None:
        """Export feature matrix for inspection or later training."""
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "pair_id",
            "label",
            "dataset_name",
            "language",
            *SIGNAL_NAMES,
            *PAIR_FEATURE_NAMES,
        ]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for record in records:
                row = {
                    "pair_id": record.pair_id,
                    "label": record.label,
                    "dataset_name": record.dataset_name,
                    "language": record.language,
                }
                row.update(record.signals)
                row.update(record.pair_features)
                writer.writerow(row)


def run_supervised_fusion_training(
    output_dir: Path,
    train_datasets: Iterable[str],
    eval_datasets: Iterable[str],
    dataset_roots: Optional[list[Path]] = None,
    train_pair_limit: Optional[int] = None,
    eval_pair_limit: Optional[int] = None,
    threshold_step: float = 0.02,
    optuna_trials: int = 40,
    seed: int = 42,
) -> TrainingWorkflowReport:
    """Convenience wrapper for the CLI."""
    runner = SupervisedFusionTrainingRunner(
        output_dir=output_dir,
        train_datasets=train_datasets,
        eval_datasets=eval_datasets,
        dataset_roots=dataset_roots,
        train_pair_limit=train_pair_limit,
        eval_pair_limit=eval_pair_limit,
        threshold_step=threshold_step,
        optuna_trials=optuna_trials,
        seed=seed,
    )
    return runner.run()
