"""
Visualization Generators for evidence chain PDF reports.

Produces:
- Similarity heatmap (seaborn/matplotlib)
- Code diff image (difflib + Pygments)
- AI probability chart (matplotlib bar chart)
- Engine comparison radar chart
"""

from __future__ import annotations

import base64
import difflib
import io
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _save_fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="white")
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode("utf-8")
    buf.close()
    return f"data:image/png;base64,{img_b64}"


def generate_similarity_heatmap(
    similarity_matrix: List[List[float]],
    labels: Optional[List[str]] = None,
    title: str = "Similarity Heatmap",
    cmap: str = "YlOrRd",
) -> str:
    """
    Generate a similarity heatmap as base64 PNG.

    Args:
        similarity_matrix: NxN matrix of pairwise similarity scores.
        labels: File/submission labels for axes.
        title: Chart title.
        cmap: Matplotlib colormap name.

    Returns:
        Base64 data URI string for embedding in HTML.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    matrix = np.array(similarity_matrix)
    n = matrix.shape[0]
    if labels is None:
        labels = [f"File {i+1}" for i in range(n)]

    fig, ax = plt.subplots(figsize=(max(6, n * 0.8), max(5, n * 0.7)))
    im = ax.imshow(matrix, cmap=cmap, vmin=0, vmax=1, aspect="auto")

    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_yticklabels(labels, fontsize=8)

    for i in range(n):
        for j in range(n):
            color = "white" if matrix[i, j] > 0.6 else "black"
            ax.text(j, i, f"{matrix[i, j]:.2f}", ha="center", va="center",
                    fontsize=7, color=color)

    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Similarity")
    ax.set_title(title, fontsize=12, fontweight="bold", pad=10)
    fig.tight_layout()

    img_uri = _save_fig_to_base64(fig)
    plt.close(fig)
    return img_uri


def generate_code_diff_image(
    code_a: str,
    code_b: str,
    file_a: str = "Submission A",
    file_b: str = "Submission B",
    max_lines: int = 60,
) -> str:
    """
    Generate a side-by-side code diff as base64 PNG.

    Uses matplotlib to render colored diff lines.

    Args:
        code_a: First code sample.
        code_b: Second code sample.
        file_a: Label for file A.
        file_b: Label for file B.
        max_lines: Maximum lines to display.

    Returns:
        Base64 data URI string.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    a_lines = code_a.splitlines(keepends=True)
    b_lines = code_b.splitlines(keepends=True)

    matcher = difflib.SequenceMatcher(None, a_lines, b_lines)
    opcodes = matcher.get_opcodes()

    render_lines: List[Tuple[str, str, str]] = []
    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            for k in range(min(i2 - i1, max_lines - len(render_lines))):
                line = a_lines[i1 + k].rstrip()
                render_lines.append(("ctx", line, line))
        elif tag == "replace":
            for k in range(min(i2 - i1, j2 - j1, max_lines - len(render_lines))):
                render_lines.append(("rep", a_lines[i1 + k].rstrip(), b_lines[j1 + k].rstrip()))
            extra_a = (i2 - i1) - (j2 - j1)
            extra_b = (j2 - j1) - (i2 - i1)
            if extra_a > 0:
                for k in range(min(extra_a, max_lines - len(render_lines))):
                    render_lines.append(("del", a_lines[i2 - extra_a + k].rstrip(), ""))
            elif extra_b > 0:
                for k in range(min(extra_b, max_lines - len(render_lines))):
                    render_lines.append(("add", "", b_lines[j2 - extra_b + k].rstrip()))
        elif tag == "delete":
            for k in range(min(i2 - i1, max_lines - len(render_lines))):
                render_lines.append(("del", a_lines[i1 + k].rstrip(), ""))
        elif tag == "insert":
            for k in range(min(j2 - j1, max_lines - len(render_lines))):
                render_lines.append(("add", "", b_lines[j1 + k].rstrip()))

        if len(render_lines) >= max_lines:
            break

    if not render_lines:
        render_lines = [("ctx", "(Files identical)", "(Files identical)")]

    n_lines = len(render_lines)
    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(12, max(4, n_lines * 0.22)))
    fig.suptitle(f"Code Diff: {file_a} vs {file_b}", fontsize=11, fontweight="bold")

    colors = {"ctx": "#f8f8f8", "rep": "#fff3cd", "del": "#ffe6e6", "add": "#e6ffe6"}
    edge_colors = {"ctx": "#ddd", "rep": "#ffc107", "del": "#dc3545", "add": "#28a745"}

    y = n_lines
    for tag, line_a, line_b in render_lines:
        color = colors.get(tag, "#fff")
        ax_a.axhspan(y - 1, y, facecolor=color, edgecolor=edge_colors.get(tag, "#ddd"), linewidth=0.5)
        ax_a.text(0.02, y - 0.5, line_a[:80], fontsize=7, va="center",
                  fontfamily="monospace", color="#333")
        ax_b.axhspan(y - 1, y, facecolor=color, edgecolor=edge_colors.get(tag, "#ddd"), linewidth=0.5)
        ax_b.text(0.02, y - 0.5, line_b[:80], fontsize=7, va="center",
                  fontfamily="monospace", color="#333")
        y -= 1

    for ax, title in [(ax_a, file_a), (ax_b, file_b)]:
        ax.set_xlim(0, 1)
        ax.set_ylim(0, n_lines)
        ax.set_title(title, fontsize=9, fontweight="bold")
        ax.axis("off")

    legend_handles = [
        mpatches.Patch(facecolor="#e6ffe6", edgecolor="#28a745", label="Added"),
        mpatches.Patch(facecolor="#ffe6e6", edgecolor="#dc3545", label="Removed"),
        mpatches.Patch(facecolor="#fff3cd", edgecolor="#ffc107", label="Modified"),
        mpatches.Patch(facecolor="#f8f8f8", edgecolor="#ddd", label="Unchanged"),
    ]
    fig.legend(handles=legend_handles, loc="lower center", ncol=4, fontsize=7,
               frameon=True, facecolor="white", edgecolor="#ddd")

    fig.tight_layout(rect=[0, 0.06, 1, 0.96])
    img_uri = _save_fig_to_base64(fig)
    plt.close(fig)
    return img_uri


def generate_ai_probability_chart(
    ai_results: Dict[str, float],
    title: str = "AI Generation Probability",
) -> str:
    """
    Generate a bar chart showing AI detection probabilities from multiple models.

    Args:
        ai_results: Dict mapping model name to probability (0-1).
        title: Chart title.

    Returns:
        Base64 data URI string.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    models = list(ai_results.keys())
    probs = list(ai_results.values())
    x = np.arange(len(models))

    fig, ax = plt.subplots(figsize=(6, 3.5))

    colors = ["#dc3545" if p > 0.7 else "#fd7e14" if p > 0.4 else "#28a745" for p in probs]
    bars = ax.bar(x, probs, color=colors, edgecolor="#333", linewidth=0.5, width=0.6)

    for bar, p in zip(bars, probs):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                f"{p:.1%}", ha="center", va="bottom", fontsize=9, fontweight="bold")

    ax.axhline(y=0.5, color="#dc3545", linestyle="--", linewidth=1, alpha=0.7, label="Threshold (0.5)")
    ax.set_xticks(x)
    ax.set_xticklabels(models, rotation=20, ha="right", fontsize=8)
    ax.set_ylabel("AI Probability", fontsize=9)
    ax.set_title(title, fontsize=11, fontweight="bold", pad=8)
    ax.set_ylim(0, 1.15)
    ax.legend(fontsize=7, loc="upper right")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    img_uri = _save_fig_to_base64(fig)
    plt.close(fig)
    return img_uri


def generate_engine_radar_chart(
    engine_scores: Dict[str, Dict[str, float]],
    title: str = "Engine Performance Radar",
) -> str:
    """
    Generate a radar/spider chart comparing engine performance across metrics.

    Args:
        engine_scores: Dict mapping engine name to dict of metric->value.
        title: Chart title.

    Returns:
        Base64 data URI string.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    metrics = list(next(iter(engine_scores.values())).keys())
    n_metrics = len(metrics)
    angles = np.linspace(0, 2 * np.pi, n_metrics, endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(6, 5), subplot_kw=dict(polar=True))

    colors = ["#2563eb", "#dc2626", "#16a34a", "#d97706", "#7c3aed"]
    for idx, (engine, scores) in enumerate(engine_scores.items()):
        values = [scores.get(m, 0) for m in metrics]
        values += values[:1]
        ax.plot(angles, values, color=colors[idx % len(colors)], linewidth=2, label=engine)
        ax.fill(angles, values, color=colors[idx % len(colors)], alpha=0.1)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(metrics, fontsize=8)
    ax.set_ylim(0, 1)
    ax.set_title(title, fontsize=11, fontweight="bold", pad=15)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=7)
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    img_uri = _save_fig_to_base64(fig)
    plt.close(fig)
    return img_uri


def generate_confusion_matrix_image(
    tp: int, fp: int, tn: int, fn: int,
    title: str = "Confusion Matrix",
) -> str:
    """
    Generate a confusion matrix visualization.

    Returns:
        Base64 data URI string.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    matrix = np.array([[tp, fn], [fp, tn]])
    labels = [["TP", "FN"], ["FP", "TN"]]
    values = [[f"{tp}\n(True Positive)", f"{fn}\n(False Negative)"],
              [f"{fp}\n(False Positive)", f"{tn}\n(True Negative)"]]

    fig, ax = plt.subplots(figsize=(5, 4))
    im = ax.imshow(matrix, cmap="Blues", aspect="auto")

    for i in range(2):
        for j in range(2):
            color = "white" if matrix[i, j] > matrix.max() / 2 else "black"
            ax.text(j, i, values[i][j], ha="center", va="center",
                    fontsize=10, color=color, fontweight="bold")

    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(["Predicted\nPositive", "Predicted\nNegative"], fontsize=8)
    ax.set_yticklabels(["Actual\nPositive", "Actual\nNegative"], fontsize=8)
    ax.set_title(title, fontsize=11, fontweight="bold", pad=10)

    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    img_uri = _save_fig_to_base64(fig)
    plt.close(fig)
    return img_uri


def generate_qr_code(
    url: str,
    size: int = 200,
    border: int = 2,
) -> str:
    """Generate a QR code as base64 PNG."""
    import qrcode
    import qrcode.image.pil
    import base64

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=border,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white", image_factory=qrcode.image.pil.PilImage)
    img = img.resize((size, size))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode("utf-8")
    return f"data:image/png;base64,{img_b64}"
