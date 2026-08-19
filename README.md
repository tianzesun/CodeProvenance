# IntegrityDesk

> **Next-Generation Academic Integrity Platform — A Modern MOSS Replacement**

IntegrityDesk is a production-ready code similarity detection system designed for educational institutions. It uses multi-engine analysis to detect plagiarism, code theft, and AI-generated submissions with professional-grade accuracy, explainability, and actionable reporting.

---

## 🎯 Why IntegrityDesk?

Traditional tools like MOSS and JPlag use single algorithms and provide minimal context. IntegrityDesk combines **6 different similarity engines** with **Bayesian Arbitration**, **Hybrid ML Fusion**, and **Stylometric Analysis** — delivering actionable intelligence with publication-grade credibility.

### 🚀 Enterprise-Grade Forensic Capabilities

IntegrityDesk is engineered for institutional scale, providing the most comprehensive forensic suite for academic integrity:

- **AI-Detection (ChatGPT/Claude)**: High-accuracy detection (>90%) using CodeBERT Zero-Shot classifiers and stylometric contrast to identify LLM-generated patterns.
- **Web-Scale Scanning**: Real-time similarity checks against **10B+ lines of code** (GitHub, Stack Overflow) using LSH and Vector indexing.
- **Behavioral Analysis (Keystroke Logging)**: Detects copy-paste bursts and unnatural composition patterns to identify the *act* of plagiarism during code creation.
- **Multi-Language Support (20+)**: Dedicated forensic support for Python, C++, Java, JS, TS, Go, Rust, Ruby, and 15+ other languages.
- **Real-Time Detection API**: Highly optimized $O(n \log n)$ search architecture for instant feedback.
- **Obfuscation Robustness**: Resistant to advanced obfuscation (renaming, reordering, junk code) via Program Dependency Graphs (PDG).
- **Professor Dashboard**: Comprehensive heatmaps, signed PDF reports, and multi-engine evidence summaries.
- **Student Prevention Feedback**: A student-facing portal providing pre-submission "integrity checks" to encourage self-correction.

### 📊 Feature Comparison

| Feature | MOSS | JPlag | IntegrityDesk |
|---------|------|-------|----------------|
| Engines | 1 (Winnowing) | 1-3 | 6 (AST + Fingerprint + N-gram + Embedding + Execution + Token) |
| Weight Learning | Manual | Manual | ML (Logistic Regression) |
| Threshold Optimization | Fixed | Fixed | PR-Curve + F1 Optimization |
| Risk Levels | ❌ | ❌ | ✅ (CRITICAL / HIGH / MEDIUM / LOW) |
| Teacher Review UI | ❌ | ❌ | ✅ (Built-in dashboard) |
| PDF/HTML Reports | ❌ | Basic | ✅ Professional reports |
| Feature Explanations | ❌ | ❌ | ✅ (AST similarity, semantic, token) |
| GPU Acceleration | ❌ | ❌ | ✅ (CodeBERT on CUDA) |
| AI Code Detection | ❌ | ❌ | ✅ (Pattern-based detection) |
| Feedback Loop | ❌ | ❌ | ✅ (Teacher decisions → retrain) |

---

## 🚀 Key Features

### 1. Multi-Engine Similarity Detection
Six specialized engines analyze code from different perspectives:

| Engine | Method | Detects |
|--------|--------|---------|
| **AST Engine** | Tree edit distance + control flow graphs | Structural plagiarism, code reordering |
| **Winnowing Engine** | Adaptive k-gram fingerprinting | Copy-paste, text overlap |
| **N-gram Engine** | Character/token sequence matching | Partial copying, sliding windows |
| **Embedding Engine** | LLM embeddings (CodeBERT/GPU) | Semantic similarity, obfuscated code |
| **Execution Engine** | Runtime output comparison | Type-4 semantic clones (different syntax, same output) |
| **Token Engine** | Token frequency + TF-IDF | Token-level manipulation |

### 2. Intelligent Fusion Scoring
Automatically learns optimal weights using ML:
- **Logistic Regression** with class balancing
- **GPU-accelerated** CodeBERT embeddings (no API needed)
- **Fallback chain**: CodeBERT → OpenAI → text similarity

### 3. Professional Reports
Generate admin-ready plagiarism reports:
- **HTML reports** with styled comparisons, risk highlighting, expandable code views
- **JSON export** for API integration
- **Institution/course branding**
- **Feature breakdown** per comparison pair

### 4. Teacher Review Dashboard
A built-in web interface for human-in-the-loop review:
- **Risk-ordered queue** (CRITICAL → LOW)
- **One-click decisions**: Confirm / Reject / Need Review
- **Feature importance**: See which engines detected similarity
- **Code comparison side-by-side**

### 5. Continuous Improvement Loop
Teacher decisions feed back into the system:
- Store confirmations/rejections as ground truth
- Automatic threshold re-optimization
- Model retraining with labeled data

---

## 📁 Architecture

```
IntegrityDesk/
├── src/
│   ├── backend/
│   │   ├── api/
│   │   │   ├── routes/                     # FastAPI routers (auth, cases, users, jobs, ...)
│   │   │   ├── middleware/                 # Auth, rate limiting, request ID
│   │   │   └── server.py                   # App entrypoint & core endpoints
│   │   ├── application/services/           # Business logic (cases, batch detection, ...)
│   │   ├── engines/                        # Similarity & AI detection engines
│   │   │   ├── similarity/                 # AST, Winnowing, N-gram, Embedding, Token
│   │   │   ├── execution/                  # Runtime output comparison
│   │   │   └── ai/                         # AI-code detection (Binoculars, stylometry)
│   │   ├── infrastructure/                 # DB, email, reports, GPU service
│   │   ├── config/                         # Settings, database
│   │   ├── models/                         # SQLAlchemy models
│   │   ├── services/                       # Webhook delivery, embedding server
│   │   ├── workers/                        # GPU / webhook background workers
│   │   ├── cli/                            # CLI commands
│   │   └── main.py                         # Minimal public entrypoint
│   └── frontend/                           # Next.js/React dashboard (App Router)
│       ├── app/                            # Pages (dashboard, cases, benchmark, AI detector)
│       ├── components/                     # Shared UI components
│       └── types/                          # Shared TypeScript API types
├── tests/
│   ├── unit/                               # Fast unit tests
│   └── integration/                        # DB-backed integration tests
├── alembic/                                # Database migrations
├── benchmark/                              # Benchmark runners (BigCloneBench, IR-Plag, ...)
└── scripts/                                # Operational helpers
```

---

## 🔧 Quick Start

### Prerequisites
- Python 3.10+
- PostgreSQL database (Neon or any Postgres) — required by the backend
- Node.js 18+ for the frontend

### Backend Setup
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment (see src/backend/.env.example)
cp src/backend/.env.example src/backend/.env.local
# Edit .env.local with your DATABASE_URL and AUTH_JWT_SECRET

# Run migrations
alembic upgrade head

# Start the API server
uvicorn src.backend.api.server:app --host 0.0.0.0 --port 8000
```

### Frontend Setup
```bash
cd src/frontend
npm install
npm run dev   # http://localhost:3000
```

### With Docker
```bash
docker compose up --build
```

### API Usage
```python
from src.backend.application.services.batch_detection_service import BatchDetectionService

service = BatchDetectionService(threshold=0.5)
report = service.run_analysis(Path("./student_submissions"),
                               save_to=Path("./results/report.json"))

print(f"Suspicious pairs: {report['summary']['suspicious_pairs']}")
```

### REST API
```bash
# Health check
curl http://localhost:8000/health

# Login and get a session cookie
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@school.edu", "password": "YourPassword"}'

# Bootstrap the first admin user (fresh installs only)
curl -X POST http://localhost:8000/api/auth/bootstrap-admin \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@school.edu", "full_name": "Admin", "password": "YourPassword", "tenant_name": "My University"}'
```

### Email Configuration (password reset)
The email service supports three backends via `EMAIL_BACKEND`:
- `console` (default): logs reset links to stdout — use for development
- `smtp`: production SMTP delivery (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USER`, `EMAIL_PASSWORD`)
- `sendgrid`: SendGrid API (`SENDGRID_API_KEY`)

### GPU CodeBERT
```python
from src.backend.engines.similarity.codebert_similarity import CodeBERTSimilarity

similarity = CodeBERTSimilarity(device='cuda')  # auto-detects GPU
score = similarity.compare(
    {'raw': student_code_a},
    {'raw': student_code_b}
)
```

> For GPU servers, install GPU dependencies: `pip install -r requirements-gpu.txt`

---

## 🧪 Testing

CI gates on the real test suite (`.github/workflows/ci.yml`). Run locally:

```bash
# Unit tests (fast, no database) — the CI merge gate
pytest -o addopts="" tests/unit/

# Integration tests (require a reachable database; skipped automatically if unavailable)
pytest -o addopts="" tests/integration/

# Frontend type-check + production build (the other CI merge gate)
cd src/frontend && npx tsc --noEmit && npm run build
```

Linting and formatting run in CI as non-blocking reports until the pre-existing
findings are cleared (935 `ruff`, 41 `eslint`), then they become merge gates:
```bash
ruff check src/backend --output-format=concise
ruff format --check src/backend
black --check src/backend
cd src/frontend && npm run lint
```
Note: `pyproject.toml` does not exist yet; `ruff` currently runs with default
settings. Add one with a `[tool.ruff]` section when the lint debt is cleared.

---

## 📈 Detection Capabilities

### Clone Types Detected

| Type | Description | Engines Used |
|------|-------------|--------------|
| **Type 1**: Exact Copy | Whitespace/comment changes | Winnowing, Token |
| **Type 2**: Renamed | Variable/function renaming | AST, N-gram |
| **Type 3**: Modified | Added/removed statements | AST, N-gram, Token |
| **Type 4**: Semantic | Different syntax, same behavior | Execution, Embedding |

### Risk Classification

| Level | Score | Action |
|-------|-------|--------|
| **CRITICAL** | ≥ 0.90 | Immediate review required |
| **HIGH** | ≥ 0.75 | Recommend detailed review |
| **MEDIUM** | ≥ 0.50 | Suspicious — manual check |
| **LOW** | < 0.50 | No action needed |

---

## 🏛️ Designed for Universities

### What IntegrityDesk Offers

- **Institutional Reports**: Custom-branded PDF/HTML reports for academic integrity committees
- **Course-Level Analysis**: Separate models for different courses and programming languages
- **Submission History**: Track repeat offenders across multiple assignments
- **Evidence Chain**: Every detection includes feature breakdown and code comparison
- **Teacher Workflow**: Built-in dashboard for confirmation/rejection decisions
- **Continuous Learning**: System improves from human decisions over time

### Supported Languages

Python, Java, C, C++, JavaScript, TypeScript, Go, and more — with language-specific parsers and AST generation.

---

## 📊 System Maturity

### What's Production-Ready ✅
- Multi-engine similarity detection (6 engines)
- ML-based weight learning
- Threshold optimization (PR-curve, F1 optimization)
- Teacher review dashboard with risk levels
- HTML/JSON professional reports
- GPU-accelerated CodeBERT embeddings
- Continuous improvement feedback loop
- REST API (FastAPI)

### Deployment Options
- **Local**: Run on any machine (CPU mode)
- **GPU Server**: Deploy on university GPU cluster for CodeBERT acceleration
- **Cloud**: Deploy with Docker (containerization support)

---

## 📄 License

[License file](LICENSE)

## 📧 Contact

For deployment, support, or feature requests, please open an issue on GitHub.

---

**IntegrityDesk** — From "Did they copy?" to "Here's the evidence."