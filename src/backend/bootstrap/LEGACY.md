# Bootstrap Module

`src/backend/bootstrap/` contains the canonical application bootstrap and architecture guard.

This module provides:
- Single execution lifecycle (`app.py`)
- Dependency injection container
- Architecture validation

The architecture guard validates layer boundaries at runtime and in CI.
