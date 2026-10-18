#!/usr/bin/env python3
"""Measure the active Binoculars pair's raw-score distribution on AIGCodeSet.

The published thresholds (0.8536 / 0.9015) were fitted on Falcon-7B. Any other
observer/performer pair sits on a different score scale, so this probe scores
known-AI (AIGCodeSet: LLAMA/CODESTRAL/GEMINI/... generated solutions) and
known-human (student solutions) Python files and reports where each class
actually lands — plus the best single-threshold separation, if any.

Run with the project venv active on a machine whose HF cache has the models
(the GPU server). Default is 25 files per class (~1-2 min on a T4):

    python3 scripts/probe-binoculars.py [n_per_class]
"""

from __future__ import annotations

import statistics
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

AIGDIR = REPO_ROOT / "data" / "datasets" / "aigcodeset"


def ensure_dataset() -> None:
    """Download and materialise AIGCodeSet when missing (idempotent)."""
    ai_dir = AIGDIR / "data" / "ai"
    human_dir = AIGDIR / "data" / "human"
    if ai_dir.is_dir() and human_dir.is_dir() and any(ai_dir.iterdir()):
        return
    print("AIGCodeSet missing — downloading CSVs from Hugging Face...")
    subprocess.run(["bash", str(AIGDIR / "download.sh")], check=True, cwd=REPO_ROOT)
    subprocess.run(
        [sys.executable, "-m", "src.backend.engines.ai.build_aigcodeset"],
        check=True,
        cwd=REPO_ROOT,
    )


def sample_files(root: Path, n: int, stratify: bool) -> list[Path]:
    """Pick up to ``n`` files; round-robin across generator tags when stratified."""
    files = sorted(p for p in root.glob("*.py") if p.stat().st_size >= 60)
    if not stratify or n >= len(files):
        return files[:n]
    groups: dict[str, list[Path]] = {}
    for path in files:
        parts = path.stem.split("__")
        groups.setdefault(parts[1] if len(parts) >= 3 else "unknown", []).append(path)
    picked: list[Path] = []
    offset = 0
    while len(picked) < n and any(groups.values()):
        for key in sorted(groups):
            bucket = groups[key]
            if bucket and len(picked) < n:
                picked.append(bucket[offset % len(bucket)])
        offset += 1
    return picked


def best_split(ai: list[float], human: list[float]) -> tuple[float, float, int]:
    """Exhaustively find (accuracy, threshold, direction) of the best single cut.

    ``direction`` is +1 when AI scores at/above the threshold and -1 when AI
    scores below it (the Falcon mapping assumes -1).
    """
    best = (0.0, 0.0, -1)
    labelled = [(v, True) for v in ai] + [(v, False) for v in human]
    for threshold in sorted({round(v, 4) for v in ai + human}):
        for direction in (1, -1):
            hits = sum(
                1
                for value, is_ai in labelled
                if (direction * value >= direction * threshold) == is_ai
            )
            accuracy = hits / len(labelled)
            if accuracy > best[0]:
                best = (accuracy, threshold, direction)
    return best


def main() -> None:
    """Run the probe and print a data-driven verdict on the pair's thresholds."""
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    ensure_dataset()

    # Imported after the dataset step: importing the detector module pulls in
    # torch/transformers, which is slow and memory-hungry.
    from src.backend.engines.ai.binoculars_detector import BinocularsDetector

    detector = BinocularsDetector()
    if not detector.is_available():
        raise SystemExit("Binoculars failed to load — check the HF cache/models")

    results: dict[str, list[tuple[str, float]]] = {"AI": [], "HUMAN": []}
    for label, root, stratify in (
        ("AI", AIGDIR / "data" / "ai", True),
        ("HUMAN", AIGDIR / "data" / "human", False),
    ):
        for path in sample_files(root, n, stratify):
            code = path.read_text(encoding="utf-8", errors="replace")
            raw = detector.analyze(code)["raw_score"]
            if raw is None:
                continue
            results[label].append((path.name, raw))
            print(f"  {label:5s} {path.name}: raw={raw:.4f}")

    print()
    medians: dict[str, float] = {}
    for label, rows in results.items():
        values = sorted(value for _, value in rows)
        if not values:
            continue
        medians[label] = statistics.median(values)
        print(
            f"{label:5s} n={len(values)} min={values[0]:.4f} "
            f"median={medians[label]:.4f} mean={statistics.mean(values):.4f} "
            f"max={values[-1]:.4f}"
        )
    ai = [value for _, value in results["AI"]]
    human = [value for _, value in results["HUMAN"]]
    if not ai or not human:
        raise SystemExit("need scores from both classes to judge separation")

    print()
    higher = (
        "HIGHER = AI (opposite of the Falcon mapping!)"
        if medians["AI"] > medians["HUMAN"]
        else "lower = AI (same direction as Falcon)"
    )
    print(
        f"Direction check: median AI {medians['AI']:.4f} vs human {medians['HUMAN']:.4f} → {higher}"
    )

    accuracy, threshold, direction = best_split(ai, human)
    side = "AI at/above" if direction > 0 else "AI at/below"
    print(
        f"Best single-threshold split: accuracy={accuracy:.2%} at raw {threshold} ({side})"
    )
    if accuracy < 0.60:
        print("→ classes overlap: this pair does NOT separate AI/human code;")
        print(
            "  demote the layer (drop it from KNOWN_CALIBRATED_PAIRS, lower the weight)."
        )
    elif accuracy < 0.80:
        print("→ weak separation; treat the layer as advisory only.")
    else:
        print(
            "→ usable separation; set this pair's thresholds from the boundary above."
        )


if __name__ == "__main__":
    main()
