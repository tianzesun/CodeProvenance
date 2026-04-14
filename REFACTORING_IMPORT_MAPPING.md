# CodeProvenance Import Mapping Reference

## Quick Reference: Old → New Import Paths

### API Layer
```python
# OLD
from src.api.server import app
from src.api.routes import health_routes
from src.api.middleware import auth_middleware
from src.api.schemas import DetectionRequest

# NEW
from src.backend.api.server import app
from src.backend.api.routes import health_routes
from src.backend.api.middleware import auth_middleware
from src.backend.api.schemas import DetectionRequest
```

### Application Services
```python
# OLD
from src.application.services import DetectionService
from src.application.use_cases import AnalyzeCodeUseCase
from src.application.pipeline import ProcessingPipeline

# NEW
from src.backend.application.services import DetectionService
from src.backend.application.use_cases import AnalyzeCodeUseCase
from src.backend.application.pipeline import ProcessingPipeline
```

### Domain Models
```python
# OLD
from src.domain.models import CodeFile, DetectionResult
from src.domain.decision import DecisionEngine

# NEW
from src.backend.domain.models import CodeFile, DetectionResult
from src.backend.domain.decision import DecisionEngine
```

### Detection Engines
```python
# OLD
from src.engines.similarity.ast_similarity import ASTSimilarity
from src.engines.similarity.token_similarity import TokenSimilarity
from src.engines.scoring import ScoringEngine
from src.engines.plagiarism_engine import PlagiarismEngine
from src.engines.registry import EngineRegistry

# NEW
from src.backend.engines.similarity.ast_similarity import ASTSimilarity
from src.backend.engines.similarity.token_similarity import TokenSimilarity
from src.backend.engines.scoring import ScoringEngine
from src.backend.engines.plagiarism_engine import PlagiarismEngine
from src.backend.engines.registry import EngineRegistry
```

### Core Analysis
```python
# OLD
from src.core.analyzer import CodeAnalyzer
from src.core.ir import IntermediateRepresentation
from src.core.processor import CodeProcessor
from src.core.similarity import SimilarityCalculator
from src.core.graph import DependencyGraph

# NEW
from src.backend.core.analyzer import CodeAnalyzer
from src.backend.core.ir import IntermediateRepresentation
from src.backend.core.processor import CodeProcessor
from src.backend.core.similarity import SimilarityCalculator
from src.backend.core.graph import DependencyGraph
```

### Infrastructure
```python
# OLD
from src.infrastructure.db import Database
from src.infrastructure.report_generator import ReportGenerator
from src.infrastructure.vector import VectorStore
from src.infrastructure.email_service import EmailService
from src.infrastructure.git_analysis import GitAnalyzer

# NEW
from src.backend.infrastructure.db import Database
from src.backend.infrastructure.report_generator import ReportGenerator
from src.backend.infrastructure.vector import VectorStore
from src.backend.infrastructure.email_service import EmailService
from src.backend.infrastructure.git_analysis import GitAnalyzer
```

### Evaluation & Benchmarking
```python
# OLD
from src.evaluation.core import EvaluationFramework
from src.evaluation.threshold import ThresholdAnalyzer
from src.benchmark.runners import BenchmarkRunner
from src.benchmark.metrics import MetricsCalculator

# NEW
from src.backend.evaluation.core import EvaluationFramework
from src.backend.evaluation.threshold import ThresholdAnalyzer
from src.backend.benchmark.runners import BenchmarkRunner
from src.backend.benchmark.metrics import MetricsCalculator
```

### Machine Learning
```python
# OLD
from src.ml.fusion_model import FusionModel
from src.ml.training import ModelTrainer
from src.evalforge.core import EvalForge

# NEW
from src.backend.ml.fusion_model import FusionModel
from src.backend.ml.training import ModelTrainer
from src.backend.evalforge.core import EvalForge
```

### Configuration & Bootstrap
```python
# OLD
from src.config.settings import Settings
from src.config.database import DatabaseConfig
from src.bootstrap.app import create_app
from src.bootstrap.container import Container

# NEW
from src.backend.config.settings import Settings
from src.backend.config.database import DatabaseConfig
from src.backend.bootstrap.app import create_app
from src.backend.bootstrap.container import Container
```

### CLI & Workers
```python
# OLD
from src.cli.main import cli
from src.cli.commands import analyze_command
from src.workers.batch_processor import BatchProcessor
from src.workers.gpu_worker import GPUWorker

# NEW
from src.backend.cli.main import cli
from src.backend.cli.commands import analyze_command
from src.backend.workers.batch_processor import BatchProcessor
from src.backend.workers.gpu_worker import GPUWorker
```

### Utilities & Services
```python
# OLD
from src.utils.database import get_db_session
from src.utils.hash_utils import compute_hash
from src.services.webhook_delivery import WebhookService
from src.integrations.ai_detection import AIDetector
from src.plugins.jaccard_ngram import JaccardNGram

# NEW
from src.backend.utils.database import get_db_session
from src.backend.utils.hash_utils import compute_hash
from src.backend.services.webhook_delivery import WebhookService
from src.backend.integrations.ai_detection import AIDetector
from src.backend.plugins.jaccard_ngram import JaccardNGram
```

### Models & Contracts
```python
# OLD
from src.models.database import User, DetectionJob
from src.contracts.registry import ContractRegistry
from src.contracts.validation import validate_contract

# NEW
from src.backend.models.database import User, DetectionJob
from src.backend.contracts.registry import ContractRegistry
from src.backend.contracts.validation import validate_contract
```

---

## Bulk Find & Replace Patterns

### For VS Code Find & Replace

**Pattern 1: from imports**
- Find: `from src\.(\w+)`
- Replace: `from src.backend.$1`
- Regex: ✓

**Pattern 2: import statements**
- Find: `import src\.(\w+)`
- Replace: `import src.backend.$1`
- Regex: ✓

**Pattern 3: String paths (if any)**
- Find: `"src/(\w+)/`
- Replace: `"src/backend/$1/`
- Regex: ✓

### For sed (Linux/Mac)

```bash
# Update from imports
find . -name "*.py" -type f ! -path "*/venv/*" ! -path "*/node_modules/*" \
  -exec sed -i 's/from src\.\([a-zA-Z_]*\)/from src.backend.\1/g' {} +

# Update import statements
find . -name "*.py" -type f ! -path "*/venv/*" ! -path "*/node_modules/*" \
  -exec sed -i 's/import src\.\([a-zA-Z_]*\)/import src.backend.\1/g' {} +

# Update string paths
find . -name "*.py" -type f ! -path "*/venv/*" ! -path "*/node_modules/*" \
  -exec sed -i 's/"src\/\([a-zA-Z_]*\)\//\"src\/backend\/\1\//g' {} +
```

### For PowerShell (Windows)

```powershell
# Update from imports
Get-ChildItem -Path . -Include "*.py" -Recurse -Exclude venv, node_modules | 
  ForEach-Object {
    (Get-Content $_) -replace 'from src\.(\w+)', 'from src.backend.$1' | 
    Set-Content $_
  }

# Update import statements
Get-ChildItem -Path . -Include "*.py" -Recurse -Exclude venv, node_modules | 
  ForEach-Object {
    (Get-Content $_) -replace 'import src\.(\w+)', 'import src.backend.$1' | 
    Set-Content $_
  }
```

---

## Files Requiring Manual Import Updates

### Critical Entry Points
1. **src/backend/main.py**
   - Update sys.path configuration
   - Update all imports

2. **src/backend/bootstrap/app.py**
   - Update app initialization imports
   - Update container setup

3. **src/backend/bootstrap/container.py**
   - Update dependency injection imports

4. **src/backend/cli/main.py**
   - Update CLI command imports

### Configuration Files
1. **pyproject.toml**
   ```toml
   [tool.pytest.ini_options]
   pythonpath = ["src/backend"]
   testpaths = ["tests"]
   ```

2. **pytest.ini**
   ```ini
   [pytest]
   pythonpath = src/backend
   testpaths = tests
   ```

3. **alembic.ini**
   ```ini
   sqlalchemy.url = driver://user:password@localhost/dbname
   script_location = alembic
   ```

4. **tests/conftest.py**
   ```python
   import sys
   from pathlib import Path
   
   # Add backend to path
   backend_path = Path(__file__).parent.parent / "src" / "backend"
   sys.path.insert(0, str(backend_path))
   ```

### Docker Configuration
1. **Dockerfile**
   ```dockerfile
   WORKDIR /app
   COPY . .
   RUN pip install -r requirements.txt
   CMD ["python", "-m", "src.backend.main"]
   ```

2. **docker-compose.yml**
   ```yaml
   services:
     backend:
       build: .
       working_dir: /app
       command: python -m src.backend.main
       volumes:
         - ./src/backend:/app/src/backend
   ```

### CI/CD Workflows
1. **.github/workflows/test.yml**
   ```yaml
   - name: Run tests
     run: pytest tests/ -v
   ```

2. **.github/workflows/lint.yml**
   ```yaml
   - name: Lint backend
     run: ruff check src/backend/
   ```

---

## Testing Import Updates

### Verify All Imports Work

```python
# test_imports.py - Run this to verify all imports work

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "src" / "backend"
sys.path.insert(0, str(backend_path))

# Test all major imports
try:
    from src.backend.api.server import app
    print("✓ API imports work")
except ImportError as e:
    print(f"✗ API imports failed: {e}")

try:
    from src.backend.application.services import DetectionService
    print("✓ Application imports work")
except ImportError as e:
    print(f"✗ Application imports failed: {e}")

try:
    from src.backend.engines.plagiarism_engine import PlagiarismEngine
    print("✓ Engine imports work")
except ImportError as e:
    print(f"✗ Engine imports failed: {e}")

try:
    from src.backend.infrastructure.db import Database
    print("✓ Infrastructure imports work")
except ImportError as e:
    print(f"✗ Infrastructure imports failed: {e}")

try:
    from src.backend.evaluation.core import EvaluationFramework
    print("✓ Evaluation imports work")
except ImportError as e:
    print(f"✗ Evaluation imports failed: {e}")

try:
    from src.backend.benchmark.runners import BenchmarkRunner
    print("✓ Benchmark imports work")
except ImportError as e:
    print(f"✗ Benchmark imports failed: {e}")

try:
    from src.backend.ml.fusion_model import FusionModel
    print("✓ ML imports work")
except ImportError as e:
    print(f"✗ ML imports failed: {e}")

try:
    from src.backend.config.settings import Settings
    print("✓ Config imports work")
except ImportError as e:
    print(f"✗ Config imports failed: {e}")

print("\nAll import tests completed!")
```

### Run Import Verification

```bash
# Run the import test
python test_imports.py

# Or use Python's import checker
python -m py_compile src/backend/**/*.py

# Or check for syntax errors
python -m py_compile src/backend/
```

---

## Common Issues & Solutions

### Issue: ModuleNotFoundError: No module named 'src.backend'

**Solution**: Ensure `src/backend/__init__.py` exists and sys.path is configured correctly.

```python
# In your entry point or conftest.py
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent / "src" / "backend"
sys.path.insert(0, str(backend_path))
```

### Issue: Circular Import Errors

**Solution**: Use lazy imports or refactor to break circular dependencies.

```python
# Instead of
from src.backend.module_a import ClassA
from src.backend.module_b import ClassB

# Use lazy import
def get_class_a():
    from src.backend.module_a import ClassA
    return ClassA
```

### Issue: Relative Imports Breaking

**Solution**: Convert all relative imports to absolute imports.

```python
# OLD (relative)
from ..utils import helper_function

# NEW (absolute)
from src.backend.utils import helper_function
```

### Issue: Tests Can't Find Modules

**Solution**: Update `tests/conftest.py` to add backend to path.

```python
# tests/conftest.py
import sys
from pathlib import Path

# Add backend to Python path
backend_path = Path(__file__).parent.parent / "src" / "backend"
sys.path.insert(0, str(backend_path))
```

---

## Verification Commands

```bash
# Check for old imports
grep -r "from src\." --include="*.py" src/backend/ | grep -v "from src.backend"

# Check for old import statements
grep -r "^import src\." --include="*.py" src/backend/ | grep -v "^import src.backend"

# Check for string paths
grep -r '"src/' --include="*.py" src/backend/ | grep -v '"src/backend'

# Verify Python syntax
python -m py_compile src/backend/

# Run linter
ruff check src/backend/

# Run formatter
black --check src/backend/

# Run type checker (if configured)
mypy src/backend/
```

---

## Rollback Commands

If you need to revert the import changes:

```bash
# Revert from imports
find . -name "*.py" -type f ! -path "*/venv/*" ! -path "*/node_modules/*" \
  -exec sed -i 's/from src\.backend\.\([a-zA-Z_]*\)/from src.\1/g' {} +

# Revert import statements
find . -name "*.py" -type f ! -path "*/venv/*" ! -path "*/node_modules/*" \
  -exec sed -i 's/import src\.backend\.\([a-zA-Z_]*\)/import src.\1/g' {} +

# Revert string paths
find . -name "*.py" -type f ! -path "*/venv/*" ! -path "*/node_modules/*" \
  -exec sed -i 's/"src\/backend\/\([a-zA-Z_]*\)\//\"src\/\1\//g' {} +
```

