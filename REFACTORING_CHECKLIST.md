# CodeProvenance Modular Refactoring - Detailed Checklist

## Pre-Migration Checklist

### Week 1: Planning & Preparation

#### Monday
- [ ] Review all refactoring documents
- [ ] Schedule team meeting to discuss refactoring
- [ ] Create feature branch: `git checkout -b refactor/modular-structure`
- [ ] Create backup of entire project
- [ ] Document current import patterns
- [ ] Identify all external references to src/ paths

#### Tuesday
- [ ] Update CI/CD configuration for new paths
- [ ] Review Docker configuration
- [ ] Check for hardcoded path strings
- [ ] Create migration guide for team
- [ ] Set up automated migration scripts
- [ ] Test migration scripts on copy of project

#### Wednesday
- [ ] Review all test files for import patterns
- [ ] Check for relative imports that need updating
- [ ] Document any special import handling
- [ ] Create import update script
- [ ] Test import update script
- [ ] Prepare rollback procedures

#### Thursday
- [ ] Team training on new structure
- [ ] Q&A session with team
- [ ] Finalize migration plan
- [ ] Assign responsibilities
- [ ] Set up monitoring for migration

#### Friday
- [ ] Final review of all documents
- [ ] Verify all scripts work correctly
- [ ] Backup project one more time
- [ ] Prepare for Monday migration start
- [ ] Communicate timeline to stakeholders

---

## Migration Execution Checklist

### Phase 1: Directory Structure Creation

#### Step 1.1: Create Backend Directory
- [ ] Create `src/backend/` directory
- [ ] Create `src/backend/__init__.py`
- [ ] Verify directory created successfully

#### Step 1.2: Create Backend Subdirectories
- [ ] Create `src/backend/api/`
- [ ] Create `src/backend/application/`
- [ ] Create `src/backend/benchmark/`
- [ ] Create `src/backend/bootstrap/`
- [ ] Create `src/backend/cli/`
- [ ] Create `src/backend/config/`
- [ ] Create `src/backend/contracts/`
- [ ] Create `src/backend/core/`
- [ ] Create `src/backend/domain/`
- [ ] Create `src/backend/engines/`
- [ ] Create `src/backend/evalforge/`
- [ ] Create `src/backend/evaluation/`
- [ ] Create `src/backend/infrastructure/`
- [ ] Create `src/backend/integrations/`
- [ ] Create `src/backend/ml/`
- [ ] Create `src/backend/models/`
- [ ] Create `src/backend/pipeline/`
- [ ] Create `src/backend/plugins/`
- [ ] Create `src/backend/services/`
- [ ] Create `src/backend/utils/`
- [ ] Create `src/backend/workers/`

#### Step 1.3: Create Frontend Directory
- [ ] Create `src/frontend/` directory
- [ ] Create `src/frontend/__init__.py`
- [ ] Create `src/frontend/shared/` directory
- [ ] Create `src/frontend/shared/__init__.py`
- [ ] Create `src/frontend/shared/hooks/`
- [ ] Create `src/frontend/shared/utils/`
- [ ] Create `src/frontend/shared/types/`

#### Step 1.4: Verify Structure
- [ ] Run: `find src/backend -type d | head -20`
- [ ] Run: `find src/frontend -type d`
- [ ] Verify all directories exist
- [ ] Verify all __init__.py files exist

---

### Phase 2: Backend File Migration

#### Step 2.1: Move Core Modules
- [ ] Move `src/api/` → `src/backend/api/`
  - [ ] Verify all files moved
  - [ ] Check for __init__.py
  - [ ] Verify no files left behind
- [ ] Move `src/application/` → `src/backend/application/`
  - [ ] Verify all files moved
  - [ ] Check for __init__.py
  - [ ] Verify no files left behind
- [ ] Move `src/domain/` → `src/backend/domain/`
  - [ ] Verify all files moved
  - [ ] Check for __init__.py
  - [ ] Verify no files left behind
- [ ] Move `src/core/` → `src/backend/core/`
  - [ ] Verify all files moved
  - [ ] Check for __init__.py
  - [ ] Verify no files left behind
- [ ] Move `src/engines/` → `src/backend/engines/`
  - [ ] Verify all files moved
  - [ ] Check for __init__.py
  - [ ] Verify no files left behind
- [ ] Move `src/infrastructure/` → `src/backend/infrastructure/`
  - [ ] Verify all files moved
  - [ ] Check for __init__.py
  - [ ] Verify no files left behind

#### Step 2.2: Move Supporting Modules
- [ ] Move `src/evaluation/` → `src/backend/evaluation/`
- [ ] Move `src/benchmark/` → `src/backend/benchmark/`
- [ ] Move `src/ml/` → `src/backend/ml/`
- [ ] Move `src/evalforge/` → `src/backend/evalforge/`
- [ ] Move `src/pipeline/` → `src/backend/pipeline/`

#### Step 2.3: Move Infrastructure & Configuration
- [ ] Move `src/config/` → `src/backend/config/`
- [ ] Move `src/bootstrap/` → `src/backend/bootstrap/`
- [ ] Move `src/models/` → `src/backend/models/`
- [ ] Move `src/contracts/` → `src/backend/contracts/`

#### Step 2.4: Move Utilities & Services
- [ ] Move `src/cli/` → `src/backend/cli/`
- [ ] Move `src/workers/` → `src/backend/workers/`
- [ ] Move `src/services/` → `src/backend/services/`
- [ ] Move `src/integrations/` → `src/backend/integrations/`
- [ ] Move `src/plugins/` → `src/backend/plugins/`
- [ ] Move `src/utils/` → `src/backend/utils/`

#### Step 2.5: Move Entry Points
- [ ] Move `src/main.py` → `src/backend/main.py`
- [ ] Move `src/architecture.py` → `src/backend/architecture.py`
- [ ] Move `src/__init__.py` → `src/backend/__init__.py`

#### Step 2.6: Verify All Files Moved
- [ ] Run: `ls -la src/backend/ | wc -l` (should be 20+)
- [ ] Run: `find src/backend -name "*.py" | wc -l` (should be 200+)
- [ ] Verify no Python files left in `src/` root
- [ ] Check for any missed directories

---

### Phase 3: Frontend File Migration

#### Step 3.1: Move Dashboard UI
- [ ] Move `src/web/dashboard-ui/` → `src/frontend/dashboard/`
  - [ ] Verify all files moved
  - [ ] Check package.json exists
  - [ ] Check node_modules moved
  - [ ] Verify no files left behind
- [ ] Remove `src/web/` directory
  - [ ] Verify it's empty
  - [ ] Delete directory

#### Step 3.2: Verify Frontend Structure
- [ ] Run: `ls -la src/frontend/dashboard/`
- [ ] Verify package.json exists
- [ ] Verify app/ directory exists
- [ ] Verify components/ directory exists
- [ ] Verify tsconfig.json exists

---

### Phase 4: Import Updates

#### Step 4.1: Update Python Imports in Backend
- [ ] Run import update script: `python update_imports.py`
- [ ] Verify script completed successfully
- [ ] Check for any errors in output
- [ ] Spot-check updated files

#### Step 4.2: Manual Import Verification
- [ ] Check `src/backend/main.py` imports
- [ ] Check `src/backend/bootstrap/app.py` imports
- [ ] Check `src/backend/cli/main.py` imports
- [ ] Check `src/backend/api/server.py` imports
- [ ] Check `src/backend/application/services/` imports

#### Step 4.3: Update Configuration Files
- [ ] Update `pyproject.toml`
  - [ ] Update package paths
  - [ ] Update pytest configuration
  - [ ] Verify syntax
- [ ] Update `pytest.ini`
  - [ ] Update pythonpath
  - [ ] Update testpaths
  - [ ] Verify syntax
- [ ] Update `alembic.ini`
  - [ ] Update script_location
  - [ ] Update sqlalchemy.url if needed
  - [ ] Verify syntax
- [ ] Update `.env` (if path references exist)
  - [ ] Check for any path references
  - [ ] Update if necessary

#### Step 4.4: Update Docker Configuration
- [ ] Update `Dockerfile`
  - [ ] Update WORKDIR
  - [ ] Update COPY commands
  - [ ] Update CMD
  - [ ] Verify syntax
- [ ] Update `docker-compose.yml`
  - [ ] Update volume mounts
  - [ ] Update working_dir
  - [ ] Update command
  - [ ] Verify syntax

#### Step 4.5: Update Test Files
- [ ] Update `tests/conftest.py`
  - [ ] Update sys.path configuration
  - [ ] Verify backend path is correct
  - [ ] Test import works
- [ ] Update all test files
  - [ ] Run: `grep -r "from src\." tests/ | grep -v "from src.backend"`
  - [ ] Update any old imports found
  - [ ] Verify all imports updated

#### Step 4.6: Update Scripts
- [ ] Update `scripts/` files
  - [ ] Check for Python imports
  - [ ] Update any old imports
  - [ ] Check for path references
  - [ ] Update if necessary
- [ ] Update shell scripts
  - [ ] Check for path references
  - [ ] Update if necessary

#### Step 4.7: Verify All Imports Updated
- [ ] Run: `grep -r "from src\." --include="*.py" src/backend/ | grep -v "from src.backend" | wc -l`
  - [ ] Should return 0
- [ ] Run: `grep -r "^import src\." --include="*.py" src/backend/ | grep -v "^import src.backend" | wc -l`
  - [ ] Should return 0
- [ ] Run: `grep -r '"src/' --include="*.py" src/backend/ | grep -v '"src/backend' | wc -l`
  - [ ] Should return 0 (or acceptable number)

---

### Phase 5: Validation & Testing

#### Step 5.1: Syntax & Linting
- [ ] Run: `python -m py_compile src/backend/`
  - [ ] Should complete without errors
- [ ] Run: `ruff check src/backend/`
  - [ ] Fix any issues found
- [ ] Run: `black --check src/backend/`
  - [ ] Format if needed: `black src/backend/`

#### Step 5.2: Import Testing
- [ ] Run: `python -c "import src.backend"`
  - [ ] Should complete without errors
- [ ] Run: `python -c "from src.backend.api import server"`
  - [ ] Should complete without errors
- [ ] Run: `python -c "from src.backend.engines import PlagiarismEngine"`
  - [ ] Should complete without errors
- [ ] Run: `python -c "from src.backend.infrastructure import Database"`
  - [ ] Should complete without errors

#### Step 5.3: Unit Tests
- [ ] Run: `pytest tests/unit/ -v`
  - [ ] All tests should pass
  - [ ] Check for any import errors
  - [ ] Fix any failing tests
- [ ] Run: `pytest tests/unit/ --tb=short`
  - [ ] Review any failures
  - [ ] Fix issues

#### Step 5.4: Integration Tests
- [ ] Run: `pytest tests/integration/ -v`
  - [ ] All tests should pass
  - [ ] Check for any import errors
  - [ ] Fix any failing tests

#### Step 5.5: Benchmark Tests
- [ ] Run: `pytest tests/benchmark_suite.py -v`
  - [ ] All tests should pass
  - [ ] Check for any import errors

#### Step 5.6: Application Startup
- [ ] Run: `python -m src.backend.main`
  - [ ] Application should start without errors
  - [ ] Check for any import errors
  - [ ] Verify API is accessible
  - [ ] Stop application (Ctrl+C)

#### Step 5.7: CLI Testing
- [ ] Run: `python -m src.backend.cli --help`
  - [ ] Should display help without errors
- [ ] Run: `python -m src.backend.cli --version`
  - [ ] Should display version without errors

#### Step 5.8: Docker Build
- [ ] Run: `docker build -t codeprovenance:test .`
  - [ ] Build should complete successfully
  - [ ] Check for any errors
- [ ] Run: `docker-compose build`
  - [ ] Build should complete successfully
  - [ ] Check for any errors

#### Step 5.9: Docker Run
- [ ] Run: `docker-compose up -d`
  - [ ] Services should start successfully
- [ ] Check logs: `docker-compose logs -f`
  - [ ] No errors in logs
- [ ] Test API: `curl http://localhost:8000/health`
  - [ ] Should return 200 OK
- [ ] Stop services: `docker-compose down`

---

### Phase 6: Documentation Updates

#### Step 6.1: Update README
- [ ] Update project structure section
- [ ] Update running instructions
- [ ] Update import examples
- [ ] Verify all paths are correct
- [ ] Test all commands in README

#### Step 6.2: Update Architecture Documentation
- [ ] Update `docs/ARCHITECTURE.md`
  - [ ] Update directory structure
  - [ ] Update module descriptions
  - [ ] Update import examples
- [ ] Update `docs/PROJECT_STRUCTURE.md`
  - [ ] Update all paths
  - [ ] Update descriptions
  - [ ] Verify accuracy

#### Step 6.3: Update Code Comments
- [ ] Search for old path references in comments
- [ ] Run: `grep -r "src/" --include="*.py" src/backend/ | grep "#"`
- [ ] Update any comments with old paths

#### Step 6.4: Update Configuration Documentation
- [ ] Update `.codex/project-context.md`
  - [ ] Update project structure
  - [ ] Update import patterns
- [ ] Update `.kilo/` configuration if needed

#### Step 6.5: Create Migration Summary
- [ ] Document what was changed
- [ ] Document any issues encountered
- [ ] Document solutions applied
- [ ] Create lessons learned document

---

### Phase 7: Cleanup & Verification

#### Step 7.1: Remove Old Directories
- [ ] Verify all files moved from `src/api/`
- [ ] Remove `src/api/` directory
- [ ] Verify all files moved from `src/application/`
- [ ] Remove `src/application/` directory
- [ ] Repeat for all 20+ modules
- [ ] Verify `src/` only contains `backend/`, `frontend/`, and `__init__.py`

#### Step 7.2: Final Verification
- [ ] Run: `ls -la src/`
  - [ ] Should only show: backend/, frontend/, __init__.py
- [ ] Run: `find src -maxdepth 1 -type d`
  - [ ] Should only show: backend, frontend
- [ ] Run: `find src -maxdepth 1 -name "*.py"`
  - [ ] Should only show: __init__.py

#### Step 7.3: Git Status Check
- [ ] Run: `git status`
  - [ ] Review all changes
  - [ ] Verify no unexpected changes
- [ ] Run: `git diff --stat`
  - [ ] Review file changes
  - [ ] Verify all expected files changed

#### Step 7.4: Commit Changes
- [ ] Stage all changes: `git add .`
- [ ] Commit with message: `git commit -m "refactor: reorganize to modular backend/frontend structure"`
- [ ] Verify commit: `git log -1`

---

### Phase 8: Post-Migration

#### Step 8.1: Update CI/CD Pipelines
- [ ] Update `.github/workflows/test.yml`
  - [ ] Update working directory if needed
  - [ ] Update test commands
  - [ ] Verify syntax
- [ ] Update `.github/workflows/lint.yml`
  - [ ] Update lint paths
  - [ ] Verify syntax
- [ ] Update `.github/workflows/build.yml`
  - [ ] Update build commands
  - [ ] Verify syntax
- [ ] Test CI/CD by pushing to feature branch

#### Step 8.2: Update Deployment Scripts
- [ ] Update any deployment scripts
  - [ ] Check for path references
  - [ ] Update if necessary
- [ ] Update any automation scripts
  - [ ] Check for path references
  - [ ] Update if necessary

#### Step 8.3: Team Communication
- [ ] Notify team of completion
- [ ] Share migration summary
- [ ] Provide training on new structure
- [ ] Answer questions
- [ ] Gather feedback

#### Step 8.4: Monitor for Issues
- [ ] Watch for any runtime errors
- [ ] Monitor CI/CD pipelines
- [ ] Check application logs
- [ ] Be ready to fix any issues

#### Step 8.5: Create Pull Request
- [ ] Push feature branch: `git push origin refactor/modular-structure`
- [ ] Create pull request on GitHub
- [ ] Add description of changes
- [ ] Request code review
- [ ] Address review comments
- [ ] Merge PR after approval

#### Step 8.6: Post-Merge Verification
- [ ] Verify main branch builds successfully
- [ ] Verify all tests pass on main
- [ ] Verify Docker builds on main
- [ ] Verify deployment works
- [ ] Monitor production for issues

---

## Rollback Checklist

If issues arise and rollback is needed:

### Immediate Rollback
- [ ] Stop any running processes
- [ ] Run: `git checkout main`
- [ ] Run: `git branch -D refactor/modular-structure`
- [ ] Verify old structure is restored
- [ ] Run tests to verify everything works

### Partial Rollback
- [ ] Identify which modules have issues
- [ ] Revert specific file moves
- [ ] Keep working modules in new structure
- [ ] Update imports for working modules
- [ ] Test thoroughly

### Post-Rollback Analysis
- [ ] Document what went wrong
- [ ] Identify root causes
- [ ] Plan fixes
- [ ] Schedule retry

---

## Success Verification Checklist

After migration is complete, verify:

- [ ] All files successfully moved to new locations
- [ ] All imports updated and working
- [ ] All unit tests passing
- [ ] All integration tests passing
- [ ] All benchmark tests passing
- [ ] Application starts without errors
- [ ] CLI commands work correctly
- [ ] Docker builds successfully
- [ ] Docker containers run successfully
- [ ] API endpoints respond correctly
- [ ] No performance degradation
- [ ] Documentation updated
- [ ] Team trained on new structure
- [ ] CI/CD pipelines working
- [ ] Zero production issues
- [ ] Team feedback positive

---

## Timeline Tracking

### Week 1: Planning
- [ ] Monday: Review & Planning
- [ ] Tuesday: Preparation
- [ ] Wednesday: Documentation
- [ ] Thursday: Training
- [ ] Friday: Final Review

### Week 2: Execution
- [ ] Monday: Directory Creation & File Migration
- [ ] Tuesday: Import Updates
- [ ] Wednesday: Testing & Validation
- [ ] Thursday: Documentation & Cleanup
- [ ] Friday: Post-Migration & Verification

### Week 3: Monitoring
- [ ] Monitor for issues
- [ ] Fix any problems
- [ ] Gather team feedback
- [ ] Document lessons learned

---

## Notes & Issues Log

### Issues Encountered
- [ ] Issue 1: _______________
  - [ ] Solution: _______________
  - [ ] Status: _______________
- [ ] Issue 2: _______________
  - [ ] Solution: _______________
  - [ ] Status: _______________

### Lessons Learned
- [ ] Lesson 1: _______________
- [ ] Lesson 2: _______________
- [ ] Lesson 3: _______________

### Improvements for Next Time
- [ ] Improvement 1: _______________
- [ ] Improvement 2: _______________
- [ ] Improvement 3: _______________

---

## Sign-Off

- [ ] Project Manager: _____________ Date: _______
- [ ] Tech Lead: _____________ Date: _______
- [ ] QA Lead: _____________ Date: _______
- [ ] DevOps Lead: _____________ Date: _______

---

**Checklist Version**: 1.0
**Last Updated**: 2024
**Status**: Ready for Use

