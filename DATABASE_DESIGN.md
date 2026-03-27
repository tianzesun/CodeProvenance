# CodeProvenance - Database Design Document

## Overview

This document details the database architecture for CodeProvenance, a B2B SaaS similarity detection engine. We use a hybrid approach with PostgreSQL for primary data and Redis for caching/queuing.

## Database Technology Choices

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Primary Database** | PostgreSQL 15+ | ACID compliance, relational integrity, JSONB support |
| **Cache/Broker** | Redis 7+ | Celery broker, rate limiting, idempotency keys, webhook queue |
| **File Storage** | Amazon S3 (prod) / Local Storage (dev) | Submission files, temporary storage |

## Connection Details

The database connection string is stored in `.env.local` (never committed):
```
DATABASE_URL=postgresql://neondb_owner:npg_OcT7SN5PtHAa@ep-soft-voice-any9rwdn-pooler.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
```

## Database Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           DATABASE LAYER                                │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐ │
│  │ PostgreSQL      │  │ Redis           │  │ S3/Local Storage        │ │
│  │ (Primary DB)    │  │ (Cache/Broker)  │  │ (File Storage)          │ │
│  │                 │  │                 │  │                         │ │
│  │ - Tenants       │  │ - Celery Broker │  │ - Uploaded Submissions  │ │
│  │ - Jobs          │  │ - Rate Limits   │  │ - Temporary Files       │ │
│  │ - Similarity    │  │ - Idempotency   │  │                         │ │
│  │   Results       │  │ - Webhook Queue │  │                         │ │
│  │ - Usage Metrics │  │ - Webhook Retry │  │                         │ │
│  │ - Audit Logs    │  │ - Session Cache │  │                         │ │
│  │ - API Keys      │  │                 │  │                         │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

## Schema Design Philosophy

1. **Multi-Tenancy**: Row-level security (RLS) for tenant isolation
2. **Scalability**: Proper indexing for query performance
3. **Auditability**: Complete change tracking
4. **Flexibility**: JSONB fields for extensibility
5. **Performance**: Connection pooling and read replicas

## Detailed Schema

### 1. Tenants Table
Stores information about each client/SaaS platform using the service.

```sql
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    api_key_hash VARCHAR(64) NOT NULL UNIQUE,
    tier VARCHAR(20) NOT NULL DEFAULT 'free' CHECK (tier IN ('free', 'basic', 'pro', 'enterprise')),
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'cancelled', 'trial')),
    settings JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    trial_ends_at TIMESTAMP WITH TIME ZONE,
    monthly_job_limit INTEGER,
    concurrent_job_limit INTEGER,
    max_payload_mb INTEGER,
    rate_limit_per_minute INTEGER
);

-- Indexes
CREATE INDEX idx_tenants_api_key_hash ON tenants(api_key_hash);
CREATE INDEX idx_tenants_status ON tenants(status);
CREATE INDEX idx_tenants_tier ON tenants(tier);
```

### 2. API Keys Table (Alternative to hash in tenants)
For more flexible key management (rotation, multiple keys per tenant).

```sql
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    key_hash VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(255),  -- e.g., "Production Key", "Staging Key"
    prefix VARCHAR(12) NOT NULL,  -- First 12 chars for display (sk_xxxxxxxx)
    permissions JSONB DEFAULT '["read", "write"]'::jsonb,
    rate_limit_override INTEGER,  -- Override tenant rate limit
    is_active BOOLEAN DEFAULT TRUE,
    last_used_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_api_keys_tenant_id ON api_keys(tenant_id);
CREATE INDEX idx_api_keys_key_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_prefix ON api_keys(prefix);
CREATE INDEX idx_api_keys_active ON api_keys(is_active) WHERE is_active = TRUE;
```

### 3. Jobs Table
Represents a similarity analysis request.

```sql
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'processing', 'completed', 'failed', 'cancelled')),
    threshold DECIMAL(3,2) NOT NULL DEFAULT 0.7 CHECK (threshold >= 0 AND threshold <= 1),
    webhook_url TEXT,
    idempotency_key VARCHAR(255) UNIQUE,
    retention_days INTEGER NOT NULL DEFAULT 90,
    detection_modes JSONB NOT NULL DEFAULT '["token", "ast", "ngram"]'::jsonb,
    language_filters JSONB,  -- Null means all languages
    exclude_patterns JSONB DEFAULT '["__pycache__", "*.class", "node_modules"]'::jsonb,
    template_files JSONB DEFAULT '[]'::jsonb,  -- Array of {filename, content_hash}
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    failed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    execution_time_ms INTEGER,
    total_submissions INTEGER DEFAULT 0,
    total_pairs_analyzed INTEGER DEFAULT 0,
    high_similarity_count INTEGER DEFAULT 0,
    settings JSONB DEFAULT '{}'::jsonb
);

-- Indexes
CREATE INDEX idx_jobs_tenant_id ON jobs(tenant_id);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_created_at ON jobs(created_at);
CREATE INDEX idx_jobs_idempotency_key ON jobs(idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX idx_jobs_webhook_url ON jobs(webhook_url) WHERE webhook_url IS NOT NULL;
CREATE INDEX idx_jobs_tenant_status ON jobs(tenant_id, status);
```

### 4. Submissions Table
Individual student submissions within a job.

```sql
CREATE TABLE submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,  -- Student name or identifier
    external_id VARCHAR(255),    -- ID from client system
    file_count INTEGER NOT NULL DEFAULT 0,
    total_size_bytes BIGINT DEFAULT 0,
    file_paths JSONB NOT NULL,   -- Array of relative file paths
    language_detected VARCHAR(50),  -- Primary language
    languages_detected JSONB,     -- All detected languages
    storage_path VARCHAR(500),    -- Path in S3/local storage
    checksum SHA256,              -- For detecting re-uploads
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    processing_error TEXT
);

-- Indexes
CREATE INDEX idx_submissions_job_id ON submissions(job_id);
CREATE INDEX idx_submissions_name ON submissions(name);
CREATE INDEX idx_submissions_external_id ON submissions(external_id);
CREATE INDEX idx_submissions_language ON submissions(language_detected);
CREATE INDEX idx_submissions_job_name ON submissions(job_id, name);
```

### 5. Similarity Results Table
Pairwise comparison results between submissions.

```sql
CREATE TABLE similarity_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    submission_a_id UUID NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
    submission_b_id UUID NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
    -- Ensure we don't duplicate pairs (A,B) and (B,A)
    CONSTRAINT no_duplicate_pairs CHECK (submission_a_id < submission_b_id),
    
    similarity_score DECIMAL(5,4) NOT NULL CHECK (similarity_score >= 0 AND similarity_score <= 1),
    confidence_lower DECIMAL(5,4) NOT NULL,
    confidence_upper DECIMAL(5,4) NOT NULL,
    confidence_level DECIMAL(3,2) DEFAULT 0.95 CHECK (confidence_level > 0 AND confidence_level <= 1),
    
    -- Detailed matching information
    matching_blocks JSONB NOT NULL DEFAULT '[]'::jsonb,
    excluded_matches JSONB DEFAULT '[]'::jsonb,
    algorithm_scores JSONB,  -- Individual algorithm scores
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_similarity_results_job_id ON similarity_results(job_id);
CREATE INDEX idx_similarity_results_submission_a ON similarity_results(submission_a_id);
CREATE INDEX idx_similarity_results_submission_b ON similarity_results(submission_b_id);
CREATE INDEX idx_similarity_results_score ON similarity_results(similarity_score DESC);
CREATE INDEX idx_similarity_results_job_score ON similarity_results(job_id, similarity_score DESC);
CREATE INDEX idx_similarity_results_submissions ON similarity_results(submission_a_id, submission_b_id);
-- Partial index for high similarity results (common query)
CREATE INDEX idx_similarity_results_high_similarity ON similarity_results(job_id, similarity_score) 
    WHERE similarity_score >= 0.7;
```

### 6. Webhook Events Table
Tracks webhook delivery attempts.

```sql
CREATE TABLE webhook_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL CHECK (event_type IN ('job.completed', 'job.failed', 'job.progress')),
    payload JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'delivered', 'failed', 'retried')),
    attempt_count INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    next_attempt_at TIMESTAMP WITH TIME ZONE,
    delivered_at TIMESTAMP WITH TIME ZONE,
    last_error TEXT,
    signature VARCHAR(128),  -- HMAC-SHA256 signature
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_webhook_events_job_id ON webhook_events(job_id);
CREATE INDEX idx_webhook_events_status ON webhook_events(status);
CREATE INDEX idx_webhook_events_next_attempt ON webhook_events(next_attempt_at) 
    WHERE status IN ('pending', 'failed');
CREATE INDEX idx_webhook_events_job_type ON webhook_events(job_id, event_type);
```

### 7. Usage Metrics Table
For billing and analytics (aggregated monthly).

```sql
CREATE TABLE usage_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    period VARCHAR(7) NOT NULL,  -- Format: YYYY-MM
    jobs_processed INTEGER DEFAULT 0,
    jobs_successful INTEGER DEFAULT 0,
    jobs_failed INTEGER DEFAULT 0,
    files_parsed INTEGER DEFAULT 0,
    total_size_mb DECIMAL(10,2) DEFAULT 0,
    compute_seconds DECIMAL(10,2) DEFAULT 0,
    api_calls INTEGER DEFAULT 0,
    webhook_attempts INTEGER DEFAULT 0,
    webhook_deliveries INTEGER DEFAULT 0,
    peak_concurrent_jobs INTEGER DEFAULT 0,
    storage_used_mb DECIMAL(10,2) DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(tenant_id, period)
);

-- Indexes
CREATE INDEX idx_usage_metrics_tenant_id ON usage_metrics(tenant_id);
CREATE INDEX idx_usage_metrics_period ON usage_metrics(period);
CREATE INDEX idx_usage_metrics_tenant_period ON usage_metrics(tenant_id, period);
```

### 8. Audit Logs Table
For compliance and debugging.

```sql
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE SET NULL,
    job_id UUID REFERENCES jobs(id) ON DELETE SET NULL,
    user_id UUID,  -- If we implement user-level auth later
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),  -- job, submission, api_key, etc.
    resource_id UUID,
    changes JSONB,  -- Before/after for updates
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_audit_logs_tenant_id ON audit_logs(tenant_id);
CREATE INDEX idx_audit_logs_job_id ON audit_logs(job_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_resource ON audit_logs(resource_type, resource_id);
```

## Row-Level Security (RLS) for Multi-Tenancy

Enable RLS on all tables to ensure tenants can only access their own data:

```sql
-- Enable RLS on all tables
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE submissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE similarity_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE webhook_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- Create policy for tenants (tenants can only see themselves)
CREATE POLICY tenant_own_tenant ON tenants
    FOR ALL USING (id = current_setting('app.current_tenant_id')::uuid);

-- Create policy for API keys
CREATE POLICY api_keys_tenant_access ON api_keys
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

-- Create policy for jobs
CREATE POLICY jobs_tenant_access ON jobs
    FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

-- Similar policies for other tables...
```

## Connection Pooling Configuration

For production deployment with PgBouncer or similar:

```
# postgresql.conf settings
max_connections = 200
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 26214kB
min_wal_size = 1GB
max_wal_size = 4GB

# Application connection pool settings
pool_size = 20
max_overflow = 30
pool_timeout = 30
pool_recycle = 1800
```

## Indexing Strategy Justification

1. **Primary Keys**: UUID indexes for fast lookups
2. **Foreign Keys**: Indexed for JOIN performance
3. **Query Patterns**: 
   - Jobs by tenant + status (most common)
   - Similarity results by job + score (ranking)
   - Webhook events by status + next_attempt (retry processing)
   - Usage metrics by tenant + period (billing)
4. **Partial Indexes**: For high-similarity results (reduces index size)
5. **Covering Indexes**: Where appropriate to avoid table lookups

## Backup and Recovery Strategy

1. **Automated Backups**: Daily snapshots via cloud provider
2. **Point-in-Time Recovery**: WAL archiving enabled
3. **Backup Retention**: 30 days for production
4. **Test Restores**: Monthly restore verification
5. **Geographic Replication**: Cross-region read replica for disaster recovery

## Migration Strategy

Using Alembic for schema migrations:

```
# Migration structure
alembic/
├── env.py
├── script.py.mako
└── versions/
    ├── 001_initial_schema.py
    ├── 002_add_api_keys_table.py
    ├── 003_add_rls_policies.py
    └── ...
```

## Sample Queries

### Get jobs for a tenant with pagination
```sql
SELECT j.id, j.name, j.status, j.created_at, j.total_submissions
FROM jobs j
WHERE j.tenant_id = :tenant_id
  AND j.status IN ('queued', 'processing', 'completed')
ORDER BY j.created_at DESC
LIMIT :limit OFFSET :offset;
```

### Get high similarity results for a job
```sql
SELECT sr.id, sr.similarity_score, sr.confidence_lower, sr.confidence_upper,
       sa.name as submission_a_name, sb.name as submission_b_name,
       sr.matching_blocks
FROM similarity_results sr
JOIN submissions sa ON sr.submission_a_id = sa.id
JOIN submissions sb ON sr.submission_b_id = sb.id
WHERE sr.job_id = :job_id
  AND sr.similarity_score >= :threshold
ORDER BY sr.similarity_score DESC
LIMIT 100;
```

### Get usage metrics for billing
```sql
SELECT period, jobs_processed, files_parsed, total_size_mb, compute_seconds
FROM usage_metrics
WHERE tenant_id = :tenant_id
  AND period >= :start_period
  AND period <= :end_period
ORDER BY period;
```

## Data Retention Policy

| Data Type | Retention Period | Deletion Method |
|-----------|------------------|-----------------|
| Jobs & Results | Configurable per job (default 90 days) | Daily batch job |
| Uploaded Files | 30 days after job completion | Daily batch job |
| Webhook Events | 90 days | Daily batch job |
| Usage Metrics | 24 months | Monthly aggregation |
| Audit Logs | 12 months | Monthly archive to cold storage |
| API Keys | Until deleted | Immediate |

## Performance Benchmarks (Target)

| Operation | Target Time | Notes |
|-----------|-------------|-------|
| Job Creation | < 100ms | Includes validation |
| Job Status Query | < 50ms | Cached in Redis |
| Results Retrieval | < 200ms | Paginated, < 1000 results |
| Similarity Calculation | < 30s | For 100 submissions |
| Webhook Delivery | < 5s | Per attempt |
| Usage Query | < 1s | Aggregated monthly |

## Security Considerations

1. **Connection Security**: SSL/TLS required (enforced by connection string)
2. **Data at Rest**: Enable PostgreSQL Transparent Data Encryption (TDE)
3. **Backups**: Encrypted backup storage
4. **Network Security**: Database in private subnet, no public access
5. **Secrets Management**: Database credentials in secret manager (AWS Secrets Manager, HashiCorp Vault)
6. **Access Control**: Least privilege principle for database users
7. **Audit Logging**: All access attempts logged

## Development vs Production

### Development (Local)
- PostgreSQL: Local instance or Docker container
- Redis: Local instance or Docker
- Storage: Local filesystem
- Connection: Direct to localhost

### Production
- PostgreSQL: Managed service (AWS RDS, Google Cloud SQL, or Neon as provided)
- Redis: Managed service (AWS ElastiCache, Google Cloud Memorystore)
- Storage: Amazon S3 with appropriate lifecycle policies
- Connection: Via connection pooling layer (PgBouncer)
- Environment: Separate database per environment (dev, staging, prod)

## Next Steps

1. **Create initial migration script** with all tables
2. **Set up connection pooling** in application configuration
3. **Implement RLS policies** in application middleware
4. **Create database utility layer** with connection handling
5. **Add migration scripts** to repository
6. **Set up automated backups** in production environment
7. **Create monitoring alerts** for database performance
