"""Unified per-student evidence dossier with viva question generation.

Synthesizes the evidence already produced by the individual detectors — AI
detection, pairwise peer similarity, and public-web provenance — into one
dossier per student, with a severity-banded evidence list and targeted viva
(interview) questions an instructor can ask to verify authorship. Turnitin has
no code equivalent: this is the product's differentiation layer on top of the
detectors, not a detector itself.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Severity bands, aligned with the server's AI thresholds and report bands.
AI_HIGH = 0.70
AI_MEDIUM = 0.40
PEER_HIGH = 0.85
WEB_HIGH = 0.80
WEB_MEDIUM = 0.50

_MAX_QUESTIONS_PER_STUDENT = 5


@dataclass
class EvidenceItem:
    """One piece of cross-detector evidence about a student's submission."""

    type: str  # "ai_detection" | "peer_similarity" | "web_provenance"
    severity: str  # "high" | "medium" | "low"
    title: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        """Serialize for API responses and reports."""
        return {
            "type": self.type,
            "severity": self.severity,
            "title": self.title,
            "detail": self.detail,
        }


@dataclass
class StudentDossier:
    """The fused evidence picture for one student submission."""

    student: str
    band: str = "low"  # overall: high | medium | low
    ai_probability: float | None = None
    ai_confidence: float | None = None
    peer_max_similarity: float | None = None
    peer_partner: str | None = None
    web_max_similarity: float | None = None
    web_best_match_url: str | None = None
    web_best_match_source: str | None = None
    evidence: list[EvidenceItem] = field(default_factory=list)
    viva_questions: list[str] = field(default_factory=list)
    viva_outcome: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API responses and reports."""
        return {
            "student": self.student,
            "band": self.band,
            "ai_probability": self.ai_probability,
            "ai_confidence": self.ai_confidence,
            "peer_max_similarity": self.peer_max_similarity,
            "peer_partner": self.peer_partner,
            "web_max_similarity": self.web_max_similarity,
            "web_best_match_url": self.web_best_match_url,
            "web_best_match_source": self.web_best_match_source,
            "evidence": [item.to_dict() for item in self.evidence],
            "viva_questions": self.viva_questions,
            "viva_outcome": self.viva_outcome,
        }


class EvidenceDossierService:
    """Build per-student evidence dossiers from an analyzed job payload."""

    def build(
        self,
        job: dict[str, Any],
        viva_outcomes: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Fuse AI, pairwise and web evidence from a job into student dossiers.

        Args:
            job: The job payload as returned by ``GET /api/job/{id}``
                (needs ``results``, optionally ``ai_detection`` and
                ``web_analysis``).
            viva_outcomes: Optional recorded viva outcomes (rows with
                ``submission_name``, ``outcome``, ``notes``, ``conducted_at``)
                merged into the matching students' dossiers.

        Returns:
            Dict with ``job_id``, ``generated_at``, source ``coverage`` flags
            and a severity-sorted ``students`` list with viva questions.
        """
        threshold = float(job.get("threshold") or 0.5)
        ai_by_name = {
            str(entry.get("name")): entry
            for entry in (job.get("ai_detection") or {}).get("submissions") or []
        }
        web_by_name = {
            str(entry.get("name")): entry
            for entry in (job.get("web_analysis") or {}).get("submissions") or []
        }
        peer_by_name = self._peer_similarity_by_name(job.get("results") or [])

        names: list[str] = []
        for name in list(ai_by_name) + list(web_by_name) + list(peer_by_name):
            if name not in names:
                names.append(name)
        names.sort()

        students = [
            self._build_student(
                name,
                ai_by_name.get(name),
                web_by_name.get(name),
                peer_by_name.get(name),
                threshold,
            )
            for name in names
        ]
        if viva_outcomes:
            outcome_by_name = {
                str(entry.get("submission_name")): entry for entry in viva_outcomes
            }
            for dossier in students:
                outcome = outcome_by_name.get(dossier.student)
                if outcome is not None:
                    dossier.viva_outcome = {
                        "outcome": str(outcome.get("outcome") or ""),
                        "notes": outcome.get("notes"),
                        "conducted_at": outcome.get("conducted_at"),
                    }
        students.sort(key=lambda dossier: (_band_rank(dossier.band), dossier.student))

        return {
            "job_id": str(job.get("id") or ""),
            "generated_at": datetime.now().isoformat(),
            "coverage": {
                "ai_detection": bool(ai_by_name),
                "web_analysis": bool(web_by_name),
                "pairwise": bool(peer_by_name),
            },
            "students": [dossier.to_dict() for dossier in students],
        }

    def _build_student(
        self,
        name: str,
        ai_entry: dict[str, Any] | None,
        web_entry: dict[str, Any] | None,
        peer_entry: dict[str, Any] | None,
        threshold: float,
    ) -> StudentDossier:
        """Assemble one student's dossier from the per-detector entries."""
        dossier = StudentDossier(student=name)

        if ai_entry:
            dossier.ai_probability = _coerce_float(ai_entry.get("ai_probability"))
            dossier.ai_confidence = _coerce_float(ai_entry.get("confidence"))
            severity = _ai_severity(dossier.ai_probability)
            dossier.evidence.append(
                EvidenceItem(
                    type="ai_detection",
                    severity=severity,
                    title=f"AI likelihood {(dossier.ai_probability or 0.0):.0%}"
                    f" ({ai_entry.get('status') or 'scored'})",
                    detail=self._ai_detail(ai_entry),
                )
            )

        if peer_entry:
            dossier.peer_max_similarity = peer_entry["max_similarity"]
            dossier.peer_partner = peer_entry["partner"]
            severity = _peer_severity(peer_entry["max_similarity"], threshold)
            dossier.evidence.append(
                EvidenceItem(
                    type="peer_similarity",
                    severity=severity,
                    title=(
                        f"{peer_entry['match_count']} similar region(s) with "
                        f"{peer_entry['partner']} (max "
                        f"{peer_entry['max_similarity']:.0%})"
                    ),
                    detail=peer_entry["detail"],
                )
            )

        if web_entry:
            sources = web_entry.get("sources") or []
            best = max(
                sources,
                key=lambda source: _coerce_float(source.get("similarity")) or 0.0,
                default={},
            )
            dossier.web_max_similarity = _coerce_float(web_entry.get("max_similarity"))
            dossier.web_best_match_url = str(best.get("url") or "")
            dossier.web_best_match_source = str(best.get("source") or "")
            severity = _web_severity(dossier.web_max_similarity)
            dossier.evidence.append(
                EvidenceItem(
                    type="web_provenance",
                    severity=severity,
                    title=(
                        f"Matches public source {dossier.web_best_match_source} "
                        f"at {(dossier.web_max_similarity or 0.0):.0%}"
                    ),
                    detail=str(best.get("name") or dossier.web_best_match_url),
                )
            )

        severity_rank = {"high": 0, "medium": 1, "low": 2}
        dossier.evidence.sort(
            key=lambda item: (severity_rank.get(item.severity, 3), item.type)
        )
        dossier.band = dossier.evidence[0].severity if dossier.evidence else "low"
        dossier.viva_questions = generate_viva_questions(dossier)
        return dossier

    @staticmethod
    def _ai_detail(ai_entry: dict[str, Any]) -> str:
        """Human-readable summary of the AI detection evidence."""
        regions = ai_entry.get("flagged_regions") or []
        top_region = regions[0] if regions else None
        parts = []
        if top_region:
            parts.append(
                f"most predictable region lines {top_region.get('start_line')}"
                f"–{top_region.get('end_line')}"
            )
        indicators = ai_entry.get("indicators") or []
        if indicators:
            parts.append("; ".join(str(i) for i in indicators[:2]))
        return "; ".join(parts) or "statistical signal profile"

    @staticmethod
    def _peer_similarity_by_name(
        results: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """Best pairwise match per file across all comparison results."""
        best: dict[str, dict[str, Any]] = {}
        for result in results:
            score = _coerce_float(result.get("score"))
            if score is None:
                continue
            file_a = str(result.get("file_a") or "")
            file_b = str(result.get("file_b") or "")
            if not file_a or not file_b:
                continue
            blocks = result.get("matching_blocks") or []
            function_name = ""
            for block in blocks:
                if isinstance(block, dict) and block.get("function_name"):
                    function_name = str(block["function_name"])
                    break
            detail = (
                f"{len(blocks)} matching region(s)"
                + (f", top function '{function_name}'" if function_name else "")
                + f", risk level {result.get('risk_level') or 'n/a'}"
            )
            for student, partner in ((file_a, file_b), (file_b, file_a)):
                current = best.get(student)
                if current is None or score > current["max_similarity"]:
                    best[student] = {
                        "max_similarity": score,
                        "partner": partner,
                        "match_count": len(blocks),
                        "detail": detail,
                    }
        return best


def generate_viva_questions(dossier: StudentDossier) -> list[str]:
    """Generate targeted viva questions from a student's evidence.

    Questions are phrased as instructions to the instructor and reference the
    concrete evidence (flagged regions, partners, matched URLs) so a hearing
    stays grounded in the dossier rather than in a bare score.
    """
    questions: list[str] = []
    by_type = {item.type: item for item in dossier.evidence}

    ai_item = by_type.get("ai_detection")
    if ai_item and ai_item.severity in ("high", "medium"):
        questions.append(
            f"Ask {dossier.student} to walk through their solution design: which "
            "function they wrote first, why they chose that decomposition, and "
            "what they would change for a larger input."
        )
        regions = _extract_region_range(ai_item.detail)
        if regions:
            questions.append(
                f"The most predictable region is lines {regions}. Ask the student "
                "to explain what that region does and re-derive its logic on the "
                "whiteboard without the code."
            )

    peer_item = by_type.get("peer_similarity")
    if peer_item and peer_item.severity in ("high", "medium"):
        function = _extract_function_name(peer_item.detail)
        focus = f"the '{function}' function" if function else "the matching regions"
        questions.append(
            f"{dossier.student} and {dossier.peer_partner} share "
            f"{(dossier.peer_max_similarity or 0.0):.0%} similarity. Ask each to "
            f"independently explain how {focus} works and how they debugged it."
        )

    web_item = by_type.get("web_provenance")
    if web_item and web_item.severity in ("high", "medium"):
        match_url = dossier.web_best_match_url or "a public source"
        questions.append(
            f"Similar code exists at {match_url}. Ask the student to "
            "reconstruct the core algorithm from scratch and explain how "
            "their version differs from the public one."
        )

    if (
        ai_item
        and peer_item
        and ai_item.severity in ("high", "medium")
        and peer_item.severity in ("high", "medium")
    ):
        questions.append(
            "Live modification check: ask the student to change the flagged "
            "function on the spot (swap the data structure or add a boundary "
            "condition) and explain the impact — this verifies practical "
            "authorship better than any score."
        )

    return questions[:_MAX_QUESTIONS_PER_STUDENT]


def _extract_region_range(detail: str) -> str:
    """Extract a 'start–end' line range from an AI detail string, if present."""
    match = re.search(r"lines (\d+)–(\d+)", detail or "")
    return f"{match.group(1)}–{match.group(2)}" if match else ""


def _extract_function_name(detail: str) -> str:
    """Extract the quoted top function name from a peer detail string."""
    match = re.search(r"top function '([^']+)'", detail or "")
    return match.group(1) if match else ""


def _ai_severity(ai_probability: float | None) -> str:
    """Band an AI probability using the product-wide thresholds."""
    if ai_probability is None:
        return "low"
    if ai_probability >= AI_HIGH:
        return "high"
    if ai_probability >= AI_MEDIUM:
        return "medium"
    return "low"


def _peer_severity(score: float, threshold: float) -> str:
    """Band a pairwise similarity score relative to the job threshold."""
    if score >= max(PEER_HIGH, threshold):
        return "high"
    if score >= threshold:
        return "medium"
    return "low"


def _web_severity(similarity: float | None) -> str:
    """Band a public-source containment similarity."""
    if similarity is None:
        return "low"
    if similarity >= WEB_HIGH:
        return "high"
    if similarity >= WEB_MEDIUM:
        return "medium"
    return "low"


def _band_rank(band: str) -> int:
    """Sort rank for overall bands (high first)."""
    return {"high": 0, "medium": 1, "low": 2}.get(band, 3)


def _coerce_float(value: Any) -> float | None:
    """Parse a float defensively, returning None for missing/bad values."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
