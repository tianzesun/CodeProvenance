# Schema Overview

**Purpose**: Lightweight reference for the IntegrityDesk database schema.  
**Do not read** `src/backend/models/database.py` (~1,360 lines, 32 models) unless explicitly instructed. Use this file instead.

## High-Level Architecture

IntegrityDesk uses a **hybrid multi-tenant model**:

- `Organization` — Top-level institution / company (newer concept)
- `Tenant` — Workspace / organization unit (still heavily used)
- Tenant-level tables carry `tenant_id`; academic tables carry `organization_id`

## Core Entity Hierarchy

```
Organization
└── Course
    └── Assignment
        └── Job
            └── Submission(s)
                └── SimilarityResult(s)
                    └── Case (via CaseResultLink)
                        ├── CaseComment
                        └── TimelineEvent
```

Courses, jobs and cases are private to their owners unless shared through
`ResourceShare` (see below).

## Key Tables

### Core Academic Flow
| Table | Purpose | Key Relationships |
|-------|---------|-------------------|
| `Organization` | Top-level institution | Has many Courses, Users (via CourseInstructor) |
| `Tenant` | Workspace / billing unit | Has many Jobs, Users, API keys |
| `Term` | Academic term (e.g. Fall 2026), unique per organization + name + year | Has many Courses |
| `Course` | Course offering (code + term + year) | Belongs to Organization; optional `term_id` |
| `CourseInstructor` | Course ↔ instructor link | |
| `Student`, `Enrollment` | Student profile across terms; enrollment in a course | |
| `Assignment` | Plagiarism check assignment | Belongs to Course |
| `AssignmentVersion` | Versioned assignment content for cross-term comparison | Belongs to Assignment |
| `Job` | Analysis run | Belongs to Assignment + Tenant |
| `Submission` | Student submission | Belongs to Job |
| `SimilarityResult` | One compared pair | Belongs to Job; no `tenant_id` of its own (scoped through the Job) |
| `AIDetectionResult` | AI-detection output for a submission | Belongs to Job |

### Review Workflow (Most Important)
| Table | Purpose |
|-------|---------|
| `Case` | Faculty review container for suspicious findings; reviewer is `investigator_id` |
| `CaseResultLink` | Join table: Case ↔ SimilarityResult |
| `CaseComment` | Discussion on a Case |
| `TimelineEvent` | Audit trail for a case or job |
| `PairReview` | Faculty decision on a flagged pair; append-only (latest row is current) |
| `VivaOutcome` | Recorded viva (authorship interview) outcome per job submission — closes the dossier case loop; unique on (job_id, submission_name) |

### Sharing and Governance
| Table | Purpose |
|-------|---------|
| `ResourceShare` | Shares a course, job or case with one user or a whole workspace; no rows means private |
| `BandThreshold` | Low / Review / High score bands per assignment mode (seeded by migration) |
| `WeightAudit` | Append-only log of fusion-weight changes and their evidence |

### Supporting Tables
- `User` — Dashboard users (professors, admins)
- `Report` — Generated PDF/HTML reports
- `Notification` — In-app + email notifications
- `BehavioralSession` — Future AI behavior analysis
- `FprValidationRun` — Benchmark false positive testing
- `TenantSubscription`, `ApiKey`, `AuditLog`, `UsageMetric`, `WebhookEvent`

## Important Patterns

1. **Tenant Scoping**
   - Tenant-level tables (`Job`, `User`, `ApiKey`, `Report`, `Notification`, …) have `tenant_id`;
     the academic tables (`Course`, `Term`, `Student`, `Case`) use `organization_id`
   - Child rows (`Submission`, `SimilarityResult`) are scoped through their `Job`

2. **Review Workflow**
   - `SimilarityResult` → `CaseResultLink` → `Case`
   - This is the main path for human review

3. **Flexible + Structured Data**
   - Use JSONB for evidence (`matching_blocks`, `algorithm_scores`, `excluded_matches`)
   - Use typed columns for filtering/sorting (`similarity_score`, `verdict`, `review_status`)

4. **Production Fields on Tenant**
   - Limits: `monthly_job_limit`, `concurrent_job_limit`, `max_payload_mb`
   - Settings stored in JSONB

## When to Read the Full Model File

Only read `src/backend/models/database.py` when you need:
- Exact column definitions
- Specific relationship loading strategies
- Migration planning
- Deep debugging of a particular model

For most day-to-day work (especially vibe coding), this overview + targeted queries is sufficient.

## Current Status (October 2026)

- Schema is stable; there is no active schema work.
- Alembic head: `t3u4v5w6x7y8` (case columns + `timeline_events`, 2026-10-25). Before that:
  `s2t3u4v5w6x7` (`resource_shares`) and `r1s2t3u4v5w6` (`weight_audit`).
- CI checks that migrations create every table and column the models use
  (`scripts/check_schema_drift.py`).
