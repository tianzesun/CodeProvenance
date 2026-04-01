"""LaTeX table generator."""
from __future__ import annotations
from typing import Any, Dict, List


def generate_main_table(results):
    all_tools = sorted(results.keys())
    all_datasets = sorted(set(ds for tool_results in results.values() for ds in tool_results.keys()))
    primary_ds = "bigclonebench" if "bigclonebench" in all_datasets else all_datasets[0]
    lines = [
        "\\begin{table}[h]",
        "\\centering",
        "\\caption{Main Results: Clone Detection Performance}",
        "\\label{tab:main-results}",
        "\\begin{tabular}{lcccc}",
        "\\toprule",
        "Tool & Precision & Recall & F1 & Accuracy \\\\",
        "\\midrule",
    ]
    for tool in all_tools:
        if primary_ds in results[tool]:
            m = results[tool][primary_ds]
            lines.append(f"{tool} & {m.get('precision', 0):.4f} & {m.get('recall', 0):.4f} & {m.get('f1', 0):.4f} & {m.get('accuracy', 0):.4f} \\\\")
    lines.extend(["\\bottomrule", "\\end{tabular}", "\\end{table}"])
    return "\n".join(lines)


def generate_cross_domain_table(results):
    all_tools = sorted(results.keys())
    all_datasets = sorted(set(ds for tool_results in results.values() for ds in tool_results.keys()))
    lines = [
        "\\begin{table}[h]",
        "\\centering",
        "\\caption{Cross-Domain Generalization Results (F1 Score)}",
        "\\label{tab:cross-domain}",
        f"\\begin{{tabular}}{{l{'c' * len(all_datasets)}}}",
        "\\toprule",
        "Tool & " + " & ".join(all_datasets) + " \\\\",
        "\\midrule",
    ]
    for tool in all_tools:
        f1s = [f"{results[tool].get(ds, {}).get('f1', 0):.4f}" for ds in all_datasets]
        lines.append(f"{tool} & {' & '.join(f1s)} \\\\")
    lines.extend(["\\bottomrule", "\\end{tabular}", "\\end{table}"])
    return "\n".join(lines)


def generate_significance_table(comparisons):
    lines = [
        "\\begin{table}[h]",
        "\\centering",
        "\\caption{Pairwise Statistical Comparison}",
        "\\label{tab:significance}",
        "\\begin{tabular}{lcccc}",
        "\\toprule",
        "Comparison & $\\Delta$F1 & CI Lower & CI Upper & p-value \\\\",
        "\\midrule",
    ]
    for comp in comparisons:
        a = comp.get("engine_a", "")
        b = comp.get("engine_b", "")
        delta = comp.get("delta_f1", 0)
        ci_lo = comp.get("ci_95_lower", 0)
        ci_hi = comp.get("ci_95_upper", 0)
        p = comp.get("p_value", 1.0)
        sig = comp.get("significant_str", "ns")
        p_str = f"{p:.4f}" if p >= 0.001 else "$<$.001"
        lines.append(f"{a} vs {b} & {delta:+.4f} & {ci_lo:+.4f} & {ci_hi:+.4f} & {p_str} {sig} \\\\")
    lines.extend(["\\bottomrule", "\\end{tabular}", "\\end{table}"])
    return "\n".join(lines)
