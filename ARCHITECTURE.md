# CodeProvenance - Architecture Design Document

## Executive Summary

This document outlines the architectural decisions for CodeProvenance, a B2B SaaS similarity detection engine. We address three key questions: **Do we need AI?**, **Do we need a database?**, and **Do we need RAG?**

---

## 1. Do We Need AI?

### Answer: **Yes, but strategically**

### 1.1 Why AI is Needed

| Use Case | Why AI Helps | Alternative |
|----------|-------------|-------------|
| **LLM Obfuscation Detection** | Detects code rewritten by ChatGPT/Copilot | Token comparison misses this |
| **Semantic Similarity** | Understands code meaning, not just syntax | AST comparison is structural only |
| **Cross-Language Detection** | Can detect Python → Java translation | Traditional algorithms can't |
| **Template Exclusion** | Smart matching of starter code | Manual pattern matching |

### 1.2 AI Components

```
┌─────────────────────────────────────────────────────────────┐
│                    AI DETECTION LAYER                        │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ Code        │  │ Embedding   │  │ Similarity          │ │
│  │ Embeddings  │  │ Comparison  │  │ Scoring             │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 AI Implementation Options

| Option | Pros | Cons | Cost |
|--------|------|------|------|
| **OpenAI Embeddings** | Best quality, easy API | Vendor lock-in, API costs | $0.0001/1K tokens |
| **Self-hosted (CodeBERT)** | No vendor dependency, free | Requires GPU, maintenance | Hardware cost |
| **Hybrid** | Best of both | Complexity | Medium |

### 1.4 Recommendation

**Start with OpenAI embeddings, plan for self-hosted migration:**
- Phase 1: Use OpenAI `code-embedding-3` for quick launch
- Phase 2: Train/fine-tune CodeBERT on your data
- Phase 3: Self-host for cost control

---

## 2. Do We Need a Database?

### Answer: **Yes, absolutely**

### 2.1 Why Database is Essential

| Data Type | Why Store | Storage Need |
|-----------|-----------|--------------|
| **Job Metadata** | Track status, progress, results | Small (JSON) |
| **Submissions** | Store uploaded files temporarily | Large (MB-GB) |
| **Similarity Results** | Cache results, avoid re-computation | Medium |
| **Tenant Data** | API keys, usage, billing | Small |
| **Audit Logs** | Compliance, debugging | Medium |
| **Webhook Events** | Retry queue, delivery tracking | Small |

### 2.2 Database Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DATABASE LAYER                            │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │ PostgreSQL      │  │ Redis           │  │ S3/Local    │ │
│  │ (Metadata)      │  │ (Cache/Queue)   │  │ (Files)     │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 Database Schema Design

```sql
-- Core Tables
CREATE TABLE tenants (
    id UUID PRIMARY KEY,
    name VARCHAR(255),
    api_key_hash VARCHAR(64),
    tier VARCHAR(20),
    created_at TIMESTAMP
);

CREATE TABLE jobs (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    name VARCHAR(255),
    status VARCHAR(20),
    threshold DECIMAL(3,2),
    webhook_url VARCHAR(500),
    idempotency_key VARCHAR(64),
    retention_days INTEGER,
    created_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE submissions (
    id UUID PRIMARY KEY,
    job_id UUID REFERENCES jobs(id),
    name VARCHAR(255),
    file_count INTEGER,
    file_path VARCHAR(500),
    created_at TIMESTAMP
);

CREATE TABLE similarity_results (
    id UUID PRIMARY KEY,
    job_id UUID REFERENCES jobs(id),
    submission_a_id UUID REFERENCES submissions(id),
    submission_b_id UUID REFERENCES submissions(id),
    similarity_score DECIMAL(5,4),
    confidence_lower DECIMAL(5,4),
    confidence_upper DECIMAL(5,4),
    matching_blocks JSONB,
    created_at TIMESTAMP
);

CREATE TABLE webhook_events (
    id UUID PRIMARY KEY,
    job_id UUID REFERENCES jobs(id),
    event_type VARCHAR(50),
    payload JSONB,
    status VARCHAR(20),
    retry_count INTEGER,
    next_retry_at TIMESTAMP,
    created_at TIMESTAMP
);

CREATE TABLE usage_metrics (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    period VARCHAR(7),  -- YYYY-MM
    jobs_processed INTEGER,
    files_parsed INTEGER,
    mb_processed DECIMAL(10,2),
    compute_seconds DECIMAL(10,2)
);
```

### 2.4 Database Technology Choices

| Component | Technology | Why |
|-----------|-----------|-----|
| **Primary DB** | PostgreSQL | ACID, JSONB support, mature |
| **Cache** | Redis | Fast, supports pub/sub |
| **File Storage** | S3 (prod) / Local (dev) | Scalable, cost-effective |
| **Queue** | Celery + Redis | Async job processing |

---

## 3. Do We Need RAG?

### Answer: **No, not for v1.0**

### 3.1 What is RAG?

RAG (Retrieval-Augmented Generation) combines:
- **Retrieval**: Search a knowledge base for relevant information
- **Generation**: Use LLM to generate answers based on retrieved context

### 3.2 Why RAG is NOT Needed

| RAG Use Case | CodeProvenance Need | Why Not |
|--------------|---------------------|---------|
| **Q&A over code** | Not a feature | We compare, not explain |
| **Code documentation** | Not a feature | We detect similarity |
| **Code search** | Not a feature | We analyze submissions |
| **Chat interface** | No GUI | Headless API service |

### 3.3 What We DO Need Instead

| Need | Solution | Why |
|------|----------|-----|
| **Code understanding** | Code embeddings | Semantic similarity |
| **Pattern matching** | AST comparison | Structural similarity |
| **Template exclusion** | File hashing | Exact match detection |
| **LLM detection** | Embedding distance | Detect AI-generated code |

### 3.4 Future RAG Consideration

RAG could be useful in **v2.0** for:
- **Explainability**: "Why are these submissions similar?"
- **Instructor insights**: "What patterns are common in this class?"
- **Code review**: "What are the differences between these submissions?"

But for v1.0, focus on **detection**, not **explanation**.

---

## 4. Complete Architecture

### 4.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           CLIENT SAAS PLATFORMS                          │
│  (Canvas, EdTech Tools, HR Platforms)                                   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         API GATEWAY / LOAD BALANCER                      │
│  - Rate limiting                                                        │
│  - Authentication                                                       │
│  - Request validation                                                   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         FASTAPI APPLICATION                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │ /jobs       │  │ /jobs/{id}  │  │ /results    │  │ /usage      │   │
│  │ POST        │  │ GET         │  │ GET         │  │ GET         │   │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         MESSAGE QUEUE (Redis/Celery)                     │
│  - Job queue                                                            │
│  - Webhook delivery queue                                               │
│  - Rate limit counters                                                  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         WORKER PROCESSES                                 │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    SIMILARITY ANALYSIS PIPELINE                  │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐           │   │
│  │  │ Parser  │→ │ Tokenizer│→ │ Similarity│→ │ Results │           │   │
│  │  │         │  │         │  │ Engine   │  │ Writer  │           │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘           │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    WEBHOOK DELIVERY WORKER                       │   │
│  │  - Retry logic                                                  │   │
│  │  - Signature generation                                         │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         DATA LAYER                                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │ PostgreSQL  │  │ Redis       │  │ S3/Local    │  │ OpenAI API  │   │
│  │ (Metadata)  │  │ (Cache)     │  │ (Files)     │  │ (Embeddings)│   │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Request Flow

```
1. Client POST /jobs
   │
   ├─ Validate API key → tenant_id
   ├─ Check rate limit (Redis)
   ├─ Check idempotency key (Redis)
   ├─ Store job metadata (PostgreSQL)
   ├─ Upload files to storage (S3/Local)
   ├─ Enqueue job (Redis/Celery)
   └─ Return job_id + status_url

2. Worker picks up job
   │
   ├─ Download files from storage
   ├─ Parse files by language
   ├─ Tokenize code
   ├─ Run similarity algorithms
   │   ├─ Token comparison
   │   ├─ AST comparison
   │   ├─ N-gram comparison
   │   └─ LLM embeddings (optional)
   ├─ Calculate confidence intervals
   ├─ Store results (PostgreSQL)
   ├─ Update job status
   └─ Enqueue webhook delivery

3. Webhook worker delivers results
   │
   ├─ Generate HMAC signature
   ├─ POST to client webhook_url
   ├─ Retry on failure (3 attempts)
   └─ Log delivery status
```

---

## 5. Technology Stack Summary

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **API Framework** | FastAPI | Async REST API |
| **Database** | PostgreSQL | Metadata, results |
| **Cache** | Redis | Rate limiting, idempotency |
| **Queue** | Celery + Redis | Background jobs |
| **File Storage** | S3 / Local | Submission files |
| **AI/ML** | OpenAI Embeddings | Semantic similarity |
| **Container** | Docker | Deployment |
| **Orchestration** | Kubernetes | Scaling |

---

## 6. Deployment Architecture

### 6.1 Development
```
┌─────────────────────────────────────────┐
│  Local Machine                          │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐ │
│  │ FastAPI │  │ SQLite  │  │ Local   │ │
│  │         │  │         │  │ Files   │ │
│  └─────────┘  └─────────┘  └─────────┘ │
└─────────────────────────────────────────┘
```

### 6.2 Production
```
┌─────────────────────────────────────────────────────────────────┐
│  Kubernetes Cluster                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ API Pods (3)    │  │ Worker Pods (5) │  │ Webhook Pods (2)│ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ PostgreSQL      │  │ Redis Cluster   │  │ S3 Bucket       │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Security Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Security Layers                                                │
├─────────────────────────────────────────────────────────────────┤
│  1. API Gateway                                                 │
│     - TLS termination                                           │
│     - DDoS protection                                           │
│     - Rate limiting                                             │
├─────────────────────────────────────────────────────────────────┤
│  2. Authentication                                              │
│     - API key validation                                        │
│     - Tenant isolation                                          │
├─────────────────────────────────────────────────────────────────┤
│  3. Input Validation                                            │
│     - File size limits                                          │
│     - File type validation                                      │
│     - Path traversal prevention                                 │
├─────────────────────────────────────────────────────────────────┤
│  4. Data Isolation                                              │
│     - Row-level security (PostgreSQL)                           │
│     - Separate storage paths per tenant                         │
├─────────────────────────────────────────────────────────────────┤
│  5. Webhook Security                                            │
│     - HMAC-SHA256 signatures                                    │
│     - Secret rotation                                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. Scalability Considerations

### 8.1 Horizontal Scaling

| Component | Scaling Strategy |
|-----------|-----------------|
| **API Pods** | Auto-scale based on CPU/request rate |
| **Worker Pods** | Auto-scale based on queue depth |
| **Database** | Read replicas for queries |
| **Redis** | Redis Cluster for high availability |
| **Storage** | S3 (infinite) or distributed storage |

### 8.2 Performance Targets

| Metric | Target |
|--------|--------|
| API Response Time | < 200ms (p95) |
| Job Processing (100 files) | < 30 seconds |
| Webhook Delivery | < 5 seconds |
| Concurrent Jobs | 100+ |
| Throughput | 1000+ requests/minute |

---

## 9. Cost Estimation

### 9.1 Monthly Costs (Production)

| Component | Cost | Notes |
|-----------|------|-------|
| **Compute (K8s)** | $200-500 | 3 API + 5 Worker pods |
| **PostgreSQL** | $50-100 | RDS or managed |
| **Redis** | $30-50 | ElastiCache |
| **S3 Storage** | $10-30 | Depends on usage |
| **OpenAI API** | $50-200 | Depends on volume |
| **Total** | **$340-880/month** | |

### 9.2 Cost Optimization

- Use spot instances for workers
- Cache embeddings to reduce API calls
- Compress files before storage
- Implement TTL for old data

---

## 10. Decision Summary

| Question | Answer | Rationale |
|----------|--------|-----------|
| **Do we need AI?** | **Yes** | LLM detection, semantic similarity, cross-language |
| **Do we need a database?** | **Yes** | Job tracking, results, tenant data, audit logs |
| **Do we need RAG?** | **No (v1.0)** | Focus on detection, not explanation |

---

## 11. Next Steps

1. **Review this architecture** with stakeholders
2. **Choose LLM provider** (OpenAI vs self-hosted)
3. **Design database schema** in detail
4. **Set up development environment**
5. **Implement core modules** (parser, tokenizer, similarity)

---

*Document Status: Draft*  
*Last Updated: 2026-03-27*
