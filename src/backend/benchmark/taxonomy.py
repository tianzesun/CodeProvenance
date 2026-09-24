"""Canonical CodeProvenance benchmark taxonomy and live coverage status.

Mirrors ``docs/CODEPROVENANCE_BENCHMARK.md``: the four top-level components
(Detection Performance, False Positive Validation, Robustness, Generalization)
and their sub-items. The static tree is the specification;
:func:`build_taxonomy_status` attaches the status actually measured in this
workspace so product surfaces can show what is live, partial, or still missing
instead of implying full coverage.

Status values:
    ``live``    - measured and reproducible from a tracked artifact.
    ``partial`` - measured only in part (e.g. unit-level, or one language).
    ``gap``     - a first-class artifact exists but the field is not surfaced.
    ``missing`` - not measured at all.

No metric values are invented here: every ``live`` item is only claimed when the
corresponding report/baseline artifact is present.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

STATUS_LIVE = "live"
STATUS_PARTIAL = "partial"
STATUS_GAP = "gap"
STATUS_MISSING = "missing"

STATUS_LABELS: dict[str, str] = {
    STATUS_LIVE: "Measured",
    STATUS_PARTIAL: "Partial",
    STATUS_GAP: "Known gap",
    STATUS_MISSING: "Not measured",
}

_REPORT_EVIDENCE = "data/datasets/aigcodeset/benchmark_report.json (grouped holdout)"


@dataclass(frozen=True)
class TaxonomyItem:
    """One sub-item of the benchmark taxonomy (e.g. §1 TPR/Recall).

    Attributes:
        key: Stable machine-readable identifier.
        label: Human-readable name shown in the UI.
        status: One of ``live`` / ``partial`` / ``gap`` / ``missing``.
        evidence: File or report the status is derived from.
    """

    key: str
    label: str
    status: str
    evidence: str

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-serialisable view of this item."""
        return {
            "key": self.key,
            "label": self.label,
            "status": self.status,
            "status_label": STATUS_LABELS.get(self.status, self.status),
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class TaxonomyComponent:
    """One top-level benchmark component (§1-§4 of the canonical tree).

    Attributes:
        key: Stable machine-readable identifier.
        number: Section number used in documentation and UI headings.
        title: Section title, e.g. "Detection Performance".
        summary: One-line description of what the component measures.
        items: Sub-items with their measured status.
    """

    key: str
    number: int
    title: str
    summary: str
    items: tuple[TaxonomyItem, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable view of this component."""
        return {
            "key": self.key,
            "number": self.number,
            "title": self.title,
            "summary": self.summary,
            "items": [item.to_dict() for item in self.items],
        }


def _grouped_metrics(reports: Mapping[str, Any] | None) -> Mapping[str, Any]:
    """Return the main report's grouped-holdout metrics, or an empty mapping."""
    if not reports:
        return {}
    main = reports.get("main") or {}
    grouped = (main.get("grouped_holdout") or {}).get("metrics") or {}
    return grouped


def _measured_status(metrics: Mapping[str, Any], key: str) -> str:
    """Return ``live`` when the metric key is present, else ``gap``."""
    return STATUS_LIVE if key in metrics else STATUS_GAP


def _real_world_fpr_item(baseline: Mapping[str, Any] | None) -> TaxonomyItem:
    """Build the §2b Real-World FPR Validation item from the measured baseline."""
    corpora = (baseline or {}).get("corpora") or {}
    if not corpora:
        return TaxonomyItem(
            key="real_world_fpr_validation",
            label="Real-World FPR Validation (held-out human code)",
            status=STATUS_MISSING,
            evidence="no human-code baseline artifact (run scripts/measure_human_fp.py)",
        )
    samples = sum(int(c.get("count") or 0) for c in corpora.values())
    names = ", ".join(sorted(corpora))
    return TaxonomyItem(
        key="real_world_fpr_validation",
        label="Real-World FPR Validation (held-out human code)",
        status=STATUS_LIVE,
        evidence=(
            "docs/HUMAN_FP_BASELINE.md (human_fp_baseline.json) - "
            f"{len(corpora)} corpora, n={samples} ({names}); "
            "reported as flag rates at 0.40/0.50/0.70"
        ),
    )


def build_taxonomy_status(
    reports: Mapping[str, Any] | None = None,
    human_fp_baseline: Mapping[str, Any] | None = None,
) -> list[TaxonomyComponent]:
    """Return the canonical taxonomy with status derived from real artifacts.

    Args:
        reports: Mapping of report name (``main``/``statistical``/``codelm``) to
            the parsed ``benchmark_report*.json`` payload.
        human_fp_baseline: Parsed ``human_fp_baseline.json`` payload.

    Returns:
        The four top-level components in canonical order (§1-§4), each carrying
        per-item status derived only from artifacts that actually exist.
    """
    metrics = _grouped_metrics(reports)
    report_status = STATUS_LIVE if metrics else STATUS_MISSING

    detection = TaxonomyComponent(
        key="detection_performance",
        number=1,
        title="Detection Performance",
        summary="Labelled, grouped-holdout metrics on AIGCodeSet (AI = positive class).",
        items=(
            TaxonomyItem(
                key="tpr_recall",
                label="TPR / Recall",
                status=(
                    _measured_status(metrics, "recall") if metrics else STATUS_MISSING
                ),
                evidence=_REPORT_EVIDENCE,
            ),
            TaxonomyItem(
                key="precision",
                label="Precision",
                status=(
                    _measured_status(metrics, "precision")
                    if metrics
                    else STATUS_MISSING
                ),
                evidence=_REPORT_EVIDENCE,
            ),
            TaxonomyItem(
                key="f1",
                label="F1",
                status=_measured_status(metrics, "f1") if metrics else STATUS_MISSING,
                evidence=_REPORT_EVIDENCE,
            ),
            TaxonomyItem(
                key="fpr_in_lab",
                label="FPR (in-lab, same dataset)",
                status=_measured_status(metrics, "fpr") if metrics else STATUS_MISSING,
                evidence=_REPORT_EVIDENCE,
            ),
            TaxonomyItem(
                key="roc_auc",
                label="ROC-AUC",
                status=_measured_status(metrics, "auc") if metrics else STATUS_MISSING,
                evidence=_REPORT_EVIDENCE,
            ),
            TaxonomyItem(
                key="pr_auc",
                label="PR-AUC (average precision)",
                status=(
                    _measured_status(metrics, "pr_auc") if metrics else STATUS_MISSING
                ),
                evidence=_REPORT_EVIDENCE,
            ),
        ),
    )

    false_positives = TaxonomyComponent(
        key="false_positive_validation",
        number=2,
        title="False Positive Validation",
        summary=(
            "Human-code false positives: in-lab synthetic split plus held-out "
            "real-world corpora."
        ),
        items=(
            TaxonomyItem(
                key="synthetic_human_code",
                label="Synthetic human code (in-lab FPR)",
                status=report_status,
                evidence="AIGCodeSet human split inside the grouped holdout",
            ),
            _real_world_fpr_item(human_fp_baseline),
        ),
    )

    robustness = TaxonomyComponent(
        key="robustness",
        number=3,
        title="Robustness",
        summary=(
            "Adversarial inputs: refactoring, completion, AI-assisted edits, "
            "mixed authorship."
        ),
        items=(
            TaxonomyItem(
                key="refactoring",
                label="Refactoring (rename / restructure / comment-strip)",
                status=STATUS_PARTIAL,
                evidence=(
                    "tests/unit/test_ai_detector_adversarial.py "
                    "(unit-level; no scored flag-rate deltas)"
                ),
            ),
            TaxonomyItem(
                key="code_completion",
                label="Code completion (partial AI: prefix-human + suffix-AI)",
                status=STATUS_MISSING,
                evidence="no partial-AI dataset collected",
            ),
            TaxonomyItem(
                key="ai_assisted",
                label="AI-assisted / lightly-edited code",
                status=STATUS_MISSING,
                evidence="no tool-assisted or paraphrased-logic dataset collected",
            ),
            TaxonomyItem(
                key="mixed_authorship",
                label="Mixed human + AI authorship",
                status=STATUS_MISSING,
                evidence="no interleaved-authorship dataset collected",
            ),
        ),
    )

    generalization = TaxonomyComponent(
        key="generalization",
        number=4,
        title="Generalization",
        summary="Cross-language coverage of the AI detector (AI-labelled samples per language).",
        items=(
            TaxonomyItem(
                key="python",
                label="Python",
                status=STATUS_LIVE if metrics else STATUS_MISSING,
                evidence="AIGCodeSet AI + Kaggle/PoolC/IR-Plag human corpora",
            ),
            TaxonomyItem(
                key="java",
                label="Java",
                status=STATUS_PARTIAL,
                evidence="IR-Plag human originals only (n=7); no AI-labelled Java set",
            ),
            TaxonomyItem(
                key="c_cpp",
                label="C / C++",
                status=STATUS_MISSING,
                evidence="similarity sets exist (CodeXGLUE); no AI-labelled AI-detector set",
            ),
            TaxonomyItem(
                key="javascript",
                label="JavaScript",
                status=STATUS_MISSING,
                evidence="similarity sets exist (BigCloneBench); no AI-labelled AI-detector set",
            ),
            TaxonomyItem(
                key="other_languages",
                label="Other (.go / .rs / .kt / .swift)",
                status=STATUS_MISSING,
                evidence="lexical heuristics only; unvalidated for AI detection",
            ),
        ),
    )

    return [detection, false_positives, robustness, generalization]


def taxonomy_summary(components: Sequence[TaxonomyComponent]) -> dict[str, int]:
    """Count item statuses across all components.

    Args:
        components: Components returned by :func:`build_taxonomy_status`.

    Returns:
        Mapping of status name to the number of items carrying it.
    """
    counts = {STATUS_LIVE: 0, STATUS_PARTIAL: 0, STATUS_GAP: 0, STATUS_MISSING: 0}
    for component in components:
        for item in component.items:
            counts[item.status] = counts.get(item.status, 0) + 1
    return counts
