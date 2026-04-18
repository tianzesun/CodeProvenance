# Backend Architecture Cleanup Plan

## Current Stable Runtime Surface

- API and entrypoints: `src/backend/main.py`, `src/backend/api/`
- Application orchestration: `src/backend/application/`
- Detection and scoring engines: `src/backend/engines/`
- Shared runtime support: `src/backend/infrastructure/`, `src/backend/config/`,
  `src/backend/models/`

## Target Structure

```text
src/backend/
  api/                # FastAPI routes, schemas, middleware
  application/        # Use cases and orchestration
  domain/             # Domain models and decision rules
  engines/            # Detection, similarity, scoring, execution engines
  infrastructure/     # DB, reporting, indexing, email, parsing
  config/             # Settings and environment wiring
  models/             # Persistence models
  backend/            # Compatibility namespace for legacy imports

benchmark/            # Offline benchmark harness and datasets
evaluation/           # Offline comparative and statistical evaluation
legacy/               # Quarantined deprecated code
docs/                 # Architecture, research, and task coordination
tests/                # Unit and integration tests
```

## Migration Rules

1. No import path should break during the first cleanup phase.
2. Runtime API code must not depend on deprecated or quarantined modules.
3. Benchmark and evaluation moves should happen behind shims or import rewrites.
4. Duplicate filenames should be reduced gradually, starting with the most
   collision-prone utility and reporting modules.

## Phase 1 Implemented Here

1. Added `src/backend/backend/` as a compatibility namespace so legacy imports
   resolve without copying code.
2. Added a structural audit script to expose duplicate basenames and legacy
   directories.
3. Documented the split between runtime code, offline benchmark code, and
   quarantined legacy code.

## Recommended Next Moves

1. Rewrite imports from `src.backend.backend.*` to `src.backend.*`.
2. Freeze `bootstrap_disabled/` as legacy-only and remove any accidental new
   imports.
3. Create a dedicated top-level home for benchmark and evaluation code, then
   move modules in small batches with import shims.
4. Rename the most duplicated filenames with package-specific names such as
   `similarity_ast.py`, `benchmark_metrics.py`, or `report_generation_service.py`
   once call sites are updated.

