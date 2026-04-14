# CodeProvenance Modular Refactoring Plan

## Executive Summary

This document outlines a comprehensive plan to reorganize the CodeProvenance project from a monolithic `src/` structure to a modular `src/backend` and `src/frontend` architecture. This refactoring improves code organization, maintainability, and enables independent scaling of frontend and backend services.

---

## 1. Target Directory Structure

### New Project Layout

```
CodeProvenance/
├── src/
│   ├── backend/                          # All Python backend code
│   │   ├── __init__.py
│   │   ├── main.py                       # Backend entry point
│   │   │
│   │   ├── api/                          # REST API layer
│   │   │   ├── __init__.py
│   │   │   ├── server.py
│   │   │   ├── middleware/
│   │   │   ├── routes/
│   │   │   └── schemas/
│   │   │
│   │   ├── application/                  # Business logic & orchestration
│   │   │   ├── __init__.py
│   │   │   ├── services/
│   │   │   ├── use_cases/
│   │   │   └── pipeline/
│   │   │
│   │   ├── domain/                       # Domain models & entities
│   │   │   ├── __init__.py
│   │   │   ├── models.py
│   │   │   └── decision/
│   │   │
│   │   ├── engines/                      # Detection & analysis engines
│   │   │   ├── __init__.py
│   │   │   ├── base_engine.py
│   │   │   ├── base.py
│   │   │   ├── plagiarism_engine.py
│   │   │   ├── similarity/               # 6 similarity detection engines
│   │   │   ├── scoring/
│   │   │   ├── ml/
│   │   │   ├── ai/
│   │   │   ├── execution/
│   │   │   ├── features/
│   │   │   ├── registry/
│   │   │   └── [other engine files]
│   │   │
│   │   ├── core/                         # Core analysis components
│   │   │   ├── __init__.py
│   │   │   ├── analyzer/
│   │   │   ├── ir/
│   │   │   ├── processor/
│   │   │   ├── similarity/
│   │   │   ├── graph/
│   │   │   ├── token_heatmap/
│   │   │   └── decision.py
│   │   │
│   │   ├── infrastructure/               # Infrastructure & persistence
│   │   │   ├── __init__.py
│   │   │   ├── db.py
│   │   │   ├── database/
│   │   │   ├── reporting/
│   │   │   ├── indexing/
│   │   │   ├── parsing/
│   │   │   ├── gpu_service/
│   │   │   ├── report_generator.py
│   │   │   ├── report.py
│   │   │   ├── visual_report.py
│   │   │   ├── diff_generator.py
│   │   │   ├── email_service.py
│   │   │   ├── git_analysis.py
│   │   │   ├── ai_detection.py
│   │   │   └── vector.py
│   │   │
│   │   ├── evaluation/                   # Evaluation & benchmarking
│   │   │   ├── __init__.py
│   │   │   ├── core/
│   │   │   ├── analysis/
│   │   │   ├── dataset/
│   │   │   ├── lab/
│   │   │   ├── reporting/
│   │   │   ├── statistics/
│   │   │   ├── threshold/
│   │   │   ├── [evaluation files]
│   │   │   └── ieee_report_generator.py
│   │   │
│   │   ├── benchmark/                   # Benchmark system
│   │   │   ├── __init__.py
│   │   │   ├── __main__.py
│   │   │   ├── registry.py
│   │   │   ├── abstraction/
│   │   │   ├── adapters/
│   │   │   ├── certification/
│   │   │   ├── competitors/
│   │   │   ├── config/
│   │   │   ├── contracts/
│   │   │   ├── cross_dataset/
│   │   │   ├── datasets/
│   │   │   ├── evaluation/
│   │   │   ├── forensics/
│   │   │   ├── generators/
│   │   │   ├── metrics/
│   │   │   ├── normalizer/
│   │   │   ├── parsers/
│   │   │   ├── pipeline/
│   │   │   ├── reporting/
│   │   │   ├── runners/
│   │   │   ├── schemas/
│   │   │   └── similarity/
│   │   │
│   │   ├── ml/                          # Machine learning models
│   │   │   ├── __init__.py
│   │   │   ├── fusion_model.py
│   │   │   ├── models/
│   │   │   ├── training/
│   │   │   ├── datasets/
│   │   │   └── checkpoints/
│   │   │
│   │   ├── evalforge/                   # Evaluation framework
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   ├── core/
│   │   │   ├── detectors/
│   │   │   ├── metrics/
│   │   │   ├── orchestration/
│   │   │   ├── pipelines/
│   │   │   └── reporting/
│   │   │
│   │   ├── pipeline/                    # Data pipelines
│   │   │   ├── __init__.py
│   │   │   ├── scoring_pipeline.py
│   │   │   ├── train.py
│   │   │   └── dataset_builders/
│   │   │
│   │   ├── config/                      # Configuration management
│   │   │   ├── __init__.py
│   │   │   ├── settings.py
│   │   │   └── database.py
│   │   │
│   │   ├── bootstrap/                   # Application bootstrap
│   │   │   ├── __init__.py
│   │   │   ├── app.py
│   │   │   ├── container.py
│   │   │   ├── architecture_guard.py
│   │   │   ├── architecture_guard_full.py
│   │   │   └── plugins/
│   │   │
│   │   ├── cli/                         # CLI commands
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   ├── context.py
│   │   │   └── commands/
│   │   │
│   │   ├── workers/                     # Background workers
│   │   │   ├── __init__.py
│   │   │   ├── batch_processor.py
│   │   │   ├── gpu_server.py
│   │   │   ├── gpu_worker.py
│   │   │   └── webhook_worker.py
│   │   │
│   │   ├── services/                    # Shared services
│   │   │   ├── __init__.py
│   │   │   └── webhook_delivery.py
│   │   │
│   │   ├── integrations/                # External integrations
│   │   │   ├── __init__.py
│   │   │   └── ai_detection.py
│   │   │
│   │   ├── contracts/                   # Contracts & validation
│   │   │   ├── __init__.py
│   │   │   ├── registry.py
│   │   │   ├── reproducibility.py
│   │   │   ├── validation.py
│   │   │   └── versioning.py
│   │   │
│   │   ├── plugins/                     # Plugin system
│   │   │   ├── __init__.py
│   │   │   ├── jaccard_ngram.py
│   │   │   ├── lcs.py
│   │   │   └── levenshtein.py
│   │   │
│   │   └── utils/                       # Utility functions
│   │       ├── __init__.py
│   │       ├── database.py
│   │       ├── hash_utils.py
│   │       └── report.py
│   │
│   └── frontend/                         # Frontend application
│       ├── dashboard/                    # Dashboard UI (moved from src/web/dashboard-ui)
│       │   ├── app/
│       │   ├── components/
│       │   ├── package.json
│       │   ├── tsconfig.json
│       │   ├── next.config.ts
│       │   ├── tailwind.config.ts
│       │   ├── postcss.config.ts
│       │   ├── eslint.config.mjs
│       │   ├── jsconfig.json
│       │   └── [other Next.js files]
│       │
│       └── shared/                      # Shared frontend utilities (future)
│           ├── __init__.py
│           ├── hooks/
│           ├── utils/
│           └── types/
│
├── alembic/                             # Database migrations (unchanged)
├── bootstrap/                           # Root bootstrap (unchanged)
├── benchmark/                           # Root benchmark (unchanged)
├── data/                                # Data directory (unchanged)
├── datasets/                            # Datasets (unchanged)
├── docker/                              # Docker config (unchanged)
├── docs/                                # Documentation (unchanged)
├── scripts/                             # Scripts (unchanged)
├── tests/                               # Tests (unchanged - will be updated)
├── tools/                               # External tools (unchanged)
├── artifacts/                           # Artifacts (unchanged)
├── reports/                             # Reports (unchanged)
├── uploads/                             # Uploads (unchanged)
├── .codex/                              # Codex config (unchanged)
├── .kilo/                               # Kilo config (unchanged)
├── .vscode/                             # VS Code config (unchanged)
├── venv/                                # Virtual environment (unchanged)
├── alembic.ini                          # Alembic config (unchanged)
├── docker-compose.yml                   # Docker compose (unchanged)
├── Dockerfile                           # Dockerfile (unchanged)
├── requirements.txt                     # Requirements (unchanged)
├── requirements-gpu.txt                 # GPU requirements (unchanged)
├── requirements-gui.txt                 # GUI requirements (unchanged)
├── README.md                            # README (unchanged)
├── LICENSE                              # License (unchanged)
├── AGENTS.md                            # Agents config (unchanged)
└── [other root files]
```

---

## 2. File Movement Mapping

### Backend Files (src/ → src/backend/)

| Current Path | New Path | Category |
|---|---|---|
| src/api/ | src/backend/api/ | API Layer |
| src/application/ | src/backend/application/ | Business Logic |
| src/benchmark/ | src/backend/benchmark/ | Benchmarking |
| src/bootstrap/ | src/backend/bootstrap/ | Bootstrap |
| src/cli/ | src/backend/cli/ | CLI |
| src/config/ | src/backend/config/ | Configuration |
| src/contracts/ | src/backend/contracts/ | Contracts |
| src/core/ | src/backend/core/ | Core Analysis |
| src/domain/ | src/backend/domain/ | Domain Models |
| src/engines/ | src/backend/engines/ | Detection Engines |
| src/evalforge/ | src/backend/evalforge/ | Evaluation Framework |
| src/evaluation/ | src/backend/evaluation/ | Evaluation |
| src/infrastructure/ | src/backend/infrastructure/ | Infrastructure |
| src/integrations/ | src/backend/integrations/ | Integrations |
| src/ml/ | src/backend/ml/ | Machine Learning |
| src/models/ | src/backend/models/ | Models |
| src/pipeline/ | src/backend/pipeline/ | Pipelines |
| src/plugins/ | src/backend/plugins/ | Plugins |
| src/services/ | src/backend/services/ | Services |
| src/utils/ | src/backend/utils/ | Utilities |
| src/workers/ | src/backend/workers/ | Workers |
| src/__init__.py | src/backend/__init__.py | Init |
| src/architecture.py | src/backend/architecture.py | Architecture |
| src/main.py | src/backend/main.py | Entry Point |

### Frontend Files (src/web/ → src/frontend/)

| Current Path | New Path | Category |
|---|---|---|
| src/web/dashboard-ui/ | src/frontend/dashboard/ | Dashboard UI |

---

## 3. Import Path Mapping

### Python Imports (Backend)

| Old Import | New Import | Notes |
|---|---|---|
| `from src.api import ...` | `from src.backend.api import ...` | API routes |
| `from src.application import ...` | `from src.backend.application import ...` | Services |
| `from src.engines import ...` | `from src.backend.engines import ...` | Detection engines |
| `from src.infrastructure import ...` | `from src.backend.infrastructure import ...` | DB, reporting |
| `from src.evaluation import ...` | `from src.backend.evaluation import ...` | Evaluation |
| `from src.benchmark import ...` | `from src.backend.benchmark import ...` | Benchmarking |
| `from src.core import ...` | `from src.backend.core import ...` | Core analysis |
| `from src.domain import ...` | `from src.backend.domain import ...` | Domain models |
| `from src.ml import ...` | `from src.backend.ml import ...` | ML models |
| `from src.config import ...` | `from src.backend.config import ...` | Configuration |
| `from src.bootstrap import ...` | `from src.backend.bootstrap import ...` | Bootstrap |
| `from src.cli import ...` | `from src.backend.cli import ...` | CLI |
| `from src.workers import ...` | `from src.backend.workers import ...` | Workers |
| `from src.utils import ...` | `from src.backend.utils import ...` | Utilities |

### Python Path Configuration

Update `sys.path` in:
- `src/backend/main.py`
- `src/backend/bootstrap/app.py`
- `tests/conftest.py`
- Any entry points

Example:
```python
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))
```

### Configuration Files to Update

1. **pyproject.toml** - Update package paths
2. **pytest.ini** - Update test paths
3. **alembic.ini** - Update migration paths
4. **.env** - Update any path references
5. **docker-compose.yml** - Update volume mounts
6. **Dockerfile** - Update WORKDIR and COPY commands

---

## 4. Step-by-Step Migration Checklist

### Phase 1: Preparation (Pre-Migration)

- [ ] Create backup of entire project
- [ ] Create new git branch: `refactor/modular-structure`
- [ ] Review all imports in codebase
- [ ] Document all external references to src/ paths
- [ ] Update CI/CD configuration for new paths
- [ ] Create migration guide for team

### Phase 2: Directory Structure Creation

- [ ] Create `src/backend/` directory
- [ ] Create `src/frontend/` directory
- [ ] Create all subdirectories under `src/backend/`
- [ ] Create `src/backend/__init__.py`
- [ ] Create `src/frontend/__init__.py`
- [ ] Create `src/frontend/shared/` directory structure

### Phase 3: Backend Migration

#### Step 1: Move Core Backend Modules
- [ ] Move `src/api/` → `src/backend/api/`
- [ ] Move `src/application/` → `src/backend/application/`
- [ ] Move `src/domain/` → `src/backend/domain/`
- [ ] Move `src/core/` → `src/backend/core/`
- [ ] Move `src/engines/` → `src/backend/engines/`
- [ ] Move `src/infrastructure/` → `src/backend/infrastructure/`

#### Step 2: Move Supporting Modules
- [ ] Move `src/evaluation/` → `src/backend/evaluation/`
- [ ] Move `src/benchmark/` → `src/backend/benchmark/`
- [ ] Move `src/ml/` → `src/backend/ml/`
- [ ] Move `src/evalforge/` → `src/backend/evalforge/`
- [ ] Move `src/pipeline/` → `src/backend/pipeline/`

#### Step 3: Move Infrastructure & Configuration
- [ ] Move `src/config/` → `src/backend/config/`
- [ ] Move `src/bootstrap/` → `src/backend/bootstrap/`
- [ ] Move `src/models/` → `src/backend/models/`
- [ ] Move `src/contracts/` → `src/backend/contracts/`

#### Step 4: Move Utilities & Services
- [ ] Move `src/cli/` → `src/backend/cli/`
- [ ] Move `src/workers/` → `src/backend/workers/`
- [ ] Move `src/services/` → `src/backend/services/`
- [ ] Move `src/integrations/` → `src/backend/integrations/`
- [ ] Move `src/plugins/` → `src/backend/plugins/`
- [ ] Move `src/utils/` → `src/backend/utils/`

#### Step 5: Move Entry Points
- [ ] Move `src/main.py` → `src/backend/main.py`
- [ ] Move `src/architecture.py` → `src/backend/architecture.py`
- [ ] Move `src/__init__.py` → `src/backend/__init__.py`

### Phase 4: Frontend Migration

- [ ] Move `src/web/dashboard-ui/` → `src/frontend/dashboard/`
- [ ] Update Next.js configuration paths
- [ ] Update TypeScript paths in `tsconfig.json`
- [ ] Update import statements in frontend code
- [ ] Update API endpoint references (if hardcoded)

### Phase 5: Import Updates

#### Step 1: Update Python Imports
- [ ] Update all `from src.` imports to `from src.backend.`
- [ ] Update all `import src.` imports to `import src.backend.`
- [ ] Search for hardcoded path strings referencing `src/`
- [ ] Update relative imports in moved files

#### Step 2: Update Configuration Files
- [ ] Update `pyproject.toml` package configuration
- [ ] Update `pytest.ini` test paths
- [ ] Update `alembic.ini` migration paths
- [ ] Update `.env` file paths (if any)
- [ ] Update `docker-compose.yml` volume mounts
- [ ] Update `Dockerfile` WORKDIR and COPY commands

#### Step 3: Update Test Files
- [ ] Update `tests/conftest.py` sys.path configuration
- [ ] Update all test imports
- [ ] Update test fixture paths
- [ ] Update test data paths

#### Step 4: Update Scripts
- [ ] Update `scripts/` Python imports
- [ ] Update shell scripts with path references
- [ ] Update CI/CD workflow files

### Phase 6: Validation & Testing

- [ ] Run linter: `ruff check src/backend/`
- [ ] Run formatter: `black src/backend/`
- [ ] Run type checker: `mypy src/backend/` (if configured)
- [ ] Run unit tests: `pytest tests/unit/ -v`
- [ ] Run integration tests: `pytest tests/integration/ -v`
- [ ] Run benchmark tests: `pytest tests/benchmark_suite.py -v`
- [ ] Verify application startup: `python -m src.backend.main`
- [ ] Verify CLI works: `python -m src.backend.cli --help`
- [ ] Check for import errors: `python -c "import src.backend"`

### Phase 7: Documentation & Cleanup

- [ ] Update `README.md` with new structure
- [ ] Update `PROJECT_STRUCTURE.md`
- [ ] Update `docs/ARCHITECTURE.md`
- [ ] Create migration guide document
- [ ] Update `.codex/project-context.md`
- [ ] Remove old `src/` directories (after verification)
- [ ] Update `.gitignore` if needed
- [ ] Commit changes with message: `refactor: reorganize to modular backend/frontend structure`

### Phase 8: Post-Migration

- [ ] Update CI/CD pipelines
- [ ] Update Docker builds
- [ ] Update deployment scripts
- [ ] Notify team of changes
- [ ] Update IDE configurations
- [ ] Update any external documentation
- [ ] Monitor for any runtime issues
- [ ] Merge PR after review

---

## 5. Critical Files Requiring Special Attention

### Entry Points
- `src/backend/main.py` - Update sys.path
- `src/backend/bootstrap/app.py` - Update imports
- `src/backend/cli/main.py` - Update imports

### Configuration
- `src/backend/config/settings.py` - Verify path configurations
- `src/backend/config/database.py` - Verify database paths
- `alembic.ini` - Update sqlalchemy.url and script_location

### Tests
- `tests/conftest.py` - Update sys.path and imports
- `tests/test_*.py` - Update all imports
- `tests/fixtures/` - Verify fixture paths

### Docker
- `Dockerfile` - Update WORKDIR and COPY commands
- `docker-compose.yml` - Update volume mounts and working directories

### CI/CD
- `.github/workflows/*.yml` - Update working directories and commands
- `.kilo/command/*.md` - Update command paths

---

## 6. Potential Issues & Solutions

### Issue 1: Circular Imports
**Problem**: Moving modules might create circular import dependencies.
**Solution**: 
- Use lazy imports where necessary
- Refactor to break circular dependencies
- Use dependency injection

### Issue 2: Relative Imports Breaking
**Problem**: Relative imports like `from ..utils import X` may break.
**Solution**:
- Convert to absolute imports: `from src.backend.utils import X`
- Update all relative imports during migration

### Issue 3: Database Migrations
**Problem**: Alembic migrations reference old paths.
**Solution**:
- Update `alembic.ini` script_location
- Update migration file imports
- Test migrations thoroughly

### Issue 4: External Tool References
**Problem**: External tools or scripts reference old paths.
**Solution**:
- Update all external references
- Create compatibility layer if needed
- Document breaking changes

### Issue 5: Docker Build Issues
**Problem**: Docker builds fail due to path changes.
**Solution**:
- Update Dockerfile COPY and WORKDIR commands
- Update docker-compose volume mounts
- Test Docker builds locally

---

## 7. Rollback Plan

If issues arise during migration:

1. **Immediate Rollback**:
   ```bash
   git checkout main
   git branch -D refactor/modular-structure
   ```

2. **Partial Rollback**:
   - Revert specific file moves
   - Keep working modules in new structure
   - Gradually migrate remaining modules

3. **Testing Before Merge**:
   - Run full test suite
   - Manual testing of critical paths
   - Performance testing
   - Load testing if applicable

---

## 8. Timeline Estimate

| Phase | Duration | Notes |
|---|---|---|
| Preparation | 1-2 days | Planning, backup, documentation |
| Directory Creation | 0.5 days | Automated script can help |
| Backend Migration | 2-3 days | Largest phase, most files |
| Frontend Migration | 0.5 days | Smaller scope |
| Import Updates | 2-3 days | Most time-consuming |
| Validation & Testing | 1-2 days | Comprehensive testing |
| Documentation | 1 day | Update all docs |
| **Total** | **8-12 days** | Depends on team size & complexity |

---

## 9. Team Communication

### Pre-Migration
- Announce refactoring plan
- Share timeline and impact
- Gather feedback
- Create FAQ document

### During Migration
- Daily standup updates
- Communicate blockers
- Share progress
- Provide support

### Post-Migration
- Document lessons learned
- Update team on new structure
- Provide training if needed
- Gather feedback for improvements

---

## 10. Success Criteria

- [ ] All files successfully moved to new locations
- [ ] All imports updated and working
- [ ] All tests passing (unit, integration, benchmark)
- [ ] Application starts without errors
- [ ] CLI commands work correctly
- [ ] Docker builds successfully
- [ ] No performance degradation
- [ ] Documentation updated
- [ ] Team trained on new structure
- [ ] Zero production issues post-deployment

---

## Appendix A: Automated Migration Script

```bash
#!/bin/bash
# migrate_structure.sh - Automated migration script

set -e

echo "Starting CodeProvenance modular refactoring..."

# Create backend structure
mkdir -p src/backend/{api,application,benchmark,bootstrap,cli,config,contracts,core,domain,engines,evalforge,evaluation,infrastructure,integrations,ml,models,pipeline,plugins,services,utils,workers}

# Create frontend structure
mkdir -p src/frontend/shared/{hooks,utils,types}

# Move backend files
echo "Moving backend files..."
for dir in api application benchmark bootstrap cli config contracts core domain engines evalforge evaluation infrastructure integrations ml models pipeline plugins services utils workers; do
    if [ -d "src/$dir" ]; then
        mv "src/$dir" "src/backend/$dir"
        echo "✓ Moved src/$dir → src/backend/$dir"
    fi
done

# Move entry points
echo "Moving entry points..."
[ -f "src/main.py" ] && mv "src/main.py" "src/backend/main.py" && echo "✓ Moved main.py"
[ -f "src/architecture.py" ] && mv "src/architecture.py" "src/backend/architecture.py" && echo "✓ Moved architecture.py"
[ -f "src/__init__.py" ] && mv "src/__init__.py" "src/backend/__init__.py" && echo "✓ Moved __init__.py"

# Move frontend
echo "Moving frontend files..."
if [ -d "src/web/dashboard-ui" ]; then
    mkdir -p src/frontend
    mv "src/web/dashboard-ui" "src/frontend/dashboard"
    echo "✓ Moved src/web/dashboard-ui → src/frontend/dashboard"
    rmdir src/web 2>/dev/null || true
fi

# Create new __init__.py files
touch src/backend/__init__.py
touch src/frontend/__init__.py
touch src/frontend/shared/__init__.py

echo "✓ Migration structure complete!"
echo "Next steps:"
echo "1. Update all imports from 'src.' to 'src.backend.'"
echo "2. Update configuration files (pyproject.toml, pytest.ini, etc.)"
echo "3. Run tests to verify: pytest tests/ -v"
echo "4. Update documentation"
```

---

## Appendix B: Import Update Script

```python
#!/usr/bin/env python3
# update_imports.py - Update imports in Python files

import re
from pathlib import Path

def update_imports_in_file(filepath):
    """Update imports in a single file."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    original = content
    
    # Update from imports
    content = re.sub(
        r'from src\.(\w+)',
        r'from src.backend.\1',
        content
    )
    
    # Update import statements
    content = re.sub(
        r'import src\.(\w+)',
        r'import src.backend.\1',
        content
    )
    
    # Skip if no changes
    if content == original:
        return False
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    return True

def main():
    """Update all Python files."""
    updated = 0
    for py_file in Path('.').rglob('*.py'):
        # Skip venv and node_modules
        if 'venv' in py_file.parts or 'node_modules' in py_file.parts:
            continue
        
        if update_imports_in_file(py_file):
            print(f"✓ Updated {py_file}")
            updated += 1
    
    print(f"\nTotal files updated: {updated}")

if __name__ == '__main__':
    main()
```

---

## Appendix C: Verification Checklist

```bash
#!/bin/bash
# verify_migration.sh - Verify migration completeness

echo "Verifying CodeProvenance migration..."

# Check directory structure
echo "Checking directory structure..."
[ -d "src/backend" ] && echo "✓ src/backend exists" || echo "✗ src/backend missing"
[ -d "src/frontend" ] && echo "✓ src/frontend exists" || echo "✗ src/frontend missing"

# Check for old directories
echo "Checking for old directories..."
[ ! -d "src/api" ] && echo "✓ src/api removed" || echo "✗ src/api still exists"
[ ! -d "src/engines" ] && echo "✓ src/engines removed" || echo "✗ src/engines still exists"

# Check imports
echo "Checking for old imports..."
old_imports=$(grep -r "from src\." --include="*.py" src/backend/ | grep -v "from src.backend" | wc -l)
if [ "$old_imports" -eq 0 ]; then
    echo "✓ No old imports found"
else
    echo "✗ Found $old_imports old imports"
fi

# Run tests
echo "Running tests..."
python -m pytest tests/unit/ -q && echo "✓ Unit tests pass" || echo "✗ Unit tests fail"

# Check imports work
echo "Checking imports..."
python -c "from src.backend.api import server" && echo "✓ Backend imports work" || echo "✗ Backend imports fail"

echo "Verification complete!"
```

---

## Conclusion

This refactoring plan provides a comprehensive roadmap for reorganizing CodeProvenance into a modular backend/frontend structure. By following this plan systematically, the project will benefit from improved organization, easier maintenance, and better separation of concerns.

Key success factors:
- Thorough planning and preparation
- Systematic execution of migration phases
- Comprehensive testing at each step
- Clear communication with the team
- Proper documentation and rollback procedures

