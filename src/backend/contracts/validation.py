"""Runtime Validation Gate - Hard stop at every boundary.

Every adapter, pipeline stage, and API endpoint must validate through this gate.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from src.backend.contracts.evaluation_result import EnrichedPair, EvaluationResult

from .schema_registry import ValidationError, registry

_EVAL_REQUIRED = frozenset({"pair_id", "score", "decision", "confidence", "engine"})
_PAIR_REQUIRED = frozenset(
    {
        "pair_id",
        "id_a",
        "id_b",
        "code_a",
        "code_b",
        "label",
        "clone_type",
        "difficulty",
        "language",
    }
)
_DIFFICULTIES = frozenset({"EASY", "MEDIUM", "HARD", "EXPERT"})


@dataclass(frozen=True)
class ValidationResult:
    """Result of validation."""

    is_valid: bool
    errors: list[str]
    warnings: list[str]

    def raise_if_invalid(self) -> None:
        if not self.is_valid:
            raise ValidationError(
                f"Validation failed with {len(self.errors)} error(s): "
                + "; ".join(self.errors)
            )


# --- field helpers ---------------------------------------------------------------
# bool is a subclass of int in Python, so True/False would otherwise pass as 1/0.


def _check_unit_interval(field: str, value: Any, errors: list[str]) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        errors.append(f"{field} must be numeric, got {type(value).__name__}")
    elif isinstance(value, float) and math.isnan(
        value
    ):  # math.isnan(huge int) overflows
        errors.append(f"{field} is NaN")
    elif not 0.0 <= value <= 1.0:
        errors.append(f"{field} must be in [0, 1], got {value}")


def _check_str(field: str, value: Any, errors: list[str]) -> None:
    if not isinstance(value, str):
        errors.append(f"{field} must be string, got {type(value).__name__}")
    elif not value.strip():
        errors.append(f"{field} must not be empty")


def _check_int_choice(
    field: str, value: Any, allowed: tuple[int, ...], errors: list[str]
) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value not in allowed:
        errors.append(f"{field} must be one of {allowed}, got {value!r}")


def _known_fields(
    cls: type, base: frozenset[str], extra: frozenset[str] = frozenset()
) -> set[str]:
    known = set(base) | set(extra)
    if dataclasses.is_dataclass(cls):
        known |= {f.name for f in dataclasses.fields(cls)}
    return known


def _as_values(data: Any, names: Iterable[str]) -> dict[str, Any]:
    """Read the named attributes off an already-constructed instance."""
    return {n: getattr(data, n) for n in names if hasattr(data, n)}


class ValidationGate:
    """Runtime validation gate - the HARD STOP for invalid data.

    Rules: reject NaN/out-of-range scores, bool-as-number, missing/empty ids,
    wrong types. Unknown fields are errors in strict mode, warnings otherwise.
    Instances are validated as strictly as dicts (constructing a dataclass does
    not validate it).
    """

    def __init__(self, strict_mode: bool = False) -> None:
        self.strict_mode = strict_mode

    def _unknown(
        self, found: set[str], known: set[str], errors: list[str], warnings: list[str]
    ) -> None:
        unknown = found - known
        if unknown:
            msg = f"Unknown fields: {sorted(unknown)}"
            (errors if self.strict_mode else warnings).append(msg)

    def validate_evaluation_result(self, data: Any) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []

        if isinstance(data, EvaluationResult):
            values = _as_values(data, _EVAL_REQUIRED | {"metadata"})
        elif isinstance(data, Mapping):
            values = dict(data)
            self._unknown(
                set(values),
                _known_fields(
                    EvaluationResult, _EVAL_REQUIRED, frozenset({"metadata"})
                ),
                errors,
                warnings,
            )
        else:
            return ValidationResult(
                False,
                [f"Expected dict or EvaluationResult, got {type(data).__name__}"],
                [],
            )

        missing = _EVAL_REQUIRED - values.keys()
        if missing:
            errors.append(f"Missing required fields: {sorted(missing)}")

        if "score" in values:
            _check_unit_interval("score", values["score"], errors)
        if "confidence" in values:
            _check_unit_interval("confidence", values["confidence"], errors)
        if "decision" in values and not isinstance(values["decision"], bool):
            errors.append(
                f"decision must be bool, got {type(values['decision']).__name__}"
            )
        if "pair_id" in values:
            _check_str("pair_id", values["pair_id"], errors)
        if "engine" in values:
            _check_str("engine", values["engine"], errors)
        if "metadata" in values and not isinstance(values["metadata"], Mapping):
            errors.append(
                f"metadata must be dict, got {type(values['metadata']).__name__}"
            )

        return ValidationResult(not errors, errors, warnings)

    def validate_enriched_pair(self, data: Any) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []

        if isinstance(data, EnrichedPair):
            values = _as_values(data, _PAIR_REQUIRED)
        elif isinstance(data, Mapping):
            values = dict(data)
            self._unknown(
                set(values),
                _known_fields(EnrichedPair, _PAIR_REQUIRED),
                errors,
                warnings,
            )
        else:
            return ValidationResult(
                False, [f"Expected dict or EnrichedPair, got {type(data).__name__}"], []
            )

        missing = _PAIR_REQUIRED - values.keys()
        if missing:
            errors.append(f"Missing required fields: {sorted(missing)}")

        for f in ("pair_id", "id_a", "id_b", "language"):
            if f in values:
                _check_str(f, values[f], errors)
        for f in ("code_a", "code_b"):
            if f in values:
                if not isinstance(values[f], str):
                    errors.append(f"{f} must be string, got {type(values[f]).__name__}")
                elif not values[f].strip():
                    warnings.append(f"{f} is empty")
        if "label" in values:
            _check_int_choice("label", values["label"], (0, 1), errors)
        if "clone_type" in values:
            _check_int_choice(
                "clone_type", values["clone_type"], (0, 1, 2, 3, 4), errors
            )
        if "difficulty" in values:
            d = values["difficulty"]
            if not isinstance(d, str) or d not in _DIFFICULTIES:
                errors.append(f"difficulty must be EASY/MEDIUM/HARD/EXPERT, got {d!r}")

        return ValidationResult(not errors, errors, warnings)

    def validate_batch(
        self, schema_name: str, items: Iterable[Any]
    ) -> ValidationResult:
        """Validate many items; errors are prefixed with the item index.

        Raises:
            KeyError: If ``schema_name`` is not registered (a caller bug, not bad data).
        """
        registry.get(schema_name)  # fail loudly up front, not once per item
        custom = {
            "EvaluationResult": self.validate_evaluation_result,
            "EnrichedPair": self.validate_enriched_pair,
        }
        all_errors: list[str] = []
        all_warnings: list[str] = []

        for i, item in enumerate(items):
            if schema_name in custom:
                result = custom[schema_name](item)
            else:
                try:
                    registry.validate(schema_name, item)
                    result = ValidationResult(True, [], [])
                except ValidationError as e:
                    result = ValidationResult(False, [str(e)], [])
            all_errors.extend(f"Item {i}: {e}" for e in result.errors)
            all_warnings.extend(f"Item {i}: {w}" for w in result.warnings)

        return ValidationResult(not all_errors, all_errors, all_warnings)


def validate_evaluation_result(data: Any, *, strict: bool = False) -> EvaluationResult:
    """Validate and return an EvaluationResult.

    Raises:
        ValidationError: If validation or construction fails.
    """
    ValidationGate(strict_mode=strict).validate_evaluation_result(
        data
    ).raise_if_invalid()
    if isinstance(data, EvaluationResult):
        return data
    try:
        return EvaluationResult.from_dict(dict(data))
    except (TypeError, ValueError, KeyError) as e:
        raise ValidationError(f"Failed to build EvaluationResult: {e}") from e


def validate_enriched_pair(data: Any, *, strict: bool = False) -> EnrichedPair:
    """Validate and return an EnrichedPair.

    Raises:
        ValidationError: If validation or construction fails.
    """
    ValidationGate(strict_mode=strict).validate_enriched_pair(data).raise_if_invalid()
    if isinstance(data, EnrichedPair):
        return data
    try:
        return EnrichedPair(**data)
    except (TypeError, ValueError) as e:  # e.g. unknown keys in non-strict mode
        raise ValidationError(f"Failed to build EnrichedPair: {e}") from e
