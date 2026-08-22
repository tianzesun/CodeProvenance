"""Measure the live AI detector's false-positive rate on real human code.

Runs the production ``AIDetectionOrchestrator`` (the same object the
background AI-detection job uses) over corpora of known-human code and
reports how often submissions would be flagged at the product's action
thresholds. This is the FP risk number the student-holdout decision gate
turns on; it needs no labelled AI side because every input is human.

Corpora:
- kaggle_student_code : novice student Python (closest to classroom input)
- ir_plag_originals   : human student Java originals from IR-Plag cases
- poolc_sample        : human community Python (contrast group, non-student)

Usage:
    python scripts/measure_human_fp.py [--poolc-n 100] [--out reports/human_fp]

Output: <out>/human_fp_report_<timestamp>.{json,md}
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.backend.engines.ai.orchestrator import AIDetectionOrchestrator  # noqa: E402

THRESHOLDS = (0.40, 0.50, 0.70)  # medium band, neutral cut, high band


def _iter_kaggle_student(dataset_root: Path) -> list[tuple[str, str, str]]:
    """Yield (corpus, name, code) for every Kaggle student submission."""
    root = dataset_root / "kaggle_student_code"
    if not root.exists():
        return []
    return [
        ("kaggle_student_code", path.name, path.read_text(encoding="utf-8", errors="replace"))
        for path in sorted(root.glob("*.py"))
    ]


def _iter_ir_plag_originals(dataset_root: Path) -> list[tuple[str, str, str]]:
    """Yield (corpus, name, code) for the human original of each IR-Plag case."""
    root = dataset_root / "IR-Plag-Dataset"
    if not root.exists():
        return []
    items: list[tuple[str, str, str]] = []
    for case_dir in sorted(root.glob("case-*")):
        for original in sorted((case_dir / "original").glob("*.java")):
            items.append(
                (
                    "ir_plag_originals",
                    f"{case_dir.name}/{original.name}",
                    original.read_text(encoding="utf-8", errors="replace"),
                )
            )
    return items


def _iter_poolc_sample(dataset_root: Path, sample_size: int) -> list[tuple[str, str, str]]:
    """Yield (corpus, name, code) for a deterministic PoolC code1 sample."""
    import pyarrow.parquet as pq

    shard = sorted((dataset_root / "poolc_600k_python" / "data").glob("*.parquet"))
    if not shard:
        return []
    table = pq.read_table(shard[0]).slice(0, sample_size * 2).to_pydict()
    items: list[tuple[str, str, str]] = []
    for index, code in enumerate(table["code1"]):
        if len(items) >= sample_size:
            break
        if code and len(code.strip()) >= 20:
            items.append(("poolc_sample", f"poolc_{index:04d}.py", code))
    return items


def _summarize(scores: list[float]) -> dict:
    """Summary statistics and flag rates for one corpus."""
    if not scores:
        return {"count": 0}
    ordered = sorted(scores)
    return {
        "count": len(scores),
        "mean": round(statistics.fmean(scores), 4),
        "median": round(statistics.median(scores), 4),
        "p90": round(ordered[int(0.9 * (len(ordered) - 1))], 4),
        "max": round(ordered[-1], 4),
        **{
            f"flagged_at_{threshold:.2f}": round(
                sum(1 for value in scores if value >= threshold) / len(scores), 4
            )
            for threshold in THRESHOLDS
        },
    }


def main() -> int:
    """Run the FP measurement across corpora and write the report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--poolc-n", type=int, default=100)
    parser.add_argument("--out", default="reports/human_fp")
    args = parser.parse_args()

    dataset_root = REPO_ROOT / "data" / "datasets"
    items = [
        *_iter_kaggle_student(dataset_root),
        *_iter_ir_plag_originals(dataset_root),
        *_iter_poolc_sample(dataset_root, args.poolc_n),
    ]
    if not items:
        print("No human corpora found under", dataset_root)
        return 1

    detector = AIDetectionOrchestrator()
    by_corpus: dict[str, list[float]] = {}
    started = time.time()
    for index, (corpus, name, code) in enumerate(items, start=1):
        language = "java" if name.endswith(".java") else "python"
        result = detector.analyze(code, language=language)
        by_corpus.setdefault(corpus, []).append(float(result["ai_probability"]))
        if index % 20 == 0 or index == len(items):
            print(f"scored {index}/{len(items)} in {time.time() - started:.0f}s", flush=True)

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "detector": "AIDetectionOrchestrator (production safe-blend)",
        "thresholds": list(THRESHOLDS),
        "corpora": {corpus: _summarize(scores) for corpus, scores in sorted(by_corpus.items())},
        "runtime_seconds": round(time.time() - started, 1),
    }

    out_dir = REPO_ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"human_fp_report_{stamp}.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Human-code false-positive report",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Detector: `{report['detector']}`",
        f"- Runtime: `{report['runtime_seconds']}s`",
        "",
        "| Corpus | n | mean | median | p90 | max | FP@0.40 | FP@0.50 | FP@0.70 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for corpus, summary in report["corpora"].items():
        if summary.get("count"):
            lines.append(
                f"| {corpus} | {summary['count']} | {summary['mean']:.3f} | "
                f"{summary['median']:.3f} | {summary['p90']:.3f} | {summary['max']:.3f} | "
                f"{summary['flagged_at_0.40']:.1%} | {summary['flagged_at_0.50']:.1%} | "
                f"{summary['flagged_at_0.70']:.1%} |"
            )
    lines += [
        "",
        "All inputs are known-human, so every flag above is a false positive.",
        "Thresholds: 0.40 = medium band, 0.50 = neutral cut, 0.70 = high band.",
    ]
    md_path = out_dir / f"human_fp_report_{stamp}.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"\nReport: {json_path}")
    for corpus, summary in report["corpora"].items():
        print(corpus, summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
