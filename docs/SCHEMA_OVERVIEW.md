# Schema Overview

**Purpose**: Lightweight reference for the IntegrityDesk database schema.  
**Do not read** `src/backend/models/database.py` (626 lines) unless explicitly instructed. Use this file instead.

## High-Level Architecture

IntegrityDesk uses a **hybrid multi-tenant model**:

- `Organization` — Top-level institution / company (newer concept)
- `Tenant` — Workspace / organization unit (still heavily used)
- Most business tables have `tenant_id` for row-level isolation
- Newer tables increasingly use `organization_id`

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
                        └── CaseAssignee
```

## Key Tables

### Core Academic Flow
| Table | Purpose | Key Relationships |
|-------|---------|-------------------|
| `Organization` | Top-level institution | Has many Courses, Users (via CourseInstructor) |
| `Tenant` | Workspace / billing unit | Has many Jobs, Users, Courses, Assignments |
| `Course` | Academic course | Belongs to Organization or Tenant |
| `Assignment` | Plagiarism check assignment | Belongs to Course |
| `Job` | Analysis run | Belongs to Assignment + Tenant |
| `Submission` | Student submission | Belongs to Job |
| `SimilarityResult` | One suspicious pair | Belongs to Job + two Submissions |

### Review Workflow (Most Important)
| Table | Purpose |
|-------|---------|
| `Case` | Faculty review container for suspicious findings |
| `CaseResultLink` | Join table: Case ↔ SimilarityResult |
| `CaseComment` | Discussion on a Case |
| `CaseAssignee` | Who is reviewing the Case |

### Supporting Tables
- `User` — Dashboard users (professors, admins)
- `Report` — Generated PDF/HTML reports
- `Notification` — In-app + email notifications
- `BehavioralSession` — Future AI behavior analysis
- `FprValidationRun` — Benchmark false positive testing
- `TenantSubscription`, `ApiKey`, `AuditLog`, etc.

## Important Patterns

1. **Tenant Scoping**
   - Almost every table has `tenant_id`
   - Used for both security (RLS) and data partitioning

2. **Review Workflow**
   - `SimilarityResult` → `CaseResultLink` → `Case`
   - This is the main path for human review

3. **Flexible + Structured Data**
   - Use JSONB for evidence (`detected_clones`, `algorithm_scores`, etc.)
   - Use typed columns for filtering/sorting (`similarity_score`, `review_status`, `pair_rank`)

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

## Current Status (May 2026)

- This schema is the result of a large "cms" branch merge.
- It is significantly more complex than earlier versions.
- Active work is happening on benchmark metrics and schema stability.
