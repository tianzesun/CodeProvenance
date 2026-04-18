"""Validation-set fusion optimization runner.

This module provides a self-contained experiment runner for comparing
baseline equal-weight fusion against automatically optimized fusion on a
validation dataset such as PROGpedia.

The implementation intentionally uses the Python standard library first so the
command can run in constrained environments. Optional dependencies such as
Optuna and scikit-learn are used when available and skipped otherwise.
"""

from __future__ import annotations

import csv
import itertools
import json
import logging
import math
import random
import re
import time
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable, Optional


LOGGER = logging.getLogger(__name__)


SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".py": "python",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
}

SIGNAL_NAMES: list[str] = [
    "token_jaccard",
    "token_sequence",
    "char_ngram",
    "line_sequence",
    "cpg_node_type",
    "cpg_node_token",
    "cpg_edge_type",
]

PAIR_FEATURE_NAMES: list[str] = [
    "size_ratio",
    "identifier_overlap",
    "normalized_edit_similarity",
]

PRIOR_SIGNAL_ALIASES: dict[str, str] = {
    "ast_sim": "cpg_node_type",
    "winnowing_sim": "token_sequence",
    "inbanding_sim": "char_ngram",
    "engine_4_sim": "line_sequence",
    "engine_5_sim": "token_jaccard",
    "engine_6_sim": "cpg_node_token",
    "engine_7_sim": "cpg_edge_type",
}

SEED_FORMULA_RAW_WEIGHTS: dict[str, float] = {
    "ast_sim": 0.40,
    "winnowing_sim": 0.25,
    "inbanding_sim": 0.20,
    "engine_4_sim": 0.10,
    "engine_5_sim": 0.10,
    "engine_6_sim": 0.10,
    "engine_7_sim": 0.10,
}

STRONG_SIGNAL_NAMES: list[str] = [
    PRIOR_SIGNAL_ALIASES["ast_sim"],
    PRIOR_SIGNAL_ALIASES["winnowing_sim"],
    PRIOR_SIGNAL_ALIASES["inbanding_sim"],
]


@dataclass
class ValidationSubmission:
    """Single validation submission."""

    submission_id: str
    problem_id: str
    verdict: str
    language: str
    code_path: str
    dsc_path: Optional[str]
    cpg_path: Optional[str]
    code: str


@dataclass
class ValidationPair:
    """Labeled validation pair."""

    pair_id: str
    left: ValidationSubmission
    right: ValidationSubmission
    label: int
    dataset_name: str = "progpedia"


@dataclass
class PairRecord:
    """Computed signals for one pair."""

    pair_id: str
    label: int
    dataset_name: str
    left_submission_id: str
    right_submission_id: str
    language: str
    left_problem_id: str
    right_problem_id: str
    signals: dict[str, float]
    pair_features: dict[str, float]


@dataclass
class ThresholdMetrics:
    """Binary classification metrics at one threshold."""

    threshold: float
    precision: float
    recall: float
    f1_score: float
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int


@dataclass
class ExperimentResult:
    """Single experiment outcome."""

    name: str
    method: str
    weights: dict[str, float]
    best_threshold: float
    best_metrics: ThresholdMetrics
    score_preview: list[float] = field(default_factory=list)
    precision_recall_curve: list[dict[str, float]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class ExperimentReport:
    """Serializable experiment report."""

    dataset_name: str
    generated_at_unix: int
    pair_count: int
    positive_pairs: int
    negative_pairs: int
    verdicts: list[str]
    languages: list[str]
    signals: list[str]
    optional_capabilities: dict[str, bool]
    experiments: list[ExperimentResult]
    best_weights: dict[str, float]
    runtime_seconds: float

    def to_json_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
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
        """Persist JSON report to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_json_dict(), indent=2), encoding="utf-8")
        return path

    def save_markdown(self, path: Path) -> Path:
        """Persist Markdown report to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)

        lines: list[str] = [
            "# Fusion Optimization Report",
            "",
            f"- Dataset: `{self.dataset_name}`",
            f"- Pairs: `{self.pair_count}`",
            f"- Positives: `{self.positive_pairs}`",
            f"- Negatives: `{self.negative_pairs}`",
            f"- Verdicts: `{', '.join(self.verdicts)}`",
            f"- Languages: `{', '.join(self.languages)}`",
            f"- Signals: `{', '.join(self.signals)}`",
            "",
            "## Summary",
            "",
            "| Experiment | Method | F1 | Precision | Recall | Threshold |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]

        ranked = sorted(
            self.experiments,
            key=lambda item: item.best_metrics.f1_score,
            reverse=True,
        )
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
                "## Best Weights",
                "",
                "| Signal | Weight |",
                "| --- | ---: |",
            ]
        )
        for signal_name in self.signals:
            lines.append(
                f"| {signal_name} | {self.best_weights.get(signal_name, 0.0):.4f} |"
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
            lines.extend(
                [
                    "",
                    "| Threshold | Precision | Recall | F1 |",
                    "| ---: | ---: | ---: | ---: |",
                ]
            )
            for point in item.precision_recall_curve:
                lines.append(
                    "| "
                    f"{point['threshold']:.2f} | "
                    f"{point['precision']:.4f} | "
                    f"{point['recall']:.4f} | "
                    f"{point['f1_score']:.4f} |"
                )

        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path


class PROGpediaValidationDataset:
    """Build a labeled validation set from local PROGpedia data."""

    def __init__(
        self,
        root: Path = Path("data/datasets/progpedia"),
        verdicts: Optional[Iterable[str]] = None,
        max_submissions_per_problem_language: int = 4,
        max_positive_pairs_per_problem_language: int = 6,
        negative_ratio: float = 1.0,
        seed: int = 42,
    ) -> None:
        self.root = root
        self.verdicts = list(verdicts or ["ACCEPTED"])
        self.max_submissions_per_problem_language = max_submissions_per_problem_language
        self.max_positive_pairs_per_problem_language = (
            max_positive_pairs_per_problem_language
        )
        self.negative_ratio = negative_ratio
        self.seed = seed

    def build_pairs(self) -> list[ValidationPair]:
        """Construct balanced labeled pairs."""
        submissions = self._load_submissions()
        grouped: dict[tuple[str, str], list[ValidationSubmission]] = {}
        for submission in submissions:
            grouped.setdefault((submission.problem_id, submission.language), []).append(
                submission
            )

        rng = random.Random(self.seed)
        positives: list[ValidationPair] = []
        negatives: list[ValidationPair] = []

        for (problem_id, language), group in sorted(grouped.items()):
            if len(group) < 2:
                continue
            group_pairs = list(itertools.combinations(group, 2))
            rng.shuffle(group_pairs)
            for left, right in group_pairs[
                : self.max_positive_pairs_per_problem_language
            ]:
                positives.append(
                    ValidationPair(
                        pair_id=self._make_pair_id(left, right, label=1),
                        left=left,
                        right=right,
                        label=1,
                    )
                )

        by_language_problem: dict[str, dict[str, list[ValidationSubmission]]] = {}
        for submission in submissions:
            by_language_problem.setdefault(submission.language, {}).setdefault(
                submission.problem_id, []
            ).append(submission)

        target_negative_count = int(round(len(positives) * self.negative_ratio))
        for language, problem_groups in sorted(by_language_problem.items()):
            problem_ids = sorted(problem_groups.keys())
            if len(problem_ids) < 2:
                continue
            candidate_pairs: list[tuple[ValidationSubmission, ValidationSubmission]] = (
                []
            )
            for first_idx, first_problem in enumerate(problem_ids):
                for second_problem in problem_ids[first_idx + 1 :]:
                    candidate_pairs.extend(
                        itertools.product(
                            problem_groups[first_problem],
                            problem_groups[second_problem],
                        )
                    )
            rng.shuffle(candidate_pairs)
            for left, right in candidate_pairs:
                negatives.append(
                    ValidationPair(
                        pair_id=self._make_pair_id(left, right, label=0),
                        left=left,
                        right=right,
                        label=0,
                    )
                )
                if len(negatives) >= target_negative_count:
                    break
            if len(negatives) >= target_negative_count:
                break

        pairs = positives + negatives[:target_negative_count]
        rng.shuffle(pairs)
        LOGGER.info(
            "Built PROGpedia validation set with %s pairs (%s positive, %s negative)",
            len(pairs),
            len(positives),
            len(negatives[:target_negative_count]),
        )
        return pairs

    def _load_submissions(self) -> list[ValidationSubmission]:
        """Load capped submissions from the dataset root."""
        if not self.root.exists():
            raise FileNotFoundError(f"PROGpedia dataset not found at {self.root}")

        submissions: list[ValidationSubmission] = []
        for problem_dir in sorted(self.root.iterdir()):
            if not problem_dir.is_dir() or not problem_dir.name.isdigit():
                continue
            for verdict in self.verdicts:
                verdict_dir = problem_dir / verdict
                if not verdict_dir.exists():
                    continue
                per_language: dict[str, list[ValidationSubmission]] = {}
                for submission_dir in sorted(verdict_dir.iterdir()):
                    if not submission_dir.is_dir():
                        continue
                    submission = self._load_submission(
                        problem_dir.name, verdict, submission_dir
                    )
                    if submission is None:
                        continue
                    per_language.setdefault(submission.language, []).append(submission)
                for language_submissions in per_language.values():
                    submissions.extend(
                        language_submissions[
                            : self.max_submissions_per_problem_language
                        ]
                    )
        if not submissions:
            raise RuntimeError("No usable submissions were found in PROGpedia")
        return submissions

    def _load_submission(
        self,
        problem_id: str,
        verdict: str,
        submission_dir: Path,
    ) -> Optional[ValidationSubmission]:
        """Load one submission directory."""
        code_file: Optional[Path] = None
        for candidate in sorted(submission_dir.iterdir()):
            if candidate.is_file() and candidate.suffix in SUPPORTED_EXTENSIONS:
                code_file = candidate
                break

        if code_file is None:
            return None

        try:
            code = code_file.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            LOGGER.warning("Skipping %s: %s", code_file, exc)
            return None

        dsc_path = next(iter(sorted(submission_dir.glob("*.dsc.csv"))), None)
        cpg_path = next(iter(sorted(submission_dir.glob("*.cpg.csv"))), None)

        return ValidationSubmission(
            submission_id=submission_dir.name,
            problem_id=problem_id,
            verdict=verdict,
            language=SUPPORTED_EXTENSIONS[code_file.suffix],
            code_path=str(code_file),
            dsc_path=str(dsc_path) if dsc_path else None,
            cpg_path=str(cpg_path) if cpg_path else None,
            code=code,
        )

    @staticmethod
    def _make_pair_id(
        left: ValidationSubmission,
        right: ValidationSubmission,
        label: int,
    ) -> str:
        """Create stable pair identifier."""
        parts = sorted(
            [
                f"{left.problem_id}:{left.submission_id}",
                f"{right.problem_id}:{right.submission_id}",
            ]
        )
        return f"{label}::{parts[0]}::{parts[1]}"


class PairSignalExtractor:
    """Pure-Python feature extractor for validation experiments."""

    TOKEN_PATTERN = re.compile(r"[A-Za-z_]\w*|[0-9]+|[^\sA-Za-z0-9_]")
    IDENTIFIER_PATTERN = re.compile(r"[A-Za-z_]\w*")

    def __init__(self, cache_path: Path) -> None:
        self.cache_path = cache_path
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, dict[str, Any]] = self._load_cache()

    def extract(self, pair: ValidationPair) -> PairRecord:
        """Extract signals for a pair, using cache when available."""
        cached = self._cache.get(pair.pair_id)
        if cached is not None:
            return PairRecord(**cached)

        left_tokens = self._tokenize(pair.left.code)
        right_tokens = self._tokenize(pair.right.code)
        left_lines = self._normalized_lines(pair.left.code)
        right_lines = self._normalized_lines(pair.right.code)

        left_node_types, left_node_tokens = self._read_dsc_features(pair.left.dsc_path)
        right_node_types, right_node_tokens = self._read_dsc_features(
            pair.right.dsc_path
        )
        left_edge_types = self._read_edge_types(pair.left.cpg_path)
        right_edge_types = self._read_edge_types(pair.right.cpg_path)

        signals = {
            "token_jaccard": self._jaccard_similarity(left_tokens, right_tokens),
            "token_sequence": self._sequence_similarity(left_tokens, right_tokens),
            "char_ngram": self._char_ngram_similarity(pair.left.code, pair.right.code),
            "line_sequence": self._sequence_similarity(left_lines, right_lines),
            "cpg_node_type": self._bag_cosine_similarity(
                left_node_types, right_node_types
            ),
            "cpg_node_token": self._bag_cosine_similarity(
                left_node_tokens, right_node_tokens
            ),
            "cpg_edge_type": self._bag_cosine_similarity(
                left_edge_types, right_edge_types
            ),
        }

        pair_features = {
            "size_ratio": self._size_ratio(pair.left.code, pair.right.code),
            "identifier_overlap": self._identifier_overlap(left_tokens, right_tokens),
            "normalized_edit_similarity": self._sequence_similarity(
                list(pair.left.code),
                list(pair.right.code),
            ),
        }

        record = PairRecord(
            pair_id=pair.pair_id,
            label=pair.label,
            dataset_name=pair.dataset_name,
            left_submission_id=pair.left.submission_id,
            right_submission_id=pair.right.submission_id,
            language=pair.left.language,
            left_problem_id=pair.left.problem_id,
            right_problem_id=pair.right.problem_id,
            signals=signals,
            pair_features=pair_features,
        )
        self._cache[pair.pair_id] = asdict(record)
        return record

    def flush(self) -> None:
        """Write cache to disk."""
        self.cache_path.write_text(
            json.dumps(self._cache, indent=2),
            encoding="utf-8",
        )

    def _load_cache(self) -> dict[str, dict[str, Any]]:
        """Load persisted cache."""
        if not self.cache_path.exists():
            return {}
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
        except Exception as exc:
            LOGGER.warning("Failed to load pair cache %s: %s", self.cache_path, exc)
        return {}

    @classmethod
    def _tokenize(cls, code: str) -> list[str]:
        """Tokenize code with a lightweight regex tokenizer."""
        return cls.TOKEN_PATTERN.findall(code)

    @staticmethod
    def _normalized_lines(code: str) -> list[str]:
        """Normalize lines before line-sequence comparison."""
        lines = [line.strip() for line in code.splitlines()]
        return [line for line in lines if line]

    @staticmethod
    def _jaccard_similarity(left: list[str], right: list[str]) -> float:
        """Set-level overlap."""
        left_set = set(left)
        right_set = set(right)
        if not left_set and not right_set:
            return 1.0
        if not left_set or not right_set:
            return 0.0
        return len(left_set & right_set) / len(left_set | right_set)

    @staticmethod
    def _sequence_similarity(left: list[str], right: list[str]) -> float:
        """Sequence similarity using difflib."""
        if not left and not right:
            return 1.0
        if not left or not right:
            return 0.0
        return SequenceMatcher(a=left, b=right, autojunk=False).ratio()

    @staticmethod
    def _char_ngram_similarity(left: str, right: str, n: int = 5) -> float:
        """Character n-gram Jaccard similarity."""

        def build_ngrams(text: str) -> set[str]:
            normalized = re.sub(r"\s+", " ", text.strip())
            if len(normalized) < n:
                return {normalized} if normalized else set()
            return {normalized[idx : idx + n] for idx in range(len(normalized) - n + 1)}

        left_ngrams = build_ngrams(left)
        right_ngrams = build_ngrams(right)
        if not left_ngrams and not right_ngrams:
            return 1.0
        if not left_ngrams or not right_ngrams:
            return 0.0
        return len(left_ngrams & right_ngrams) / len(left_ngrams | right_ngrams)

    @staticmethod
    def _read_dsc_features(
        dsc_path: Optional[str],
    ) -> tuple[dict[str, int], dict[str, int]]:
        """Read node-type and node-token histograms from a DSC CSV."""
        if not dsc_path:
            return {}, {}
        node_types: dict[str, int] = {}
        node_tokens: dict[str, int] = {}
        try:
            with open(dsc_path, "r", encoding="utf-8", errors="ignore") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    node_type = (row.get("type") or "").strip()
                    token = (row.get("token") or "").strip()
                    if node_type:
                        node_types[node_type] = node_types.get(node_type, 0) + 1
                    if token:
                        node_tokens[token] = node_tokens.get(token, 0) + 1
        except OSError as exc:
            LOGGER.debug("Failed to read %s: %s", dsc_path, exc)
        return node_types, node_tokens

    @staticmethod
    def _read_edge_types(cpg_path: Optional[str]) -> dict[str, int]:
        """Read edge-type histogram from a CPG CSV."""
        if not cpg_path:
            return {}
        edge_types: dict[str, int] = {}
        try:
            with open(cpg_path, "r", encoding="utf-8", errors="ignore") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    edge_type = (row.get("type") or "").strip()
                    if edge_type:
                        edge_types[edge_type] = edge_types.get(edge_type, 0) + 1
        except OSError as exc:
            LOGGER.debug("Failed to read %s: %s", cpg_path, exc)
        return edge_types

    @staticmethod
    def _bag_cosine_similarity(left: dict[str, int], right: dict[str, int]) -> float:
        """Cosine similarity over sparse count bags."""
        if not left and not right:
            return 1.0
        if not left or not right:
            return 0.0
        keys = set(left) | set(right)
        dot_product = sum(left.get(key, 0) * right.get(key, 0) for key in keys)
        left_norm = math.sqrt(sum(value * value for value in left.values()))
        right_norm = math.sqrt(sum(value * value for value in right.values()))
        if left_norm == 0.0 or right_norm == 0.0:
            return 0.0
        return dot_product / (left_norm * right_norm)

    @classmethod
    def _identifier_overlap(
        cls, left_tokens: list[str], right_tokens: list[str]
    ) -> float:
        """Identifier overlap excluding short names."""
        left_identifiers = {
            token.lower()
            for token in left_tokens
            if cls.IDENTIFIER_PATTERN.fullmatch(token) and len(token) > 2
        }
        right_identifiers = {
            token.lower()
            for token in right_tokens
            if cls.IDENTIFIER_PATTERN.fullmatch(token) and len(token) > 2
        }
        if not left_identifiers and not right_identifiers:
            return 1.0
        if not left_identifiers or not right_identifiers:
            return 0.0
        return len(left_identifiers & right_identifiers) / len(
            left_identifiers | right_identifiers
        )

    @staticmethod
    def _size_ratio(left_code: str, right_code: str) -> float:
        """Symmetric size ratio in [0, 1]."""
        left_size = max(len(left_code), 1)
        right_size = max(len(right_code), 1)
        return min(left_size, right_size) / max(left_size, right_size)


class FusionOptimizationRunner:
    """Run baseline and optimized fusion experiments."""

    def __init__(
        self,
        output_dir: Path,
        dataset_root: Path = Path("data/datasets/progpedia"),
        verdicts: Optional[Iterable[str]] = None,
        trials: int = 80,
        threshold_step: float = 0.02,
        max_submissions_per_problem_language: int = 4,
        max_positive_pairs_per_problem_language: int = 6,
        negative_ratio: float = 1.0,
        seed: int = 42,
    ) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.dataset = PROGpediaValidationDataset(
            root=dataset_root,
            verdicts=verdicts,
            max_submissions_per_problem_language=max_submissions_per_problem_language,
            max_positive_pairs_per_problem_language=max_positive_pairs_per_problem_language,
            negative_ratio=negative_ratio,
            seed=seed,
        )
        self.trials = trials
        self.threshold_step = threshold_step
        self.seed = seed
        self.extractor = PairSignalExtractor(
            self.output_dir / "cache" / "pair_signals.json"
        )

    def run(self) -> ExperimentReport:
        """Execute the experiment suite and write reports."""
        started = time.time()
        pairs = self.dataset.build_pairs()
        records = [self.extractor.extract(pair) for pair in pairs]
        self.extractor.flush()
        self._export_training_matrix(records)

        optional_capabilities = {
            "optuna": self._module_available("optuna"),
            "sklearn": self._module_available("sklearn"),
        }

        experiments: list[ExperimentResult] = []

        baseline_weights = self._equal_weights()
        experiments.append(
            self._evaluate_weighted_strategy(
                name="Equal Weight Baseline",
                method="weighted_average",
                records=records,
                weights=baseline_weights,
            )
        )

        seeded_weights = self._seed_formula_weights()
        experiments.append(
            self._evaluate_weighted_strategy(
                name="Seeded Prior Fusion",
                method="seeded_weighted_average",
                records=records,
                weights=seeded_weights,
                notes=[
                    "seed_formula=0.4*AST + 0.25*Winnowing + 0.2*Inbanding + 4*0.1 other engines",
                    "seed_formula_normalized=true",
                    self._alias_note(),
                ],
            )
        )

        experiments.append(
            self._evaluate_weighted_strategy(
                name="Seeded Prior + Strong Pooling",
                method="strong_pool_then_weighted_average",
                records=records,
                weights=seeded_weights,
                pool_mix=0.35,
                notes=[
                    "strong_pool_mix=0.35",
                    f"strong_signals={','.join(STRONG_SIGNAL_NAMES)}",
                    self._alias_note(),
                ],
            )
        )

        optimized_weights, optimized_pool_mix, optimization_notes = (
            self._optimize_seeded_fusion(records)
        )
        optimized_result = self._evaluate_weighted_strategy(
            name="Optimized Seeded Fusion",
            method="weighted_average",
            records=records,
            weights=optimized_weights,
            pool_mix=optimized_pool_mix,
            notes=optimization_notes + [self._alias_note()],
        )
        experiments.append(optimized_result)

        pooling_result = self._evaluate_max_pooling(records)
        experiments.append(pooling_result)

        rf_result = self._evaluate_random_forest(records)
        if rf_result is not None:
            experiments.append(rf_result)

        report = ExperimentReport(
            dataset_name="progpedia",
            generated_at_unix=int(time.time()),
            pair_count=len(records),
            positive_pairs=sum(record.label for record in records),
            negative_pairs=sum(1 for record in records if record.label == 0),
            verdicts=self.dataset.verdicts,
            languages=sorted({record.language for record in records}),
            signals=list(SIGNAL_NAMES),
            optional_capabilities=optional_capabilities,
            experiments=experiments,
            best_weights=optimized_weights,
            runtime_seconds=time.time() - started,
        )
        return report

    @staticmethod
    def _module_available(module_name: str) -> bool:
        """Check optional dependency availability."""
        try:
            __import__(module_name)
            return True
        except Exception:
            return False

    @staticmethod
    def _equal_weights() -> dict[str, float]:
        """Return exact equal weights for the seven signals."""
        weight = 1.0 / len(SIGNAL_NAMES)
        return {name: weight for name in SIGNAL_NAMES}

    @staticmethod
    def _alias_note() -> str:
        """Explain how requested engine names map to local signals."""
        return (
            "signal_aliases="
            "ast_sim->cpg_node_type,"
            "winnowing_sim->token_sequence,"
            "inbanding_sim->char_ngram"
        )

    def _seed_formula_weights(self) -> dict[str, float]:
        """Map the requested seed formula onto local signals."""
        raw_weights = {
            PRIOR_SIGNAL_ALIASES[name]: value
            for name, value in SEED_FORMULA_RAW_WEIGHTS.items()
        }
        return self._normalize_weights(raw_weights)

    def _optimize_seeded_fusion(
        self,
        records: list[PairRecord],
    ) -> tuple[dict[str, float], float, list[str]]:
        """Optimize weights and pooling using Optuna or fallback random search."""
        if self._module_available("optuna"):
            try:
                return self._optimize_seeded_fusion_with_optuna(records)
            except Exception as exc:
                LOGGER.warning(
                    "Optuna optimization failed, falling back to random search: %s", exc
                )

        return self._optimize_seeded_fusion_with_random_search(records)

    def _optimize_seeded_fusion_with_optuna(
        self,
        records: list[PairRecord],
    ) -> tuple[dict[str, float], float, list[str]]:
        """Optimize weights with Optuna around the seed formula."""
        import optuna

        seed_weights = self._seed_formula_weights()

        def objective(trial: optuna.Trial) -> float:
            raw_weights = {
                signal_name: seed_weights[signal_name]
                * trial.suggest_float(f"scale_{signal_name}", 0.25, 2.50)
                for signal_name in SIGNAL_NAMES
            }
            weights = self._normalize_weights(raw_weights)
            pool_mix = trial.suggest_float("pool_mix", 0.0, 0.8)
            scores = [
                self._weighted_score(record, weights, pool_mix=pool_mix)
                for record in records
            ]
            _, best_metrics, _ = self._find_best_threshold(
                scores,
                [record.label for record in records],
            )
            return best_metrics.f1_score

        study = optuna.create_study(direction="maximize")
        study.optimize(objective, n_trials=self.trials, show_progress_bar=False)
        best_weights = self._normalize_weights(
            {
                signal_name: seed_weights[signal_name]
                * study.best_params[f"scale_{signal_name}"]
                for signal_name in SIGNAL_NAMES
            }
        )
        return (
            best_weights,
            float(study.best_params["pool_mix"]),
            [
                "optimizer=optuna",
                "seed_formula_used_as_prior=true",
            ],
        )

    def _optimize_seeded_fusion_with_random_search(
        self,
        records: list[PairRecord],
    ) -> tuple[dict[str, float], float, list[str]]:
        """Optimize around the seed formula with standard-library random search."""
        rng = random.Random(self.seed)
        seed_weights = self._seed_formula_weights()
        best_weights = dict(seed_weights)
        best_pool_mix = 0.0
        best_f1 = -1.0
        for baseline_pool_mix in (0.0, 0.35):
            baseline_scores = [
                self._weighted_score(record, best_weights, pool_mix=baseline_pool_mix)
                for record in records
            ]
            _, baseline_metrics, _ = self._find_best_threshold(
                baseline_scores,
                [record.label for record in records],
            )
            if baseline_metrics.f1_score > best_f1:
                best_f1 = baseline_metrics.f1_score
                best_pool_mix = baseline_pool_mix

        for _ in range(self.trials):
            candidate = self._sample_seeded_weights(rng, seed_weights)
            pool_mix = rng.uniform(0.0, 0.8)
            scores = [
                self._weighted_score(record, candidate, pool_mix=pool_mix)
                for record in records
            ]
            _, metrics, _ = self._find_best_threshold(
                scores, [record.label for record in records]
            )
            if metrics.f1_score > best_f1:
                best_f1 = metrics.f1_score
                best_weights = candidate
                best_pool_mix = pool_mix

        return (
            best_weights,
            best_pool_mix,
            [
                "optimizer=random_search",
                "seed_formula_used_as_prior=true",
            ],
        )

    @staticmethod
    def _sample_simplex_weights(rng: random.Random) -> dict[str, float]:
        """Sample non-negative weights summing to one."""
        raw_values = {}
        for signal_name in SIGNAL_NAMES:
            value = -math.log(max(rng.random(), 1e-12))
            raw_values[signal_name] = value
        return FusionOptimizationRunner._normalize_weights(raw_values)

    @staticmethod
    def _sample_seeded_weights(
        rng: random.Random,
        seed_weights: dict[str, float],
    ) -> dict[str, float]:
        """Sample weights around a seed formula."""
        raw_values: dict[str, float] = {}
        for signal_name in SIGNAL_NAMES:
            multiplier = rng.uniform(0.25, 2.50)
            raw_values[signal_name] = seed_weights[signal_name] * multiplier
        if rng.random() < 0.25:
            return FusionOptimizationRunner._sample_simplex_weights(rng)
        return FusionOptimizationRunner._normalize_weights(raw_values)

    @staticmethod
    def _normalize_weights(weights: dict[str, float]) -> dict[str, float]:
        """Normalize weights to sum to one."""
        total = sum(max(value, 0.0) for value in weights.values())
        if total <= 0.0:
            return FusionOptimizationRunner._equal_weights()
        return {
            signal_name: max(weights.get(signal_name, 0.0), 0.0) / total
            for signal_name in SIGNAL_NAMES
        }

    def _evaluate_weighted_strategy(
        self,
        name: str,
        method: str,
        records: list[PairRecord],
        weights: dict[str, float],
        pool_mix: float = 0.0,
        notes: Optional[list[str]] = None,
    ) -> ExperimentResult:
        """Evaluate a weighted-average strategy."""
        scores = [
            self._weighted_score(record, weights, pool_mix=pool_mix)
            for record in records
        ]
        best_threshold, best_metrics, curve = self._find_best_threshold(
            scores,
            [record.label for record in records],
        )
        return ExperimentResult(
            name=name,
            method=method,
            weights=weights,
            best_threshold=best_threshold,
            best_metrics=best_metrics,
            score_preview=[round(score, 4) for score in scores[:10]],
            precision_recall_curve=curve,
            notes=list(notes or []),
        )

    @staticmethod
    def _weighted_score(
        record: PairRecord,
        weights: dict[str, float],
        pool_mix: float = 0.0,
    ) -> float:
        """Compute weighted average with optional strong-signal pooling."""
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

    def _evaluate_max_pooling(self, records: list[PairRecord]) -> ExperimentResult:
        """Evaluate max-pooling filter before averaging."""
        pooling_gate = 0.75
        scores: list[float] = []
        for record in records:
            active_scores = [
                record.signals[signal_name]
                for signal_name in SIGNAL_NAMES
                if record.signals[signal_name] >= pooling_gate
            ]
            if not active_scores:
                active_scores = [
                    record.signals[signal_name] for signal_name in SIGNAL_NAMES
                ]
            scores.append(sum(active_scores) / len(active_scores))

        best_threshold, best_metrics, curve = self._find_best_threshold(
            scores,
            [record.label for record in records],
        )
        return ExperimentResult(
            name="Max Pooling Fusion",
            method="max_pool_then_average",
            weights={
                signal_name: 1.0 / len(SIGNAL_NAMES) for signal_name in SIGNAL_NAMES
            },
            best_threshold=best_threshold,
            best_metrics=best_metrics,
            score_preview=[round(score, 4) for score in scores[:10]],
            precision_recall_curve=curve,
            notes=[f"pooling_gate={pooling_gate:.2f}"],
        )

    def _evaluate_random_forest(
        self,
        records: list[PairRecord],
    ) -> Optional[ExperimentResult]:
        """Evaluate Random Forest fusion if scikit-learn is available."""
        if not self._module_available("sklearn"):
            return ExperimentResult(
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
                notes=["scikit-learn unavailable in this environment"],
            )

        try:
            from sklearn.ensemble import RandomForestClassifier
        except Exception as exc:
            LOGGER.warning("Random Forest unavailable: %s", exc)
            return ExperimentResult(
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
                notes=[f"scikit-learn import failed: {exc}"],
            )

        rng = random.Random(self.seed)
        shuffled_records = list(records)
        rng.shuffle(shuffled_records)
        split_index = max(1, int(len(shuffled_records) * 0.8))
        train_records = shuffled_records[:split_index]
        eval_records = shuffled_records[split_index:] or shuffled_records

        train_x = [self._meta_features(record) for record in train_records]
        train_y = [record.label for record in train_records]
        eval_x = [self._meta_features(record) for record in eval_records]
        eval_y = [record.label for record in eval_records]

        model = RandomForestClassifier(
            n_estimators=200,
            random_state=self.seed,
            max_depth=8,
        )
        model.fit(train_x, train_y)
        probabilities = model.predict_proba(eval_x)
        scores = [max(0.0, min(1.0, float(row[1]))) for row in probabilities]
        best_threshold, best_metrics, curve = self._find_best_threshold(scores, eval_y)

        return ExperimentResult(
            name="Random Forest Meta Learner",
            method="random_forest",
            weights={},
            best_threshold=best_threshold,
            best_metrics=best_metrics,
            score_preview=[round(score, 4) for score in scores[:10]],
            precision_recall_curve=curve,
            notes=["train_split=0.80", f"eval_pairs={len(eval_records)}"],
        )

    def _export_training_matrix(self, records: list[PairRecord]) -> None:
        """Export the training matrix for later meta-model experiments."""
        matrix_path = self.output_dir / "fusion_training_matrix.csv"
        fieldnames = [
            "pair_id",
            "label",
            "language",
            "left_problem_id",
            "right_problem_id",
            *SIGNAL_NAMES,
            *PAIR_FEATURE_NAMES,
        ]
        with matrix_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for record in records:
                row = {
                    "pair_id": record.pair_id,
                    "label": record.label,
                    "language": record.language,
                    "left_problem_id": record.left_problem_id,
                    "right_problem_id": record.right_problem_id,
                }
                row.update(record.signals)
                row.update(record.pair_features)
                writer.writerow(row)

    @staticmethod
    def _meta_features(record: PairRecord) -> list[float]:
        """Build meta-learner feature vector."""
        return [
            *(record.signals[name] for name in SIGNAL_NAMES),
            *(record.pair_features[name] for name in PAIR_FEATURE_NAMES),
        ]

    def _find_best_threshold(
        self,
        scores: list[float],
        labels: list[int],
    ) -> tuple[float, ThresholdMetrics, list[dict[str, float]]]:
        """Sweep thresholds and return the best F1 point."""
        best_threshold = 0.5
        best_metrics = self._metrics_at_threshold(scores, labels, 0.5)
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
        """Compute binary metrics at a threshold."""
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


def run_fusion_optimization(
    output_dir: Path,
    dataset_root: Path = Path("data/datasets/progpedia"),
    verdicts: Optional[Iterable[str]] = None,
    trials: int = 80,
    threshold_step: float = 0.02,
    max_submissions_per_problem_language: int = 4,
    max_positive_pairs_per_problem_language: int = 6,
    negative_ratio: float = 1.0,
    seed: int = 42,
) -> ExperimentReport:
    """Convenience wrapper used by the CLI."""
    runner = FusionOptimizationRunner(
        output_dir=output_dir,
        dataset_root=dataset_root,
        verdicts=verdicts,
        trials=trials,
        threshold_step=threshold_step,
        max_submissions_per_problem_language=max_submissions_per_problem_language,
        max_positive_pairs_per_problem_language=max_positive_pairs_per_problem_language,
        negative_ratio=negative_ratio,
        seed=seed,
    )
    return runner.run()
