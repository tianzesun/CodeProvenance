# IntegrityDesk

> **Next-Generation Academic Integrity Platform — a modern MOSS replacement**

IntegrityDesk (repository: `CodeProvenance`) is a code similarity and AI-authorship
detection system built for schools and universities. It combines multiple similarity
engines, a learned fusion model, an AI-generated-code detector, and a professor-facing
review workspace — so the output is not just a score, but evidence a faculty member can
act on and a committee can defend.

**Stack:** Python 3.12 · FastAPI · PostgreSQL (row-level multi-tenancy) · Alembic ·
Next.js 16 / React 19 dashboard · systemd + Apache/nginx deployment.

---

## 🎯 Why IntegrityDesk?

Traditional tools such as MOSS and JPlag apply one algorithm and return one number.
IntegrityDesk fuses **eight weighted similarity signals**, a **learned fusion model**,
**course-aware weight profiles**, and an **8-signal AI detector**, then routes every
flag through a band-based review policy with human dispositions.

### ✨ What was added recently

| Area | Capability |
|------|-----------|
| **Academic hierarchy** | Organizations → courses → terms → assignments → students, with instructors, enrollments, assignment versions, and per-course engine weight profiles |
| **Review workspace** | Band-based queue, allowed/blocked dispositions, AI-corroboration rule, workload card, pair navigation, verdicts and review notes |
| **Evidence dossier** | Per-student printable dossier, generated viva questions, and viva outcome tracking that closes the case loop |
| **AI detection** | 8 independent signals, safe-blend ML classifier, Turnitin-style likelihood bands, background-job execution, and student-code false positives cut from 21.3% → 2.3% |
| **Reporting** | Integrity Assessment Report (Dean/Chair-grade PDF), committee report, AI originality PDF, HTML/JSON/PDF/CSV exports with caching |
| **Benchmarking** | EvalForge framework, adapters for MOSS/JPlag/NiCad/Dolos/PMD, loaders for 13+ clone/corpus datasets, taxonomy with measured TPR/FPR/PR-AUC, statistical certification |
| **Public REST API** | `/api/v1/analyze` with API-key auth, rate limiting, job polling, results, reports, and usage metering |
| **LLM providers** | Multi-vendor catalog (OpenAI, Anthropic, Google, xAI, Mistral, DeepSeek, Groq, OpenRouter, Ollama) with live model discovery |
| **Source scanning** | Matches submissions against GitHub and Stack Overflow sources |
| **Operations** | Background analysis with live progress, migration CI against a fresh Postgres, gitleaks secret scan, Locust/k6 load tests |

### 📊 Feature Comparison

| Feature | MOSS | JPlag | IntegrityDesk |
|---------|------|-------|----------------|
| Engines | 1 (Winnowing) | 1–3 | 8 weighted signals (AST, Graph, Winnowing, N-gram/GST, Token, Embedding, Execution, Static rules) |
| Weight learning | Manual | Manual | Learned fusion model + Optuna tuning |
| Threshold optimization | Fixed | Fixed | PR-curve / F1 optimization + calibration |
| Risk levels | ❌ | ❌ | ✅ (CRITICAL / HIGH / MEDIUM / LOW) |
| Teacher review UI | ❌ | ❌ | ✅ Built-in dashboard with dispositions |
| Reports | ❌ | Basic | ✅ HTML, JSON, PDF, CSV |
| Feature explanations | ❌ | ❌ | ✅ Per-engine contribution breakdown |
| GPU acceleration | ❌ | ❌ | ✅ CodeBERT / UniXcoder on CUDA |
| AI code detection | ❌ | ❌ | ✅ 8-signal ensemble with confidence bands |
| Course-aware config | ❌ | ❌ | ✅ Profiles per course/assignment type |
| Reproducible benchmarking | ❌ | Partial | ✅ EvalForge + certification statistics |

---

## 🚀 Key Features

### 1. Multi-Engine Similarity Detection

| Engine | Method | Detects |
|--------|--------|---------|
| **AST** | Tree paths, subtree hashes, tree edit distance | Structural plagiarism, reordered code |
| **Graph** | CFG + DFG structural comparison | Semantic-preserving rewrites |
| **Winnowing** | Adaptive k-gram fingerprinting | Copy-paste, text overlap |
| **N-gram / GST** | Character/token sequences + greedy string tiling | Partial copying, sliding windows |
| **Token** | Token frequency + TF-IDF | Token-level manipulation |
| **Embedding** | UniXcoder / CodeBERT (GPU) with OpenAI fallback | Semantic similarity, obfuscated code |
| **Execution** | Runtime output comparison | Type-4 clones (different syntax, same behavior) |
| **Static rules** | File-type–aware heuristics | Boilerplate, framework idioms |

Engines are registered through a plugin registry
(`src/backend/engines/engine_registry.py`), and `src/backend/plugins/` ships additional
drop-in algorithms (Jaccard n-gram, LCS, Levenshtein).

### 2. Intelligent Fusion Scoring

- **Learned fusion model** is the production primary score (retrained on 1,371 labeled pairs)
- **Weight profiles**: `standard`, `conservative`, `rewrite-sensitive`, plus course profiles
  in `src/backend/engines/course_profiles.yaml`
- **Precision guards**: minimum concrete/lexical engine agreement and score floors before a
  high score is trusted
- **Optuna tuner** (`src/backend/engines/tuning/optuna_tuner.py`) for threshold/weight search
- **Starter-code exclusion** so template code never inflates a pair score

### 3. Academic Hierarchy & Assignment Awareness

- Organizations, courses, terms, assignments, versions, students and enrollments
- Per-course engine weight mapping (e.g. UTSC/UofT course catalog seeding)
- Assignment modes with an automatic "suggest mode" helper
- Seedable demo data for a fresh deployment

### 4. Professor Review Workspace

- **Risk-ordered queue** with review bands: `low`, `review`, `high`
- **Band-dependent dispositions** — `no_action`, `note_on_file`, `conversation`,
  `step_up_verification`, `formal_escalation`; high-stakes options stay blocked until
  corroborating evidence exists
- **AI corroboration rule**: an AI flag is only escalated when structural similarity or a
  web match supports it
- Side-by-side code comparison, per-engine feature importance, and a workload card

### 5. Evidence Dossier & Viva

- Unified per-student dossier with a severity-banded evidence list
- Generated viva questions and recorded viva outcomes (closes the case loop)
- Printable PDF export (`/dossier/{job_id}/download-pdf`)

### 6. AI-Generated Code Detection

Eight independent signals — perplexity, burstiness, stylometry, LLM pattern library,
structural entropy, vocabulary richness, and more — blended with a trained ML classifier:

- Turnitin-style likelihood bands in the report
- Honest confidence and per-layer visibility
- Calibration and retraining endpoints (`/api/ai-detect/calibrate`, `/retrain`)
- Measured human-code false-positive baseline surfaced in the product
- Runs as a background job so large uploads do not time out

### 7. Professional Reporting

- **Integrity Assessment Report** — Dean/Chair-grade PDF with T1–T5 plagiarism
  classification, 8-signal AI analysis, 95% bootstrap confidence intervals, a
  due-process evidence chain, student response template, digital signature and a
  reproducibility hash
- Committee report, AI originality PDF, HTML/JSON downloads, CSV export
- Per-pair feature breakdown and expandable code views
- Institution/course branding

### 8. Benchmarking & Evaluation

- **EvalForge** (`python -m src.backend.evalforge.main`) — dataset, detector, metric and
  report pipelines
- **Adapters** for MOSS, JPlag, NiCad, Dolos, PMD and lexical/AST baselines so external
  tools are compared under the same harness
- **Dataset loaders**: BigCloneBench, CodeSearchNet, CodeXGLUE, POJ-104, HumanEval, MBPP,
  Google CodeJam, Kaggle student code, IR-Plag, AIGCodeSet, and more
- **Taxonomy** with live/partial/gap/missing status, TPR/FPR/PR-AUC reporting, and
  competitor comparison views
- **Certification**: confidence intervals, effect sizes, statistical tests, stratified and
  reproducibility reports

### 9. Public REST API

Authenticate with `Authorization: Bearer <API_KEY>`:

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/v1/analyze` | Submit submissions for analysis |
| `GET` | `/api/v1/jobs/{job_id}` | Poll job status |
| `GET` | `/api/v1/jobs/{job_id}/results` | Retrieve similarity results |
| `GET` | `/api/v1/jobs/{job_id}/report` | Download the report |
| `GET` | `/api/v1/usage` | Metering for the calling key |

API keys are managed by `src/backend/api/middleware/auth.py` (prefix `sk_live_`,
per-key rate limits, revocation).

### 10. LLM Provider Integration

Bring-your-own-key evidence summarization and rewrite analysis. The settings page can
authenticate a connection and list the vendor's **live** model catalog; when the model
list cannot be fetched, a clearly-labelled recommended set is shown instead. All callers
degrade gracefully to a heuristic summary when no key is configured.

---

## 📁 Architecture

```
CodeProvenance/
├── src/
│   ├── backend/
│   │   ├── api/
│   │   │   ├── routes/            # FastAPI routers (auth, cases, users, settings,
│   │   │   │                      #   academic, analyze, benchmark, reviews, ...)
│   │   │   ├── middleware/        # Auth + API keys, rate limiting, request ID
│   │   │   ├── schemas/           # Pydantic request/response contracts
│   │   │   └── server.py          # ASGI app, core endpoints, background jobs
│   │   ├── application/           # Services, pipelines, use cases
│   │   ├── domain/                # Domain models, decision engine
│   │   ├── contracts/             # Schema registry, versioning, reproducibility
│   │   ├── core/                  # IR, graph, token heatmap, analyzer primitives
│   │   ├── engines/
│   │   │   ├── similarity/        # AST, graph, winnowing, n-gram, token, embedding,
│   │   │   │                      #   execution, boilerplate filter, two-stage pipeline
│   │   │   ├── ai/                # AI detector: ensemble, signals, classifier, FP control
│   │   │   ├── detection/         # 4 layers: deterministic → statistical → semantic → explain
│   │   │   ├── scoring/           # Fusion, learned fusion, review policy, professor profiles
│   │   │   ├── tuning/            # Optuna tuner
│   │   │   ├── execution/         # Runtime comparison adapter layer
│   │   │   └── *.yaml             # Engine weights, course profiles, detection policy
│   │   ├── evaluation/            # Dossier, cluster detection, fingerprints, IEEE reports,
│   │   │                          #   calibration, significance testing, shadow mode
│   │   ├── benchmark/             # Datasets, adapters, suites, metrics, certification
│   │   ├── evalforge/             # Standalone benchmarking framework (CLI)
│   │   ├── ml/ + pipeline/        # Fusion model training, checkpoints, dataset builders
│   │   ├── integrations/          # LLM provider catalog + request layer
│   │   ├── infrastructure/        # DB, email, PDF/CSV report exporters, GPU service
│   │   ├── models/                # SQLAlchemy models (31 Alembic migrations)
│   │   ├── plugins/               # Drop-in algorithms (Jaccard, LCS, Levenshtein)
│   │   ├── workers/               # Webhook, batch and GPU workers
│   │   ├── load_tests/            # Locust + k6 suites
│   │   ├── cli/                   # Typer CLI commands
│   │   └── main.py                # Minimal public entrypoint
│   └── frontend/                  # Next.js App Router dashboard
│       ├── app/                   # Pages (see dashboard map below)
│       ├── components/            # Shared UI components
│       ├── lib/                   # API client + shared helpers
│       └── types/                 # Shared TypeScript API types
├── tests/                         # unit/ · integration/ · scoring/ · fixtures/
├── alembic/                       # Migrations (validated in CI on fresh Postgres)
├── data/datasets/                 # IR-Plag, AIGCodeSet and benchmark fixtures
├── deploy/                        # Apache/nginx + systemd + TLS installer
├── docs/                          # Architecture, PRD, benchmarks, guides
└── scripts/                       # Operational helpers
```

### Dashboard map

| Page | What it does |
|------|--------------|
| `/upload` | Run a plagiarism check: file/ZIP upload, engine selection, starter-code exclusion, live progress |
| `/results` | Review workspace — risk-ordered pairs, side-by-side code, dispositions |
| `/history` | Persisted history of past checks with status filters and warnings |
| `/cases` | Case queue with timeline, comments, assignment and export |
| `/dossier/[id]` | Per-student evidence dossier and viva workflow |
| `/reports` | Report bundles and exports |
| `/ai-detector` | AI authorship analysis with likelihood bands and signal breakdown |
| `/courses`, `/assignments` | Course and assignment management |
| `/admin` | Tabs for users, instructors, courses/assignments overview, retention |
| `/analytics` | Department integrity overview, risk trends, repeat-offender stats |
| `/benchmark` | Run benchmarks, compare tools, view TPR/FPR/PR-AUC and suggestions |
| `/datasets`, `/tools/fpr-validation` | Dataset readiness and false-positive validation runs |
| `/error-analysis` | Per-file false-positive deep dive |
| `/settings` | Detection thresholds, engine config, profiles, AI providers, limits |
| `/compare-tools`, `/evidence-view`, `/cluster-detection`, `/historical-fingerprint` | R&D surfaces (see *Current gaps*) |

---

## 🔧 Quick Start

### Prerequisites

- **Python 3.12** (3.10+ supported)
- **PostgreSQL** (Neon or any Postgres) — required; SQLite is not supported
- **Node.js 20+** for the dashboard
- Redis — required only for the webhook worker / caching

### Backend

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment (see src/backend/.env.example)
cp src/backend/.env.example src/backend/.env
# Edit .env — set DATABASE_URL and AUTH_JWT_SECRET

# Run migrations
alembic upgrade head

# Start the API server
uvicorn src.backend.api.server:app --host 0.0.0.0 --port 8000
```

Interactive docs: `http://localhost:8000/docs`

### Dashboard

```bash
cd src/frontend
npm install
npm run dev   # http://localhost:3000
```

> Production is deployed through the systemd/Apache path in `deploy/`
> (`deploy/README.md`). The Docker quickstart was removed during release hardening
> because it shipped stale, insecure configuration.

### API Usage (Python)

```python
from pathlib import Path

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
  -d '{"email": "admin@school.edu", "full_name": "Admin",
       "password": "YourPassword", "tenant_name": "My University"}'

# Public analysis API (API-key authenticated)
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Authorization: Bearer sk_live_..." \
  -H "Content-Type: application/json" \
  -d '{"name": "Homework 1", "submissions": [...]}'
```

### Email Configuration (password reset)

The email service supports three backends via `EMAIL_BACKEND`:

- `console` (default) — logs reset links to stdout; use for development
- `smtp` — production SMTP delivery (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USER`, `EMAIL_PASSWORD`)
- `sendgrid` — SendGrid API (`SENDGRID_API_KEY`)

### GPU Embeddings (CodeBERT / UniXcoder)

```bash
pip install -r requirements-gpu.txt   # GPU servers only
```

The embedding engine auto-detects CUDA and falls back to OpenAI embeddings, then to
text similarity, when a GPU is unavailable. An optional self-hosted embedding server
runs as its own service (`src/backend/services/embedding_server.py`).

---

## 🧪 Testing & CI

CI gates on the real test suite (`.github/workflows/ci.yml`). Run locally:

```bash
# Unit tests (fast, no database) — the CI merge gate
pytest -o addopts="" tests/unit/

# Integration tests (require a reachable database; skipped automatically if unavailable)
pytest -o addopts="" tests/integration/

# Frontend type-check + production build (the other CI merge gate)
cd src/frontend && npx tsc --noEmit && npm run build
```

The suite is roughly 1,400 tests across ~90 modules, plus scoring and fixture suites.

CI also runs:

| Job | What it catches |
|-----|-----------------|
| **Migrations** | Full `alembic upgrade head` from scratch on Postgres 16, then `downgrade -1` + re-apply — duplicate revision ids, from-scratch breakage, drifted schemas |
| **Secret scan** | gitleaks over full history |
| **Backend tests** | `pytest tests/unit/` |
| **Frontend** | `tsc --noEmit` + production build |
| **Lint/format** | `ruff`, `ruff format`, `black`, `eslint` — currently non-blocking reports until the pre-existing findings are cleared (see the TODOs in `ci.yml`), then they become merge gates |

Linting and formatting:

```bash
ruff check src/backend --output-format=concise
ruff format --check src/backend
black --check src/backend
cd src/frontend && npm run lint
```

`pyproject.toml` ships a `[tool.ruff]` section (line length 100, project-specific
ignores and per-file ignores for FastAPI/Typer idioms).

### Load Testing

```bash
pip install -r requirements-load-test.txt
locust -f src/backend/load_tests/locustfile.py --host http://localhost:8000
k6 run src/backend/load_tests/load_test.js
```

See `docs/LOAD_TESTING.md`.

---

## 📈 Detection Capabilities

### Clone Types Detected

| Type | Description | Engines Used |
|------|-------------|--------------|
| **T1** Identical copy | Whitespace/comment changes | Winnowing, Token, GST |
| **T2** Renamed | Identifier renaming | AST, N-gram |
| **T3** Restructured | Added/removed/reordered statements | AST, Graph, N-gram |
| **T4** Semantic clone | Different syntax, same behavior | Execution, Embedding |
| **T5** Independent work | No evidence of copying | Baseline across all engines |

### Risk Bands

| Level | Score | Action |
|-------|-------|--------|
| **CRITICAL** | ≥ 0.85 | Immediate review; corroborating evidence required |
| **HIGH** | ≥ 0.65 | Recommend detailed review |
| **MEDIUM** | ≥ 0.35 | Suspicious — manual check |
| **LOW** | < 0.35 | No action needed |

Review bands are course-aware and tunable per assignment type
(`introductory`, `algorithms`, `projects`, `capstone`) in
`src/backend/engines/scoring/review_policy.py`.

### Detection Layers

1. **Deterministic** — exact/normalized matches, static rules
2. **Statistical** — fingerprints, n-grams, token distributions
3. **Semantic** — AST/graph/embedding/execution agreement
4. **Explainability** — per-engine contribution, evidence spans, reviewer-facing narrative

---

## 🏛️ Designed for Universities

- **Institutional reports** — branded, committee-ready PDF/HTML with evidence chains
- **Course-level analysis** — separate weight profiles per course and language
- **Submission history** — repeat patterns tracked across assignments
- **Human-in-the-loop** — every disposition is stored and can retrain thresholds
- **Multi-tenant** — row-level security with per-tenant API keys and usage metering
- **Supported languages** — Python, Java, C, C++, JavaScript, TypeScript, Go and more,
  with language-specific parsers and AST generation

---

## 🚀 Deployment

`deploy/README.md` covers a fresh Ubuntu/Debian install behind Apache (or nginx) with
TLS via Let's Encrypt, managed by systemd:

| Service | Port | Unit |
|---|---|---|
| FastAPI backend | 127.0.0.1:8000 | `integritydesk-backend` |
| Next.js dashboard | 127.0.0.1:3000 | `integritydesk-dashboard` |
| Webhook worker (Redis) | – | `integritydesk-worker` |
| Embedding server *(optional)* | 127.0.0.1:8001 | `integritydesk-embedding` |

```bash
sudo bash deploy/bootstrap.sh          # OS packages
cp deploy/deploy.conf.example deploy.conf && vim deploy.conf
sudo bash deploy/setup.sh              # build + start
sudo bash deploy/update.sh             # after every git pull
```

---

## 🗂️ Documentation Map

| Document | Contents |
|----------|----------|
| `docs/ARCHITECTURE.md` | Architecture decisions (AI, database, RAG) |
| `docs/FIVE_LAYER_DETECTION_ARCHITECTURE.md` | Layered detection design |
| `docs/ENGINE_ARCHITECTURE.md`, `docs/COURSE_PROFILE_SYSTEM.md` | Engine and profile design |
| `docs/BENCHMARK_*.md`, `docs/CODEPROVENANCE_BENCHMARK.md` | Benchmarking methodology and results |
| `docs/product/API_REFERENCE.md` | REST interface reference |
| `docs/product/USER_GUIDE.md`, `docs/PROFESSOR_GUIDE.md` | End-user and professor guides |
| `docs/INVESTIGATION_SYSTEM_DESIGN.md` | Investigation & evidence management design |
| `docs/LOAD_TESTING.md` | Locust / k6 load testing guide |
| `docs/product/CANVAS_INTEGRATION.md` | LTI 1.3 / Canvas integration plan |
| `docs/product/SCIENTIFIC_WHITE_PAPER.md` | Methodology and evaluation |
| `docs/archive/` | Superseded fix notes and session records |
| `deploy/README.md` | Production deployment |
| `AGENTS.md`, `CLAUDE.md` | Contributor / agent working rules |
| `CHANGELOG.md` | Release history |

---

## ⚠️ Current Gaps

- Several routers exist but are not yet mounted on the ASGI app in
  `src/backend/api/server.py`: LTI/Canvas (`lti`), webhooks and usage management,
  visualize, and the cluster-detection / evidence-view / historical-fingerprint routers.
  Their dashboard pages therefore have no live backend yet.
- The `academic` router is mounted with a duplicated `/api` prefix, so those endpoints
  currently resolve under `/api/api/...`.
- Python and frontend lint jobs are non-blocking until the pre-existing findings are
  cleared.

---

## 📄 License

[License file](LICENSE)

## 📧 Contact

For deployment, support, or feature requests, please open an issue on GitHub.

---

**IntegrityDesk** — From "Did they copy?" to "Here's the evidence."
