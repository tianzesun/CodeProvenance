# Legacy Bootstrap Quarantine

`src/backend/bootstrap_disabled/` is a legacy area and must not be used by
active production code.

It remains in the repository only as a temporary migration boundary while the
backend package is being normalized. Production packages must not import from
this directory.

Rules:

1. Do not add new imports from `src.backend.bootstrap_disabled`.
2. Do not add new features here.
3. Prefer deleting or migrating files out of this directory in small batches.
4. Use `python scripts/backend_structure_audit.py` to verify no production
   modules depend on this package.

Exit criteria:

1. No production imports remain.
2. Any still-useful code is moved to stable packages.
3. The directory can be removed entirely.
