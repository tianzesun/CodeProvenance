# Backend Structure Tasks

## Current Phase

Improve backend structure without breaking runtime behavior.

## Workflow

1. Project Manager
   - Track structural cleanup tasks here.
2. Researcher
   - Record best-practice findings in `docs/research.md`.
3. Architect
   - Maintain the target module boundaries in `docs/architecture.md`.
4. Developer
   - Apply low-risk structural changes and compatibility shims first.
5. Tester
   - Validate imports and targeted backend tests.
6. Reviewer
   - Confirm no new production dependencies on legacy paths.

## Immediate Tasks

- [x] Add a compatibility namespace for `src.backend.backend.*`.
- [x] Add a backend structure audit script.
- [x] Document the staged cleanup plan.
- [x] Rewrite tests away from `src.backend.backend.*`.
- [ ] Rewrite any remaining runtime imports away from `src.backend.backend.*`.
- [ ] Inventory duplicate basenames and prioritize the highest-risk collisions.
- [x] Reduce `report_generator.py` collisions by renaming modules to role-specific names.
- [x] Reduce most runtime `registry.py` collisions by renaming module files to role-specific names.
- [x] Reduce `config.py` collisions by renaming benchmark and GPU service config modules.
- [ ] Define the first module batch to move out of `src/backend/benchmark/`.
- [x] Quarantine `src/backend/bootstrap_disabled/` and block new production imports.
- [ ] Remove `src/backend/bootstrap_disabled/` after migration or deletion of any remaining useful code.

## Feature Initiative: Unified Detection Platform

### Goal

Make IntegrityDesk the professor-facing hub for running multiple plagiarism and
code-integrity tools from one workflow. IntegrityDesk should remain a strong
native engine, but the product should also orchestrate trusted external tools
such as MOSS, JPlag, Dolos, and NiCad when a professor wants corroborating
evidence or a different detection style.

### Acceptance Criteria

- [ ] Professors can view available detection tools and IntegrityDesk preset
      modes with language support, availability, and execution notes.
- [ ] Professors can select one or more tools for the same assignment analysis.
- [ ] The platform can recommend a tool bundle from assignment features such as
      language, starter-code usage, assignment size, expected transformations,
      and AI-assistance concern.
- [ ] Multi-tool results are normalized into one report with per-tool evidence,
      failures, and confidence notes.
- [ ] Professors can override recommendations before running analysis.
- [ ] External tool credentials and local binaries are never hardcoded.

### Agent Task Board

1. Project Manager
   - [x] Define the workflow objective and acceptance criteria.
   - [x] Create the multi-agent prompt-chain assets under `docs/agents/`.
2. Researcher
   - [x] Inventory existing external tool adapters, registries, and execution
         code.
   - [ ] Confirm current frontend analysis flow and report surfaces before UI
         implementation.
3. Architect
   - [x] Add a module plan for tool catalog, recommendation, orchestration, and
         normalized reports.
   - [ ] Define API request/response schemas for the first implementation
         slice.
4. Developer
   - [ ] Implement a read-only detection tool catalog endpoint.
   - [ ] Implement assignment-feature recommendation logic without new
         dependencies.
   - [ ] Wire selected tools into the existing job request path.
5. Tester
   - [ ] Add unit tests for catalog and recommendation logic.
   - [ ] Add integration tests for multi-tool request validation.
   - [ ] Add a partial-failure report test when one selected tool is unavailable.
6. Reviewer
   - [ ] Review external tool execution risk, secret handling, timeout behavior,
         and professor-facing failure messages.

### Researcher Handoff

Investigate existing backend execution, benchmark adapter, tool registry, job
API, and report-generation code. Focus on how to reuse current MOSS, JPlag,
Dolos, NiCad, and IntegrityDesk engine concepts as a product catalog rather than
only as benchmark infrastructure.

### Architect Handoff

Design the first implementation slice around a read-only catalog and
recommendation service before running real multi-tool jobs. Keep external tool
execution optional and explicit because professor trust depends on transparent
tool availability and failure states.
