# CodeProvenance - Product Requirements Document (PRD)

## 1. Overview

**Project Name:** CodeProvenance  
**Project Type:** B2B SaaS Backend Service (Headless, API-first)  
**Core Functionality:** Software similarity detection engine for EdTech platforms  
**Target Users:** SaaS Platforms (Canvas, custom EdTech tools, HR technical interview platforms)  
**Business Model:** Multi-tenant SaaS with tiered pricing  

---

## 2. Problem Statement

EdTech platforms and HR tools need automated code similarity detection to identify potential plagiarism or cheating. Manual review is time-consuming and unreliable at scale.

**Goals:**
- Provide a robust similarity detection API for B2B clients
- Ensure strict data isolation between tenants
- Offer advanced detection features (template exclusion, LLM obfuscation)
- Support webhook-based async processing for large submissions

---

## 3. Architecture Overview

### 3.1 Design Principles
- **API-First**: All functionality exposed via REST API
- **Headless**: No GUI, clients build their own interfaces
- **Multi-Tenant**: Strict data isolation between clients
- **Scalable**: Horizontal scaling via queue workers
- **Metered**: Usage tracking for billing purposes

### 3.2 Tech Stack
- **Language:** Python 3.11+
- **Framework:** FastAPI (async REST API)
- **Database:** PostgreSQL (production), SQLite (development)
- **Cache:** Redis
- **Queue:** Celery or similar for background tasks
- **Hosting:** Docker/Kubernetes ready

---

## 4. User Stories & Requirements

### 4.1 Core User Stories

| ID | Story | Priority |
|----|-------|----------|
| US-01 | As a client SaaS, I can upload a folder containing multiple student submissions | P0 |
| US-02 | As a client SaaS, I can configure similarity thresholds | P0 |
| US-03 | As a client SaaS, I can receive webhook notifications when analysis completes | P0 |
| US-04 | As a client SaaS, I can retrieve similarity results for all submission pairs | P0 |
| US-05 | As a client SaaS, I can filter results by similarity score | P1 |
| US-06 | As a client SaaS, I can specify supported programming languages | P1 |
| US-07 | As a client SaaS, I can upload template/starter code to exclude from comparison | P1 |
| US-08 | As a client SaaS, I can use idempotency keys to prevent duplicate processing | P1 |
| US-09 | As a client SaaS, I can configure per-job data retention | P1 |
| US-10 | As a client SaaS, I can detect LLM-obfuscated code | P2 |

### 4.2 Multi-Tenancy Stories

| ID | Story | Priority |
|----|-------|----------|
| MT-01 | As CodeProvenance, I ensure no cross-pollination between tenant submissions | P0 |
| MT-02 | As a client, my API key is tied to my tenant_id | P0 |
| MT-03 | As a client, I can configure data retention policies | P1 |
| MT-04 | As CodeProvenance, I can enforce tier-based rate limits | P0 |

---

## 5. API Specification

### 5.1 Base URL
```
https://api.codeprovenance.io/v1
```

### 5.2 Authentication
```http
Authorization: Bearer <api_key>
X-Tenant-ID: <tenant_id>  (optional, derived from API key)
```

### 5.3 Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/jobs` | Create new similarity analysis job |
| GET | `/jobs/{job_id}` | Get job status |
| GET | `/jobs/{job_id}/results` | Get similarity results |
| DELETE | `/jobs/{job_id}` | Cancel/delete job |
| POST | `/jobs/{job_id}/abort` | Abort running job |
| GET | `/languages` | List supported languages |
| GET | `/health` | Health check |
| GET | `/usage` | Get usage metrics for API key |

### 5.4 Create Job Request
```json
{
  "name": "Assignment 1 - Sorting Algorithms",
  "webhook_url": "https://client-saas.com/api/webhook/codeprovenance",
  "idempotency_key": "uuid-v4-client-generated",
  "threshold": 0.7,
  "languages": ["python", "java"],
  "exclude_patterns": ["__pycache__", "*.class", "node_modules"],
  "template_files": [
    {
      "filename": "interface.java",
      "content": "base64-encoded-content"
    }
  ],
  "retention_days": 90,
  "detection_modes": ["token", "ast", "llm_embeddings"]
}
```

### 5.5 Create Job Response
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "created_at": "2026-03-27T18:00:00Z",
  "idempotency_key": "uuid-v4-client-generated",
  "estimated_completion": "2026-03-27T18:01:00Z",
  "status_url": "/v1/jobs/550e8400-e29b-41d4-a716-446655440000"
}
```

---

## 6. Webhook Architecture

### 6.1 Event Types
| Event | Trigger |
|-------|---------|
| `job.completed` | Analysis finished successfully |
| `job.failed` | Analysis encountered an error |
| `job.progress` | Progress update (optional, every 25%) |

### 6.2 Webhook Payload - job.completed
```json
{
  "event": "job.completed",
  "timestamp": "2026-03-27T18:05:00Z",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_id": "tenant-123",
  "data": {
    "status": "completed",
    "total_submissions": 30,
    "total_pairs_analyzed": 435,
    "high_similarity_count": 5,
    "execution_time_ms": 12500,
    "results_summary": {
      "average_similarity": 0.23,
      "max_similarity": 0.92,
      "min_similarity": 0.01
    },
    "results_url": "/v1/jobs/550e8400-e29b-41d4-a716-446655440000/results"
  }
}
```

### 6.3 Webhook Payload - job.failed
```json
{
  "event": "job.failed",
  "timestamp": "2026-03-27T18:05:00Z",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_id": "tenant-123",
  "data": {
    "status": "failed",
    "error_code": "FILE_PARSE_ERROR",
    "error_message": "Unable to parse file: submission_15/solution.py - Syntax error at line 42",
    "can_retry": true
  }
}
```

### 6.4 Webhook Security
- HMAC-SHA256 signature in `X-Webhook-Signature` header
- Secret per tenant (configurable)
- Retry policy: 3 attempts with exponential backoff

---

## 7. Similarity Results Schema

### 7.1 Full Results Response
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "threshold_used": 0.7,
  "total_submissions": 30,
  "total_pairs": 435,
  "high_similarity_pairs": 5,
  "execution_time_ms": 12500,
  "results": [
    {
      "submission_a": {
        "id": "sub_001",
        "name": "student_alice",
        "files_analyzed": 3
      },
      "submission_b": {
        "id": "sub_002",
        "name": "student_bob",
        "files_analyzed": 3
      },
      "overall_similarity_score": 0.85,
      "confidence_interval": {
        "lower": 0.82,
        "upper": 0.88,
        "confidence": 0.95
      },
      "matching_blocks": [
        {
          "file_a": "sort.py",
          "file_b": "sort.py",
          "block_type": "function",
          "function_name": "quick_sort",
          "lines_a": "10-45",
          "lines_b": "12-47",
          "similarity": 0.94,
          "token_overlap": 0.89,
          "ast_similarity": 0.96
        },
        {
          "file_a": "main.py",
          "file_b": "main.py",
          "block_type": "code_block",
          "lines_a": "100-120",
          "lines_b": "105-125",
          "similarity": 0.78
        }
      ],
      "excluded_matches": [
        {
          "reason": "template_match",
          "template_file": "interface.java",
          "description": "Starter code provided by instructor"
        }
      ]
    }
  ],
  "metadata": {
    "algorithms_used": ["token", "ast", "ngram"],
    "llm_detection_applied": true,
    "llm_similarity_score": 0.45
  }
}
```

---

## 8. Multi-Tenancy & Security

### 8.1 Tenant Isolation Rules
1. **Strict Job Boundaries**: Similarity is ONLY calculated within submissions of the SAME job
2. **No Cross-Tenant Access**: API keys are tenant-scoped
3. **Database Isolation**: Row-level security or separate schemas per tenant
4. **Queue Isolation**: Jobs processed in isolated contexts

### 8.2 API Key Structure
```
cp_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
|______| |________________________________|
  prefix     random key (32 chars)
```

### 8.3 Data Retention
| Setting | Default | Configurable |
|---------|---------|--------------|
| Job data | 90 days | Yes (per job or per account) |
| Uploaded files | 30 days | Yes |
| Results | 90 days | Yes |

---

## 9. Tiered Rate Limiting

### 9.1 Tier Definitions

| Tier | Concurrent Jobs | Max Payload | Monthly Jobs | Rate |
|------|-----------------|-------------|--------------|------|
| Free | 1 | 50MB | 10 | 60 req/min |
| Basic | 5 | 200MB | 500 | 100 req/min |
| Pro | 20 | 1GB | 5000 | 200 req/min |
| Enterprise | 100 | 5GB | Unlimited | 500 req/min |

### 9.2 Rate Limit Headers
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1648401600
X-RateLimit-Policy: Basic
```

### 9.3 Usage Metrics Response
```json
{
  "tenant_id": "tenant-123",
  "current_tier": "Basic",
  "period": "2026-03",
  "usage": {
    "jobs_processed": 45,
    "files_parsed": 890,
    "mb_processed": 125.5,
    "compute_seconds": 234.5
  },
  "limits": {
    "jobs_remaining": 455,
    "mb_remaining": 874.5
  }
}
```

---

## 10. Advanced Detection Features

### 10.1 Template/Boilerplate Exclusion
- Client uploads template files with job creation
- Templates stored securely per job
- Matched sections excluded from similarity calculation
- Results include `excluded_matches` field

### 10.2 LLM Obfuscation Detection
- Secondary analysis pass using code embeddings
- Detects structurally similar but lexically different code
- Returns `llm_similarity_score` in results
- Useful for AI-assisted plagiarism detection

### 10.3 Detection Algorithms

| Algorithm | Description | Use Case |
|-----------|-------------|----------|
| `token` | Token-based comparison | Fast, basic similarity |
| `ngram` | N-gram text comparison | Code structure similarity |
| `ast` | Abstract Syntax Tree comparison | Structural plagiarism |
| `winnowing` | Fingerprinting with k-grams | Efficient large-scale |
| `llm_embeddings` | Code embedding similarity | LLM obfuscation detection |

---

## 11. Configuration Options

```yaml
# config/default.yaml
service:
  name: "CodeProvenance"
  version: "1.0.0"
  host: "0.0.0.0"
  port: 8000

database:
  type: "postgresql"
  host: "${DB_HOST}"
  port: 5432
  name: "codeprovenance"
  pool_size: 20

redis:
  host: "${REDIS_HOST}"
  port: 6379
  db: 0

queue:
  type: "celery"
  broker: "${CELERY_BROKER_URL}"

webhook:
  max_retries: 3
  retry_delay_seconds: 60
  timeout_seconds: 30
  hmac_algorithm: "sha256"

analysis:
  default_threshold: 0.7
  max_file_size_mb: 10
  max_folder_size_mb: 500
  job_timeout_seconds: 600
  max_concurrent_jobs_per_tenant: 5
  algorithms:
    enabled: ["token", "ast", "ngram"]
    default: "token"
  llm:
    enabled: false
    provider: "openai"
    model: "code-embedding-3"

languages:
  supported:
    - python
    - java
    - javascript
    - typescript
    - c
    - cpp
    - csharp
    - go
    - rust
    - ruby
    - php

tiers:
  free:
    concurrent_jobs: 1
    max_payload_mb: 50
    monthly_jobs: 10
    rate_limit: 60
  basic:
    concurrent_jobs: 5
    max_payload_mb: 200
    monthly_jobs: 500
    rate_limit: 100
  pro:
    concurrent_jobs: 20
    max_payload_mb: 1024
    monthly_jobs: 5000
    rate_limit: 200
  enterprise:
    concurrent_jobs: 100
    max_payload_mb: 5120
    monthly_jobs: -1  # unlimited
    rate_limit: 500

storage:
  type: "local"
  path: "./data"
  retention:
    job_data_days: 90
    uploaded_files_days: 30
```

---

## 12. Supported Languages

| Language | Extensions | Parser |
|----------|------------|--------|
| Python | .py | ast (stdlib) |
| Java | .java | javalang |
| JavaScript | .js | babel-parser |
| TypeScript | .ts, .tsx | babel-parser |
| C | .c | cparser |
| C++ | .cpp, .cc, .h, .hpp | tree-sitter-cpp |
| C# | .cs | tree-sitter-csharp |
| Go | .go | goparser |
| Rust | .rs | rustpython-parser |
| Ruby | .rb | ruby-parser |
| PHP | .php | php-parser |

---

## 13. Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `INVALID_REQUEST` | 400 | Malformed request body |
| `AUTH_FAILED` | 401 | Invalid or missing API key |
| `FORBIDDEN` | 403 | Tenant not authorized for action |
| `NOT_FOUND` | 404 | Job or resource not found |
| `PAYLOAD_TOO_LARGE` | 413 | File/folder exceeds size limit |
| `RATE_LIMITED` | 429 | Rate limit exceeded |
| `IDEMPOTENCY_CONFLICT` | 409 | Different request with same idempotency key |
| `FILE_PARSE_ERROR` | 422 | Unable to parse uploaded file |
| `JOB_TIMEOUT` | 504 | Analysis exceeded timeout |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

---

## 14. Out of Scope (v1.0)

- User interface / Web UI
- User authentication (B2B API keys only)
- Payment / Billing integration
- Email notifications
- Visualization of similarity results
- Direct student/instructor access
- File export/import features

---

## 15. Open Questions / TBD

| Item | Question | Status |
|------|----------|--------|
| Q1 | Which LLM provider for embeddings? (OpenAI, Anthropic, self-hosted) | Open |
| Q2 | Database: separate schemas or row-level security per tenant? | Open |
| Q3 | Webhook retry queue: database-backed or Redis? | Open |
| Q4 | LLM detection enabled by default or opt-in? | Open |
| Q5 | Support for password-protected ZIP files? | Open |
| Q6 | Custom similarity thresholds per language? | Open |

---

## 16. Success Criteria

- [ ] Upload ZIP with 100+ submissions, complete analysis in < 60 seconds
- [ ] Correctly identify obvious copies (same code with variable renaming)
- [ ] Webhook delivery with < 1% failure rate
- [ ] Zero cross-tenant data leakage (verified by tests)
- [ ] 80%+ unit test coverage on core algorithms
- [ ] Idempotency key prevents duplicate processing
- [ ] Rate limiting enforced correctly per tier
- [ ] API response schema matches documented format

---

## 17. TODO

- [ ] Finalize LLM provider choice
- [ ] Design database schema with tenant isolation
- [ ] Implement idempotency layer
- [ ] Build webhook delivery system with retry logic
- [ ] Implement rate limiting middleware
- [ ] Add usage metering
- [ ] Review and approve PRD

---

*Document Status: Draft v2*  
*Last Updated: 2026-03-27*
