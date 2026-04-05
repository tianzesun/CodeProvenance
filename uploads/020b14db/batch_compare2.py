"""
batch_compare.py — All-pairs plagiarism check for a folder of student submissions.

Usage:
    python batch_compare.py --submissions ./submissions/ --threshold 0.85
    python batch_compare.py --submissions ./submissions/ --threshold 0.80 --output report.html

The script:
1. Reads all .py files from the submissions folder
2. Embeds all of them in a single GPU pass (fast)
3. Computes the full N×N similarity matrix
4. Reports all suspicious pairs above the threshold
"""

import argparse
import sys
from pathlib import Path

# ─────────────────────────────────────────────────────────
#  Argument parsing
# ─────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Batch plagiarism check using UniXcoder + AST fusion"
    )
    parser.add_argument(
        "--submissions", required=True,
        help="Path to folder containing student .py files"
    )
    parser.add_argument(
        "--threshold", type=float, default=0.85,
        help="Similarity threshold for flagging pairs (default: 0.85)"
    )
    parser.add_argument(
        "--output", default=None,
        help="Optional HTML report output path (e.g. report.html)"
    )
    parser.add_argument(
        "--ext", default=".py",
        help="File extension to scan (default: .py)"
    )
    return parser.parse_args()


# ─────────────────────────────────────────────────────────
#  Load submissions
# ─────────────────────────────────────────────────────────

def load_submissions(folder: Path, ext: str):
    files = sorted(folder.glob(f"*{ext}"))
    if not files:
        print(f"[ERROR] No {ext} files found in {folder}")
        sys.exit(1)

    submissions = {}
    for f in files:
        try:
            submissions[f.name] = f.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            print(f"[WARN] Could not read {f.name}: {e}")

    print(f"[INFO] Loaded {len(submissions)} submissions from {folder}")
    return submissions


# ─────────────────────────────────────────────────────────
#  Risk label helper
# ─────────────────────────────────────────────────────────

def risk_label(score: float) -> str:
    if score >= 0.95: return "CRITICAL"
    if score >= 0.90: return "HIGH"
    if score >= 0.85: return "MEDIUM"
    return "LOW"

def risk_color(score: float) -> str:
    if score >= 0.95: return "#d32f2f"
    if score >= 0.90: return "#f57c00"
    if score >= 0.85: return "#fbc02d"
    return "#388e3c"


# ─────────────────────────────────────────────────────────
#  Main comparison
# ─────────────────────────────────────────────────────────

def run(args):
    folder = Path(args.submissions)
    if not folder.exists():
        print(f"[ERROR] Folder not found: {folder}")
        sys.exit(1)

    submissions = load_submissions(folder, args.ext)
    names = list(submissions.keys())
    codes = list(submissions.values())
    n = len(codes)

    if n < 2:
        print("[INFO] Need at least 2 submissions to compare.")
        sys.exit(0)

    # ── Step 1: UniXcoder batch embedding (one GPU pass) ──────────────────
    print(f"[INFO] Embedding {n} submissions …")
    try:
        from src.engines.similarity.unixcoder_similarity import UniXcoderSimilarity
        engine = UniXcoderSimilarity()
        suspicious = engine.top_suspicious_pairs(
            codes=codes,
            labels=names,
            threshold=args.threshold,
        )
    except Exception as e:
        print(f"[ERROR] UniXcoder failed: {e}")
        suspicious = []

    # ── Step 2: AST cross-check for flagged pairs ─────────────────────────
    print(f"[INFO] Running AST cross-check on {len(suspicious)} suspicious pairs …")
    enriched = []
    for pair in suspicious:
        ast_score = 0.0
        try:
            from src.engines.similarity.ast_similarity import ASTSimilarity
            ast_engine = ASTSimilarity()
            ast_score = ast_engine.compare(
                {"raw": codes[pair["i"]], "tokens": []},
                {"raw": codes[pair["j"]], "tokens": []},
            )
        except Exception:
            pass

        # Fuse: 60% semantic (UniXcoder), 40% structural (AST)
        fused = round(0.60 * pair["score"] + 0.40 * ast_score, 4)
        enriched.append({
            **pair,
            "ast_score": round(ast_score, 4),
            "fused_score": fused,
            "risk": risk_label(fused),
        })

    # Sort by fused score
    enriched.sort(key=lambda x: x["fused_score"], reverse=True)

    # ── Step 3: Print results ─────────────────────────────────────────────
    if not enriched:
        print(f"\n✅  No suspicious pairs found above threshold {args.threshold:.0%}")
    else:
        print(f"\n{'─'*70}")
        print(f"  ⚠️  {len(enriched)} suspicious pair(s) found (threshold: {args.threshold:.0%})")
        print(f"{'─'*70}")
        print(f"  {'Risk':<10} {'Fused':>7} {'Semantic':>9} {'AST':>6}  Pair")
        print(f"{'─'*70}")
        for r in enriched:
            print(
                f"  {r['risk']:<10} {r['fused_score']:>6.1%}"
                f"  {r['score']:>7.1%}  {r['ast_score']:>5.1%}"
                f"  {r['label_i']}  ↔  {r['label_j']}"
            )
        print(f"{'─'*70}")

    # ── Step 4: HTML report (optional) ───────────────────────────────────
    if args.output:
        _write_html_report(enriched, args.output, args.threshold, names, n)
        print(f"\n[INFO] HTML report saved to: {args.output}")


# ─────────────────────────────────────────────────────────
#  HTML report
# ─────────────────────────────────────────────────────────

def _write_html_report(pairs, output_path, threshold, names, n_students):
    rows = ""
    for r in pairs:
        color = risk_color(r["fused_score"])
        rows += f"""
        <tr>
            <td style="color:{color};font-weight:bold">{r['risk']}</td>
            <td>{r['fused_score']:.1%}</td>
            <td>{r['score']:.1%}</td>
            <td>{r['ast_score']:.1%}</td>
            <td>{r['label_i']}</td>
            <td>{r['label_j']}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>CodeProvenance — Plagiarism Report</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         max-width: 960px; margin: 40px auto; padding: 0 20px; color: #333; }}
  h1 {{ color: #1a1a2e; }}
  .summary {{ background: #f5f5f5; border-radius: 8px; padding: 16px;
              display: flex; gap: 32px; margin-bottom: 24px; }}
  .stat {{ text-align: center; }}
  .stat-value {{ font-size: 2rem; font-weight: bold; color: #1a1a2e; }}
  .stat-label {{ font-size: 0.85rem; color: #666; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ background: #1a1a2e; color: white; padding: 10px 12px; text-align: left; }}
  td {{ padding: 10px 12px; border-bottom: 1px solid #eee; }}
  tr:hover {{ background: #fafafa; }}
  .empty {{ text-align: center; padding: 48px; color: #666; font-size: 1.1rem; }}
</style>
</head>
<body>
<h1>📋 CodeProvenance — Plagiarism Report</h1>
<div class="summary">
  <div class="stat">
    <div class="stat-value">{n_students}</div>
    <div class="stat-label">Submissions</div>
  </div>
  <div class="stat">
    <div class="stat-value">{len(pairs)}</div>
    <div class="stat-label">Suspicious Pairs</div>
  </div>
  <div class="stat">
    <div class="stat-value">{threshold:.0%}</div>
    <div class="stat-label">Threshold</div>
  </div>
  <div class="stat">
    <div class="stat-value">UniXcoder + AST</div>
    <div class="stat-label">Engines</div>
  </div>
</div>

{'<table><thead><tr><th>Risk</th><th>Fused Score</th><th>Semantic</th><th>AST</th><th>Student A</th><th>Student B</th></tr></thead><tbody>' + rows + '</tbody></table>' if pairs else '<div class="empty">✅ No suspicious pairs found above threshold.</div>'}

</body>
</html>"""

    Path(output_path).write_text(html, encoding="utf-8")


# ─────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    run(parse_args())
