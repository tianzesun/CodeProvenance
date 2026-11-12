# IntegrityDesk

> **Next-Generation Academic Integrity Platform — a modern MOSS replacement**

IntegrityDesk (repository: `CodeProvenance`) is a code similarity and AI-authorship
detection system built for schools and universities. It combines multiple similarity
engines, a learned fusion model, an AI-generated-code detector, and a professor-facing
review workspace — so the output is not just a score, but evidence a faculty member can
act on and a committee can defend.

**Stack:** Python 3.12 · FastAPI · PostgreSQL (row-level multi-tenancy) · Alembic ·
Celery + Redis job queue · Next.js 16 / React 19 dashboard · systemd + Apache/nginx
deployment.

---

## 🎯 Why IntegrityDesk?

Traditional tools such as MOSS and JPlag apply one algorithm and return one number.
IntegrityDesk scores each pair with a **learned model over seven similarity signals**,
shows which of them raised that pair's score, adds an **8-signal AI detector**, and turns
flags into cases with a per-student evidence dossier and viva questions.

On ConPlag (911 human-annotated contest pairs) it ranks pairs on par with JPlag and
Dolos (AUC 0.813 vs 0.821 / 0.838), and 2.3% of innocent pairs reach its high band. Like
those tools, it misses copies rewritten inside a student's own scaffolding. Measurements
and caveats: `docs/BENCHMARK_WORK.md`.

### ✨ What was added recently

| Area | Capability |
|------|-----------|
| **Academic hierarchy** | Organizations → courses → terms → assignments → students, with instructors, enrollments, assignment versions, and assignment types recorded on reports |
| **Review workspace** | Risk-ordered pairs, per-pair score explanation, side-by-side code, review status, workload card and cases. Band-based dispositions and the AI-corroboration rule exist in the reviews API but not yet in the dashboard |
| **Evidence dossier** | Per-student printable dossier, generated viva questions, and viva outcome tracking that closes the case loop |
| **AI detection** | 8 independent signals, safe-blend ML classifier, Turnitin-style likelihood bands, background-job execution, and student-code false positives cut from 21.3% → 2.3% |
| **Reporting** | Integrity Assessment Report (Dean/Chair-grade PDF), committee report, AI originality PDF, HTML/JSON/PDF/CSV exports with caching |
| **Benchmarking** | EvalForge framework, adapters for MOSS/JPlag/NiCad/Dolos/PMD, loaders for 13+ clone/corpus datasets, taxonomy with measured TPR/FPR/PR-AUC, statistical certification |
| **Public REST API** | `/api/v1/analyze` with API-key auth, rate limiting, job polling, results, reports, and usage metering |
| **LLM providers** | Multi-vendor catalog (OpenAI, Anthropic, Google, xAI, Mistral, DeepSeek, Groq, OpenRouter, Ollama) with live model discovery |
| **Source scanning** | Matches submissions against GitHub and Stack Overflow sources |
| **Operations** | Celery + Redis analysis queue with bounded workers and in-process fallback, live job progress, migration CI against a fresh Postgres, gitleaks secret scan, Locust/k6 load tests |

### 📊 Feature Comparison

| Feature | MOSS | JPlag | IntegrityDesk |
|---------|------|-------|----------------|
| Engines | 1 (Winnowing) | 1–3 | 7 signals combined by a learned model (see below) |
| Weight learning | Manual | Manual | Learned fusion model; Optuna tuner for benchmark runs |
| Threshold optimization | Fixed | Fixed | PR-curve / F1 analysis in benchmarks; product bands fixed until a student holdout exists |
| Risk levels | ❌ | ❌ | ✅ (CRITICAL / HIGH / MEDIUM / LOW) |
| Teacher review UI | HTML result pages | Report viewer | ✅ Review workspace, cases, dossier and viva |
| Reports | HTML result pages | Report viewer | ✅ HTML, JSON, PDF, CSV |
| Feature explanations | ❌ | ❌ | ✅ Per-engine contribution to each pair's score |
| GPU acceleration | ❌ | ❌ | ✅ UniXcoder embeddings on CUDA |
| AI code detection | ❌ | ❌ | ✅ 8-signal ensemble with confidence bands |
| Course-aware config | ❌ | ❌ | Partial: assignment types are recorded; their weight presets only reach the rule-based fallback |
| Reproducible benchmarking | ❌ | Partial | ✅ EvalForge + certification statistics |

---

## 🚀 Key Features

### 1. Multi-Engine Similarity Detection

The production score is a logistic model over seven signals
(`src/backend/engines/similarity/models/learned_fusion_model.json`), listed by their weight:

| Signal | Method | Role in the score |
|--------|--------|-------------------|
| **Chunk hash match** (winnowing) | Adaptive k-gram fingerprinting | Strongest: shared copied passages |
| **Matched-line coverage** | Share of lines inside matched blocks | Raises the score |
| **Token n-gram match** | Consecutive token runs | Raises the score |
| **Logic flow** | Order and shape of control flow | Raises the score |
| **Semantic meaning** (embedding) | UniXcoder, CPU or GPU | Little effect |
| **Token fingerprint** | Token-sequence overlap | Offset: moves in lockstep with chunk hash match |
| **Structure** (AST) | Tree paths, subtree hashes | Offset: about as high for independent solutions as for copies |

A near-exact match from the rule-based fusion (which also uses graph, string tiling,
TF-IDF and static-rule signals) sets the score to 1.0, and a structure-agreement floor
keeps reordered copies from slipping. Otherwise those extra signals do not move the
score. An execution engine (`src/backend/engines/execution/`) exists but is not run on
uploads.

Engines are registered through a plugin registry
(`src/backend/engines/engine_registry.py`), and `src/backend/plugins/` ships additional
drop-in algorithms (Jaccard n-gram, LCS, Levenshtein).

### 2. Intelligent Fusion Scoring

- **Learned fusion model** is the production primary score (retrained on 1,371 labeled pairs)
- **Review holds**: tiny files and pairs whose overlap is mostly starter or boilerplate code
  are held at 0.5 with a stated reason
- **Starter-code exclusion** so template code never inflates a pair score, and code most of
  the class shares is left out (and professors are told)
- **Weight profiles** (`standard`, `conservative`, `rewrite-sensitive`, course profiles in
  `src/backend/engines/course_profiles.yaml`) apply only to the rule-based fallback used
  when the learned model cannot load
- **Optuna tuner** (`src/backend/engines/tuning/optuna_tuner.py`) for benchmark
  threshold/weight search

### 3. Academic Hierarchy & Assignment Awareness

- Organizations, courses, terms, assignments, versions, students and enrollments
- Course codes map to assignment types (e.g. UTSC/UofT course catalog seeding); the type
  is recorded on the committee report but does not change how a check is scored yet
- Assignment modes with a "suggest mode" helper (`/api/assignment-modes/suggest`)
- Seedable demo data for a fresh deployment

### 4. Professor Review Workspace

- **Risk-ordered pairs** with verdict labels, filters and per-pair review status
- **Score explanation**: the engines that raised each pair's score, strongest first
- Side-by-side code comparison with matched blocks, a workload card, and one-click cases
- **In the reviews API, not yet in the dashboard**: band-dependent dispositions
  (`no_action`, `note_on_file`, `conversation`, `step_up_verification`,
  `formal_escalation`, high-stakes options blocked until corroborating evidence exists),
  per-assignment-type review bands, and the AI corroboration rule (an AI flag is only
  escalated when structural similarity or a web match supports it)

### 5. Evidence Dossier & Viva

- Unified per-student dossier with a severity-banded evidence list
- Generated viva questions and recorded viva outcomes (closes the case loop)
- Printable PDF export (`/dossier/{job_id}/download-pdf`)

### 6. AI-Generated Code Detection

Eight independent signals — perplexity, burstiness, stylometry, LLM pattern library,
structural entropy, vocabulary richness, and more — blended with a trained ML classifier:

- Turnitin-style likelihood bands in the report
- Honest confidence and per-layer visibility
- Measured accuracy is modest: AUC 0.591 in-domain (AIGCodeSet) and 0.523 on an external
  holdout (CoDet-M4); see `docs/AI_DETECTOR_VS_TURNITIN.md` before relying on a score
- Calibration and retraining endpoints (`/api/ai-detect/calibrate`, `/retrain`)
- Measured human-code false-positive baseline surfaced in the product
- Runs as a background job so large uploads do not time out

### 7. Professional Reporting

- **Integrity Assessment Report** — Dean/Chair-grade PDF with T1–T5 plagiarism
  classification, 8-signal AI analysis, a 95% interval on the class's mean pair score
  (normal approximation), a due-process evidence chain, student response template,
  signature lines and a reproducibility hash
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
│   │   │   └── server.py          # ASGI app, core endpoints, job dispatch
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
│   │   ├── models/                # SQLAlchemy models (41 Alembic migrations)
│   │   ├── plugins/               # Drop-in algorithms (Jaccard, LCS, Levenshtein)
│   │   ├── workers/               # Celery analysis queue, webhook, batch and GPU workers
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

### Runtime topology

```
Browser ──► reverse proxy ──► FastAPI ──► PostgreSQL
                     │
                     ├── Celery analysis queue (Redis) ──► analysis workers
                     │                                        │
                     │            job status/progress ◄───────┘
                     ▼
              Next.js dashboard (polls /api/job/{id})
```

Uploads return a job id immediately; analysis runs in the bounded Celery worker
pool (`integritydesk-analysis-worker`), or on a bounded in-process pool when
Redis is unavailable.

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
| `/compare-tools`, `/evidence-view`, `/cluster-detection`, `/historical-fingerprint` | R&D surfaces |

---

## 🔧 Quick Start

### Prerequisites

- **Python 3.12** (3.10+ supported)
- **PostgreSQL** (Neon or any Postgres) — required; SQLite is not supported
- **Node.js 20+** for the dashboard
- Redis — analysis queue (Celery), webhook worker and caching; uploads still work without it via the bounded in-process fallback

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

The unit suite is roughly 2,100 tests across ~140 modules, plus integration, scoring and
fixture suites.

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

| Type | Description | How well it is caught |
|------|-------------|-----------------------|
| **T1** Identical copy | Whitespace/comment changes | Reliably: 4 of 5 Kaggle pairs scored 1.0; the fifth, a very short file, was held at review (0.5) by design |
| **T2** Renamed | Identifier renaming | Reliably: all 24 renamed Kaggle copies scored 1.0 (in-sample: Kaggle is in the training set) |
| **T3** Restructured | Added/removed/reordered statements | Partly: logic flow and the structure floor help; heavy rewrites score low |
| **T4** Semantic clone | Different syntax, same behavior | Rarely: embedding has little weight and execution is not run on uploads |
| **T5** Independent work | No evidence of copying | Same-task solutions can still score high; read the evidence |

On ConPlag, copies scoring at or above 0.75 were near-verbatim, while copies rewritten
inside a student's own scaffolding looked like independent work to every signal (and to
JPlag and Dolos). See `docs/BENCHMARK_WORK.md` § ConPlag.

### Risk Bands

| Level | Score | Action |
|-------|-------|--------|
| **CRITICAL** | ≥ 0.85 | Immediate review; corroborating evidence required |
| **HIGH** | ≥ 0.65 | Recommend detailed review |
| **MEDIUM** | ≥ 0.35 | Suspicious — manual check |
| **LOW** | < 0.35 | No action needed |

These bands are the same for every assignment type. Per-type review bands
(`introductory`, `algorithms`, `projects`, `capstone`) are defined in
`src/backend/engines/scoring/review_policy.py` and used by the reviews API, but not by the
dashboard; changing bands waits for a labelled student-code holdout
(`docs/STUDENT_DATA_REQUEST_PACK.md`).

### Detection Layers (experimental)

A four-layer pipeline (deterministic → statistical → semantic → explainability) lives in
`src/backend/engines/detection/`. It is not on the upload path: uploads are scored by the
learned model described above.

---

## 🏛️ Designed for Universities

- **Institutional reports** — branded, committee-ready PDF/HTML with evidence chains
- **Class-level analysis** — code most of the class shares is left out, and the score is
  shown against the class's own distribution
- **Submission history** — optional matching against earlier offerings of a course, and
  repeat-pattern analytics
- **Human-in-the-loop** — review decisions are stored per pair; thresholds are changed only
  from labelled data, never retrained automatically
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
| Analysis worker (Celery) | – | `integritydesk-analysis-worker` |
| Embedding server *(optional)* | 127.0.0.1:8001 | `integritydesk-embedding` |

```bash
sudo bash deploy/bootstrap.sh          # OS packages
cp deploy/deploy.conf.example deploy.conf && vim deploy.conf
sudo bash deploy/setup.sh              # build + start
sudo bash deploy/update.sh             # after every git pull
```

---

## 📄 License

[License file](LICENSE)

## 📧 Contact

For deployment, support, or feature requests, please open an issue on GitHub.

---

**IntegrityDesk** — From "Did they copy?" to "Here's the evidence."
