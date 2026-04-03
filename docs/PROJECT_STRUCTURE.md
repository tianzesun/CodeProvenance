# CodeProvenance Project Structure

## Overview

The project follows a clean, consolidated structure with strict architecture boundaries enforced in code.

## Root Directory

```
.
├── .gitignore          # Git ignore rules
├── alembic/            # Database migrations (Alembic)
├── config/             # Configuration files
├── data/               # Large datasets (gitignored)
│   ├── datasets/       # Actual dataset files
│   ├── raw/            # Raw unprocessed data
│   ├── processed/      # Processed/cleaned data
│   ├── benchmarks/     # Benchmark results
│   └── external/       # External data sources
├── docker/             # Docker configuration
├── docs/               # Documentation
├── scripts/            # Build and utility scripts
├── src/                # Core source code (strict architecture)
├── templates/          # HTML templates
├── tests/              # Test files
├── tools/              # External tools and large systems
├── alembic.ini         # Alembic configuration
├── docker-compose.yml  # Docker Compose configuration
├── Dockerfile          # Docker build file
├── LICENSE             # License file
├── README.md           # Project README
├── requirements*.txt   # Python dependencies
└── venv/               # Virtual environment (gitignored)
```

## Source Code (`src/`) - Strict Architecture

The `src/` directory enforces strict architecture boundaries with import validation:

```
src/
├── __init__.py         # Architecture enforcement and validation
├── api/                # REST API endpoints (presentation layer)
├── application/        # Application layer (use cases, orchestration)
├── benchmark/          # Benchmark system (evaluation framework)
├── bootstrap/          # Single execution lifecycle (canonical entry point)
├── config/             # Configuration management
├── core/               # Core similarity detection (kernel logic)
├── domain/             # Domain models (business logic - NO infrastructure imports)
├── engines/            # Detection engines (runtime execution logic)
├── evaluation/         # Consolidated evaluation framework
│   ├── core/           # Core evaluation logic
│   ├── dataset/        # Dataset management
│   ├── lab/            # Evaluation laboratory
│   └── analysis/       # Error analysis and classification
├── infrastructure/     # External systems (implements domain interfaces)
├── ml/                 # Machine learning models (training/inference)
├── models/             # Data structures and ML models
├── pipeline/           # Processing orchestration
├── utils/              # Utility functions
├── web/                # Web interface (presentation layer)
└── workers/            # Background workers (infrastructure)
```

### Architecture Boundaries (Enforced in Code)

1. **Domain Layer** (`domain/`)
   - Contains business logic only
   - **CANNOT** import from `infrastructure/`, `api/`, `web/`, or `utils/`
   - Defines interfaces that infrastructure must implement

2. **Application Layer** (`application/`)
   - Use cases and orchestration
   - Depends only on `domain/` and `core/`
   - Coordinates between domain and infrastructure

3. **Infrastructure Layer** (`infrastructure/`)
   - Implements domain interfaces
   - Handles external systems (database, APIs, file systems)
   - Can import from `domain/` and `core/`

4. **Core Layer** (`core/`)
   - Shared primitives and kernel logic
   - No dependencies on other layers
   - Provides base classes and utilities

5. **Engines Layer** (`engines/`)
   - Runtime execution logic
   - Detection algorithms and processing
   - Depends on `core/` and `domain/`

6. **ML Layer** (`ml/`)
   - Training and inference logic
   - Machine learning models
   - Can be merged with `engines/` if boundaries unclear

7. **Pipeline Layer** (`pipeline/`)
   - Processing orchestration
   - Coordinates multiple engines
   - Depends on `engines/` and `core/`

8. **API/Web Layer** (`api/`, `web/`)
   - Presentation layer only
   - Depends on `application/` and `domain/`
   - Handles HTTP requests and responses

### Single Execution Lifecycle

All initialization flows through `bootstrap/app.py`:

```python
from src.bootstrap.app import get_application

# Single entry point
app = get_application(config)
result = app.run(input_data)
```

**Initialization Order:**
1. Configuration (`config/`)
2. Database (`infrastructure/db.py`)
3. Domain models (`domain/models.py`)
4. Engines (`engines/`)
5. Pipeline (`pipeline/`)

### Import Validation

The `src/__init__.py` file enforces architecture boundaries:

```python
# Architecture enforcement at import time
def validate_architecture():
    """Enforce architecture boundaries."""
    # Validates import restrictions
    # Prevents domain from importing infrastructure
    # Ensures single execution lifecycle
```

## External Tools (`tools/`)

All external tools and large systems are consolidated in `tools/`:

```
tools/
├── BPlag/              # BPlag plagiarism detector
├── Deckard/            # Deckard clone detector
├── dolos/              # Dolos plagiarism detector
├── evalforge/          # Evaluation framework (moved from src/)
├── experiments/        # Research experiments (moved from src/)
├── gpu_service/        # GPU service (moved from src/)
├── JPlag/              # JPlag plagiarism detector
├── NiCad-6.2/          # NiCad clone detector
├── pmd/                # PMD static analysis
├── Sherlock/           # Sherlock plagiarism detector
├── sim/                # Sim tool
├── SourcererCC/        # SourcererCC clone detector
├── strange/            # Strange tool
├── web/                # Web interface (moved from src/)
└── workers/            # Background workers (moved from src/)
```

## Data Storage (`data/`)

The `data/` directory contains large dataset files that are not tracked in git:

```
data/
├── datasets/           # Actual dataset files
│   ├── bigclonebench/  # BigCloneBench dataset
│   ├── codesearchnet/  # CodeSearchNet dataset
│   ├── codexglue_clone/
│   ├── codexglue_defect/
│   ├── google_codejam/
│   ├── kaggle_student_code/
│   ├── poj104/
│   ├── synthetic/
│   ├── xiangtan/
│   ├── dataset_manifest.json # Dataset registry
│   ├── dataset_versions.lock # Version pinning
│   ├── download_external.sh # Download script
│   └── download_popular_datasets.sh # Popular datasets
├── raw/                # Raw unprocessed data
├── processed/          # Processed/cleaned data
├── benchmarks/         # Benchmark results
└── external/           # External data sources
```

## Configuration (`config/`)

```
config/
├── benchmark.yaml                    # Main benchmark config
├── benchmark_v2.yaml                 # Benchmark v2 config
├── benchmark_codeprovenance.yaml     # CodeProvenance benchmark
├── benchmark_codeprovenance_v2.yaml  # CodeProvenance v2 benchmark
├── benchmark_codeprovenance_v3.yaml  # CodeProvenance v3 benchmark
├── benchmark_codeprovenance_v4.yaml  # CodeProvenance v4 benchmark
├── benchmark_dolos.yaml              # Dolos benchmark
├── benchmark_jplag.yaml              # JPlag benchmark
├── benchmark_moss.yaml               # MOSS benchmark
├── benchmark_nicad.yaml              # NiCad benchmark
└── thresholds/                       # Threshold configurations
```

## Tests (`tests/`)

```
tests/
├── __init__.py
├── conftest.py         # Pytest configuration
├── test_auth.py        # Authentication tests
├── test_engine_registry.py # Engine registry tests
├── test_ir_layer.py    # IR layer tests
├── test_main.py        # Main application tests
├── benchmark_bigclonebench.py # BigCloneBench benchmark tests
├── benchmark_suite.py  # Benchmark suite tests
├── fixtures/           # Test fixtures
├── integration/        # Integration tests
└── unit/               # Unit tests
```

## Documentation (`docs/`)

```
docs/
├── ARCHITECTURE.md           # Architecture documentation
├── BENCHMARK_GUIDE.md        # Benchmark guide
├── BENCHMARK_SYSTEM.md       # Benchmark system documentation
├── BENCHMARK_RESULTS.md      # Benchmark results
├── DATABASE_DESIGN.md        # Database design
├── DEPLOYMENT.md             # Deployment guide
├── PRD.md                    # Product requirements
├── PROJECT_STRUCTURE.md      # This file
├── README.md                 # Documentation README
├── TESTING.md                # Testing guide
└── ...
```

## Key Design Principles

1. **Strict Architecture Enforcement:** Boundaries enforced in code, not just documentation
2. **Single Execution Lifecycle:** All initialization flows through `bootstrap/app.py`
3. **Clear Separation:** Source code, tools, configuration, and data are clearly separated
4. **Domain-Driven Design:** Business logic isolated from infrastructure
5. **Hexagonal Architecture:** Ports and adapters pattern for external systems

## Adding New Components

### Adding a New Engine

1. Create engine file in `src/engines/`
2. Register engine in `src/engines/registry.py`
3. Update configuration in `config/`

### Adding a New Tool

1. Create tool directory in `tools/`
2. Create adapter in `src/infrastructure/` (if needed)
3. Update configuration in `config/`

### Adding a New Dataset

1. Create loader in `src/benchmark/datasets/`
2. Add dataset files to `data/datasets/`
3. Update configuration in `config/`

## Quick Reference

| Component | Location | Purpose | Dependencies |
|-----------|----------|---------|--------------|
| Main Application | `src/bootstrap/app.py` | Application entry point | All layers |
| API Endpoints | `src/api/` | REST API | application, domain |
| Core Engines | `src/engines/` | Detection algorithms | core, domain |
| Benchmark System | `src/benchmark/` | Benchmark framework | evaluation, engines |
| External Tools | `tools/` | Third-party analysis tools | None |
| Configuration | `config/` | Configuration files | None |
| Data Storage | `data/` | Dataset files | None |
| Tests | `tests/` | Test files | All layers |
| Documentation | `docs/` | Documentation | None |

## Maintenance Notes

- **Architecture Enforcement:** Import restrictions are validated at runtime
- **Single Entry Point:** All code must flow through `bootstrap/app.py`
- **Domain Isolation:** Business logic cannot import infrastructure code
- **Git Ignore:** The `.gitignore` file excludes cache directories, virtual environments, and large data files
- **Virtual Environment:** `venv/` is not tracked in git
- **Data Files:** Large dataset files in `data/` are not tracked in git
- **Build Artifacts:** `artifacts/` and `reports/` are not tracked in git