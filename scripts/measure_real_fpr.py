#!/usr/bin/env python3
"""
Measure Real False Positive Rate on Known-Clean Student Submissions.

This script is the most important validation step before releasing the Plagiarism Checker to professors.

Usage:
    python scripts/measure_real_fpr.py --clean-dir /path/to/known_clean_submissions

What it does:
- Loads every file in the directory as one "submission".
- Runs the full plagiarism detection pipeline on all pairs.
- Because these submissions are known to be clean (instructors confirmed no plagiarism),
  any pair that scores above a threshold = False Positive.
- Reports FPR at multiple thresholds so you can choose a safe operating point.

Recommended before release:
- Use real submissions from previous semesters that instructors are confident had ZERO copying.
- Aim for FPR < 4-5% at the threshold you plan to show professors.
"""

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.backend.application.services.batch_detection_service import BatchDetectionService


def find_code_files(directory: Path) -> List[Path]:
    """Recursively find code files (common programming languages)."""
    extensions = {".py", ".java", ".c", ".cpp", ".cc", ".h", ".hpp", ".js", ".ts", ".go", ".rs", ".cs"}
    files = []
    for ext in extensions:
        files.extend(directory.rglob(f"*{ext}"))
    return sorted(files)


def load_submissions(files: List[Path]) -> Dict[str, str]:
    """Load file contents into a dict {filename: code}."""
    submissions = {}
    for f in files:
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
            if len(content.strip()) > 20:  # ignore tiny files
                submissions[f.name] = content
        except Exception as e:
            print(f"Warning: Could not read {f}: {e}")
    return submissions


def compute_all_pairs(submissions: Dict[str, str], threshold: float = 0.0) -> List[Dict]:
    """
    Run the plagiarism detector on all pairs.
    We use a low threshold here so we capture the full score distribution.
    """
    if len(submissions) < 2:
        print("Error: Need at least 2 submissions to compute pairs.")
        return []

    service = BatchDetectionService(threshold=threshold)
    results = service.compare_all_pairs(submissions)

    # convert to list of dicts for easier processing
    pairs = []
    for r in results:
        pairs.append({
            "file_a": r.file_a,
            "file_b": r.file_b,
            "score": float(r.score),
        })
    return pairs


def calculate_fpr_at_thresholds(pairs: List[Dict], thresholds: List[float]) -> Dict[float, float]:
    """For each threshold, compute what % of pairs exceed it (FPR on clean data)."""
    total_pairs = len(pairs)
    if total_pairs == 0:
        return {}

    fpr_results = {}
    for t in thresholds:
        above = sum(1 for p in pairs if p["score"] >= t)
        fpr = above / total_pairs
        fpr_results[t] = fpr
    return fpr_results


def print_fpr_table(fpr_results: Dict[float, float]):
    print("\n" + "=" * 70)
    print("REAL FALSE POSITIVE RATE ON KNOWN-CLEAN SUBMISSIONS")
    print("=" * 70)
    print(f"{'Threshold':<12} {'FPR':<10} {'Interpretation'}")
    print("-" * 70)

    for t, fpr in sorted(fpr_results.items()):
        if fpr < 0.01:
            interp = "Excellent - very safe for professors"
        elif fpr < 0.03:
            interp = "Good - acceptable for most courses"
        elif fpr < 0.05:
            interp = "Borderline - consider raising threshold"
        else:
            interp = "High - risky to show professors"

        print(f"{t:<12.2f} {fpr*100:>6.2f}%    {interp}")

    print("=" * 70)


def print_score_distribution(pairs: List[Dict], num_bins: int = 10):
    """Show how similarity scores are distributed on clean data."""
    if not pairs:
        return

    scores = [p["score"] for p in pairs]
    min_s, max_s = min(scores), max(scores)

    print(f"\nScore Distribution on Clean Data (n={len(pairs)} pairs)")
    print(f"Min: {min_s:.3f}   Max: {max_s:.3f}   Mean: {sum(scores)/len(scores):.3f}")

    # simple histogram
    bins = [0.0] * num_bins
    for s in scores:
        idx = min(int(s * num_bins), num_bins - 1)
        bins[idx] += 1

    max_count = max(bins) or 1
    for i, count in enumerate(bins):
        low = i / num_bins
        high = (i + 1) / num_bins
        bar = "#" * int((count / max_count) * 40)
        print(f"[{low:.1f}-{high:.1f}) | {bar} ({count})")


def main():
    parser = argparse.ArgumentParser(description="Measure real FPR on known-clean submissions")
    parser.add_argument("--clean-dir", required=True, help="Directory containing known-clean submissions (no plagiarism)")
    parser.add_argument("--thresholds", default="0.50,0.55,0.60,0.65,0.70,0.75,0.80,0.85,0.90",
                        help="Comma-separated list of thresholds to evaluate")
    args = parser.parse_args()

    clean_dir = Path(args.clean_dir).expanduser().resolve()
    if not clean_dir.exists():
        print(f"Error: Directory not found: {clean_dir}")
        sys.exit(1)

    print(f"Scanning clean submissions in: {clean_dir}")
    files = find_code_files(clean_dir)
    print(f"Found {len(files)} code files")

    if len(files) < 2:
        print("Need at least 2 files to compute pairwise FPR.")
        sys.exit(1)

    submissions = load_submissions(files)
    print(f"Loaded {len(submissions)} valid submissions")

    thresholds = [float(t.strip()) for t in args.thresholds.split(",")]

    print("\nRunning full plagiarism detection on all pairs (this may take a while)...")
    pairs = compute_all_pairs(submissions, threshold=0.0)
    print(f"Generated {len(pairs)} pairwise comparisons")

    fpr_results = calculate_fpr_at_thresholds(pairs, thresholds)

    print_score_distribution(pairs)
    print_fpr_table(fpr_results)

    # Simple recommendation
    best_threshold = None
    for t in sorted(fpr_results.keys(), reverse=True):
        if fpr_results[t] <= 0.04:   # <= 4% FPR
            best_threshold = t
            break

    print("\nRecommendation:")
    if best_threshold:
        print(f"  → Consider operating around {best_threshold:.0%} (FPR ≈ {fpr_results[best_threshold]*100:.1f}%)")
    else:
        print("  → Even at 90% the FPR is still high. You may need to improve filtering (templates, starter code, etc.)")


if __name__ == "__main__":
    main()
