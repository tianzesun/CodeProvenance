#!/usr/bin/env python
"""Train the AI-generated-code classifier from a labeled dataset.

Labelled dataset format
-----------------------
A directory containing two subdirectories:

    data/
      ai/     <- one file per AI-generated submission (.py/.java/.cpp/.cs/...)
      human/  <- one file per human-written submission

Alternatively a single JSON/JSONL file ``dataset.json``::

    {"samples": [{"code": "...", "label": 1, "source": "optional"}]}

where ``label`` is 1 (AI) or 0 (human).

Run::

    python -m src.backend.engines.ai.train_classifier data/ \
        --model-dir src/backend/engines/ai/models

Outputs a ``joblib`` model and a metrics report (precision/recall/F1/AUC).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from src.backend.engines.ai.ast_features import TreeSitterASTExtractor  # noqa: E402
from src.backend.engines.ai.classifier import (  # noqa: E402
    AICodeClassifier,
    assemble_features,
)
from src.backend.engines.ai.perplexity import PerplexityScorer  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
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


def _infer_language(filename: str) -> str:
    """Infer the language from a file name (mirrors server helper)."""
    suffix = Path(filename).suffix.lower()
    mapping = {
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
    return mapping.get(suffix, "python")


def load_dataset(path: Path) -> Tuple[List[str], List[int], List[str]]:
    """Load labelled code samples and return (codes, labels, sources)."""
    if path.is_file():
        if path.suffix.lower() in (".json", ".jsonl"):
            return _load_json_dataset(path)
        raise ValueError("Dataset must be a directory or .json/.jsonl file")

    if not path.is_dir():
        raise ValueError(f"Dataset path not found: {path}")

    codes: List[str] = []
    labels: List[int] = []
    sources: List[str] = []
    for subdir, label in (("ai", 1), ("human", 0)):
        category = path / subdir
        if not category.is_dir():
            raise ValueError(
                f"Expecting '{path}/{subdir}' directory for labelled samples"
            )
        for file_path in sorted(category.rglob("*")):
            if file_path.suffix.lower() not in SUPPORTED_SUFFIXES:
                continue
            code = file_path.read_text(encoding="utf-8", errors="replace")
            if len(code.strip()) < 20:
                continue
            codes.append(code)
            labels.append(label)
            sources.append(str(file_path))
    return codes, labels, sources


def _load_json_dataset(path: Path) -> Tuple[List[str], List[int], List[str]]:
    """Load samples from a JSON/JSONL dataset file."""
    lines = path.read_text(encoding="utf-8").splitlines()
    data: List[Dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        data.append(record)
    if len(data) == 1 and isinstance(data[0].get("samples"), list):
        data = data[0]["samples"]

    codes = [str(item["code"]) for item in data if item.get("code")]
    labels = [int(item["label"]) for item in data if item.get("code")]
    sources = [str(item.get("source") or "json") for item in data if item.get("code")]
    return codes, labels, sources


def build_feature_rows(codes: List[str], sources: List[str]) -> List[Dict[str, float]]:
    """Compute the classifier feature dict for every sample."""
    ast_extractor = TreeSitterASTExtractor()
    perplexity = PerplexityScorer()
    rows: List[Dict[str, float]] = []
    from src.backend.engines.features.code_stylometry import StylometryExtractor

    stylometry_extractor = StylometryExtractor()

    for code, source in zip(codes, sources):
        language = _infer_language(source)
        ast_vector = ast_extractor.extract(code, language)
        stylometry = stylometry_extractor.extract(code, doc_id="")
        perp = perplexity.score(code)
        rows.append(assemble_features(ast_vector, stylometry, perp))
    return rows


def main() -> None:
    """Train the classifier and emit a metrics report."""
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
        help="Intended scoring mode (ml = use classifier in ensemble)",
    )
    args = parser.parse_args()

    codes, labels, sources = load_dataset(args.dataset)
    if len(codes) < 10 or len(set(labels)) < 2:
        raise SystemExit("Need >=10 samples covering both classes to train")

    positive = sum(labels)
    logger.info(
        "Loaded %d samples (%d AI, %d human)",
        len(codes),
        positive,
        len(labels) - positive,
    )

    rows = build_feature_rows(codes, sources)

    # Hold out a stratified 20% for evaluation
    from sklearn.model_selection import StratifiedShuffleSplit

    split = StratifiedShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_idx, test_idx = next(iter(split.split(rows, labels)))
    train_rows = [rows[i] for i in train_idx]
    train_labels = [labels[i] for i in train_idx]
    test_rows = [rows[i] for i in test_idx]
    test_labels = [labels[i] for i in test_idx]

    classifier = AICodeClassifier(model_dir=args.model_dir)
    version = classifier.train(
        train_rows,
        train_labels,
        feature_names=AICodeClassifier.FEATURE_KEYS,
    )
    model_path = classifier.save()
    logger.info("Trained model version=%s saved to %s", version, model_path)

    evaluate(classifier, test_rows, test_labels, test_idx, sources)


def evaluate(
    classifier: AICodeClassifier,
    test_rows: List[Dict[str, float]],
    test_labels: List[int],
    test_idx: List[int],
    sources: List[str],
) -> None:
    """Print precision/recall/F1/AUC for a trained classifier."""
    from sklearn.metrics import (
        accuracy_score,
        classification_report,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )

    predictions = [
        int(classifier.predict(row).ai_probability >= 0.5) for row in test_rows
    ]
    probabilities = [classifier.predict(row).ai_probability for row in test_rows]

    report = {
        "accuracy": round(accuracy_score(test_labels, predictions), 4),
        "precision": round(precision_score(test_labels, predictions), 4),
        "recall": round(recall_score(test_labels, predictions), 4),
        "f1": round(f1_score(test_labels, predictions), 4),
        "auc": round(roc_auc_score(test_labels, probabilities), 4),
        "test_size": len(test_rows),
    }
    print("\n=== Classifier evaluation ===")
    for key, value in report.items():
        print(f"{key:12}: {value}")
    print("\nClassification report:")
    print(classification_report(test_labels, predictions, zero_division=0))

    # Show a few mistakes for debugging
    print("\nMisclassified samples:")
    shown = 0
    for i, (pred, actual) in enumerate(zip(predictions, test_labels)):
        if pred != actual and shown < 5:
            source_idx = test_idx[i]
            print(
                f"  {sources[source_idx]} pred={pred} actual={actual} "
                f"prob={probabilities[i]:.3f}"
            )
            shown += 1


if __name__ == "__main__":
    main()
