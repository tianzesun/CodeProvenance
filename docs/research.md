# Backend Structure Research

## Goal

Improve the backend package structure without breaking runtime behavior or the
existing import surface.

## Findings

1. The current backend mixes production code, benchmark code, experiments, and
   legacy bootstrap code under `src/backend/`.
2. There are many duplicate basenames across active directories such as
   `report_generator.py`, `ast_similarity.py`, `metrics.py`, `ground_truth.py`,
   and `calibration.py`. This increases import ambiguity and makes navigation
   slower.
3. `src/backend/benchmark/`, `src/backend/evaluation/`, and
   `src/backend/evalforge/` overlap conceptually. They all contain evaluation or
   benchmark logic, but they are implemented as separate package trees.
4. `src/backend/bootstrap_disabled/` is a legacy area that should be treated as
   quarantined code, not a production subsystem.
5. Tests still use the legacy `src.backend.backend.*` import path, so a strict
   move or rename would break the test suite and probably some local tooling.

## Best-Practice Direction

1. Keep production request-serving code under a stable backend package.
2. Move benchmark and offline evaluation workflows toward top-level,
   non-production directories only after compatibility shims exist.
3. Quarantine dead or deprecated code behind explicit legacy boundaries instead
   of leaving it mixed into active production areas.
4. Prefer package-level names that encode responsibility, not implementation
   history.
5. Add automated structural audits so duplicate names and legacy paths are
   visible in CI or local checks.

## Safe Immediate Actions

1. Preserve the current import contract with a compatibility namespace for
   `src.backend.backend.*`.
2. Add an audit script to make duplicate basenames and legacy directories
   visible.
3. Document a staged migration rather than doing a wide directory move in one
   change.

## Deferred Higher-Risk Actions

1. Move `src/backend/benchmark/` to a top-level package after import migration.
2. Consolidate `evaluation/` and `evalforge/` into one offline-evaluation
   domain.
3. Relocate `bootstrap_disabled/` into an explicit legacy area or remove it once
   no internal references remain.

