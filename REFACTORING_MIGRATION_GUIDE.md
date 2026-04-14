# CodeProvenance Modular Refactoring - Team Migration Guide

## Overview

This guide helps team members understand and work with the new modular project structure after the refactoring from monolithic `src/` to `src/backend` and `src/frontend`.

---

## What Changed?

### Before (Monolithic)
```
src/
├── api/
├── application/
├── engines/
├── infrastructure/
├── evaluation/
├── benchmark/
├── web/
│   └── dashboard-ui/
└── [20+ other directories]
```

### After (Modular)
```
src/
├── backend/                    # All Python backend code
│   ├── api/
│   ├── application/
│   ├── engines/
│   ├── infrastructure/
│   ├── evaluation/
│   ├── benchmark/
│   └── [all other backend modules]
│
└── frontend/                   # All frontend code
    ├── dashboard/              # Moved from src/web/dashboard-ui
    └── shared/                 # Shared frontend utilities
```

---

## Key Changes for Developers

### 1. Import Statements

**All Python imports must be updated:**

```python
# OLD
from src.api import routes
from src.engines import PlagiarismEngine
from src.infrastructure import Database

# NEW
from src.backend.api import routes
from src.backend.engines import PlagiarismEngine
from src.backend.infrastructure import Database
```

### 2. File Locations

All backend Python files are now under `src/backend/`:

| What | Old Location | New Location |
|---|---|---|
| API routes | `src/api/routes/` | `src/backend/api/routes/` |
| Services | `src/application/services/` | `src/backend/application/services/` |
| Engines | `src/engines/` | `src/backend/engines/` |
| Database | `src/infrastructure/db.py` | `src/backend/infrastructure/db.py` |
| Dashboard UI | `src/web/dashboard-ui/` | `src/frontend/dashboard/` |

### 3. Running the Application

```bash
# OLD
python -m src.main

# NEW
python -m src.backend.main
```

### 4. Running Tests

```bash
# Tests still run the same way
pytest tests/ -v

# But conftest.py now handles the new path structure
```

### 5. CLI Commands

```bash
# OLD
python -m src.cli --help

# NEW
python -m src.backend.cli --help
```

---

## Common Tasks

### Task 1: Adding a New Backend Module

1. Create the module under `src/backend/`:
   ```bash
   mkdir -p src/backend/my_module
   touch src/backend/my_module/__init__.py
   ```

2. Import it correctly:
   ```python
   from src.backend.my_module import MyClass
   ```

3. Update tests:
   ```python
   from src.backend.my_module import MyClass
   ```

### Task 2: Modifying an Existing Module

1. Find the module in `src/backend/`:
   ```bash
   # Example: Find the API routes
   ls src/backend/api/routes/
   ```

2. Update imports in the file:
   ```python
   # Update any imports to use src.backend
   from src.backend.infrastructure import Database
   ```

3. Update any files that import from this module:
   ```python
   # Update the import path
   from src.backend.api.routes import health_routes
   ```

### Task 3: Adding a New Test

1. Create test file in `tests/`:
   ```bash
   touch tests/unit/test_my_feature.py
   ```

2. Import from backend:
   ```python
   from src.backend.my_module import MyClass
   
   def test_my_feature():
       obj = MyClass()
       assert obj.method() == expected_value
   ```

3. Run the test:
   ```bash
   pytest tests/unit/test_my_feature.py -v
   ```

### Task 4: Working with Frontend

1. Frontend code is now in `src/frontend/dashboard/`:
   ```bash
   cd src/frontend/dashboard
   npm install
   npm run dev
   ```

2. Frontend imports remain the same (TypeScript/JavaScript):
   ```typescript
   import { Component } from '@/components'
   ```

### Task 5: Updating Configuration

1. Configuration files are in `src/backend/config/`:
   ```bash
   # Settings
   src/backend/config/settings.py
   
   # Database config
   src/backend/config/database.py
   ```

2. Import configuration:
   ```python
   from src.backend.config import Settings
   ```

---

## IDE Setup

### VS Code

1. Update Python path in `.vscode/settings.json`:
   ```json
   {
     "python.linting.enabled": true,
     "python.linting.pylintEnabled": true,
     "python.linting.pylintPath": "${workspaceFolder}/venv/bin/pylint",
     "python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python",
     "python.analysis.extraPaths": ["${workspaceFolder}/src/backend"]
   }
   ```

2. Update import resolution:
   ```json
   {
     "python.analysis.typeCheckingMode": "basic",
     "python.analysis.extraPaths": ["${workspaceFolder}/src/backend"]
   }
   ```

### PyCharm

1. Mark `src/backend` as Sources Root:
   - Right-click `src/backend` → Mark Directory as → Sources Root

2. Configure Python interpreter:
   - Settings → Project → Python Interpreter
   - Select the virtual environment

### Vim/Neovim

1. Update LSP configuration to include `src/backend` in path
2. Configure Pylance or Pyright to recognize the new structure

---

## Debugging

### Issue: "ModuleNotFoundError: No module named 'src.backend'"

**Solution**: Ensure you're running from the project root:
```bash
# Correct
python -m src.backend.main

# Wrong (from src/ directory)
cd src
python -m backend.main  # This won't work
```

### Issue: Import errors in IDE

**Solution**: 
1. Restart the IDE
2. Verify Python interpreter is set correctly
3. Check that `src/backend/__init__.py` exists
4. Verify PYTHONPATH includes `src/backend`

### Issue: Tests can't find modules

**Solution**: Check `tests/conftest.py` has correct path setup:
```python
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent / "src" / "backend"
sys.path.insert(0, str(backend_path))
```

---

## Git Workflow

### Creating a Feature Branch

```bash
# Create feature branch
git checkout -b feature/my-feature

# Make changes (imports already updated in new structure)
# Commit changes
git add .
git commit -m "feat: add my feature"

# Push to remote
git push origin feature/my-feature
```

### Handling Merge Conflicts

If you have merge conflicts with import statements:

```python
# If you see both old and new imports, keep only new:
# <<<<<<< HEAD
# from src.backend.module import Class
# =======
# from src.module import Class
# >>>>>>> main

# Keep this:
from src.backend.module import Class
```

### Rebasing on Main

```bash
# Fetch latest
git fetch origin

# Rebase on main
git rebase origin/main

# If conflicts occur, resolve them and continue
git rebase --continue
```

---

## Documentation Updates

### Updating README

If you update README.md, ensure it reflects new structure:

```markdown
## Running the Application

### Backend
```bash
python -m src.backend.main
```

### Frontend
```bash
cd src/frontend/dashboard
npm run dev
```
```

### Updating Code Comments

Update any code comments that reference old paths:

```python
# OLD
# See src/engines/plagiarism_engine.py for details

# NEW
# See src/backend/engines/plagiarism_engine.py for details
```

---

## Performance Considerations

The new structure has no performance impact:
- Same Python modules, just reorganized
- Same import resolution time
- Same runtime performance

---

## Troubleshooting

### Problem: "Cannot find module" in tests

**Check**:
1. Is `tests/conftest.py` configured correctly?
2. Is the module in `src/backend/`?
3. Are imports using `src.backend.`?

**Fix**:
```bash
# Verify module exists
ls src/backend/my_module/

# Run test with verbose output
pytest tests/unit/test_file.py -vv

# Check Python path
python -c "import sys; print(sys.path)"
```

### Problem: IDE can't find imports

**Check**:
1. Is Python interpreter set to project venv?
2. Is `src/backend` marked as source root?
3. Do you need to restart IDE?

**Fix**:
```bash
# Restart IDE
# Verify interpreter: which python
# Verify path: python -c "import src.backend"
```

### Problem: Docker build fails

**Check**:
1. Is Dockerfile updated with new paths?
2. Are volume mounts correct in docker-compose.yml?
3. Is working directory correct?

**Fix**:
```dockerfile
# Dockerfile should have:
WORKDIR /app
COPY . .
CMD ["python", "-m", "src.backend.main"]
```

---

## Quick Reference

### Common Commands

```bash
# Run backend
python -m src.backend.main

# Run CLI
python -m src.backend.cli --help

# Run tests
pytest tests/ -v

# Run specific test
pytest tests/unit/test_file.py::test_function -v

# Lint backend
ruff check src/backend/

# Format backend
black src/backend/

# Run frontend dev server
cd src/frontend/dashboard && npm run dev

# Build frontend
cd src/frontend/dashboard && npm run build
```

### Directory Quick Links

```
Backend Entry Points:
- src/backend/main.py          # Application entry
- src/backend/cli/main.py      # CLI entry
- src/backend/bootstrap/app.py # App initialization

Frontend Entry Points:
- src/frontend/dashboard/app/  # Next.js app directory
- src/frontend/dashboard/package.json

Configuration:
- src/backend/config/settings.py
- src/backend/config/database.py

Tests:
- tests/unit/
- tests/integration/
- tests/conftest.py
```

---

## Getting Help

### Resources

1. **Refactoring Plan**: `REFACTORING_PLAN_MODULAR.md`
2. **Import Mapping**: `REFACTORING_IMPORT_MAPPING.md`
3. **Architecture**: `docs/ARCHITECTURE.md`
4. **Project Structure**: `docs/PROJECT_STRUCTURE.md`

### Asking Questions

When asking for help, include:
1. What you're trying to do
2. The error message (full traceback)
3. The file path you're working in
4. The import statement you're using

Example:
```
I'm trying to import the PlagiarismEngine in tests/unit/test_detection.py
Error: ModuleNotFoundError: No module named 'src.backend.engines'
Import: from src.backend.engines import PlagiarismEngine
```

---

## Checklist for New Team Members

- [ ] Clone the repository
- [ ] Create virtual environment: `python -m venv venv`
- [ ] Activate venv: `source venv/bin/activate` (or `venv\Scripts\activate` on Windows)
- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Verify backend runs: `python -m src.backend.main`
- [ ] Run tests: `pytest tests/ -v`
- [ ] Read `REFACTORING_PLAN_MODULAR.md`
- [ ] Read `REFACTORING_IMPORT_MAPPING.md`
- [ ] Set up IDE with correct Python path
- [ ] Create a test branch and make a small change to verify workflow

---

## FAQ

**Q: Do I need to update all my old code?**
A: Yes, all imports must use `src.backend.` for the code to work.

**Q: Can I still use relative imports?**
A: It's better to use absolute imports (`from src.backend.module import X`) for clarity.

**Q: Does this affect the database?**
A: No, the database schema and migrations remain unchanged.

**Q: Do I need to reinstall dependencies?**
A: No, the dependencies are the same. Just ensure you're using the correct Python path.

**Q: How do I run the frontend?**
A: `cd src/frontend/dashboard && npm run dev`

**Q: What if I find a file in the old location?**
A: Report it! It means the migration wasn't complete. Check if it needs to be moved to `src/backend/`.

**Q: Can I revert to the old structure?**
A: Yes, but it's not recommended. The new structure is better organized. If you need to revert, use git: `git checkout <old-commit>`

---

## Feedback

If you have suggestions for improving this guide or the new structure, please:
1. Create an issue in the repository
2. Discuss with the team
3. Document the change

---

## Summary

The new modular structure improves code organization and maintainability. Key points:

✓ All backend code is in `src/backend/`
✓ All frontend code is in `src/frontend/`
✓ All imports use `src.backend.` prefix
✓ Tests and configuration are updated
✓ No functional changes, just reorganization

Welcome to the new structure! 🎉

