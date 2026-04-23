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

---

# Unified Detection Platform Research

## Goal

Position IntegrityDesk as a unified platform where professors can run the native
IntegrityDesk engine and trusted external tools such as MOSS, JPlag, Dolos, and
NiCad from one workflow. The platform should also recommend suitable tools or
IntegrityDesk preset modes from assignment features.

## Current Repo Evidence

1. `src/backend/engines/execution/execution_engine.py` already defines a real
   subprocess execution layer for external plagiarism detection tools with
   timeout handling, deterministic environment setup, sandbox support, and
   normalized `ExecutionResult` metadata.
2. `src/backend/engines/execution/adapter_layer.py` already adapts MOSS, JPlag,
   and Dolos outputs into a shared `ToolFinding` shape that can convert to the
   domain `Finding` model.
3. `src/backend/benchmark/tools/tool_registry.py` already models tool metadata:
   name, category, entry kind, root path, adapter module, adapter class,
   supported languages, enabled state, official state, and notes.
4. `tools/README.md` already describes external tool reproducibility rules,
   including version, path, adapter, config, dataset, timestamp, and commit
   metadata.
5. Tests already cover benchmark tribunal behavior and adapter registry
   behavior for MOSS, JPlag, and Dolos in `tests/unit/test_benchmark_tribunal.py`.

## Best-Practice Direction

1. Promote the existing benchmark tool registry concept into a professor-facing
   detection tool catalog instead of duplicating tool metadata.
2. Keep tool recommendation separate from tool execution. Recommendation should
   be deterministic, explainable, and safe to run even when external binaries
   are unavailable.
3. Treat every detector as one evidence source. The report should preserve
   per-tool findings and failures instead of hiding disagreements behind one
   fused score.
4. Make recommendations overrideable. Professors may trust MOSS, prefer JPlag
   for structural copy detection, or run multiple tools for corroboration.
5. Use availability checks and explicit failure states before invoking external
   tools. MOSS credentials, JPlag jars, Dolos packages, and NiCad binaries should
   be reported as configuration state, not assumed.

## Suggested Tool Positioning

| Tool Or Mode | Strong Fit | Caution |
| --- | --- | --- |
| IntegrityDesk presets | Combined evidence, explainable reports, AI/stylometry-aware review | Presets must be named and documented clearly |
| MOSS | Familiar professor workflow, token/fingerprint-style similarity | Credential and service availability need explicit handling |
| JPlag | Structural and token-sequence copy detection across supported languages | Java/JAR requirements and output parsing must be validated |
| Dolos | Local open-source workflow and visualization-style evidence | Node/Ruby package state can complicate deployment |
| NiCad | Clone detection and near-miss code clone workflows | Installation/runtime can be heavier than simple web jobs |

## Recommended First Slice

1. Add a read-only detection tool catalog that exposes supported tools, language
   support, availability, notes, and whether a professor can select the tool.
2. Add a recommendation service that maps assignment features to suggested tool
   bundles and explains the reason for each recommendation.
3. Keep execution wiring as the second slice after catalog and recommendation
   behavior are tested.

## Risks And Unknowns

1. The current benchmark registry paths refer to `tools/external/`, while the
   actual repo contains tools such as `tools/JPlag/`, `tools/NiCad-6.2/`, and
   `tools/dolos/`. The product catalog should verify real paths or add a
   compatibility mapping.
2. MOSS may require private credentials or network access. That should be
   represented as `configured=false` or `available=false`, not as a runtime
   crash.
3. Running multiple external tools in parallel can become a background-job,
   timeout, resource, and sandboxing problem. Treat orchestration as high risk.
4. UI work needs a current frontend inspection before implementation because the
   analysis form and report surfaces may already have established patterns.

## Architect Handoff

Design four boundaries: detection tool catalog, assignment feature profile,
recommendation engine, and multi-tool job orchestration. Start with catalog and
recommendation APIs; leave real external multi-tool execution as a later slice
unless the Developer confirms the current job pipeline already supports it
cleanly.
