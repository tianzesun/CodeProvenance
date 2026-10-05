#!/usr/bin/env python
"""Train the AI-generated-code classifier from a labeled dataset.

Labelled dataset format
-----------------------
A directory containing two subdirectories:

    data/
      ai/     <- one file per AI-generated submission (.py/.java/.cpp/.cs/...)
      human/  <- one file per human-written submission
      samples.jsonl   (optional) per-sample ``problem_id``; see below

Alternatively a single JSON/JSONL file::

    {"samples": [{"code": "...", "label": 1, "problem_id": "p1", "language": "python"}]}

where ``label`` is 1 (AI) or 0 (human).

Evaluation is GROUPED by ``problem_id`` whenever the dataset carries one
(``samples.jsonl`` next to ``ai/`` + ``human/``, or a ``problem_id`` field in the
JSON records): the same problem never appears in both train and test. A random
split lets the classifier memorise problem-specific style and reports inflated
metrics, which is exactly what ``benchmark_classifier`` is written to avoid;
this script used to do it anyway. Without problem ids the script falls back to a
stratified random split and says so.

Run::

    python -m src.backend.engines.ai.train_classifier data/ \
        --model-dir src/backend/engines/ai/models --refit-all

Outputs a ``joblib`` model (with a SHA-256 sidecar) and a metrics report
(precision/recall/F1/AUC/FPR). Add ``--refit-all`` to retrain on every sample
after evaluating, so the shipped model uses all the data.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from src.backend.engines.ai.classifier import AICodeClassifier
from src.backend.engines.ai.feature_rows import build_feature_rows

logger = logging.getLogger("train_classifier")

SUPPORTED_SUFFIXES = {
    ".py",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".cc",
    ".cs",
    ".js",
    ".ts",
    ".go",
    ".rs",
    ".rb",
    ".php",
}

_SUFFIX_LANGUAGES = {
    ".py": "python",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".h": "c",
    ".cs": "csharp",
    ".js": "javascript",
    ".ts": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
}


def _infer_language(filename: str) -> str:
    """Infer the language from a file name (mirrors server helper)."""
    return _SUFFIX_LANGUAGES.get(Path(filename).suffix.lower(), "python")


@dataclass
class LabelledDataset:
    """Labelled samples with the metadata needed for a grouped evaluation."""

    codes: list[str] = field(default_factory=list)
    labels: list[int] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    #: problem id per sample ("" when unknown)
    groups: list[str] = field(default_factory=list)

    @property
    def grouped(self) -> bool:
        """True when the samples fall into at least 5 identifiable problem groups."""
        return len({g for g in self.groups if g}) >= 5 and all(self.groups)


def _find_index(path: Path) -> dict[str, dict[str, Any]]:
    """Map file name -> record from a ``samples.jsonl`` at or just above ``path``."""
    for candidate in (path / "samples.jsonl", path.parent / "samples.jsonl"):
        if candidate.exists():
            index: dict[str, dict[str, Any]] = {}
            for line in candidate.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if record.get("file"):
                        index[Path(str(record["file"])).name] = record
            return index
    return {}


def load_labelled_dataset(path: Path) -> LabelledDataset:
    """Load labelled code samples, including problem groups and languages."""
    if path.is_file():
        if path.suffix.lower() in (".json", ".jsonl"):
            return _load_json_dataset_full(path)
        raise ValueError("Dataset must be a directory or .json/.jsonl file")
    if not path.is_dir():
        raise ValueError(f"Dataset path not found: {path}")

    data = LabelledDataset()
    index = _find_index(path)
    for subdir, label in (("ai", 1), ("human", 0)):
        category = path / subdir
        if not category.is_dir():
            raise ValueError(f"Expecting '{path}/{subdir}' directory for labelled samples")
        for file_path in sorted(category.rglob("*")):
            if file_path.suffix.lower() not in SUPPORTED_SUFFIXES:
                continue
            code = file_path.read_text(encoding="utf-8", errors="replace")
            if len(code.strip()) < 20:
                continue
            meta = index.get(file_path.name, {})
            data.codes.append(code)
            data.labels.append(label)
            data.sources.append(str(file_path))
            data.languages.append(str(meta.get("language") or _infer_language(file_path.name)))
            data.groups.append(str(meta.get("problem_id") or ""))
    return data


def load_dataset(path: Path) -> tuple[list[str], list[int], list[str]]:
    """Load labelled code samples and return (codes, labels, sources)."""
    data = load_labelled_dataset(path)
    return data.codes, data.labels, data.sources


def _read_json_records(path: Path) -> list[dict[str, Any]]:
    """Read records from a JSON document or a JSONL file.

    Line-by-line parsing was applied to ``.json`` as well, so the documented
    single-object ``{"samples": [...]}`` form (pretty-printed over many lines)
    failed with a JSONDecodeError.
    """
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".json":
        payload = json.loads(text)
        if isinstance(payload, dict) and isinstance(payload.get("samples"), list):
            return payload["samples"]
        if isinstance(payload, list):
            return payload
        raise ValueError('JSON dataset must be a list or {"samples": [...]}')
    records = []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{number}: invalid JSON ({exc})") from exc
        records.extend(record["samples"] if isinstance(record.get("samples"), list) else [record])
    return records


def _load_json_dataset_full(path: Path) -> LabelledDataset:
    data = LabelledDataset()
    for number, item in enumerate(_read_json_records(path), 1):
        code = item.get("code")
        if not code:
            continue
        try:
            label = int(item["label"])
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"record {number}: 'label' must be 0 or 1") from None
        if label not in (0, 1):
            raise ValueError(f"record {number}: label {label} is not 0 or 1")
        data.codes.append(str(code))
        data.labels.append(label)
        data.sources.append(str(item.get("source") or "json"))
        data.languages.append(str(item.get("language") or "python"))
        data.groups.append(str(item.get("problem_id") or ""))
    return data


def _load_json_dataset(path: Path) -> tuple[list[str], list[int], list[str]]:
    """Load samples from a JSON/JSONL dataset file."""
    data = _load_json_dataset_full(path)
    return data.codes, data.labels, data.sources


def build_feature_rows_for(codes: list[str], sources: list[str], languages: list[str] | None = None, cache_path: Path | None = None):
    """Compute the classifier feature dict for every sample."""
    languages = languages or [_infer_language(s) for s in sources]
    return build_feature_rows(codes, languages, cache_path=cache_path)


def split_indices(
    labels: list[int], groups: list[str], grouped: bool, test_size: float, seed: int
) -> tuple[list[int], list[int]]:
    """Train/test indices: grouped by problem when possible, else stratified."""
    rows = list(range(len(labels)))
    if grouped:
        from sklearn.model_selection import GroupShuffleSplit

        train_idx, test_idx = next(
            GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=seed).split(rows, labels, groups)
        )
    else:
        from sklearn.model_selection import StratifiedShuffleSplit

        train_idx, test_idx = next(
            StratifiedShuffleSplit(n_splits=1, test_size=test_size, random_state=seed).split(rows, labels)
        )
    return list(map(int, train_idx)), list(map(int, test_idx))


def main() -> None:
    """Train the classifier and emit a metrics report."""
    # Logging is configured here, not at import: importing this module (for
    # example from a test or another script) used to reconfigure the root logger.
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "dataset", type=Path, help="Directory (ai/ + human/) or JSON file"
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=Path(__file__).parent / "models",
        help="Where to save the trained model",
    )
    parser.add_argument(
        "--feature-mode",
        default="ml",
        choices=["ml", "heuristic"],
        help="Deprecated and ignored.",
    )
    parser.add_argument("--test-size", type=float, default=0.2, help="held-out fraction")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--refit-all",
        action="store_true",
        help="after evaluating on the held-out set, retrain on ALL samples and save that model",
    )
    parser.add_argument(
        "--feature-cache",
        type=Path,
        default=None,
        help="JSON file caching computed features (invalidated when extractor code changes)",
    )
    args = parser.parse_args()
    if args.feature_mode != "ml":
        logger.warning("--feature-mode is deprecated and ignored")

    data = load_labelled_dataset(args.dataset)
    if len(data.codes) < 10 or len(set(data.labels)) < 2:
        raise SystemExit("Need >=10 samples covering both classes to train")

    positive = sum(data.labels)
    logger.info(
        "Loaded %d samples (%d AI, %d human)",
        len(data.codes),
        positive,
        len(data.labels) - positive,
    )

    build = build_feature_rows_for(data.codes, data.sources, data.languages, args.feature_cache)
    rows = build.rows
    metadata = {"perplexity_model": build.perplexity_model}

    if data.grouped:
        logger.info("Evaluating on held-out PROBLEMS (%d groups)", len(set(data.groups)))
    else:
        logger.warning(
            "No problem ids found: using a random stratified split. Metrics will be "
            "OPTIMISTIC because the same problem can appear in train and test. Provide "
            "samples.jsonl (build_aigcodeset / build_student_dataset) for a grouped evaluation."
        )
    train_idx, test_idx = split_indices(data.labels, data.groups, data.grouped, args.test_size, args.seed)
    train_labels = [data.labels[i] for i in train_idx]
    test_labels = [data.labels[i] for i in test_idx]
    if len(set(train_labels)) < 2:
        raise SystemExit("The training split contains a single class; use more data or another seed")

    classifier = AICodeClassifier(model_dir=args.model_dir)
    version = classifier.train(
        [rows[i] for i in train_idx],
        train_labels,
        feature_names=AICodeClassifier.FEATURE_KEYS,
        metadata=metadata,
    )
    logger.info("Trained model version=%s on %d samples", version, len(train_idx))
    evaluate(classifier, [rows[i] for i in test_idx], test_labels, test_idx, data.sources, grouped=data.grouped)

    if args.refit_all:
        # The evaluation above describes the 80% model; the shipped model uses all the data.
        version = classifier.train(
            rows, data.labels, feature_names=AICodeClassifier.FEATURE_KEYS, metadata=metadata
        )
        logger.info("Refit on all %d samples: version=%s", len(rows), version)
    model_path = classifier.save()
    logger.info("Saved model version=%s to %s", version, model_path)


def evaluate(
    classifier: AICodeClassifier,
    test_rows: list[dict[str, float]],
    test_labels: list[int],
    test_idx: list[int],
    sources: list[str],
    grouped: bool = False,
) -> dict[str, Any]:
    """Print precision/recall/F1/AUC/FPR for a trained classifier."""
    from sklearn.metrics import classification_report

    from src.backend.engines.ai.benchmark_classifier import compute_metrics

    # Predicted once (it was called twice per sample).
    probabilities = [r.ai_probability for r in classifier.predict_many(test_rows)]
    predictions = [int(p >= 0.5) for p in probabilities]

    report = {
        "split": "grouped by problem" if grouped else "random (optimistic)",
        "test_size": len(test_rows),
        "at_0.50": compute_metrics(test_labels, probabilities, 0.5),
        "at_0.40": compute_metrics(test_labels, probabilities, 0.40),
        "at_0.70": compute_metrics(test_labels, probabilities, 0.70),
    }
    print(f"\n=== Classifier evaluation ({report['split']}, n={len(test_rows)}) ===")
    for name in ("at_0.50", "at_0.40", "at_0.70"):
        m = report[name]
        auc = "n/a" if m["auc"] is None else f"{m['auc']:.4f}"
        print(
            f"{name}: acc={m['accuracy']:.4f} precision={m['precision']:.4f} "
            f"recall={m['recall']:.4f} f1={m['f1']:.4f} FPR={m['fpr']:.4f} auc={auc}"
        )
    print("\nClassification report:")
    print(classification_report(test_labels, predictions, zero_division=0))

    # Show a few mistakes for debugging
    print("\nMisclassified samples:")
    shown = 0
    for i, (pred, actual) in enumerate(zip(predictions, test_labels)):
        if pred != actual and shown < 5:
            print(
                f"  {sources[test_idx[i]]} pred={pred} actual={actual} "
                f"prob={probabilities[i]:.3f}"
            )
            shown += 1
    return report


if __name__ == "__main__":
    main()
