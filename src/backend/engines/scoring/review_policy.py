"""Review band and AI corroboration policy for IntegrityDesk.

This module implements the two core policy functions that drive the faculty
review workflow:

``compute_band``
    Maps a (similarity_score, assignment_mode) pair to a faculty-facing
    review band: ``'low'``, ``'review'``, or ``'high'``.  Thresholds are
    looked up from ``BAND_THRESHOLDS`` (DB-seeded defaults; can be overridden
    by passing a ``BandThresholdConfig`` directly).

``compute_corroboration``
    Evaluates whether an AI detection flag is *corroborated* by structural
    evidence, and returns the full label, blocked dispositions, and a
    human-readable reason.  Implements the five rules from the design spec:

    Rule 1 — AI-only flag (similarity below review threshold, no web match)
    Rule 2 — AI + structural similarity (corroborated)
    Rule 3 — AI + web match (corroborated)
    Rule 4 — High similarity, AI not elevated
    Rule 5 — High AI, borderline similarity (elevated to Review but blocked)

All policy logic is pure (no DB calls, no I/O) so it is fast, deterministic,
and easy to unit-test.  The DB integration lives in ``PairReviewService``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Band threshold configuration
# ---------------------------------------------------------------------------

#: Default per-mode thresholds.  These mirror the seeded rows in
#: ``band_thresholds`` and are used when no DB override is available.
BAND_THRESHOLDS: dict[str, dict[str, float]] = {
    "introductory": {
        "review_min": 0.45,
        "high_min": 0.70,
        "ai_elevated_min": 0.65,
        "web_match_min": 0.70,
        "engine_agree_count": 2,
        "engine_agree_min": 0.50,
    },
    "algorithms": {
        "review_min": 0.35,
        "high_min": 0.65,
        "ai_elevated_min": 0.65,
        "web_match_min": 0.70,
        "engine_agree_count": 2,
        "engine_agree_min": 0.50,
    },
    "projects": {
        "review_min": 0.25,
        "high_min": 0.55,
        "ai_elevated_min": 0.65,
        "web_match_min": 0.70,
        "engine_agree_count": 2,
        "engine_agree_min": 0.50,
    },
    "capstone": {
        "review_min": 0.20,
        "high_min": 0.50,
        "ai_elevated_min": 0.65,
        "web_match_min": 0.70,
        "engine_agree_count": 2,
        "engine_agree_min": 0.50,
    },
    "default": {
        "review_min": 0.35,
        "high_min": 0.65,
        "ai_elevated_min": 0.65,
        "web_match_min": 0.70,
        "engine_agree_count": 2,
        "engine_agree_min": 0.50,
    },
}

#: Dispositions that require corroboration before they can be offered.
#: Step-up verification and formal escalation must never be triggered by AI
#: detection alone.
HIGH_STAKES_DISPOSITIONS: frozenset[str] = frozenset({"step_up_verification", "formal_escalation"})

#: All valid disposition values (enforced server-side in the reviews endpoint).
VALID_DISPOSITIONS: frozenset[str] = frozenset(
    {
        "no_action",
        "note_on_file",
        "conversation",
        "step_up_verification",
        "formal_escalation",
    }
)

#: Dispositions allowed when a pair is in the Low band.
LOW_BAND_DISPOSITIONS: frozenset[str] = frozenset({"no_action", "note_on_file"})

#: Dispositions allowed when a pair is in the Review band.
REVIEW_BAND_DISPOSITIONS: frozenset[str] = frozenset(
    {"no_action", "note_on_file", "conversation", "step_up_verification"}
)

#: Dispositions allowed when a pair is in the High band.
HIGH_BAND_DISPOSITIONS: frozenset[str] = frozenset(VALID_DISPOSITIONS)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class BandThresholdConfig:
    """Threshold configuration for a single assignment mode.

    Can be constructed directly from a ``BandThreshold`` ORM row or from the
    ``BAND_THRESHOLDS`` defaults dict.

    Args:
        review_min: Lower edge of the Review band.
        high_min: Lower edge of the High band.
        ai_elevated_min: AI probability above which a score is "elevated".
        web_match_min: Minimum web-match snippet overlap to count as
            corroboration.
        engine_agree_count: Number of engines that must individually score
            >= ``engine_agree_min`` for engine-agreement corroboration.
        engine_agree_min: Per-engine score floor for agreement counting.
    """

    review_min: float
    high_min: float
    ai_elevated_min: float = 0.65
    web_match_min: float = 0.70
    engine_agree_count: int = 2
    engine_agree_min: float = 0.50

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BandThresholdConfig":
        """Build from a plain dict (e.g. from BAND_THRESHOLDS or a DB row)."""
        return cls(
            review_min=float(d["review_min"]),
            high_min=float(d["high_min"]),
            ai_elevated_min=float(d.get("ai_elevated_min", 0.65)),
            web_match_min=float(d.get("web_match_min", 0.70)),
            engine_agree_count=int(d.get("engine_agree_count", 2)),
            engine_agree_min=float(d.get("engine_agree_min", 0.50)),
        )


@dataclass
class BandResult:
    """Output of ``compute_band``.

    Attributes:
        band: ``'low'``, ``'review'``, or ``'high'``.
        allowed_dispositions: Set of dispositions the reviewer may select
            *before* corroboration is applied.  The corroboration check may
            further restrict this.
        thresholds: The resolved threshold config that was used.
    """

    band: str
    allowed_dispositions: frozenset[str]
    thresholds: BandThresholdConfig


@dataclass
class CorroborationResult:
    """Output of ``compute_corroboration``.

    Attributes:
        ai_flag: True when the AI score meets or exceeds ``ai_elevated_min``.
        corroborated: True when AI flag is accompanied by independent
            structural or web evidence.
        label: Short human-readable label for the UI (e.g. ``'AI-only flag'``).
        reason: Longer explanation shown in the disposition panel.
        blocked_dispositions: Dispositions the UI must grey out and the API
            must reject.  Empty when the AI flag is not elevated or is
            corroborated.
        rule: Which of the five design-spec rules fired (1–5, or 0 for
            "AI not elevated").
    """

    ai_flag: bool
    corroborated: bool
    label: str
    reason: str
    blocked_dispositions: frozenset[str] = field(default_factory=frozenset)
    rule: int = 0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_thresholds(
    assignment_mode: str | None,
    override: BandThresholdConfig | None = None,
) -> BandThresholdConfig:
    """Return the threshold config for *assignment_mode*.

    Lookup order:
    1. ``override`` (if provided) — used by tests and admin overrides.
    2. ``BAND_THRESHOLDS[assignment_mode]`` (normalised to lower-case).
    3. ``BAND_THRESHOLDS['default']`` as fallback.

    Args:
        assignment_mode: Canonical mode string (e.g. ``'introductory'``).
            Case-insensitive.  ``None`` falls through to ``'default'``.
        override: Optional explicit config that bypasses the lookup table.

    Returns:
        A :class:`BandThresholdConfig` instance.
    """
    if override is not None:
        return override
    mode_key = (assignment_mode or "").lower().strip()
    raw = BAND_THRESHOLDS.get(mode_key) or BAND_THRESHOLDS["default"]
    return BandThresholdConfig.from_dict(raw)


def compute_band(
    similarity_score: float,
    assignment_mode: str | None = None,
    threshold_override: BandThresholdConfig | None = None,
) -> BandResult:
    """Map a similarity score to a faculty review band.

    Args:
        similarity_score: Fused similarity score in [0.0, 1.0].  Values
            outside this range are clamped.
        assignment_mode: Assignment mode string.  ``None`` uses ``'default'``.
        threshold_override: Optional explicit threshold config; bypasses the
            lookup table (useful in tests and admin workflows).

    Returns:
        A :class:`BandResult` with ``band``, ``allowed_dispositions``, and
        the resolved ``thresholds``.

    Examples::

        >>> result = compute_band(0.72, "algorithms")
        >>> result.band
        'high'

        >>> result = compute_band(0.40, "algorithms")
        >>> result.band
        'review'

        >>> result = compute_band(0.20, "algorithms")
        >>> result.band
        'low'
    """
    score = max(0.0, min(1.0, float(similarity_score)))
    cfg = get_thresholds(assignment_mode, threshold_override)

    if score >= cfg.high_min:
        return BandResult(
            band="high",
            allowed_dispositions=HIGH_BAND_DISPOSITIONS,
            thresholds=cfg,
        )
    if score >= cfg.review_min:
        return BandResult(
            band="review",
            allowed_dispositions=REVIEW_BAND_DISPOSITIONS,
            thresholds=cfg,
        )
    return BandResult(
        band="low",
        allowed_dispositions=LOW_BAND_DISPOSITIONS,
        thresholds=cfg,
    )


def compute_corroboration(
    ai_score: float,
    similarity_score: float,
    assignment_mode: str | None = None,
    engine_scores: dict[str, float] | None = None,
    web_match_score: float = 0.0,
    threshold_override: BandThresholdConfig | None = None,
) -> CorroborationResult:
    """Evaluate whether an AI detection flag is corroborated.

    Implements the five rules from the design spec (evaluated in order;
    first match wins):

    **Rule 1** — AI-only flag: AI elevated but similarity below review
    threshold and no web-match corroboration.  High-stakes dispositions
    blocked.

    **Rule 2** — AI + structural similarity: AI elevated, similarity meets
    review threshold, and ≥ ``engine_agree_count`` engines individually score
    ≥ ``engine_agree_min``.  Fully corroborated.

    **Rule 3** — AI + web match: AI elevated and a web-match snippet meets
    ``web_match_min``.  Fully corroborated.

    **Rule 4** — AI not elevated: Standard banding applies; no AI label shown.

    **Rule 5** — High AI, borderline similarity: AI ≥ 0.80 and similarity is
    non-trivially positive (≥ 0.10) but below review threshold; band is
    elevated to Review but high-stakes dispositions are still blocked.

    Args:
        ai_score: AI detection probability in [0.0, 1.0].
        similarity_score: Fused structural similarity score (AI contribution
            *excluded* from this value for display purposes).
        assignment_mode: Used to look up threshold config.
        engine_scores: Dict of per-engine scores, e.g.
            ``{'ast': 0.61, 'token': 0.55, 'semantic': 0.48}``.  Used for
            engine-agreement corroboration.
        web_match_score: Highest web-match snippet overlap score (0.0–1.0).
        threshold_override: Optional threshold config override.

    Returns:
        A :class:`CorroborationResult`.

    Examples::

        >>> r = compute_corroboration(0.80, 0.30, "algorithms")
        >>> r.ai_flag, r.corroborated, r.rule
        (True, False, 1)

        >>> r = compute_corroboration(0.80, 0.60, "algorithms",
        ...     engine_scores={"ast": 0.70, "token": 0.65})
        >>> r.ai_flag, r.corroborated, r.rule
        (True, True, 2)

        >>> r = compute_corroboration(0.30, 0.60, "algorithms")
        >>> r.ai_flag, r.corroborated, r.rule
        (False, False, 4)
    """
    score = max(0.0, min(1.0, float(similarity_score)))
    ai = max(0.0, min(1.0, float(ai_score)))
    cfg = get_thresholds(assignment_mode, threshold_override)
    engines = engine_scores or {}

    ai_elevated = ai >= cfg.ai_elevated_min
    web_corroborates = web_match_score >= cfg.web_match_min

    # Count how many engines individually meet the agreement threshold
    agreeing_engines = sum(
        1
        for v in engines.values()
        if isinstance(v, (int, float)) and float(v) >= cfg.engine_agree_min
    )
    engine_agrees = agreeing_engines >= cfg.engine_agree_count

    # Rule 4 — AI not elevated (evaluated before AI rules to short-circuit)
    if not ai_elevated:
        # Rule 5 subset: very high AI but below ai_elevated_min is impossible
        # by definition; keep Rule 4 clean.
        return CorroborationResult(
            ai_flag=False,
            corroborated=False,
            label="",
            reason="",
            blocked_dispositions=frozenset(),
            rule=4,
        )

    # AI IS elevated from here on down.

    # Rule 3 — AI + web match
    if web_corroborates:
        return CorroborationResult(
            ai_flag=True,
            corroborated=True,
            label="AI + web evidence",
            reason=(
                f"AI detection elevated ({ai:.0%}) and a web match with "
                f"{web_match_score:.0%} snippet overlap was found. "
                "All disposition actions are available."
            ),
            blocked_dispositions=frozenset(),
            rule=3,
        )

    # Rule 2 — AI + structural similarity (engine agreement required)
    if score >= cfg.review_min and engine_agrees:
        engine_list = ", ".join(
            k
            for k, v in engines.items()
            if isinstance(v, (int, float)) and float(v) >= cfg.engine_agree_min
        )
        return CorroborationResult(
            ai_flag=True,
            corroborated=True,
            label="AI + similarity",
            reason=(
                f"AI detection elevated ({ai:.0%}) and structural similarity "
                f"({score:.0%}) is above the threshold for this assignment type, "
                f"with {agreeing_engines} engines agreeing"
                + (f" ({engine_list})" if engine_list else "")
                + ". All disposition actions are available."
            ),
            blocked_dispositions=frozenset(),
            rule=2,
        )

    # Rule 5 — High AI (≥ 0.80), borderline similarity (non-trivial but below
    # review threshold).  Elevate band signal but still block high-stakes.
    if ai >= 0.80 and score >= 0.10:
        return CorroborationResult(
            ai_flag=True,
            corroborated=False,
            label="AI-only flag – elevated priority",
            reason=(
                f"AI detection is high ({ai:.0%}) but structural similarity "
                f"({score:.0%}) is below the review threshold for this assignment "
                f"type ({cfg.review_min:.0%}). Step-up verification and formal "
                "escalation require corroborating structural evidence."
            ),
            blocked_dispositions=HIGH_STAKES_DISPOSITIONS,
            rule=5,
        )

    # Rule 1 — AI-only flag (elevated AI, insufficient corroboration)
    return CorroborationResult(
        ai_flag=True,
        corroborated=False,
        label="AI-only flag",
        reason=(
            f"AI detection is elevated ({ai:.0%}), but structural similarity "
            f"({score:.0%}) is below the threshold for this assignment type "
            f"({cfg.review_min:.0%}) and no corroborating web or structural "
            "evidence was found. Step-up verification and formal escalation "
            "are not available. This reflects IntegrityDesk policy: AI "
            "detection alone is preliminary evidence, not proof."
        ),
        blocked_dispositions=HIGH_STAKES_DISPOSITIONS,
        rule=1,
    )


def allowed_dispositions_for_pair(
    band_result: BandResult,
    corroboration_result: CorroborationResult,
) -> frozenset[str]:
    """Return the final set of dispositions available for a pair.

    Intersects the band-level allowed set with the corroboration constraint:
    if the AI flag is elevated but not corroborated, high-stakes dispositions
    are removed regardless of band.

    Args:
        band_result: Output of :func:`compute_band`.
        corroboration_result: Output of :func:`compute_corroboration`.

    Returns:
        The set of disposition strings the reviewer may select.
    """
    return band_result.allowed_dispositions - corroboration_result.blocked_dispositions


def validate_disposition(
    disposition: str,
    band_result: BandResult,
    corroboration_result: CorroborationResult,
) -> tuple[bool, str]:
    """Check whether *disposition* is permitted for this pair.

    Used server-side in the POST /reviews endpoint to reject invalid
    dispositions even if the frontend fails to enforce them.

    Args:
        disposition: The disposition string submitted by the reviewer.
        band_result: Output of :func:`compute_band`.
        corroboration_result: Output of :func:`compute_corroboration`.

    Returns:
        ``(True, "")`` if valid, or ``(False, reason_string)`` if not.
    """
    if disposition not in VALID_DISPOSITIONS:
        return False, f"'{disposition}' is not a valid disposition."

    allowed = allowed_dispositions_for_pair(band_result, corroboration_result)
    if disposition not in allowed:
        if disposition in corroboration_result.blocked_dispositions:
            return (
                False,
                f"'{disposition}' requires corroborating evidence. "
                f"{corroboration_result.reason}",
            )
        return (
            False,
            f"'{disposition}' is not available for the '{band_result.band}' band.",
        )
    return True, ""
