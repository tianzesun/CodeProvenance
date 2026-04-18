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
